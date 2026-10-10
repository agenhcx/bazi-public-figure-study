#!/usr/bin/env python3
from __future__ import annotations
import os
import csv,datetime as dt,json,re,time,urllib.error,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

ROOT=Path("data")
CAND_NAMES=["nas_viaf_dob_candidates_v1.csv","nas_science_core_dob_crosswalk/nas_viaf_dob_candidates_v1.csv"]
ALL_NAMES=["nas_viaf_dob_diagnostic_v1.csv","nas_science_core_dob_crosswalk/nas_viaf_dob_diagnostic_v1.csv"]
OUT=ROOT/"nas_viaf_provenance_audit_v1.csv"
VAL=ROOT/"nas_viaf_provenance_validation_v1.csv"
VER=ROOT/"nas_viaf_provenance_verified_candidates_v1.csv"
SUMMARY=ROOT/"summary_nas_viaf_provenance_audit_v1.json"
UA="bazi-public-figure-study/1.0 (VIAF contributing-authority provenance audit; no BaZi computation)"
MARC_NS={"m":"http://www.loc.gov/MARC21/slim"}

def locate(names):
    for n in names:
        p=ROOT/n
        if p.exists():return p
    for p in ROOT.rglob(names[0]):
        return p
    raise FileNotFoundError(names)

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
    for m in re.finditer(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.]([12]\d{3})(?!\d)",s):
        # Ambiguous numeric dates are used only as evidence for a pre-existing candidate below.
        a,b,y=int(m.group(1)),int(m.group(2)),int(m.group(3))
        for mo,day in ((a,b),(b,a)):
            d=iso(y,mo,day)
            if d:vals.add(d)
    for m in re.finditer(r"(?<!\d)([12]\d{3})(\d{2})(\d{2})(?!\d)",re.sub(r"\s+","",s)):
        d=iso(m.group(1),m.group(2),m.group(3))
        if d:vals.add(d)
    return sorted(vals)

def get(url,accept="application/json,text/xml,application/xml;q=0.9,*/*;q=0.1",retries=2):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=25) as r:
                return getattr(r,"status",200),r.read(4_000_000),r.geturl(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code in {400,401,403,404}:return e.code,b"",url,"HTTP "+str(e.code)
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            time.sleep(min(5,2**i))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(5,2**i))
    return getattr(last,"code",""),b"",url,repr(last)

def parse_loc(data,candidate):
    root=ET.fromstring(data)
    fields=[]
    for f in root.findall(".//m:datafield",MARC_NS):
        if f.attrib.get("tag") in {"046","670","678"}:
            vals=[(x.attrib.get("code",""),(x.text or "").strip()) for x in f.findall("m:subfield",MARC_NS)]
            fields.append((f.attrib.get("tag")," ".join(v for _,v in vals if v)))
    structured=" || ".join(v for tag,v in fields if tag=="046")
    notes=" || ".join(v for tag,v in fields if tag in {"670","678"})
    ds=set(exact_dates(structured))
    explicit=int(candidate in ds or candidate in exact_dates(notes))
    return sorted(ds),explicit,structured,notes

def parse_idref(data,candidate):
    root=ET.fromstring(data)
    f103=[];notes=[]
    for f in root.findall(".//m:datafield",MARC_NS):
        tag=f.attrib.get("tag")
        vals=[(x.attrib.get("code",""),(x.text or "").strip()) for x in f.findall("m:subfield",MARC_NS)]
        joined=" ".join(v for _,v in vals if v)
        if tag=="103":f103.append(joined)
        elif tag in {"300","810"}:notes.append(joined)
    structured=" || ".join(f103)
    ds=set(exact_dates(structured))
    explicit=int(candidate in ds or candidate in exact_dates(" || ".join(notes)))
    return sorted(ds),explicit,structured," || ".join(notes)

def walk_strings(obj):
    if isinstance(obj,str):
        yield obj
    elif isinstance(obj,list):
        for x in obj:yield from walk_strings(x)
    elif isinstance(obj,dict):
        for x in obj.values():yield from walk_strings(x)

def gnd_birth_values(obj):
    vals=[]
    if not isinstance(obj,dict):return vals
    raw=obj.get("dateOfBirth",[])
    if not isinstance(raw,list):raw=[raw]
    for x in raw:
        vals.extend(list(walk_strings(x)))
    return vals

def parse_gnd(data,candidate):
    obj=json.loads(data.decode("utf-8","ignore"))
    raw=gnd_birth_values(obj)
    structured=" || ".join(raw)
    ds=exact_dates(structured)
    explicit=int(candidate in ds)
    notes=json.dumps({k:obj.get(k) for k in ("source","biographicalOrHistoricalInformation") if k in obj},ensure_ascii=False)
    if not explicit and candidate in exact_dates(notes):explicit=1
    return ds,explicit,structured,notes

def bnf_urls(raw_id):
    x=str(raw_id or "").strip()
    if not x:return []
    # VIAF BNF SIDs may already include cb-prefix/check character, or just the ARK identifier.
    candidates=[x]
    if x.startswith("cb"):candidates.append(x[2:])
    else:candidates.append("cb"+x)
    urls=[]
    for z in dict.fromkeys(candidates):
        urls += [
          f"https://data.bnf.fr/ark:/12148/{urllib.parse.quote(z)}/rdf.jsonld",
          f"https://data.bnf.fr/ark:/12148/{urllib.parse.quote(z)}.rdf",
        ]
    return urls

def parse_bnf(data,candidate):
    txt=data.decode("utf-8","ignore")
    ds=exact_dates(txt)
    return ds,int(candidate in ds),"",txt[:5000]

def split_sids(s):
    out=[]
    for sid in str(s or "").split("|"):
        # Flat CSV uses "|" both between SIDs and inside code|id, so reconstruct adjacent code/id tokens.
        pass
    toks=[x.strip() for x in str(s or "").split("|") if x.strip()]
    i=0
    known={"LC","SUDOC","DNB","BNF","ISNI","NTA","NKC","NDL","WKP"}
    while i<len(toks):
        if toks[i] in known and i+1<len(toks):
            out.append((toks[i],toks[i+1]));i+=2
        else:i+=1
    return out

def fetch_one(code,ident,candidate):
    if code=="LC":
        url=f"https://id.loc.gov/authorities/names/{urllib.parse.quote(ident)}.marcxml.xml"
        st,data,final,err=get(url,"application/xml,text/xml;q=0.9,*/*;q=0.1")
        if not data:return code,ident,{"ok":0,"url":final,"status":st,"error":err,"dates":[],"supports":0,"structured":"","notes":""}
        try:ds,sup,structured,notes=parse_loc(data,candidate)
        except Exception as e:return code,ident,{"ok":0,"url":final,"status":st,"error":repr(e),"dates":[],"supports":0,"structured":"","notes":""}
    elif code=="SUDOC":
        url=f"https://www.idref.fr/{urllib.parse.quote(ident)}.xml"
        st,data,final,err=get(url,"application/xml,text/xml;q=0.9,*/*;q=0.1")
        if not data:return code,ident,{"ok":0,"url":final,"status":st,"error":err,"dates":[],"supports":0,"structured":"","notes":""}
        try:ds,sup,structured,notes=parse_idref(data,candidate)
        except Exception as e:return code,ident,{"ok":0,"url":final,"status":st,"error":repr(e),"dates":[],"supports":0,"structured":"","notes":""}
    elif code=="DNB":
        url=f"https://lobid.org/gnd/{urllib.parse.quote(ident)}.json"
        st,data,final,err=get(url,"application/json")
        if not data:return code,ident,{"ok":0,"url":final,"status":st,"error":err,"dates":[],"supports":0,"structured":"","notes":""}
        try:ds,sup,structured,notes=parse_gnd(data,candidate)
        except Exception as e:return code,ident,{"ok":0,"url":final,"status":st,"error":repr(e),"dates":[],"supports":0,"structured":"","notes":""}
    elif code=="BNF":
        last={"ok":0,"url":"","status":"","error":"","dates":[],"supports":0,"structured":"","notes":""}
        for url in bnf_urls(ident):
            st,data,final,err=get(url,"application/ld+json,application/rdf+xml,text/xml;q=0.8,*/*;q=0.1")
            if not data:
                last={"ok":0,"url":final,"status":st,"error":err,"dates":[],"supports":0,"structured":"","notes":""};continue
            try:ds,sup,structured,notes=parse_bnf(data,candidate)
            except Exception as e:
                last={"ok":0,"url":final,"status":st,"error":repr(e),"dates":[],"supports":0,"structured":"","notes":""};continue
            if sup:return code,ident,{"ok":1,"url":final,"status":st,"error":"","dates":ds,"supports":sup,"structured":structured,"notes":notes}
            last={"ok":1,"url":final,"status":st,"error":"","dates":ds,"supports":sup,"structured":structured,"notes":notes}
        return code,ident,last
    else:raise ValueError(code)
    return code,ident,{"ok":1,"url":final,"status":st,"error":"","dates":ds,"supports":sup,"structured":structured,"notes":notes}

cand_rows=read_csv(locate(CAND_NAMES))
all_rows=read_csv(locate(ALL_NAMES))
# Add a bounded validation set whose VIAF date already matches the frozen master; this tests direct-source tracing.
validation_n=int(os.environ.get("VIAF_PROVENANCE_VALIDATION_N","20"))
val_rows=[r for r in all_rows if r.get("cohort")=="validation" and r.get("viaf_candidate_dob") and r.get("validation_match")=="1"][:validation_n]
targets=[("candidate",r) for r in cand_rows]+[("validation",r) for r in val_rows]

jobs={}
for cohort,r in targets:
    candidate=r.get("viaf_candidate_dob","")
    for code,ident in split_sids(r.get("contributing_authority_sids","")):
        if code in {"LC","SUDOC","DNB","BNF"}:
            jobs[(code,ident,candidate)]=None

with ThreadPoolExecutor(max_workers=12) as ex:
    fs={ex.submit(fetch_one,*k):k for k in jobs}
    for f in as_completed(fs):
        k=fs[f]
        try:jobs[k]=f.result()[2]
        except Exception as e:jobs[k]={"ok":0,"url":"","status":"","error":repr(e),"dates":[],"supports":0,"structured":"","notes":""}

fields=[
 "cohort","name","profile_url","viaf_candidate_dob","master_exact_dob",
 "direct_sources_attempted","direct_sources_fetched","direct_supporting_sources",
 "direct_conflicting_sources","verified_by_direct_authority","verified_source_codes",
 "verified_source_urls","all_direct_dates","audit_details"
]
out=[];verified=[];validation=[]
for cohort,r in targets:
    cand=r.get("viaf_candidate_dob","");attempted=[];fetched=[];support=[];conflicts=[];dates=set();details=[]
    for code,ident in split_sids(r.get("contributing_authority_sids","")):
        if code not in {"LC","SUDOC","DNB","BNF"}:continue
        attempted.append(code+":"+ident)
        z=jobs.get((code,ident,cand),{})
        if z.get("ok"):fetched.append(code+":"+ident)
        dates.update(z.get("dates",[]))
        if z.get("supports"):support.append(code+":"+ident)
        if z.get("dates") and cand not in z.get("dates",[]):conflicts.append(code+":"+ident+":"+",".join(z.get("dates",[])))
        details.append(json.dumps({"code":code,"id":ident,"url":z.get("url",""),"status":z.get("status",""),"supports":z.get("supports",0),"dates":z.get("dates",[]),"error":z.get("error","")},ensure_ascii=False))
    verified_flag=int(bool(support) and not conflicts)
    row={
      "cohort":cohort,"name":r.get("name",""),"profile_url":r.get("profile_url",""),
      "viaf_candidate_dob":cand,"master_exact_dob":r.get("master_exact_dob",""),
      "direct_sources_attempted":"|".join(attempted),"direct_sources_fetched":"|".join(fetched),
      "direct_supporting_sources":"|".join(support),"direct_conflicting_sources":"|".join(conflicts),
      "verified_by_direct_authority":verified_flag,
      "verified_source_codes":"|".join(sorted({x.split(":",1)[0] for x in support})),
      "verified_source_urls":"|".join(sorted({jobs[(code,ident,cand)].get("url","") for code,ident in split_sids(r.get("contributing_authority_sids","")) if code in {"LC","SUDOC","DNB","BNF"} and jobs.get((code,ident,cand),{}).get("supports")})),
      "all_direct_dates":"|".join(sorted(dates)),"audit_details":" || ".join(details)
    }
    out.append(row)
    if cohort=="candidate" and verified_flag:verified.append(row)
    if cohort=="validation":validation.append(row)

write_csv(OUT,out,fields);write_csv(VER,verified,fields);write_csv(VAL,validation,fields)
vfetch=[x for x in validation if x["direct_sources_fetched"]]
summary={
 "dataset":"NAS VIAF candidate contributing-authority provenance audit v1",
 "viaf_candidate_rows":len(cand_rows),
 "candidate_rows_with_any_direct_source_attempted":sum(bool(x["direct_sources_attempted"]) for x in out if x["cohort"]=="candidate"),
 "candidate_rows_with_any_direct_source_fetched":sum(bool(x["direct_sources_fetched"]) for x in out if x["cohort"]=="candidate"),
 "candidate_rows_verified_by_direct_authority":len(verified),
 "verified_candidates":[{"name":x["name"],"dob":x["viaf_candidate_dob"],"source_codes":x["verified_source_codes"]} for x in verified],
 "candidate_rows_with_direct_conflict":sum(bool(x["direct_conflicting_sources"]) for x in out if x["cohort"]=="candidate"),
 "validation_rows":len(validation),
 "validation_rows_with_any_direct_source_fetched":len(vfetch),
 "validation_rows_directly_verified":sum(int(x["verified_by_direct_authority"]) for x in validation),
 "validation_direct_verification_rate":round(sum(int(x["verified_by_direct_authority"]) for x in validation)/len(vfetch),6) if vfetch else None,
 "bazi_variables_computed":0,
 "decision_note":"A VIAF candidate is marked verified only when at least one contributing LC/SUDOC(IdRef)/DNB(GND)/BnF authority record directly supports the exact candidate date and no fetched direct authority record exposes a conflicting exact date. Verified rows remain a proposed post-v16 provenance supplement until separately frozen."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
