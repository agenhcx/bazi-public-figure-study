#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from collections import defaultdict
from pathlib import Path

BASE=Path("data")
OUT=BASE/"nas_viaf_full_validation_by_status_v1.csv"
CONFLICT=BASE/"nas_viaf_full_validation_conflicts_v1.csv"
SUMMARY=BASE/"summary_nas_viaf_full_validation_v1.json"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

files=sorted(BASE.glob("nas_viaf_full_validation_shard*.csv"))
if not files:raise RuntimeError("No shard CSVs found")
rows=[r for p in files for r in read_csv(p)]
groups=defaultdict(list)
for r in rows:
    if r.get("viaf_unique_exact")!="1":continue
    key=(r.get("dob_status") or "UNKNOWN", "deceased" if r.get("deceased")=="Y" else "living")
    groups[key].append(r)

out=[]
for (status,living),rr in sorted(groups.items()):
    n=len(rr);m=sum(r.get("viaf_match")=="1" for r in rr);c=sum(r.get("viaf_conflict")=="1" for r in rr)
    out.append({"dob_status":status,"living_status":living,"comparable_rows":n,"matches":m,"conflicts":c,"match_rate":round(m/n,6) if n else ""})
write_csv(OUT,out,["dob_status","living_status","comparable_rows","matches","conflicts","match_rate"])

conf=[r for r in rows if r.get("viaf_conflict")=="1"]
write_csv(CONFLICT,conf,list(rows[0].keys()) if rows else [])

high_quality_labels=[
 "exact_nas_card_plus_wikidata_agree",
 "exact_manual_supplement_v5_loc_provenance",
]
hq=[r for r in rows if r.get("viaf_unique_exact")=="1" and r.get("dob_status") in high_quality_labels]
deceased=[r for r in rows if r.get("viaf_unique_exact")=="1" and r.get("deceased")=="Y"]
living=[r for r in rows if r.get("viaf_unique_exact")=="1" and r.get("deceased")!="Y"]
payload={
 "dataset":"NAS VIAF full exact-DOB validation by frozen provenance v1",
 "shard_files":len(files),"all_exact_reliable_qid_rows":len(rows),
 "rows_with_viaf_id":sum(bool(r.get("viaf_ids")) for r in rows),
 "rows_with_unique_exact_viaf_date":sum(r.get("viaf_unique_exact")=="1" for r in rows),
 "matches":sum(r.get("viaf_match")=="1" for r in rows),
 "conflicts":len(conf),
 "overall_match_rate":round(sum(r.get("viaf_match")=="1" for r in rows)/sum(r.get("viaf_unique_exact")=="1" for r in rows),6) if sum(r.get("viaf_unique_exact")=="1" for r in rows) else None,
 "deceased_comparable":len(deceased),"deceased_matches":sum(r.get("viaf_match")=="1" for r in deceased),"deceased_conflicts":sum(r.get("viaf_conflict")=="1" for r in deceased),
 "deceased_match_rate":round(sum(r.get("viaf_match")=="1" for r in deceased)/len(deceased),6) if deceased else None,
 "living_comparable":len(living),"living_matches":sum(r.get("viaf_match")=="1" for r in living),"living_conflicts":sum(r.get("viaf_conflict")=="1" for r in living),
 "living_match_rate":round(sum(r.get("viaf_match")=="1" for r in living)/len(living),6) if living else None,
 "preselected_high_quality_status_comparable":len(hq),
 "preselected_high_quality_status_matches":sum(r.get("viaf_match")=="1" for r in hq),
 "preselected_high_quality_status_conflicts":sum(r.get("viaf_conflict")=="1" for r in hq),
 "status_table":out,
 "conflict_names":[{"name":r.get("name"),"dob_status":r.get("dob_status"),"deceased":r.get("deceased"),"v16":r.get("v16_exact_dob"),"viaf":r.get("viaf_candidate_dob")} for r in conf],
 "bazi_variables_computed":0,
 "decision_note":"Validation only. No source class is accepted based solely on overall agreement. Deceased complete-coverage rows and provenance-specific strata are reported separately to identify a defensible gold-standard subset."
}
SUMMARY.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False,indent=2))
