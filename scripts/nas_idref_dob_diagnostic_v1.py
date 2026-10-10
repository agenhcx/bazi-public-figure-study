#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v16.csv"
OUT=BASE/"nas_idref_dob_diagnostic_v1.csv"
CAND=BASE/"nas_idref_dob_candidates_v1.csv"
VAL=BASE/"nas_idref_dob_validation_conflicts_v1.csv"
SUMMARY=BASE/"summary_nas_idref_dob_diagnostic_v1.json"
UA="bazi-public-figure-study/1.0 (NAS IdRef DOB diagnostic; no BaZi computation)"
QLEVER="https://qlever.dev/api/wikidata"
NS={"m":"http://www.loc.gov/MARC21/slim"}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def present(v):return str(v or "").strip() not in ("","nan","None")

def as_int(v,d=0):
    try:return int(float(str(v)))
    except:return d

def norm(s):return " ".join(re.sub(r"[^a-z0-9]+"," ",str(s or "").lower()).split())

def reliable_qid(r):
    q=(r.get("wikidata_qid") or "").strip()
    if re.fullmatch(r"Q\d+",q):return q,"wikidata_qid"
    q=(r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+",q):return "",""
    if as_int(r.get("global_exact_name_match_count"))!=1:return "",""
    toks=len(norm(r.get("name","")).split())
    if toks>=3 or as_int(r.get("global_affiliation_match"))==1:return q,"global_unique_identity"
    return "",""

def chunks(xs,n=100):
    for i in range(0,len(xs),n):yield xs[i:i+n]

def run_sparql(q,retries=5):
    body=urllib.parse.urlencode({"query":q,"action":"tsv_export"}).encode()
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(QLEVER,data=body,method="POST",headers={
                "User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded",
                "Accept":"text/tab-separated-values"
            })
            with urllib.request.urlopen(req,timeout=180) as r:raw=r.read().decode("utf-8-sig")
            rr=list(csv.reader(raw.splitlines(),delimiter="\t"))
            if not rr:return []
            h=[x.lstrip("?").strip() for x in rr[0]];out=[]
            for row in rr[1:]:
                row+=[""]*(len(h)-len(row));d={}
                for j,k in enumerate(h):
                    v=(row[j] or "").strip()
                    if v.startswith("<") and v.endswith(">"):v=v[1:-1]
                    elif len(v)>=2 and v[0]=='"':
                        e=v.rfind('"')
                        if e>0:v=v[1:e]
                    d[k]=v
                out.append(d)
            return out
        except Exception as e:
            last=e
            if i+1>=retries:raise
            time.sleep(min(20,2**i))
    raise RuntimeError(last)

def get(url,accept="application/xml,text/xml;q=0.9,*/*;q=0.1",retries=3):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=45) as r:
                return getattr(r,"status",200),r.read(3_000_000),r.geturl(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code in {400,401,403,404}:return e.code,b"",url,"HTTP "+str(e.code)
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            time.sleep(min(10,2**i))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(10,2**i))
    return getattr(last,"code",""),b"",url,repr(last)

def iso(y,m,d):
    try:return dt.date(int(y),int(m),int(d)).isoformat()
    except:return ""

def parse_exact_token(raw):
    s=re.sub(r"\s+","",str(raw or ""))
    vals=set()
    for m in re.finditer(r"(?<!\d)([12]\d{3})(\d{2})(\d{2})(?!\d)",s):
        d=iso(m.group(1),m.group(2),m.group(3))
        if d:vals.add(d)
    for m in re.finditer(r"(?<!\d)([12]\d{3})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)",s):
        d=iso(m.group(1),m.group(2),m.group(3))
        if d:vals.add(d)
    for m in re.finditer(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.]([12]\d{3})(?!\d)",s):
        d=iso(m.group(3),m.group(2),m.group(1))
        if d:vals.add(d)
    return sorted(vals)

def parse_idref_xml(data):
    root=ET.fromstring(data)
    rec=root if root.tag.endswith("record") else root.find(".//m:record",NS)
    out={"heading":"","field103":[],"field300":[],"field810":[],"dates":[]}
    if rec is None:return out
    for f in rec.findall(".//m:datafield",NS):
        tag=f.attrib.get("tag","")
        sub=[(x.attrib.get("code",""),(x.text or "").strip()) for x in f.findall("m:subfield",NS)]
        joined=" ".join(v for _,v in sub if v).strip()
        if tag in {"200","900"} and not out["heading"]:out["heading"]=joined
        elif tag=="103":
            out["field103"].append(joined)
            for _,v in sub:out["dates"].extend(parse_exact_token(v))
        elif tag=="300":out["field300"].append(joined)
        elif tag=="810":out["field810"].append(joined)
    out["dates"]=sorted(set(out["dates"]))
    return out

def fetch_idref(ppn):
    url=f"https://www.idref.fr/{urllib.parse.quote(ppn)}.xml"
    st,data,final,err=get(url)
    if not data:return ppn,{"ok":0,"status":st,"url":final,"error":err,"dates":[],"heading":"","field103":"","notes":""}
    try:
        p=parse_idref_xml(data)
        return ppn,{
          "ok":1,"status":st,"url":final,"error":"","dates":p["dates"],"heading":p["heading"],
          "field103":" || ".join(p["field103"]),
          "notes":" || ".join((p["field300"]+p["field810"])[:12])
        }
    except Exception as e:
        return ppn,{"ok":0,"status":st,"url":final,"error":repr(e),"dates":[],"heading":"","field103":"","notes":""}

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")

living=[r for r in rows if r.get("deceased")!="Y"]
known=[r for r in living if present(r.get("final_exact_dob"))]
unresolved=[r for r in living if not present(r.get("final_exact_dob"))]

# Validation sample is deterministic but broad enough to estimate exact-date precision.
known=sorted(known,key=lambda r:hashlib.sha256(("idref-validation-v1:"+r["profile_url"]).encode()).hexdigest())[:300]
targets=[("validation",r) for r in known]+[("unresolved",r) for r in unresolved]

qid_rows=[]
for cohort,r in targets:
    q,b=reliable_qid(r)
    if q:qid_rows.append((cohort,r,q,b))
allq=sorted({q for _,_,q,_ in qid_rows})

ids=defaultdict(set)
for batch in chunks(allq,120):
    vals=" ".join("wd:"+q for q in batch)
    q=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
SELECT ?person ?idref WHERE {{
 VALUES ?person {{ {vals} }}
 ?person wdt:P269 ?idref .
}}"""
    for x in run_sparql(q):
        person=(x.get("person") or "").rsplit("/",1)[-1]
        ppn=(x.get("idref") or "").strip()
        if re.fullmatch(r"Q\d+",person) and ppn:ids[person].add(ppn)

all_ppn=sorted({p for q in allq for p in ids[q]})
fetched={}
with ThreadPoolExecutor(max_workers=12) as ex:
    fs={ex.submit(fetch_idref,p):p for p in all_ppn}
    for f in as_completed(fs):
        p=fs[f]
        try:pp,res=f.result();fetched[pp]=res
        except Exception as e:fetched[p]={"ok":0,"status":"","url":"","error":repr(e),"dates":[],"heading":"","field103":"","notes":""}

fields=[
 "cohort","profile_url","name","election_year","affiliation","qid","identity_basis","master_exact_dob",
 "idref_ids","idref_fetch_successes","idref_exact_dates","idref_candidate_dob","idref_source_conflict",
 "age_at_election","age_plausible","validation_match","candidate_for_manual_review",
 "idref_urls","idref_headings","idref_field103","idref_notes","fetch_errors"
]
out=[];valconf=[];cands=[]
for cohort,r,q,b in qid_rows:
    ps=sorted(ids[q])
    if not ps:continue
    dates=set();urls=[];heads=[];f103=[];notes=[];errs=[];ok=0
    for p in ps:
        z=fetched.get(p,{})
        ok+=int(z.get("ok",0))
        dates.update(z.get("dates",[]))
        if z.get("url"):urls.append(z["url"])
        if z.get("heading"):heads.append(z["heading"])
        if z.get("field103"):f103.append(p+":"+z["field103"])
        if z.get("notes"):notes.append(p+":"+z["notes"])
        if z.get("error"):errs.append(p+":"+z["error"])
    dates=sorted(dates)
    cand=dates[0] if len(dates)==1 else ""
    conflict=int(len(dates)>1)
    ey=as_int(r.get("election_year"))
    age=ey-int(cand[:4]) if ey and cand else None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    master=r.get("final_exact_dob","") if cohort=="validation" else ""
    vm=int(cand==master) if cohort=="validation" and cand else ""
    row={
      "cohort":cohort,"profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"qid":q,"identity_basis":b,"master_exact_dob":master,
      "idref_ids":"|".join(ps),"idref_fetch_successes":ok,"idref_exact_dates":"|".join(dates),
      "idref_candidate_dob":cand,"idref_source_conflict":conflict,
      "age_at_election":age if age is not None else "","age_plausible":ageok,"validation_match":vm,
      "candidate_for_manual_review":int(cohort=="unresolved" and bool(cand) and not conflict and ageok==1),
      "idref_urls":"|".join(urls),"idref_headings":" || ".join(heads),
      "idref_field103":" || ".join(f103),"idref_notes":" || ".join(notes),
      "fetch_errors":" || ".join(errs)
    }
    out.append(row)
    if cohort=="validation" and cand and vm==0:valconf.append(row)
    if row["candidate_for_manual_review"]==1:cands.append(row)

write_csv(OUT,out,fields)
write_csv(CAND,cands,fields)
write_csv(VAL,valconf,fields)

val=[x for x in out if x["cohort"]=="validation"]
val_found=[x for x in val if x["idref_candidate_dob"]]
unres=[x for x in out if x["cohort"]=="unresolved"]
summary={
 "dataset":"NAS IdRef exact-DOB diagnostic v1",
 "input":INPUT.name,
 "input_rows":len(rows),
 "living_validation_sample_rows":len(known),
 "living_unresolved_rows":len(unresolved),
 "reliable_qid_target_rows":len(qid_rows),
 "unique_qids":len(allq),
 "qids_with_p269":sum(bool(ids[q]) for q in allq),
 "unique_idref_ids":len(all_ppn),
 "idref_fetch_successes":sum(int(fetched[p].get("ok",0)) for p in all_ppn),
 "validation_rows_with_p269":sum(bool(ids[q]) for cohort,r,q,b in qid_rows if cohort=="validation"),
 "validation_rows_with_unique_exact_candidate":len(val_found),
 "validation_exact_matches":sum(x["validation_match"]==1 for x in val_found),
 "validation_exact_conflicts":len(valconf),
 "validation_match_rate":round(sum(x["validation_match"]==1 for x in val_found)/len(val_found),6) if val_found else None,
 "unresolved_rows_with_p269":sum(bool(ids[q]) for cohort,r,q,b in qid_rows if cohort=="unresolved"),
 "unresolved_rows_with_any_exact_idref_date":sum(bool(x["idref_exact_dates"]) for x in unres),
 "unresolved_rows_with_unique_exact_candidate":sum(bool(x["idref_candidate_dob"]) and not int(x["idref_source_conflict"]) for x in unres),
 "unresolved_candidates_for_manual_review":len(cands),
 "candidate_names":[x["name"] for x in cands],
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. Identity linkage is frozen NAS reliable QID -> Wikidata P269 -> IdRef MARCXML. Only exact day-level values parsed from UNIMARC authority field 103 are candidates. No v16 DOB is modified automatically."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
