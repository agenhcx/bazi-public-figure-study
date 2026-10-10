#!/usr/bin/env python3
from __future__ import annotations
import csv,datetime as dt,json,re,time,urllib.error,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

ROOT=Path("data")
UA="bazi-public-figure-study/1.0 (VIAF processed source provenance; no BaZi computation)"
CAND=ROOT/"nas_viaf_dob_candidates_v1.csv"
ALL=ROOT/"nas_viaf_dob_diagnostic_v1.csv"
OUT=ROOT/"nas_viaf_processed_source_provenance_v1.csv"
SUMMARY=ROOT/"summary_nas_viaf_processed_source_provenance_v1.json"
MARC_NS={"m":"http://www.loc.gov/MARC21/slim"}

def locate(name):
    p=ROOT/name
    if p.exists():return p
    for x in ROOT.rglob(name):return x
    raise FileNotFoundError(name)

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def iso(y,m,d):
    try:return dt.date(int(y),int(m),int(d)).isoformat()
    except:return ""
def exact_dates(text):
    s=str(text or "")
    vals=set()
    for m in re.finditer(r"(?<!\d)([12]\d{3})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)",s):
        d=iso(m.group(1),m.group(2),m.group(3))
        if d:vals.add(d)
    for m in re.finditer(r"(?<!\d)([12]\d{3})(\d{2})(\d{2})(?!\d)",re.sub(r"\s+","",s)):
        d=iso(m.group(1),m.group(2),m.group(3))
        if d:vals.add(d)
    return sorted(vals)

def candidate_forms(d):
    if not d:return set()
    try:
        x=dt.date.fromisoformat(d)
    except:return {d}
    months=["","january","february","march","april","may","june","july","august","september","october","november","december"]
    vals={
      d,f"{x.year}{x.month:02d}{x.day:02d}",f"{x.day:02d}/{x.month:02d}/{x.year}",
      f"{x.month:02d}/{x.day:02d}/{x.year}",f"{x.day} {months[x.month]} {x.year}",
      f"{months[x.month]} {x.day} {x.year}",f"{months[x.month]} {x.day}, {x.year}"
    }
    return {re.sub(r"[^a-z0-9]+"," ",v.lower()).strip() for v in vals}

def explicit_candidate(text,d):
    n=re.sub(r"[^a-z0-9]+"," ",str(text or "").lower()).strip()
    return int(any(v and v in n for v in candidate_forms(d)))

def split_sids(s):
    toks=[x.strip() for x in str(s or "").split("|") if x.strip()]
    out=[];i=0
    codes={"LC","SUDOC","DNB","BNF","ISNI","NTA","NKC","NDL","WKP","J9U","BIBSYS","CAOONL","NUKAT","NII","RERO","KRNLK","NLA","PLWABN","NSK","BNC","LNB","PTBNP","SIMACOB","XR","BLBNB","LIH","SELIBR","SZ","W2Z","BNE","DBC","GRATEVE","N6I","XA","BNCHL"}
    while i<len(toks):
        if toks[i] in codes and i+1<len(toks):
            out.append((toks[i],toks[i+1]));i+=2
        else:i+=1
    return out

def get(url,retries=2):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/xml,text/xml;q=0.9,*/*;q=0.1"})
            with urllib.request.urlopen(req,timeout=20) as r:
                return getattr(r,"status",200),r.read(4_000_000),r.geturl(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code in {400,401,403,404}:return e.code,b"",url,"HTTP "+str(e.code)
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            time.sleep(min(4,2**i))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(4,2**i))
    return getattr(last,"code",""),b"",url,repr(last)

def relevant_xml_text(data):
    try:root=ET.fromstring(data)
    except:return data.decode("utf-8","ignore")
    vals=[]
    # VIAF may return MARCXML, UNIMARC-like XML, or its internal XML.
    for elem in root.iter():
        tag=elem.tag.split("}")[-1]
        if tag=="datafield":
            ft=elem.attrib.get("tag","")
            if ft in {"046","103","670","678","100","200"}:
                vals.append(" ".join((x.text or "") for x in elem.iter() if (x.text or "").strip()))
        elif tag.lower() in {"birthdate","dateofbirth","date","dates"} and (elem.text or "").strip():
            vals.append(elem.text.strip())
    return " || ".join(vals) if vals else ET.tostring(root,encoding="unicode")

def fetch_processed(code,ident,candidate):
    sid=f"{code}|{ident}"
    enc=urllib.parse.quote(sid,safe="")
    urls=[
      f"https://viaf.org/processed/{enc}?httpAccept=application/xml",
      f"https://viaf.org/processed/{enc}?httpAccept=application/marc21%2Bxml",
    ]
    errs=[];last_status=""
    for url in urls:
        st,data,final,err=get(url)
        last_status=st
        if not data:
            errs.append(f"{url}:{st}:{err}");continue
        txt=relevant_xml_text(data)
        ds=exact_dates(txt)
        sup=explicit_candidate(txt,candidate)
        return {"ok":1,"status":st,"url":final,"dates":ds,"supports":sup,"excerpt":txt[:1800],"error":""}
    return {"ok":0,"status":last_status,"url":urls[0],"dates":[],"supports":0,"excerpt":"","error":" || ".join(errs)}

cand=read_csv(locate("nas_viaf_dob_candidates_v1.csv"))
allrows=read_csv(locate("nas_viaf_dob_diagnostic_v1.csv"))
validation=[r for r in allrows if r.get("cohort")=="validation" and r.get("viaf_candidate_dob") and r.get("validation_match")=="1"][:20]
targets=[("candidate",r) for r in cand]+[("validation",r) for r in validation]

jobs={}
for cohort,r in targets:
    d=r.get("viaf_candidate_dob","")
    for code,ident in split_sids(r.get("contributing_authority_sids","")):
        if code=="WKP":continue
        jobs[(code,ident,d)]=None

with ThreadPoolExecutor(max_workers=20) as ex:
    fs={ex.submit(fetch_processed,*k):k for k in jobs}
    for f in as_completed(fs):
        k=fs[f]
        try:jobs[k]=f.result()
        except Exception as e:jobs[k]={"ok":0,"status":"","url":"","dates":[],"supports":0,"excerpt":"","error":repr(e)}

fields=["cohort","name","profile_url","viaf_candidate_dob","master_exact_dob","processed_sources_attempted","processed_sources_fetched","supporting_processed_sources","supporting_source_codes","conflicting_processed_sources","verified_by_processed_source","source_details"]
out=[]
for cohort,r in targets:
    d=r.get("viaf_candidate_dob","")
    att=[];fet=[];sup=[];conf=[];details=[]
    for code,ident in split_sids(r.get("contributing_authority_sids","")):
        if code=="WKP":continue
        att.append(code+":"+ident);z=jobs.get((code,ident,d),{})
        if z.get("ok"):fet.append(code+":"+ident)
        if z.get("supports"):sup.append(code+":"+ident)
        if z.get("dates") and d not in z.get("dates",[]):conf.append(code+":"+ident+":"+",".join(z.get("dates",[])))
        details.append(json.dumps({"code":code,"id":ident,"ok":z.get("ok",0),"status":z.get("status",""),"supports":z.get("supports",0),"dates":z.get("dates",[]),"url":z.get("url",""),"error":z.get("error","")},ensure_ascii=False))
    out.append({
      "cohort":cohort,"name":r.get("name",""),"profile_url":r.get("profile_url",""),
      "viaf_candidate_dob":d,"master_exact_dob":r.get("master_exact_dob",""),
      "processed_sources_attempted":"|".join(att),"processed_sources_fetched":"|".join(fet),
      "supporting_processed_sources":"|".join(sup),"supporting_source_codes":"|".join(sorted({x.split(":",1)[0] for x in sup})),
      "conflicting_processed_sources":"|".join(conf),
      "verified_by_processed_source":int(bool(sup) and not conf),
      "source_details":" || ".join(details)
    })

write_csv(OUT,out,fields)
crows=[x for x in out if x["cohort"]=="candidate"]
vrows=[x for x in out if x["cohort"]=="validation"]
summary={
 "dataset":"NAS VIAF processed-source provenance diagnostic v1",
 "candidate_rows":len(crows),
 "candidate_rows_with_any_processed_source_fetched":sum(bool(x["processed_sources_fetched"]) for x in crows),
 "candidate_rows_with_candidate_date_in_processed_source":sum(bool(x["supporting_processed_sources"]) for x in crows),
 "candidate_rows_verified_without_processed_source_conflict":sum(int(x["verified_by_processed_source"]) for x in crows),
 "verified_candidates":[{"name":x["name"],"dob":x["viaf_candidate_dob"],"source_codes":x["supporting_source_codes"]} for x in crows if x["verified_by_processed_source"]],
 "candidate_rows_with_conflict":sum(bool(x["conflicting_processed_sources"]) for x in crows),
 "validation_rows":len(vrows),
 "validation_rows_with_any_processed_source_fetched":sum(bool(x["processed_sources_fetched"]) for x in vrows),
 "validation_rows_supported":sum(bool(x["supporting_processed_sources"]) for x in vrows),
 "validation_rows_verified_without_conflict":sum(int(x["verified_by_processed_source"]) for x in vrows),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. This queries VIAF source-specific processed authority records, not the cluster-level birthDate. WKP is deliberately excluded. A candidate remains eligible for a post-v16 supplement only if the exact date appears in a non-WKP processed authority source without a conflicting exact date."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
