#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, re, time, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v14.csv"
OUT=BASE/"nas_loc_670_hidden_dob_v1.csv"
VAL=BASE/"nas_loc_670_hidden_dob_validation_conflicts_v1.csv"
CAND=BASE/"nas_loc_670_hidden_dob_candidates_v1.csv"
SUMMARY=BASE/"summary_loc_670_hidden_dob_v1.json"
UA="bazi-public-figure-study/1.0 (LOC MARC 670 hidden-DOB diagnostic; no BaZi computation)"
NS={"m":"http://www.loc.gov/MARC21/slim"}
MONTHS={m.lower():i for i,m in enumerate(["","January","February","March","April","May","June","July","August","September","October","November","December"])}
for k,v in list(MONTHS.items()):
    if len(k)>=3:MONTHS[k[:3]]=v

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    fields=fields or (list(rows[0].keys()) if rows else [])
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def as_int(v,d=0):
    try:return int(float(str(v)))
    except:return d
def norm_name(s):return " ".join(re.sub(r"[^a-z0-9]+"," ",str(s or "").lower()).split())
def reliable_qid(r):
    q=(r.get("wikidata_qid") or "").strip()
    if re.fullmatch(r"Q\d+",q):return q,"wikidata_qid"
    q=(r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+",q):return "",""
    if as_int(r.get("global_exact_name_match_count"))!=1:return "",""
    toks=len(norm_name(r.get("name","")).split())
    if toks>=3 or as_int(r.get("global_affiliation_match"))==1:return q,"global_unique_identity"
    return "",""
def get(url,accept="application/json",retries=5):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=90) as r:return getattr(r,"status",200),r.read(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code==404:return 404,b"","HTTP 404"
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            try:delay=float(e.headers.get("Retry-After",""))
            except Exception:delay=min(20,2**i)
            time.sleep(max(2,delay))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(20,2**i))
    return getattr(last,"code",""),b"",repr(last)
def dv(snak):
    try:return snak["datavalue"]["value"]
    except:return None
def fetch_entity(qid):
    url=f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    st,data,err=get(url,"application/json")
    if not data:return qid,{"ok":0,"loc":[],"error":err}
    try:
        obj=json.loads(data.decode("utf-8"))
        ent=(obj.get("entities") or {}).get(qid) or {}
        vals=[]
        for c in (ent.get("claims") or {}).get("P244",[]):
            v=dv(c.get("mainsnak") or {})
            if isinstance(v,str) and v.strip():vals.append(v.strip())
        return qid,{"ok":1,"loc":sorted(set(vals)),"error":""}
    except Exception as e:return qid,{"ok":0,"loc":[],"error":repr(e)}
def parse_loc(data):
    root=ET.fromstring(data)
    rec=root if root.tag.endswith("record") else root.find(".//m:record",NS)
    f046=[];f670=[];heading=""
    if rec is None:return {"heading":"","f046":[],"f670":[]}
    for f in rec.findall("m:datafield",NS):
        tag=f.attrib.get("tag","")
        sf=[(s.attrib.get("code",""),(s.text or "").strip()) for s in f.findall("m:subfield",NS)]
        if tag=="100":heading=" ".join(v for _,v in sf if v)
        elif tag=="046":f046.append(sf)
        elif tag=="670":f670.append(" ".join(v for _,v in sf if v))
    return {"heading":heading,"f046":f046,"f670":f670}
def two_digit_year(yy,election_year):
    yy=int(yy)
    opts=[1900+yy,2000+yy]
    ok=[y for y in opts if election_year and 25<=election_year-y<=100]
    if len(ok)==1:return ok[0]
    if len(ok)>1:return min(ok)
    return 1900+yy
def iso(y,m,d):
    try:
        import datetime as dt
        return dt.date(int(y),int(m),int(d)).isoformat()
    except:return ""
def parse_numeric_date(s,election_year):
    s=s.strip()
    # YYYY-MM-DD or YYYY/MM/DD
    m=re.fullmatch(r"([12]\d{3})[-/](\d{1,2})[-/](\d{1,2})",s)
    if m:return iso(*m.groups())
    # MM/DD/YYYY or MM/DD/YY
    m=re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2}|[12]\d{3})",s)
    if m:
        mo,d,y=m.groups();y=int(y)
        if y<100:y=two_digit_year(y,election_year)
        return iso(y,mo,d)
    return ""
def parse_textual_date(s,election_year):
    s=re.sub(r"[.,]"," ",s)
    s=" ".join(s.split())
    # Month DD YYYY
    m=re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2})\s+((?:19|20)?\d{2})\b",s)
    if m and m.group(1).lower()[:3] in MONTHS:
        mo=MONTHS[m.group(1).lower()[:3]];d=int(m.group(2));y=int(m.group(3))
        if y<100:y=two_digit_year(y,election_year)
        return iso(y,mo,d)
    # DD Month YYYY
    m=re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+((?:19|20)?\d{2})\b",s)
    if m and m.group(2).lower()[:3] in MONTHS:
        d=int(m.group(1));mo=MONTHS[m.group(2).lower()[:3]];y=int(m.group(3))
        if y<100:y=two_digit_year(y,election_year)
        return iso(y,mo,d)
    return ""
def marker_dates(text,election_year):
    vals=set();evidence=[]
    # Only inspect local windows following explicit birth markers, avoiding publication dates.
    for m in re.finditer(r"(?i)\b(?:b(?:orn)?\.?|birth\s*date|date\s*of\s*birth)\s*[:=]?\s*",text):
        w=text[m.end():m.end()+55]
        candidates=[]
        for p in [
            r"[12]\d{3}[-/]\d{1,2}[-/]\d{1,2}",
            r"\d{1,2}[-/]\d{1,2}[-/](?:[12]\d{3}|\d{2})",
            r"[A-Za-z]{3,9}\s+\d{1,2},?\s+(?:[12]\d{3}|\d{2})",
            r"\d{1,2}\s+[A-Za-z]{3,9}\s+(?:[12]\d{3}|\d{2})",
        ]:
            mm=re.search(p,w)
            if mm:candidates.append(mm.group(0))
        for c in candidates:
            d=parse_numeric_date(c,election_year) or parse_textual_date(c,election_year)
            if d:
                vals.add(d);evidence.append(text[max(0,m.start()-25):m.end()+70].strip())
    return vals,evidence
def field046_dates(fields):
    vals=set();evidence=[]
    for sf in fields:
        for code,v in sf:
            if code!="f":continue
            raw=re.sub(r"[^0-9]","",v)
            d=""
            if re.fullmatch(r"[12]\d{7}",raw):
                d=iso(raw[:4],raw[4:6],raw[6:8])
            else:
                m=re.search(r"([12]\d{3})[-/]?(\d{2})[-/]?(\d{2})",v)
                if m:d=iso(*m.groups())
            if d:vals.add(d);evidence.append(f"$f {v}")
    return vals,evidence
def fetch_loc(locid):
    url=f"https://id.loc.gov/authorities/names/{urllib.parse.quote(locid)}.marcxml.xml"
    st,data,err=get(url,"application/xml,text/xml;q=0.9,*/*;q=0.1")
    if not data:return locid,{"ok":0,"dates":[],"evidence":[],"heading":"","error":err,"url":url}
    try:
        p=parse_loc(data)
        return locid,{"ok":1,"parsed":p,"error":"","url":url}
    except Exception as e:return locid,{"ok":0,"dates":[],"evidence":[],"heading":"","error":repr(e),"url":url}

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
unresolved=[]
known=[]
for r in rows:
    q,b=reliable_qid(r)
    if not q:continue
    if present(r.get("final_exact_dob")):known.append((r,q,b))
    else:unresolved.append((r,q,b))
known=sorted(known,key=lambda x:hashlib.sha256(x[0]["profile_url"].encode()).hexdigest())[:300]

allq=sorted({q for _,q,_ in unresolved+known})
entities={}
with ThreadPoolExecutor(max_workers=10) as ex:
    fs={ex.submit(fetch_entity,q):q for q in allq}
    for f in as_completed(fs):
        q=fs[f]
        try:qq,res=f.result();entities[qq]=res
        except Exception as e:entities[q]={"ok":0,"loc":[],"error":repr(e)}

locids=sorted({x for q in allq for x in entities.get(q,{}).get("loc",[])})
locraw={}
with ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(fetch_loc,x):x for x in locids}
    for f in as_completed(fs):
        x=fs[f]
        try:xx,res=f.result();locraw[xx]=res
        except Exception as e:locraw[x]={"ok":0,"parsed":{},"error":repr(e),"url":""}

def loc_dates_for(r,q):
    vals=set();ev=[];urls=[];notes=[]
    ey=as_int(r.get("election_year"))
    for lid in entities.get(q,{}).get("loc",[]):
        z=locraw.get(lid,{})
        if not z.get("ok"):continue
        p=z.get("parsed",{})
        a,e=field046_dates(p.get("f046",[]));vals|=a;ev+=e
        for note in p.get("f670",[]):
            a,e=marker_dates(note,ey);vals|=a;ev+=e
            if a:notes.append(note)
        urls.append(z.get("url",""))
    return sorted(vals),ev,urls,notes

valrows=[];comp=match=conf=0
for r,q,b in known:
    ds,ev,urls,notes=loc_dates_for(r,q)
    if len(ds)==1:
        comp+=1
        if ds[0]==r.get("final_exact_dob"):match+=1
        else:
            conf+=1
            valrows.append({
              "profile_url":r["profile_url"],"name":r["name"],"qid":q,
              "master_exact_dob":r.get("final_exact_dob",""),"loc_hidden_candidate_dob":ds[0],
              "loc_ids":"|".join(entities.get(q,{}).get("loc",[])),"evidence":" || ".join(ev),
              "loc_urls":"|".join(urls)
            })

out=[];cands=[]
for r,q,b in unresolved:
    ds,ev,urls,notes=loc_dates_for(r,q)
    conflict=int(len(ds)>1)
    cand=ds[0] if len(ds)==1 else ""
    ey=as_int(r.get("election_year"))
    age=ey-int(cand[:4]) if cand and ey else None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    row={
      "profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"qid":q,"identity_basis":b,
      "loc_ids":"|".join(entities.get(q,{}).get("loc",[])),
      "loc_hidden_exact_dates":"|".join(ds),"loc_hidden_conflict":conflict,"loc_candidate_dob":cand,
      "age_at_election":age if age is not None else "","age_plausible":ageok,
      "candidate_for_manual_provenance_review":int(bool(cand) and not conflict and ageok==1),
      "evidence":" || ".join(ev),"supporting_670_notes":" || ".join(notes),"loc_urls":"|".join(urls)
    }
    out.append(row)
    if int(row["candidate_for_manual_provenance_review"])==1:cands.append(row)

write_csv(OUT,out)
write_csv(VAL,valrows,["profile_url","name","qid","master_exact_dob","loc_hidden_candidate_dob","loc_ids","evidence","loc_urls"])
write_csv(CAND,cands,list(out[0].keys()) if out else [])
summary={
 "dataset":"NAS LOC MARC hidden exact-DOB diagnostic v1",
 "input_v14_rows":len(rows),
 "unresolved_reliable_qid_rows":len(unresolved),
 "validation_sample_rows":len(known),
 "wikidata_entity_fetch_successes":sum(int(entities.get(q,{}).get("ok",0)) for q in allq),
 "unique_loc_ids":len(locids),
 "loc_fetch_successes":sum(int(locraw.get(x,{}).get("ok",0)) for x in locids),
 "validation_comparable_exact_rows":comp,
 "validation_exact_matches":match,
 "validation_exact_conflicts":conf,
 "validation_match_rate":round(match/comp,6) if comp else None,
 "unresolved_rows_with_loc_id":sum(bool(entities.get(q,{}).get("loc")) for _,q,_ in unresolved),
 "unresolved_rows_with_unique_hidden_exact_candidate":sum(bool(x["loc_candidate_dob"]) and not int(x["loc_hidden_conflict"]) for x in out),
 "candidates_for_manual_provenance_review":len(cands),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. Candidate dates are extracted only from MARC 046 birth-date subfield $f or explicit birth-marker windows in MARC 670 notes. No DOB is auto-written."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
