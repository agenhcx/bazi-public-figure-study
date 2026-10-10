#!/usr/bin/env python3
from __future__ import annotations
import csv,datetime as dt,hashlib,json,re,time,urllib.error,urllib.parse,urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v16.csv"
OUT=BASE/"nas_viaf_dob_diagnostic_v1.csv"
CAND=BASE/"nas_viaf_dob_candidates_v1.csv"
VAL=BASE/"nas_viaf_dob_validation_conflicts_v1.csv"
SUMMARY=BASE/"summary_nas_viaf_dob_diagnostic_v1.json"
QLEVER="https://qlever.dev/api/wikidata"
UA="bazi-public-figure-study/1.0 (NAS VIAF exact-DOB diagnostic; no BaZi computation)"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
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
    if len(norm(r.get("name","")).split())>=3 or as_int(r.get("global_affiliation_match"))==1:return q,"global_unique_identity"
    return "",""
def chunks(xs,n=120):
    for i in range(0,len(xs),n):yield xs[i:i+n]
def sparql(q,retries=5):
    body=urllib.parse.urlencode({"query":q,"action":"tsv_export"}).encode()
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(QLEVER,data=body,method="POST",headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"text/tab-separated-values"})
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
def get_json(url,retries=3):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=35) as r:
                return getattr(r,"status",200),json.loads(r.read(5_000_000).decode("utf-8","ignore")),r.geturl(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code in {400,401,403,404}:return e.code,None,url,"HTTP "+str(e.code)
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            time.sleep(min(10,2**i))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(10,2**i))
    return getattr(last,"code",""),None,url,repr(last)
def iso(s):
    m=re.fullmatch(r"([12]\d{3})-(\d{2})-(\d{2})",str(s or "").strip())
    if not m:return ""
    try:return dt.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except:return ""
def walk_values(obj,key_suffix):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if str(k).split(":")[-1]==key_suffix:vals.append(v)
            vals.extend(walk_values(v,key_suffix))
    elif isinstance(obj,list):
        for x in obj:vals.extend(walk_values(x,key_suffix))
    return vals
def flatten_strings(x):
    out=[]
    if isinstance(x,str):out.append(x)
    elif isinstance(x,list):
        for z in x:out.extend(flatten_strings(z))
    elif isinstance(x,dict):
        for z in x.values():out.extend(flatten_strings(z))
    return out
def viaf_dates(obj):
    vals=set()
    for v in walk_values(obj,"birthDate"):
        for s in flatten_strings(v):
            d=iso(s)
            if d:vals.add(d)
    return sorted(vals)
def viaf_sources(obj):
    vals=set()
    for v in walk_values(obj,"sid"):
        for s in flatten_strings(v):
            if "|" in s:vals.add(s)
    for v in walk_values(obj,"source"):
        if isinstance(v,list):
            for z in v:
                if isinstance(z,dict):
                    sid=z.get("sid") or z.get("ns1:sid")
                    if isinstance(sid,str) and "|" in sid:vals.add(sid)
    return sorted(vals)
def viaf_name(obj):
    vals=walk_values(obj,"text")
    ss=[]
    for v in vals:ss.extend(flatten_strings(v))
    return next((s for s in ss if s.strip()),"")
def fetch_viaf(vid):
    url=f"https://viaf.org/viaf/{urllib.parse.quote(vid)}/viaf.json"
    st,obj,final,err=get_json(url)
    if not isinstance(obj,dict):
        return vid,{"ok":0,"status":st,"url":final,"error":err,"dates":[],"sources":[],"name":""}
    return vid,{"ok":1,"status":st,"url":final,"error":"","dates":viaf_dates(obj),"sources":viaf_sources(obj),"name":viaf_name(obj)}

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
living=[r for r in rows if r.get("deceased")!="Y"]
known=[r for r in living if present(r.get("final_exact_dob"))]
unresolved=[r for r in living if not present(r.get("final_exact_dob"))]
known=sorted(known,key=lambda r:hashlib.sha256(("viaf-validation-v1:"+r["profile_url"]).encode()).hexdigest())[:300]
targets=[("validation",r) for r in known]+[("unresolved",r) for r in unresolved]
qid_rows=[]
for cohort,r in targets:
    q,b=reliable_qid(r)
    if q:qid_rows.append((cohort,r,q,b))
qids=sorted({q for _,_,q,_ in qid_rows})

ids=defaultdict(set)
for batch in chunks(qids):
    vals=" ".join("wd:"+q for q in batch)
    q=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
SELECT ?person ?viaf WHERE {{
 VALUES ?person {{ {vals} }}
 ?person wdt:P214 ?viaf .
}}"""
    for x in sparql(q):
        person=(x.get("person") or "").rsplit("/",1)[-1]
        vid=(x.get("viaf") or "").strip()
        if re.fullmatch(r"Q\d+",person) and vid:ids[person].add(vid)

all_vid=sorted({v for q in qids for v in ids[q]})
fetched={}
with ThreadPoolExecutor(max_workers=12) as ex:
    fs={ex.submit(fetch_viaf,v):v for v in all_vid}
    for f in as_completed(fs):
        v=fs[f]
        try:vv,res=f.result();fetched[vv]=res
        except Exception as e:fetched[v]={"ok":0,"status":"","url":"","error":repr(e),"dates":[],"sources":[],"name":""}

fields=[
 "cohort","profile_url","name","election_year","affiliation","qid","identity_basis","master_exact_dob",
 "viaf_ids","viaf_fetch_successes","viaf_exact_dates","viaf_candidate_dob","viaf_source_conflict",
 "age_at_election","age_plausible","validation_match","candidate_for_manual_provenance_review",
 "viaf_urls","viaf_names","contributing_authority_sids","contributing_authority_codes","fetch_errors"
]
out=[];cands=[];valconf=[]
for cohort,r,q,b in qid_rows:
    vids=sorted(ids[q])
    if not vids:continue
    dates=set();urls=[];names=[];sids=set();errs=[];ok=0
    for v in vids:
        z=fetched.get(v,{})
        ok+=int(z.get("ok",0));dates.update(z.get("dates",[]));sids.update(z.get("sources",[]))
        if z.get("url"):urls.append(z["url"])
        if z.get("name"):names.append(z["name"])
        if z.get("error"):errs.append(v+":"+z["error"])
    dates=sorted(dates)
    cand=dates[0] if len(dates)==1 else ""
    conflict=int(len(dates)>1)
    ey=as_int(r.get("election_year"));age=ey-int(cand[:4]) if ey and cand else None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    master=r.get("final_exact_dob","") if cohort=="validation" else ""
    vm=int(cand==master) if cohort=="validation" and cand else ""
    codes=sorted({s.split("|",1)[0] for s in sids if "|" in s})
    row={
      "cohort":cohort,"profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"qid":q,"identity_basis":b,"master_exact_dob":master,
      "viaf_ids":"|".join(vids),"viaf_fetch_successes":ok,"viaf_exact_dates":"|".join(dates),
      "viaf_candidate_dob":cand,"viaf_source_conflict":conflict,
      "age_at_election":age if age is not None else "","age_plausible":ageok,"validation_match":vm,
      "candidate_for_manual_provenance_review":int(cohort=="unresolved" and bool(cand) and not conflict and ageok==1),
      "viaf_urls":"|".join(urls),"viaf_names":" || ".join(names),"contributing_authority_sids":"|".join(sorted(sids)),
      "contributing_authority_codes":"|".join(codes),"fetch_errors":" || ".join(errs)
    }
    out.append(row)
    if row["candidate_for_manual_provenance_review"]==1:cands.append(row)
    if cohort=="validation" and cand and vm==0:valconf.append(row)

write_csv(OUT,out,fields);write_csv(CAND,cands,fields);write_csv(VAL,valconf,fields)
val=[x for x in out if x["cohort"]=="validation"];vf=[x for x in val if x["viaf_candidate_dob"]]
unres=[x for x in out if x["cohort"]=="unresolved"]
code_counts=defaultdict(int)
for x in unres:
    for c in str(x["contributing_authority_codes"]).split("|"):
        if c:code_counts[c]+=1
summary={
 "dataset":"NAS VIAF exact-DOB diagnostic v1",
 "input":INPUT.name,
 "living_validation_sample_rows":len(known),
 "living_unresolved_rows":len(unresolved),
 "reliable_qid_target_rows":len(qid_rows),
 "qids_with_p214":sum(bool(ids[q]) for q in qids),
 "unique_viaf_ids":len(all_vid),
 "viaf_fetch_successes":sum(int(fetched[v].get("ok",0)) for v in all_vid),
 "validation_rows_with_viaf":sum(bool(ids[q]) for cohort,r,q,b in qid_rows if cohort=="validation"),
 "validation_rows_with_unique_exact_candidate":len(vf),
 "validation_exact_matches":sum(x["validation_match"]==1 for x in vf),
 "validation_exact_conflicts":len(valconf),
 "validation_match_rate":round(sum(x["validation_match"]==1 for x in vf)/len(vf),6) if vf else None,
 "unresolved_rows_with_viaf":sum(bool(ids[q]) for cohort,r,q,b in qid_rows if cohort=="unresolved"),
 "unresolved_rows_with_any_exact_viaf_date":sum(bool(x["viaf_exact_dates"]) for x in unres),
 "unresolved_rows_with_unique_exact_candidate":sum(bool(x["viaf_candidate_dob"]) and not int(x["viaf_source_conflict"]) for x in unres),
 "unresolved_candidates_for_manual_provenance_review":len(cands),
 "candidate_names":[x["name"] for x in cands],
 "contributing_authority_code_counts_among_unresolved_viaf_rows":dict(sorted(code_counts.items(),key=lambda kv:(-kv[1],kv[0]))),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. VIAF exact dates are treated as locator candidates, not final evidence. Any unresolved exact-date candidate must be traced to a contributing authority source record before acceptance into a post-v16 provenance amendment."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
