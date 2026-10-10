#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, hashlib, json
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v16.csv"
PATCH=Path("data/nas_science_core_dob_manual_supplement_v9.csv")
OUT=BASE/"nas_science_core_dob_crosswalk_v17.csv"
LOG=BASE/"nas_science_core_dob_manual_supplement_log_v9.csv"
SUMMARY=BASE/"summary_v17.json"
FREEZE=Path("data/nas_science_core_dob_freeze_v17.json")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    fields=fields or (list(rows[0].keys()) if rows else [])
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def valid(v):return dt.date.fromisoformat(v).isoformat()
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

rows=read_csv(INPUT);patches=read_csv(PATCH)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
before=sum(present(r.get("final_exact_dob")) for r in rows)
before_dead=sum(r.get("deceased")=="Y" for r in rows)
before_dead_exact=sum(r.get("deceased")=="Y" and present(r.get("final_exact_dob")) for r in rows)
log=[]
deceased_status_changes=0

for p in patches:
    u=(p.get("profile_url") or "").strip()
    matches=[r for r in rows if (r.get("profile_url") or "").strip()==u] if u else [r for r in rows if r.get("name","").strip()==p["name"].strip()]
    if len(matches)!=1:raise RuntimeError(f"Expected unique target for {p['name']}, got {len(matches)}")
    r=matches[0]
    if r.get("name","").strip()!=p["name"].strip():raise RuntimeError(f"Name mismatch for {u}: {r.get('name')!r} vs {p['name']!r}")
    old=(r.get("final_exact_dob") or "").strip()
    exp=(p.get("expected_old_final_exact_dob") or "").strip()
    if old!=exp:raise RuntimeError(f"Old DOB mismatch for {p['name']}: {old!r} vs expected {exp!r}")
    if old:raise RuntimeError(f"v9 only fills blank DOBs: {p['name']}")
    old_deceased=(r.get("deceased") or "").strip()
    new=valid(p["new_final_exact_dob"].strip())
    requested_deceased=(p.get("new_deceased") or "").strip()
    death_raw=(p.get("death_date") or "").strip()
    death=valid(death_raw) if death_raw else ""
    if requested_deceased and requested_deceased not in {"Y"}:
        raise RuntimeError(f"Unsupported new_deceased value for {p['name']}: {requested_deceased!r}")
    if death and requested_deceased!="Y":
        raise RuntimeError(f"death_date requires new_deceased=Y for {p['name']}")
    r["final_exact_dob"]=new
    if requested_deceased:
        if old_deceased=="Y":raise RuntimeError(f"Target already deceased before v9: {p['name']}")
        r["deceased"]=requested_deceased
        deceased_status_changes+=1
    r["dob_status"]="exact_manual_supplement_v9_official_provenance"
    for k in ("review_status","primary_source_url","secondary_source_url","death_date","note"):
        r["manual_supplement_v9_"+k]=p.get(k,"")
    log.append({
      **p,
      "matched_profile_url":r.get("profile_url",""),
      "old_deceased":old_deceased,
      "new_deceased_applied":r.get("deceased","")
    })

for r in rows:
    for k in ("review_status","primary_source_url","secondary_source_url","death_date","note"):
        r.setdefault("manual_supplement_v9_"+k,"")

after=sum(present(r.get("final_exact_dob")) for r in rows)
dead=[r for r in rows if r.get("deceased")=="Y"]
living=[r for r in rows if r.get("deceased")!="Y"]
dead_exact=sum(present(r.get("final_exact_dob")) for r in dead)
living_exact=sum(present(r.get("final_exact_dob")) for r in living)
if after!=before+len(patches):raise RuntimeError("Exact-DOB delta invariant failed")
if len(dead)!=before_dead+deceased_status_changes:raise RuntimeError("Deceased-status delta invariant failed")
if dead_exact!=before_dead_exact+deceased_status_changes:raise RuntimeError("Deceased exact-DOB delta invariant failed")
if dead_exact!=len(dead):raise RuntimeError("Deceased completeness regressed")

write_csv(OUT,rows);write_csv(LOG,log)
summary={
 "dataset":"NAS science-core exact-DOB crosswalk v17 staged official-provenance amendment",
 "parent":INPUT.name,
 "science_core_rows":len(rows),
 "input_exact_dob_rows":before,
 "supplement_rows":len(patches),
 "deceased_status_changes":deceased_status_changes,
 "final_exact_dob_rows":after,
 "final_exact_dob_coverage":round(after/len(rows),6),
 "remaining_without_exact_dob":len(rows)-after,
 "deceased_rows":len(dead),
 "deceased_final_exact_dob_rows":dead_exact,
 "deceased_final_exact_dob_coverage":round(dead_exact/len(dead),6),
 "living_rows":len(living),
 "living_final_exact_dob_rows":living_exact,
 "living_final_exact_dob_coverage":round(living_exact/len(living),6),
 "bazi_variables_computed":0,
 "policy_note":"Post-v16 amendment contains only high-authority non-library provenance corrections: Jay Quade (official NAS profile plus University of Arizona-hosted CV), Mark Johnston (University of Colorado School of Medicine-hosted CV), and John M. Tranquada (Brookhaven National Laboratory-hosted professional biographical record). Jay Quade also receives an operational deceased-status correction. VIAF/library-chain-only candidates remain excluded pending independent non-library corroboration.",
 "files":{OUT.name:sha(OUT),LOG.name:sha(LOG),PATCH.name:sha(PATCH)}
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
freeze={
 "dataset":"NAS science-core exact-DOB collection freeze candidate v17",
 "parent_v16_sha256":"f577b22bf646b4b5355a133cc265d4d9ccf253f501bac98b6afddce874fc4561",
 "cohort_rows":len(rows),
 "exact_dob_rows":after,
 "exact_dob_coverage":round(after/len(rows),6),
 "unresolved_rows":len(rows)-after,
 "deceased_rows":len(dead),
 "deceased_exact_dob_rows":dead_exact,
 "living_rows":len(living),
 "living_exact_dob_rows":living_exact,
 "v17_csv_sha256":sha(OUT),
 "amendment_log_sha256":sha(LOG),
 "supplement_patch_sha256":sha(PATCH),
 "freeze_status":"staged_not_final",
 "bazi_variables_computed":0,
 "collection_stop_rule":"Retain v16 stop rule. Only independently corroborated high-authority post-freeze corrections may enter v17 before the hierarchy-wide pre-unblinding freeze."
}
FREEZE.write_text(json.dumps(freeze,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(freeze,ensure_ascii=False,indent=2))
