#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, hashlib, json
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v12.csv"
PATCH=Path("data/nas_science_core_dob_manual_supplement_v6.csv")
OUT_CSV=BASE/"nas_science_core_dob_crosswalk_v13.csv"
LOG=BASE/"nas_science_core_dob_manual_supplement_log_v6.csv"
SUMMARY=BASE/"summary_v13.json"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    if fields is None:fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def valid_date(v):
    try:return dt.date.fromisoformat(v).isoformat()
    except Exception as e:raise RuntimeError(f"Invalid exact date {v!r}") from e

rows=read_csv(INPUT); patches=read_csv(PATCH)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
by={r["profile_url"]:r for r in rows}
input_exact=sum(present(r.get("final_exact_dob")) for r in rows)
input_living=sum(present(r.get("final_exact_dob")) for r in rows if r.get("deceased")!="Y")
input_dead=sum(present(r.get("final_exact_dob")) for r in rows if r.get("deceased")=="Y")
log=[]
for p in patches:
    u=p["profile_url"]
    if u not in by:raise RuntimeError(f"Patch target not found: {u}")
    r=by[u]
    if r.get("name","")!=p["name"]:raise RuntimeError(f"Name mismatch: {r.get('name')} vs {p['name']}")
    old=(r.get("final_exact_dob") or "").strip()
    if old!=(p.get("expected_old_final_exact_dob") or "").strip():raise RuntimeError(f"Old DOB mismatch for {p['name']}: {old!r}")
    if old:raise RuntimeError(f"v6 may only fill blank DOBs: {p['name']}")
    if r.get("deceased")=="Y":raise RuntimeError(f"v6 expected living row: {p['name']}")
    new=valid_date(p["new_final_exact_dob"].strip())
    r["final_exact_dob"]=new
    r["dob_status"]="exact_manual_supplement_v6_authority_provenance"
    r["manual_supplement_v6_status"]=p.get("review_status","")
    r["manual_supplement_v6_primary_source_url"]=p.get("primary_source_url","")
    r["manual_supplement_v6_secondary_source_url"]=p.get("secondary_source_url","")
    r["manual_supplement_v6_note"]=p.get("note","")
    log.append({k:p.get(k,"") for k in p.keys()})
for r in rows:
    for k in ("manual_supplement_v6_status","manual_supplement_v6_primary_source_url","manual_supplement_v6_secondary_source_url","manual_supplement_v6_note"):r.setdefault(k,"")
exact=sum(present(r.get("final_exact_dob")) for r in rows)
living=[r for r in rows if r.get("deceased")!="Y"];dead=[r for r in rows if r.get("deceased")=="Y"]
living_exact=sum(present(r.get("final_exact_dob")) for r in living);dead_exact=sum(present(r.get("final_exact_dob")) for r in dead)
unresolved=[r for r in rows if not present(r.get("final_exact_dob"))]
if exact!=input_exact+len(patches):raise RuntimeError("Overall delta invariant failed")
if living_exact!=input_living+len(patches):raise RuntimeError("Living delta invariant failed")
if dead_exact!=input_dead:raise RuntimeError("Deceased count changed")
if dead_exact!=len(dead):raise RuntimeError("Deceased completeness regressed")
write_csv(OUT_CSV,rows);write_csv(LOG,log)
summary={
 "dataset":"NAS science-core exact-DOB crosswalk v13 after audited global-QID authority supplement v6",
 "parent":INPUT.name,"science_core_rows":len(rows),"input_exact_dob_rows":input_exact,
 "supplement_rows":len(patches),"final_exact_dob_rows":exact,"final_exact_dob_coverage":round(exact/len(rows),6),
 "remaining_without_exact_dob":len(unresolved),"deceased_rows":len(dead),"deceased_final_exact_dob_rows":dead_exact,
 "deceased_final_exact_dob_coverage":round(dead_exact/len(dead),6),"living_rows":len(living),
 "living_final_exact_dob_rows":living_exact,"living_final_exact_dob_coverage":round(living_exact/len(living),6),
 "bazi_variables_computed":0,
 "policy_note":"v6 adds six living exact DOBs after individual authority provenance review. Rosen 1965-01-01 is accepted because LOC MARC 670 explicitly cites his CV stating January 1, 1965; it is not a year-only placeholder.",
 "files":{OUT_CSV.name:{"sha256":sha256(OUT_CSV)},LOG.name:{"sha256":sha256(LOG)},PATCH.name:{"sha256":sha256(PATCH)}}
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
