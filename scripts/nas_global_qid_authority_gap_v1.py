#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v12.csv"
OUT=BASE/"nas_global_qid_authority_gap_v1.csv"
CAND=BASE/"nas_global_qid_authority_gap_candidates_v1.csv"
SUMMARY=BASE/"summary_global_qid_authority_gap_v1.json"
QLEVER="https://qlever.dev/api/wikidata"
UA="bazi-public-figure-study/1.0 (global-QID authority gap diagnostic; no BaZi computation)"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    if fields is None:fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v): return str(v or "").strip() not in ("","nan","None")
def as_int(v,d=0):
    try:return int(float(str(v)))
    except:return d
def norm_name(s):return " ".join(re.sub(r"[^a-z0-9]+"," ",str(s or "").lower()).split())
def qlever(query,retries=5):
    body=urllib.parse.urlencode({"query":query,"action":"tsv_export"}).encode()
    last=None
    for i in range(retries):
        req=urllib.request.Request(QLEVER,data=body,method="POST",headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"text/tab-separated-values"})
        try:
            with urllib.request.urlopen(req,timeout=300) as r:raw=r.read().decode("utf-8-sig")
            break
        except Exception as e:
            last=e
            if i+1>=retries:raise
            time.sleep(min(20,2**i))
    rr=list(csv.reader(raw.splitlines(),delimiter="	"))
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
def chunks(xs,n=150):
    for i in range(0,len(xs),n):yield xs[i:i+n]
def authority_ids(qids):
    out=defaultdict(lambda:{"gnd":set(),"loc":set(),"dob":[]})
    for batch in chunks(sorted(set(qids))):
        vals=" ".join("wd:"+q for q in batch if re.fullmatch(r"Q\d+",q))
        query=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
PREFIX p:<http://www.wikidata.org/prop/>
PREFIX psv:<http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase:<http://wikiba.se/ontology#>
SELECT ?person ?gnd ?loc ?dob ?precision WHERE {{
 VALUES ?person {{ {vals} }}
 OPTIONAL {{ ?person wdt:P227 ?gnd . }}
 OPTIONAL {{ ?person wdt:P244 ?loc . }}
 OPTIONAL {{ ?person p:P569 ?st . ?st psv:P569 ?dv . ?dv wikibase:timeValue ?dob ; wikibase:timePrecision ?precision . }}
}}"""
        for r in qlever(query):
            q=r.get("person","").rsplit("/",1)[-1]
            if not q:continue
            if r.get("gnd"):out[q]["gnd"].add(r["gnd"])
            if r.get("loc"):out[q]["loc"].add(r["loc"])
            if r.get("dob") and r.get("precision"):out[q]["dob"].append((r["dob"],r["precision"]))
    return out
def http_json(url,retries=4):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=90) as r:return 1,json.loads(r.read().decode("utf-8")),""
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(10,2**i))
    return 0,None,repr(last)
def exact_date(s):
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",str(s or ""))
    return "-".join(m.groups()) if m else ""
def gnd_dates(obj):
    vals=set()
    if not isinstance(obj,dict):return []
    raw=obj.get("dateOfBirth",[])
    if not isinstance(raw,list):raw=[raw]
    for x in raw:
        if isinstance(x,dict):
            for k in ("@value","value","label"):
                d=exact_date(x.get(k,""))
                if d:vals.add(d)
        else:
            d=exact_date(x)
            if d:vals.add(d)
    return sorted(vals)
def walk(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if "birthdate" in str(k).lower():vals.append(v)
            vals.extend(walk(v))
    elif isinstance(obj,list):
        for x in obj:vals.extend(walk(x))
    return vals
def strings(obj):
    out=[]
    if isinstance(obj,str):out.append(obj)
    elif isinstance(obj,dict):
        for v in obj.values():out.extend(strings(v))
    elif isinstance(obj,list):
        for x in obj:out.extend(strings(x))
    return out
def loc_dates(obj):
    vals=set()
    for x in walk(obj):
        for s in strings(x):
            d=exact_date(s)
            if d:vals.add(d)
    return sorted(vals)
def fetch_one(kind,ident):
    if kind=="gnd":
        ok,obj,err=http_json(f"https://lobid.org/gnd/{urllib.parse.quote(ident)}.json")
        return gnd_dates(obj) if ok else [],ok,err
    ok,obj,err=http_json(f"https://id.loc.gov/authorities/names/{urllib.parse.quote(ident)}.json")
    return loc_dates(obj) if ok else [],ok,err

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
targets=[]
for r in rows:
    if present(r.get("final_exact_dob")):continue
    if present(r.get("wikidata_qid")):continue
    q=(r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+",q):continue
    if as_int(r.get("global_exact_name_match_count"))!=1:continue
    token_count=len(norm_name(r.get("name","")).split())
    aff=as_int(r.get("global_affiliation_match"))==1
    if token_count>=3 or aff:
        targets.append(r)

ids=authority_ids([r["global_candidate_qid"] for r in targets])
all_gnd=sorted({x for r in targets for x in ids[r["global_candidate_qid"]]["gnd"]})
all_loc=sorted({x for r in targets for x in ids[r["global_candidate_qid"]]["loc"]})
fetched={}
with ThreadPoolExecutor(max_workers=6) as ex:
    fut={}
    for x in all_gnd:fut[ex.submit(fetch_one,"gnd",x)]=("gnd",x)
    for x in all_loc:fut[ex.submit(fetch_one,"loc",x)]=("loc",x)
    for f in as_completed(fut):
        k=fut[f]
        try:fetched[k]=f.result()
        except Exception as e:fetched[k]=([],0,repr(e))

out=[]
for r in targets:
    q=r["global_candidate_qid"]; meta=ids[q]
    wd_exact=sorted({exact_date(d) for d,p in meta["dob"] if str(p)=="11" and exact_date(d)})
    g=set();l=set();gok=lok=0
    for x in meta["gnd"]:
        ds,ok,_=fetched.get(("gnd",x),([],0,""));g.update(ds);gok+=ok
    for x in meta["loc"]:
        ds,ok,_=fetched.get(("loc",x),([],0,""));l.update(ds);lok+=ok
    g=sorted(g);l=sorted(l)
    cand="";basis="";conflict=0
    if len(wd_exact)==1:cand=wd_exact[0];basis="wikidata_exact_now"
    if len(g)==1 and len(l)==1:
        if g[0]==l[0]:
            if cand and cand!=g[0]:conflict=1
            elif not cand:cand=g[0];basis="gnd_plus_loc_agree"
        else:conflict=1
    elif len(g)==1 and not l:
        if cand and cand!=g[0]:conflict=1
        elif not cand:cand=g[0];basis="gnd_unique"
    elif len(l)==1 and not g:
        if cand and cand!=l[0]:conflict=1
        elif not cand:cand=l[0];basis="loc_unique"
    elif (len(g)>1 or len(l)>1):conflict=1
    try:age=int(r.get("election_year") or 0)-int(cand[:4]) if cand else None
    except:age=None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    review=int(bool(cand) and not conflict and ageok==1)
    out.append({
      "profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"global_candidate_qid":q,
      "identity_rule":"unique exact human name + (3plus name tokens or affiliation corroboration)",
      "name_token_count":len(norm_name(r.get("name","")).split()),
      "global_affiliation_match":r.get("global_affiliation_match",""),
      "gnd_ids":"|".join(sorted(meta["gnd"])),"loc_ids":"|".join(sorted(meta["loc"])),
      "wikidata_exact_now":"|".join(wd_exact),"gnd_exact_dates":"|".join(g),"loc_exact_dates":"|".join(l),
      "authority_candidate_dob":cand,"candidate_basis":basis,"source_conflict":conflict,
      "age_at_election":age if age is not None else "","age_plausible":ageok,
      "candidate_for_manual_provenance_review":review
    })
write_csv(OUT,out)
cands=[x for x in out if int(x["candidate_for_manual_provenance_review"])==1]
write_csv(CAND,cands,list(out[0].keys()) if out else [])
summary={
 "dataset":"NAS unresolved global-QID authority gap diagnostic v1",
 "input_v12_rows":len(rows),
 "unresolved_rows":sum(not present(r.get("final_exact_dob")) for r in rows),
 "identity_only_global_qid_targets":len(targets),
 "targets_with_gnd_id":sum(bool(ids[r["global_candidate_qid"]]["gnd"]) for r in targets),
 "targets_with_loc_id":sum(bool(ids[r["global_candidate_qid"]]["loc"]) for r in targets),
 "targets_with_wikidata_exact_day_now":sum(bool(x["wikidata_exact_now"]) for x in out),
 "targets_with_any_authority_exact_candidate":sum(bool(x["authority_candidate_dob"]) for x in out),
 "targets_with_source_conflict":sum(int(x["source_conflict"]) for x in out),
 "candidates_for_manual_provenance_review":len(cands),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. This recovers identity-only unique exact-name Wikidata QIDs that were previously left unaccepted solely because Wikidata lacked an exact DOB. No DOB is written automatically."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
