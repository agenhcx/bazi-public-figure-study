#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re
from collections import defaultdict, Counter
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v14.csv"
WD_CANDIDATES=[
    Path("data/nas_wikidata_dob_pilot/nas_wikidata_dob_collapsed.csv"),
    Path("pilot_artifact/nas_wikidata_dob_pilot/nas_wikidata_dob_collapsed.csv"),
]
WD=next((p for p in WD_CANDIDATES if p.exists()),WD_CANDIDATES[0])
OUT=BASE/"nas_v14_missingness_rows.csv"
DECADE=BASE/"nas_v14_missingness_by_election_decade.csv"
SECTION=BASE/"nas_v14_missingness_by_section.csv"
SUMMARY=BASE/"summary_v14_missingness.json"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    fields=fields or (list(rows[0].keys()) if rows else [])
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def years(s):return set(re.findall(r"([12]\d{3})-\d{2}-\d{2}",str(s or "")))
def as_int(v,d=0):
    try:return int(float(str(v)))
    except:return d
def reliable_qid(r):
    q=(r.get("wikidata_qid") or "").strip()
    if re.fullmatch(r"Q\d+",q):return q,"wikidata_qid"
    q=(r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+",q):return "",""
    if as_int(r.get("global_exact_name_match_count"))!=1:return "",""
    toks=len(re.sub(r"[^a-z0-9]+"," ",r.get("name","").lower()).split())
    if toks>=3 or as_int(r.get("global_affiliation_match"))==1:return q,"global_unique_identity"
    return "",""

rows=read_csv(INPUT);wdrows=read_csv(WD)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
wd={r.get("qid",""):r for r in wdrows if r.get("qid")}

out=[]
for r in rows:
    exact=(r.get("final_exact_dob") or "").strip()
    q,qbasis=reliable_qid(r)
    birth_year=exact[:4] if re.fullmatch(r"\d{4}-\d{2}-\d{2}",exact) else ""
    year_source="final_exact_dob" if birth_year else ""
    year_conflict=0
    p569_precision=""
    if not birth_year and q:
        wr=wd.get(q,{})
        vals=set()
        for col in ("exact_day_values","month_precision_values","year_precision_values","direct_p569_values"):
            vals|=years(wr.get(col,""))
        if len(vals)==1:
            birth_year=next(iter(vals));year_source="frozen_wikidata_unique_birth_year"
        elif len(vals)>1:year_conflict=1
        p569_precision=wr.get("max_precision") or wr.get("max_birthdate_precision") or ""
    try:ey=int(float(r.get("election_year") or ""))
    except:ey=None
    decade=(ey//10)*10 if ey is not None else ""
    if exact:bucket="exact_dob"
    elif birth_year:bucket="year_known_exact_missing"
    elif q:bucket="reliable_qid_no_birth_year"
    else:bucket="no_reliable_qid"
    out.append({
      "profile_url":r.get("profile_url",""),"name":r.get("name",""),"election_year":r.get("election_year",""),
      "election_decade":decade,"deceased":r.get("deceased",""),"primary_section":r.get("primary_section",""),
      "affiliation":r.get("affiliation",""),"has_exact_dob":int(bool(exact)),"final_exact_dob":exact,
      "reliable_qid":q,"qid_basis":qbasis,"birth_year_known":int(bool(birth_year)),"birth_year":birth_year,
      "birth_year_source":year_source,"birth_year_conflict":year_conflict,"p569_precision":p569_precision,
      "missingness_bucket":bucket
    })
write_csv(OUT,out)

def aggregate(key):
    groups=defaultdict(list)
    for r in out:groups[r[key]].append(r)
    ans=[]
    for k,rr in sorted(groups.items(),key=lambda x:str(x[0])):
        n=len(rr);exact=sum(x["has_exact_dob"] for x in rr);year=sum(x["birth_year_known"] for x in rr)
        living=[x for x in rr if x["deceased"]!="Y"]
        ans.append({
          key:k,"n":n,"exact_dob_rows":exact,"exact_dob_coverage":round(exact/n,6) if n else "",
          "birth_year_known_rows":year,"birth_year_coverage":round(year/n,6) if n else "",
          "living_rows":len(living),"living_exact_dob_rows":sum(x["has_exact_dob"] for x in living),
          "living_exact_dob_coverage":round(sum(x["has_exact_dob"] for x in living)/len(living),6) if living else "",
          "no_reliable_qid_rows":sum(x["missingness_bucket"]=="no_reliable_qid" for x in rr)
        })
    return ans
write_csv(DECADE,aggregate("election_decade"))
write_csv(SECTION,aggregate("primary_section"))

unresolved=[r for r in out if not r["has_exact_dob"]]
counts=Counter(r["missingness_bucket"] for r in out)
ucounts=Counter(r["missingness_bucket"] for r in unresolved)
summary={
 "dataset":"NAS v14 exact-DOB missingness diagnostic",
 "frozen_wikidata_pilot_run_id":37778826271,
 "science_core_rows":len(out),
 "exact_dob_rows":sum(r["has_exact_dob"] for r in out),
 "exact_dob_coverage":round(sum(r["has_exact_dob"] for r in out)/len(out),6),
 "unresolved_rows":len(unresolved),
 "unresolved_with_unique_birth_year_known":sum(r["birth_year_known"] for r in unresolved),
 "unresolved_with_reliable_qid":sum(bool(r["reliable_qid"]) for r in unresolved),
 "unresolved_with_reliable_qid_but_no_unique_birth_year":sum(bool(r["reliable_qid"]) and not r["birth_year_known"] for r in unresolved),
 "unresolved_without_reliable_qid":sum(not bool(r["reliable_qid"]) for r in unresolved),
 "birth_year_conflict_rows":sum(r["birth_year_conflict"] for r in unresolved),
 "missingness_bucket_counts_all":dict(counts),
 "missingness_bucket_counts_unresolved":dict(ucounts),
 "deceased_exact_dob_rows":sum(r["deceased"]=="Y" and r["has_exact_dob"] for r in out),
 "deceased_rows":sum(r["deceased"]=="Y" for r in out),
 "living_exact_dob_rows":sum(r["deceased"]!="Y" and r["has_exact_dob"] for r in out),
 "living_rows":sum(r["deceased"]!="Y" for r in out),
 "bazi_variables_computed":0,
 "decision_note":"Availability/missingness diagnostic only. Birth-year-only data must not be used for BaZi computation. This report is intended to decide whether further exact-DOB collection is worth the marginal effort and to quantify selection bias before analysis."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
