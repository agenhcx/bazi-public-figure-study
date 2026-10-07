#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE = Path("data/nas_science_core_dob_crosswalk")
INPUT = BASE / "nas_science_core_dob_crosswalk.csv"
WIKIDATA = Path("data/nas_wikidata_dob_pilot/nas_wikidata_dob_collapsed.csv")
DBPEDIA = "https://dbpedia.org/sparql"

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def chunks(seq,n=70):
    for i in range(0,len(seq),n):
        yield seq[i:i+n]

def valid_exact_date(s: str) -> str:
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",s or "")
    if not m: return ""
    y,mo,d=map(int,m.groups())
    try:
        dt.date(y,mo,d)
    except Exception:
        return ""
    return f"{y:04d}-{mo:02d}-{d:02d}"

def parse_years(s: str):
    return sorted(set(int(x) for x in re.findall(r"([12]\d{3})-",s or "")))

def run_dbpedia(query: str):
    body=urllib.parse.urlencode({"query":query,"format":"text/csv"}).encode("utf-8")
    req=urllib.request.Request(
        DBPEDIA,data=body,method="POST",
        headers={
            "User-Agent":"bazi-public-figure-study/1.0 NAS DOB supplement",
            "Content-Type":"application/x-www-form-urlencoded",
            "Accept":"text/csv",
        },
    )
    with urllib.request.urlopen(req,timeout=180) as r:
        raw=r.read().decode("utf-8-sig")
    return list(csv.DictReader(raw.splitlines()))

def dbpedia_dobs(qids):
    out=defaultdict(set)
    for batch in chunks(sorted(set(qids))):
        vals=" ".join(f"<http://www.wikidata.org/entity/{q}>" for q in batch if re.fullmatch(r"Q\d+",q))
        if not vals: continue
        query=f"""
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT DISTINCT ?wd ?birthDate WHERE {{
  VALUES ?wd {{ {vals} }}
  ?resource owl:sameAs ?wd ;
            dbo:birthDate ?birthDate .
}}
"""
        for r in run_dbpedia(query):
            q=(r.get("wd") or "").rsplit("/",1)[-1]
            d=valid_exact_date(r.get("birthDate") or "")
            if q and d: out[q].add(d)
    return out

rows=read_csv(INPUT)
wdrows=read_csv(WIKIDATA)
wd_by_qid={r["qid"]:r for r in wdrows if r.get("qid")}

candidate_qids=set()
identity_qid={}
identity_basis={}

for r in rows:
    if r.get("final_exact_dob"):
        continue
    if r.get("dob_status") in {"wikidata_implausible_election_age_review","wikidata_exact_conflict_review"}:
        continue

    q=(r.get("wikidata_qid") or "").strip()
    method=(r.get("wikidata_match_method") or "").strip()
    if q and method in {"strict_unique_name","relaxed_unique_name"}:
        identity_qid[r["profile_url"]]=q
        identity_basis[r["profile_url"]]=method
        candidate_qids.add(q)
        continue

    gq=(r.get("global_candidate_qid") or "").strip()
    try: gcount=int(float(r.get("global_exact_name_match_count") or 0))
    except Exception: gcount=0
    try: gaff=int(float(r.get("global_affiliation_match") or 0))
    except Exception: gaff=0
    token_count=len(re.findall(r"[A-Za-z0-9]+",r.get("name") or ""))
    if gq and gcount==1 and (token_count>=3 or gaff==1):
        identity_qid[r["profile_url"]]=gq
        identity_basis[r["profile_url"]]="global_exact_name_identity"
        candidate_qids.add(gq)

dbp=dbpedia_dobs(candidate_qids)

out=[]
for r0 in rows:
    r=dict(r0)
    q=identity_qid.get(r["profile_url"],"")
    vals=sorted(dbp.get(q,set())) if q else []
    dbp_conflict=len(vals)>1
    dbp_dob=vals[0] if len(vals)==1 else ""

    known_wd_years=[]
    if q and q in wd_by_qid:
        wr=wd_by_qid[q]
        known_wd_years=parse_years(wr.get("year_precision_values") or "")
        known_wd_years+=parse_years(wr.get("month_precision_values") or "")
        known_wd_years=sorted(set(known_wd_years))

    year_conflict=bool(dbp_dob and known_wd_years and int(dbp_dob[:4]) not in known_wd_years)
    try: age=int(r.get("election_year") or 0)-int(dbp_dob[:4]) if dbp_dob else None
    except Exception: age=None
    age_ok=(age is None or 25<=age<=100)

    used=0
    if (not r.get("final_exact_dob")) and dbp_dob and not dbp_conflict and not year_conflict and age_ok:
        r["final_exact_dob"]=dbp_dob
        r["dob_status"]="exact_dbpedia"
        used=1

    r["dbpedia_qid"]=q
    r["dbpedia_identity_basis"]=identity_basis.get(r["profile_url"],"")
    r["dbpedia_exact_values"]="|".join(vals)
    r["dbpedia_exact_conflict"]=int(dbp_conflict)
    r["dbpedia_wikidata_year_conflict"]=int(year_conflict)
    r["dbpedia_age_at_election"]=age if age is not None else ""
    r["dbpedia_used"]=used
    out.append(r)

fields=list(out[0].keys())
write_csv(BASE/"nas_science_core_dob_crosswalk_v6.csv",out,fields)

review=[
    r for r in out
    if not r.get("final_exact_dob")
    or int(float(r.get("source_conflict") or 0))
    or int(float(r.get("wikidata_exact_conflict") or 0))
    or int(float(r.get("dbpedia_exact_conflict") or 0))
    or int(float(r.get("dbpedia_wikidata_year_conflict") or 0))
]
write_csv(BASE/"nas_science_core_dob_review_v6.csv",review,fields)

living=[r for r in out if r.get("deceased")!="Y"]
dead=[r for r in out if r.get("deceased")=="Y"]
summary={
    "source":"DBpedia dbo:birthDate via Wikidata owl:sameAs",
    "endpoint":DBPEDIA,
    "input_rows":len(out),
    "candidate_qids_queried":len(candidate_qids),
    "qids_with_any_exact_dbpedia_birthdate":sum(bool(v) for v in dbp.values()),
    "dbpedia_rows_used":sum(int(r["dbpedia_used"]) for r in out),
    "dbpedia_multiple_exact_date_conflicts":sum(int(r["dbpedia_exact_conflict"]) for r in out),
    "dbpedia_vs_wikidata_birthyear_conflicts":sum(int(r["dbpedia_wikidata_year_conflict"]) for r in out),
    "final_exact_dob_rows":sum(bool(r.get("final_exact_dob")) for r in out),
    "final_exact_dob_coverage":round(sum(bool(r.get("final_exact_dob")) for r in out)/len(out),6),
    "deceased_final_exact_dob_rows":sum(bool(r.get("final_exact_dob")) for r in dead),
    "deceased_final_exact_dob_coverage":round(sum(bool(r.get("final_exact_dob")) for r in dead)/len(dead),6),
    "living_final_exact_dob_rows":sum(bool(r.get("final_exact_dob")) for r in living),
    "living_final_exact_dob_coverage":round(sum(bool(r.get("final_exact_dob")) for r in living)/len(living),6),
    "remaining_without_exact_dob":sum(not bool(r.get("final_exact_dob")) for r in out),
    "review_rows":len(review),
    "bazi_variables_computed":0,
    "acceptance_rule":"unique exact DBpedia date; reliable pre-existing identity linkage; election age 25-100; if Wikidata has year/month precision, DBpedia year must agree",
}
(BASE/"summary_v6.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(summary,indent=2,ensure_ascii=False))
