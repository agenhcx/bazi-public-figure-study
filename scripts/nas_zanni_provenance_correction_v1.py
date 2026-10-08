#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v15.csv"
PATCH=Path("data/nas_science_core_dob_provenance_correction_v1.csv")
OUT=BASE/"nas_science_core_dob_crosswalk_v16.csv"
LOG=BASE/"nas_science_core_dob_provenance_correction_log_v1.csv"
SUMMARY=BASE/"summary_v16.json"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    fields=fields or (list(rows[0].keys()) if rows else [])
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

rows=read_csv(INPUT);patches=read_csv(PATCH)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
by={r["profile_url"]:r for r in rows}
before=sum(present(r.get("final_exact_dob")) for r in rows)
log=[]
for p in patches:
    u=p["profile_url"]
    if u not in by:raise RuntimeError(f"Missing target {u}")
    r=by[u]
    if r.get("name","")!=p["name"]:raise RuntimeError(f"Name mismatch for {u}")
    exp=p["expected_final_exact_dob"].strip()
    got=(r.get("final_exact_dob") or "").strip()
    if got!=exp:raise RuntimeError(f"DOB mismatch for {p['name']}: got {got!r}, expected {exp!r}")
    r["dob_status"]="exact_provenance_upgraded_v1_official_cv"
    for k in ("review_status","primary_source_url","secondary_source_url","note"):
        r["provenance_correction_v1_"+k]=p.get(k,"")
    log.append(dict(p))
for r in rows:
    for k in ("review_status","primary_source_url","secondary_source_url","note"):
        r.setdefault("provenance_correction_v1_"+k,"")
after=sum(present(r.get("final_exact_dob")) for r in rows)
if after!=before:raise RuntimeError("Provenance-only correction changed exact-DOB count")
living=[r for r in rows if r.get("deceased")!="Y"];dead=[r for r in rows if r.get("deceased")=="Y"]
living_exact=sum(present(r.get("final_exact_dob")) for r in living)
dead_exact=sum(present(r.get("final_exact_dob")) for r in dead)
write_csv(OUT,rows);write_csv(LOG,log)
summary={
 "dataset":"NAS science-core exact-DOB crosswalk v16 after provenance correction v1",
 "parent":INPUT.name,"science_core_rows":len(rows),"provenance_correction_rows":len(patches),
 "final_exact_dob_rows":after,"final_exact_dob_coverage":round(after/len(rows),6),
 "remaining_without_exact_dob":len(rows)-after,
 "deceased_rows":len(dead),"deceased_final_exact_dob_rows":dead_exact,
 "living_rows":len(living),"living_final_exact_dob_rows":living_exact,
 "bazi_variables_computed":0,
 "policy_note":"Provenance-only update. Martin T. Zanni remains 1972-02-28, now supported primarily by a University of Wisconsin-Madison-hosted CV explicitly stating the date of birth; no DOB values or cohort counts changed.",
 "files":{OUT.name:sha(OUT),LOG.name:sha(LOG),PATCH.name:sha(PATCH)}
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
