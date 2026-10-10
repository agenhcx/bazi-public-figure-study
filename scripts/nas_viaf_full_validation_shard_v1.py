#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,datetime as dt,json,re,time,urllib.error,urllib.parse,urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

BASE=Path("data")
INPUT=BASE/"nas_science_core_dob_crosswalk_v16.csv"
UA="bazi-public-figure-study/1.0 (NAS VIAF full provenance validation; no BaZi computation)"
QLEVER="https://qlever.dev/api/wikidata"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","None","nan")
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
def get_json(url,retries=2):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=25) as r:
                return getattr(r,"status",200),json.loads(r.read(5_000_000).decode("utf-8","ignore")),r.geturl(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code in {400,401,403,404}:return e.code,None,url,"HTTP "+str(e.code)
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            time.sleep(min(6,2**i))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(6,2**i))
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
    return sorted(vals)
def fetch_viaf(vid):
    q=urllib.parse.quote(vid)
    urls=[
      f"https://viaf.org/viaf/{q}?httpAccept=application/json",
      f"https://viaf.org/viaf/{q}?format=json",
      f"https://viaf.org/viaf/{q}/viaf.json",
    ]
    errs=[];last=""
    for url in urls:
        st,obj,final,err=get_json(url)
        last=st
        if isinstance(obj,dict):
            return vid,{"ok":1,"status":st,"url":final,"dates":viaf_dates(obj),"sources":viaf_sources(obj),"error":""}
        errs.append(f"{st}:{err}")
    return vid,{"ok":0,"status":last,"url":urls[0],"dates":[],"sources":[],"error":" || ".join(errs)}

ap=argparse.ArgumentParser();ap.add_argument("--shard",type=int,required=True);ap.add_argument("--shards",type=int,required=True);args=ap.parse_args()
rows=read_csv(INPUT)
targets=[]
for r in rows:
    if not present(r.get("final_exact_dob")):continue
    q,b=reliable_qid(r)
    if q:targets.append((r,q,b))
targets=sorted(targets,key=lambda x:x[0].get("profile_url",""))
targets=[x for i,x in enumerate(targets) if i%args.shards==args.shard]
qids=sorted({q for _,q,_ in targets})

ids=defaultdict(set)
for batch in chunks(qids):
    vals=" ".join("wd:"+q for q in batch)
    query=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
SELECT ?person ?viaf WHERE {{ VALUES ?person {{ {vals} }} OPTIONAL {{ ?person wdt:P214 ?viaf . }} }}"""
    for x in sparql(query):
        q=(x.get("person") or "").rsplit("/",1)[-1];v=(x.get("viaf") or "").strip()
        if q and v:ids[q].add(v)

all_vid=sorted({v for q in qids for v in ids[q]})
fetched={}
with ThreadPoolExecutor(max_workers=16) as ex:
    fs={ex.submit(fetch_viaf,v):v for v in all_vid}
    for f in as_completed(fs):
        v=fs[f]
        try:vv,z=f.result();fetched[vv]=z
        except Exception as e:fetched[v]={"ok":0,"status":"","url":"","dates":[],"sources":[],"error":repr(e)}

fields=["profile_url","name","deceased","election_year","dob_status","v16_exact_dob","qid","identity_basis","viaf_ids","viaf_exact_dates","viaf_candidate_dob","viaf_unique_exact","viaf_match","viaf_conflict","viaf_source_codes","viaf_source_sids","fetch_errors"]
out=[]
for r,q,b in targets:
    vids=sorted(ids[q]);dates=set();sids=set();errs=[]
    for v in vids:
        z=fetched.get(v,{})
        dates.update(z.get("dates",[]));sids.update(z.get("sources",[]))
        if z.get("error"):errs.append(v+":"+z["error"])
    dates=sorted(dates);cand=dates[0] if len(dates)==1 else ""
    codes=sorted({s.split("|",1)[0] for s in sids if "|" in s})
    master=r.get("final_exact_dob","")
    out.append({
      "profile_url":r.get("profile_url",""),"name":r.get("name",""),"deceased":r.get("deceased",""),
      "election_year":r.get("election_year",""),"dob_status":r.get("dob_status",""),"v16_exact_dob":master,
      "qid":q,"identity_basis":b,"viaf_ids":"|".join(vids),"viaf_exact_dates":"|".join(dates),
      "viaf_candidate_dob":cand,"viaf_unique_exact":int(bool(cand)),
      "viaf_match":int(bool(cand) and cand==master),"viaf_conflict":int(bool(cand) and cand!=master),
      "viaf_source_codes":"|".join(codes),"viaf_source_sids":"||".join(sorted(sids)),
      "fetch_errors":" || ".join(errs)
    })
path=BASE/f"nas_viaf_full_validation_shard{args.shard}.csv";write_csv(path,out,fields)
summary={
 "dataset":"NAS VIAF full exact-DOB validation shard v1","shard":args.shard,"shards":args.shards,
 "exact_dob_reliable_qid_targets":len(targets),"rows_with_viaf_id":sum(bool(x["viaf_ids"]) for x in out),
 "rows_with_unique_exact_viaf_date":sum(int(x["viaf_unique_exact"]) for x in out),
 "matches":sum(int(x["viaf_match"]) for x in out),"conflicts":sum(int(x["viaf_conflict"]) for x in out),
 "deceased_targets":sum(x["deceased"]=="Y" for x in out),"bazi_variables_computed":0
}
(BASE/f"summary_nas_viaf_full_validation_shard{args.shard}.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
