#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re
from collections import defaultdict
from pathlib import Path

ROOT=Path("data")
OUT=ROOT/"nas_viaf_validation_by_v16_status_v1.csv"
CONFLICT=ROOT/"nas_viaf_validation_conflicts_by_status_v1.csv"
SUMMARY=ROOT/"summary_nas_viaf_validation_by_v16_status_v1.json"

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
def present(x):return str(x or "").strip() not in ("","None","nan")

v16=read_csv(locate("nas_science_core_dob_crosswalk_v16.csv"))
viaf=read_csv(locate("nas_viaf_dob_diagnostic_v1.csv"))
master={r["profile_url"]:r for r in v16}
rows=[]
for x in viaf:
    if x.get("cohort")!="validation" or not present(x.get("viaf_candidate_dob")):continue
    r=master.get(x.get("profile_url",""),{})
    if not r:continue
    rows.append((r,x))

groups=defaultdict(list)
for r,x in rows:
    status=(r.get("dob_status") or "UNKNOWN").strip()
    groups[status].append((r,x))

summary_rows=[]
conflicts=[]
for status,rr in sorted(groups.items()):
    n=len(rr);match=sum(x.get("viaf_candidate_dob")==r.get("final_exact_dob") for r,x in rr)
    conflict=n-match
    # expose provenance-bearing nonempty fields without interpreting them
    source_fields=sorted({k for r,x in rr for k,v in r.items() if present(v) and re.search(r"(source|url|authority|manual|supplement|proven|wikidata|loc|gnd|bnf|official)",k,re.I)})
    summary_rows.append({
      "dob_status":status,"viaf_comparable_rows":n,"matches":match,"conflicts":conflict,
      "match_rate":round(match/n,6) if n else "","observed_source_fields":"|".join(source_fields)
    })
    for r,x in rr:
        if x.get("viaf_candidate_dob")==r.get("final_exact_dob"):continue
        conflicts.append({
          "name":r.get("name",""),"profile_url":r.get("profile_url",""),"dob_status":status,
          "v16_exact_dob":r.get("final_exact_dob",""),"viaf_exact_dob":x.get("viaf_candidate_dob",""),
          "wikidata_qid":r.get("wikidata_qid",""),"wikidata_match_method":r.get("wikidata_match_method",""),
          "contributing_authority_codes":x.get("contributing_authority_codes",""),
          "contributing_authority_sids":x.get("contributing_authority_sids","")
        })

write_csv(OUT,summary_rows,["dob_status","viaf_comparable_rows","matches","conflicts","match_rate","observed_source_fields"])
write_csv(CONFLICT,conflicts,["name","profile_url","dob_status","v16_exact_dob","viaf_exact_dob","wikidata_qid","wikidata_match_method","contributing_authority_codes","contributing_authority_sids"])

payload={
 "dataset":"NAS VIAF validation stratified by frozen v16 DOB provenance status v1",
 "viaf_comparable_validation_rows":len(rows),
 "status_groups":summary_rows,
 "conflict_rows":conflicts,
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. The purpose is to avoid treating all frozen-v16 exact DOBs as equally authoritative. Any future acceptance rule should be calibrated preferentially against independently sourced/high-authority v16 strata rather than Wikidata-only exact dates."
}
SUMMARY.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False,indent=2))
