#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,time,urllib.parse,urllib.request
from collections import defaultdict
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v16.csv"
OUT=BASE/"nas_extended_authority_id_coverage_v1.csv"
SUMMARY=BASE/"summary_nas_extended_authority_id_coverage_v1.json"
QLEVER="https://qlever.dev/api/wikidata"
UA="bazi-public-figure-study/1.0 (NAS extended authority ID coverage; no BaZi computation)"

PROPS={
 "P214":"viaf_id",
 "P213":"isni_id",
 "P349":"ndl_id",
 "P269":"idref_id",
 "P950":"bne_id",
 "P1006":"nta_id",
 "P691":"nkc_id",
 "P244":"loc_id",
 "P227":"gnd_id",
 "P268":"bnf_id",
 "P396":"sbn_id",
 "P7029":"nlk_id",
}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
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
def query(q,retries=5):
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

rows=read_csv(INPUT)
unresolved=[r for r in rows if r.get("deceased")!="Y" and not str(r.get("final_exact_dob") or "").strip()]
targets=[]
for r in unresolved:
    q,b=reliable_qid(r)
    if q:targets.append((r,q,b))
qids=sorted({q for _,q,_ in targets})

vals=defaultdict(lambda:defaultdict(set))
opt="\n".join(f'OPTIONAL {{ ?person wdt:{p} ?{name} . }}' for p,name in PROPS.items())
select=" ".join("?"+name for name in PROPS.values())
for batch in chunks(qids):
    entities=" ".join("wd:"+q for q in batch)
    sparql=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
SELECT ?person {select} WHERE {{
 VALUES ?person {{ {entities} }}
 {opt}
}}"""
    for x in query(sparql):
        q=(x.get("person") or "").rsplit("/",1)[-1]
        if not q:continue
        for name in PROPS.values():
            v=(x.get(name) or "").strip()
            if v:vals[q][name].add(v)

fields=["profile_url","name","election_year","affiliation","qid","identity_basis"]+list(PROPS.values())+["new_authority_family_count"]
out=[]
for r,q,b in targets:
    row={"profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),"affiliation":r.get("affiliation",""),"qid":q,"identity_basis":b}
    new_count=0
    for name in PROPS.values():
        row[name]="|".join(sorted(vals[q][name]))
        if vals[q][name] and name not in {"loc_id","gnd_id","bnf_id"}:new_count+=1
    row["new_authority_family_count"]=new_count
    out.append(row)
write_csv(OUT,out,fields)

coverage={}
for name in PROPS.values():
    coverage[name]=sum(bool(vals[q][name]) for q in qids)
summary={
 "dataset":"NAS extended authority ID coverage diagnostic v1",
 "input":INPUT.name,
 "unresolved_living_rows":len(unresolved),
 "unresolved_rows_with_reliable_qid":len(targets),
 "unique_reliable_qids":len(qids),
 "coverage_by_authority_id":coverage,
 "rows_with_any_new_authority_family":sum(any(vals[q][n] for n in PROPS.values() if n not in {"loc_id","gnd_id","bnf_id"}) for q in qids),
 "rows_with_two_or_more_new_authority_families":sum(sum(bool(vals[q][n]) for n in PROPS.values() if n not in {"loc_id","gnd_id","bnf_id"})>=2 for q in qids),
 "already_swept_authorities":["loc_id","gnd_id","bnf_id"],
 "bazi_variables_computed":0,
 "decision_note":"Coverage diagnostic only. No DOB acquisition or BaZi computation. Use counts to prioritize genuinely new high-authority source families before any further systematic sweep."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
