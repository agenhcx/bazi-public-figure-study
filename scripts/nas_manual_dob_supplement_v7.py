#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, hashlib, json
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v13.csv"
PATCH=Path("data/nas_science_core_dob_manual_supplement_v7.csv")
OUT=BASE/"nas_science_core_dob_crosswalk_v14.csv"
LOG=BASE/"nas_science_core_dob_manual_supplement_log_v7.csv"
SUMMARY=BASE/"summary_v14.json"

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
by={r["profile_url"]:r for r in rows}
before=sum(present(r.get("final_exact_dob")) for r in rows)
before_living=sum(present(r.get("final_exact_dob")) for r in rows if r.get("deceased")!="Y")
before_dead=sum(present(r.get("final_exact_dob")) for r in rows if r.get("deceased")=="Y")
log=[]
for p in patches:
    u=p["profile_url"]
    if u not in by:raise RuntimeError(f"Missing target {u}")
    r=by[u]
    if r.get("name","")!=p["name"]:raise RuntimeError(f"Name mismatch for {u}")
    old=(r.get("final_exact_dob") or "").strip()
    exp=(p.get("expected_old_final_exact_dob") or "").strip()
    if old!=exp:raise RuntimeError(f"Old DOB mismatch for {p['name']}: got {old!r}, expected {exp!r}")
    if old:raise RuntimeError(f"v7 may only fill blank DOBs: {p['name']}")
    if r.get("deceased")=="Y":raise RuntimeError(f"v7 expected living row: {p['name']}")
    new=valid(p["new_final_exact_dob"].strip())
    r["final_exact_dob"]=new
    r["dob_status"]="exact_manual_supplement_v7_ambiguous_qid_provenance"
    for k in ("review_status","primary_source_url","secondary_source_url","note"):
        r["manual_supplement_v7_"+k]=p.get(k,"")
    log.append(dict(p))
for r in rows:
    for k in ("review_status","primary_source_url","secondary_source_url","note"):
        r.setdefault("manual_supplement_v7_"+k,"")
after=sum(present(r.get("final_exact_dob")) for r in rows)
living=[r for r in rows if r.get("deceased")!="Y"];dead=[r for r in rows if r.get("deceased")=="Y"]
living_exact=sum(present(r.get("final_exact_dob")) for r in living)
dead_exact=sum(present(r.get("final_exact_dob")) for r in dead)
unresolved=len(rows)-after
if after!=before+len(patches):raise RuntimeError("Overall delta invariant failed")
if living_exact!=before_living+len(patches):raise RuntimeError("Living delta invariant failed")
if dead_exact!=before_dead or dead_exact!=len(dead):raise RuntimeError("Deceased completeness regressed")
write_csv(OUT,rows);write_csv(LOG,log)
summary={
 "dataset":"NAS science-core exact-DOB crosswalk v14 after audited ambiguous-QID supplement v7",
 "parent":INPUT.name,"science_core_rows":len(rows),"input_exact_dob_rows":before,
 "supplement_rows":len(patches),"final_exact_dob_rows":after,"final_exact_dob_coverage":round(after/len(rows),6),
 "remaining_without_exact_dob":unresolved,"deceased_rows":len(dead),"deceased_final_exact_dob_rows":dead_exact,
 "deceased_final_exact_dob_coverage":round(dead_exact/len(dead),6),"living_rows":len(living),
 "living_final_exact_dob_rows":living_exact,"living_final_exact_dob_coverage":round(living_exact/len(living),6),
 "bazi_variables_computed":0,
 "policy_note":"v7 adds ten living exact DOBs after manual provenance review of affiliation-resolved ambiguous Wikidata identities. Michael E. Goldberg is corrected to 1941-08-10 after rejecting a wrong-person GND link; four other candidates remain held.",
 "files":{OUT.name:sha(OUT),LOG.name:sha(LOG),PATCH.name:sha(PATCH)}
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
