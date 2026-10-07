#!/usr/bin/env python3
# Audited supplement v4: living exact-DOB additions from independent published/official sources.
# Trigger PR CI with v4 wired into the checkpoint workflow.
from __future__ import annotations
import csv, datetime as dt, hashlib, json
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v10.csv"
PATCH=Path("data/nas_science_core_dob_manual_supplement_v4.csv")
OUT_CSV=BASE/"nas_science_core_dob_crosswalk_v11.csv"
LOG=BASE/"nas_science_core_dob_manual_supplement_log_v4.csv"
SUMMARY=BASE/"summary_v11.json"

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

def main():
    rows=read_csv(INPUT); patches=read_csv(PATCH)
    if len(rows)!=3051:raise RuntimeError(f"Expected 3051 science-core rows, got {len(rows)}")
    by_url={r["profile_url"]:r for r in rows}
    if len(by_url)!=len(rows):raise RuntimeError("Duplicate profile_url in v10 input")
    if len({p["profile_url"] for p in patches})!=len(patches):raise RuntimeError("Duplicate profile_url in supplement v4 patch")
    input_exact=sum(present(r.get("final_exact_dob")) for r in rows)
    input_living_exact=sum(present(r.get("final_exact_dob")) for r in rows if r.get("deceased")!="Y")
    input_dead_exact=sum(present(r.get("final_exact_dob")) for r in rows if r.get("deceased")=="Y")
    log=[]
    for p in patches:
        u=p["profile_url"]
        if u not in by_url:raise RuntimeError(f"Patch target not found: {u}")
        r=by_url[u]
        if r.get("name","")!=p["name"]:raise RuntimeError(f"Name mismatch for {u}: {r.get('name')} vs {p['name']}")
        old=(r.get("final_exact_dob") or "").strip()
        expected=(p.get("expected_old_final_exact_dob") or "").strip()
        if old!=expected:raise RuntimeError(f"Old DOB mismatch for {p['name']}: got {old!r}, expected {expected!r}")
        if old:raise RuntimeError(f"Supplement v4 may only add to blank DOBs: {p['name']}")
        if r.get("deceased")=="Y":raise RuntimeError(f"Supplement v4 is reserved for living rows: {p['name']}")
        new=valid_date((p.get("new_final_exact_dob") or "").strip())
        r["final_exact_dob"]=new
        r["dob_status"]="exact_manual_supplement_v4"
        r["manual_supplement_v4_status"]=p.get("review_status","")
        r["manual_supplement_v4_primary_source_url"]=p.get("primary_source_url","")
        r["manual_supplement_v4_secondary_source_url"]=p.get("secondary_source_url","")
        r["manual_supplement_v4_note"]=p.get("note","")
        log.append({"profile_url":u,"name":p["name"],"old_final_exact_dob":old,"new_final_exact_dob":new,
                    "review_status":p.get("review_status",""),"primary_source_url":p.get("primary_source_url",""),
                    "secondary_source_url":p.get("secondary_source_url",""),"note":p.get("note","")})
    for r in rows:
        for k in ("manual_supplement_v4_status","manual_supplement_v4_primary_source_url",
                  "manual_supplement_v4_secondary_source_url","manual_supplement_v4_note"):r.setdefault(k,"")
    exact=sum(present(r.get("final_exact_dob")) for r in rows)
    living=[r for r in rows if r.get("deceased")!="Y"]; dead=[r for r in rows if r.get("deceased")=="Y"]
    living_exact=sum(present(r.get("final_exact_dob")) for r in living)
    dead_exact=sum(present(r.get("final_exact_dob")) for r in dead)
    unresolved=[r for r in rows if not present(r.get("final_exact_dob"))]
    if exact!=input_exact+len(patches):raise RuntimeError("Overall supplement delta invariant failed")
    if living_exact!=input_living_exact+len(patches):raise RuntimeError("Living supplement delta invariant failed")
    if dead_exact!=input_dead_exact:raise RuntimeError("v4 unexpectedly changed deceased exact-DOB count")
    if exact+len(unresolved)!=len(rows):raise RuntimeError("Resolved/unresolved partition invariant failed")
    write_csv(OUT_CSV,rows);write_csv(LOG,log)
    summary={"dataset":"NAS science-core exact-DOB crosswalk v11 after audited living supplement v4",
      "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"parent":INPUT.name,
      "science_core_rows":len(rows),"input_exact_dob_rows":input_exact,"supplement_rows":len(patches),
      "final_exact_dob_rows":exact,"final_exact_dob_coverage":round(exact/len(rows),6),
      "remaining_without_exact_dob":len(unresolved),"deceased_rows":len(dead),
      "deceased_final_exact_dob_rows":dead_exact,"deceased_final_exact_dob_coverage":round(dead_exact/len(dead),6),
      "living_rows":len(living),"living_final_exact_dob_rows":living_exact,
      "living_final_exact_dob_coverage":round(living_exact/len(living),6),"bazi_variables_computed":0,
      "policy_note":"v4 accepts only independently audited exact dates: a published specialist reference for John F. Dewey and the official National Inventors Hall of Fame fact sheet for Harald Hess. Wikipedia alone is not treated as sufficient.",
      "files":{OUT_CSV.name:{"sha256":sha256(OUT_CSV),"bytes":OUT_CSV.stat().st_size},
               LOG.name:{"sha256":sha256(LOG),"bytes":LOG.stat().st_size},
               PATCH.name:{"sha256":sha256(PATCH),"bytes":PATCH.stat().st_size}}}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
