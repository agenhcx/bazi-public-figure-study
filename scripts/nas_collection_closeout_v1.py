#!/usr/bin/env python3
from __future__ import annotations
import csv, json
from collections import defaultdict
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v16.csv"
DECADE=BASE/"nas_v16_missingness_by_election_decade.csv"
SECTION=BASE/"nas_v16_missingness_by_section.csv"
STATUS=BASE/"nas_v16_missingness_by_living_status.csv"
SUMMARY=BASE/"summary_nas_collection_closeout_v1.json"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    fields=fields or (list(rows[0].keys()) if rows else [])
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def as_int(v):
    try:return int(float(str(v)))
    except:return None

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")

for r in rows:
    r["_exact"]=int(present(r.get("final_exact_dob")))
    r["_living"]=int(r.get("deceased")!="Y")
    ey=as_int(r.get("election_year"))
    r["_decade"]=(ey//10)*10 if ey is not None else "unknown"

def aggregate(key):
    groups=defaultdict(list)
    for r in rows:groups[r[key]].append(r)
    out=[]
    for k,rr in sorted(groups.items(),key=lambda kv:str(kv[0])):
        n=len(rr);exact=sum(x["_exact"] for x in rr)
        living=[x for x in rr if x["_living"]]
        deceased=[x for x in rr if not x["_living"]]
        le=sum(x["_exact"] for x in living);de=sum(x["_exact"] for x in deceased)
        out.append({
          key.lstrip("_"):k,
          "n":n,
          "exact_dob_rows":exact,
          "exact_dob_coverage":round(exact/n,6) if n else "",
          "unresolved_rows":n-exact,
          "living_rows":len(living),
          "living_exact_dob_rows":le,
          "living_exact_dob_coverage":round(le/len(living),6) if living else "",
          "living_unresolved_rows":len(living)-le,
          "deceased_rows":len(deceased),
          "deceased_exact_dob_rows":de,
          "deceased_exact_dob_coverage":round(de/len(deceased),6) if deceased else "",
        })
    return out

dec=aggregate("_decade")
sec=aggregate("primary_section")
status=[
 {"living_status":"living","n":sum(r["_living"] for r in rows),
  "exact_dob_rows":sum(r["_living"] and r["_exact"] for r in rows)},
 {"living_status":"deceased","n":sum(not r["_living"] for r in rows),
  "exact_dob_rows":sum((not r["_living"]) and r["_exact"] for r in rows)}
]
for x in status:
    x["exact_dob_coverage"]=round(x["exact_dob_rows"]/x["n"],6) if x["n"] else ""
    x["unresolved_rows"]=x["n"]-x["exact_dob_rows"]

write_csv(DECADE,dec)
write_csv(SECTION,sec)
write_csv(STATUS,status)

living=[r for r in rows if r["_living"]]
recent=[r for r in living if isinstance(r["_decade"],int) and r["_decade"]>=2000]
pre2000=[r for r in living if isinstance(r["_decade"],int) and r["_decade"]<2000]
summary={
 "dataset":"NAS science-core exact-DOB collection closeout diagnostic v1",
 "parent":INPUT.name,
 "science_core_rows":len(rows),
 "exact_dob_rows":sum(r["_exact"] for r in rows),
 "exact_dob_coverage":round(sum(r["_exact"] for r in rows)/len(rows),6),
 "unresolved_rows":sum(1-r["_exact"] for r in rows),
 "deceased_rows":sum(not r["_living"] for r in rows),
 "deceased_exact_dob_rows":sum((not r["_living"]) and r["_exact"] for r in rows),
 "living_rows":len(living),
 "living_exact_dob_rows":sum(r["_exact"] for r in living),
 "living_exact_dob_coverage":round(sum(r["_exact"] for r in living)/len(living),6),
 "living_unresolved_rows":sum(1-r["_exact"] for r in living),
 "living_pre2000_election_rows":len(pre2000),
 "living_pre2000_exact_rows":sum(r["_exact"] for r in pre2000),
 "living_pre2000_exact_coverage":round(sum(r["_exact"] for r in pre2000)/len(pre2000),6) if pre2000 else None,
 "living_2000plus_election_rows":len(recent),
 "living_2000plus_exact_rows":sum(r["_exact"] for r in recent),
 "living_2000plus_exact_coverage":round(sum(r["_exact"] for r in recent)/len(recent),6) if recent else None,
 "systematic_source_sweeps_completed":[
   "NAS official cards / memorial records",
   "Wikidata exact and global-QID crosswalks",
   "DBpedia and Wikipedia diagnostics",
   "GND and Library of Congress authority records",
   "BnF structured authority records",
   "LOC MARC 046/670 hidden-DOB parsing",
   "Wikidata P569 reference URLs",
   "Wikidata P856 official homepages and same-site CV/bio links"
 ],
 "collection_stop_rule":"Freeze systematic exact-DOB acquisition at v16 unless a new high-authority source or a small manually audited correction set is identified. Treat missingness as a modeled selection mechanism in downstream analysis rather than filling with weak sources.",
 "analysis_recommendation":"Report deceased and living coverage separately; stratify or adjust by election era and section before comparing BaZi distributions. Do not impute exact DOBs from year-only records.",
 "bazi_variables_computed":0
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
