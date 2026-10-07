#!/usr/bin/env python3
from __future__ import annotations
import csv, json, hashlib, datetime as dt
from pathlib import Path

INPUT=Path("data/nas_science_core_dob_crosswalk/nas_science_core_dob_crosswalk_v6.csv")
PATCH=Path("data/nas_science_core_dob_manual_review_v1.csv")
OUT=Path("data/nas_science_core_dob_crosswalk")
OUT_CSV=OUT/"nas_science_core_dob_crosswalk_v7.csv"
LOG=OUT/"nas_science_core_dob_manual_review_log_v1.csv"
SUMMARY=OUT/"summary_v7.json"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    if fields is None:fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def present(v):return str(v or "").strip() not in ("","nan","None")

def main():
    rows=read_csv(INPUT); patches=read_csv(PATCH)
    if len(rows)!=3051:raise RuntimeError(f"Expected 3051 science-core rows, got {len(rows)}")
    by_url={r["profile_url"]:r for r in rows}
    if len(by_url)!=len(rows):raise RuntimeError("Duplicate profile_url in v6 input")
    seen=set(); log=[]
    for p in patches:
        u=p["profile_url"]
        if u not in by_url:raise RuntimeError(f"Patch target not found: {u}")
        if u in seen:raise RuntimeError(f"Duplicate patch target: {u}")
        seen.add(u); r=by_url[u]
        if r.get("name","")!=p["name"]:raise RuntimeError(f"Name mismatch for {u}: {r.get('name')} vs {p['name']}")
        old=(r.get("final_exact_dob") or "").strip()
        expected=(p.get("expected_old_final_exact_dob") or "").strip()
        if old!=expected:raise RuntimeError(f"Old DOB mismatch for {p['name']}: got {old!r}, expected {expected!r}")
        action=p["action"].strip()
        new=(p.get("new_final_exact_dob") or "").strip()
        if action=="retain":
            if new!=old:raise RuntimeError(f"retain action changes DOB for {p['name']}")
        elif action=="replace":
            if not new:raise RuntimeError(f"replace missing new DOB for {p['name']}")
            r["final_exact_dob"]=new
            r["dob_status"]="exact_manual_review"
        elif action=="withdraw":
            if new:raise RuntimeError(f"withdraw unexpectedly has new DOB for {p['name']}")
            r["final_exact_dob"]=""
            r["dob_status"]="manual_review_unresolved_conflict"
        else:
            raise RuntimeError(f"Unknown action {action!r}")

        r["manual_review_action"]=action
        r["manual_review_status"]=p["review_status"]
        r["manual_review_primary_source_url"]=p["primary_source_url"]
        r["manual_review_secondary_source_url"]=p["secondary_source_url"]
        r["manual_review_note"]=p["note"]
        log.append({
            "profile_url":u,"name":p["name"],"old_final_exact_dob":old,
            "action":action,"new_final_exact_dob":r.get("final_exact_dob",""),
            "review_status":p["review_status"],
            "primary_source_url":p["primary_source_url"],
            "secondary_source_url":p["secondary_source_url"],
            "note":p["note"],
        })

    # Ensure every row has audit columns.
    for r in rows:
        for k in ("manual_review_action","manual_review_status","manual_review_primary_source_url",
                  "manual_review_secondary_source_url","manual_review_note"):
            r.setdefault(k,"")

    exact=sum(present(r.get("final_exact_dob")) for r in rows)
    deceased=[r for r in rows if r.get("deceased")=="Y"]
    living=[r for r in rows if r.get("deceased")!="Y"]
    deceased_exact=sum(present(r.get("final_exact_dob")) for r in deceased)
    living_exact=sum(present(r.get("final_exact_dob")) for r in living)
    unresolved=[r for r in rows if not present(r.get("final_exact_dob"))]

    if exact!=2194:raise RuntimeError(f"Expected 2194 final exact DOB rows after review, got {exact}")
    if deceased_exact!=1357:raise RuntimeError(f"Expected deceased exact DOB count 1357, got {deceased_exact}")
    if living_exact!=837:raise RuntimeError(f"Expected living exact DOB count 837, got {living_exact}")
    if len(unresolved)!=857:raise RuntimeError(f"Expected 857 unresolved rows, got {len(unresolved)}")

    write_csv(OUT_CSV,rows)
    write_csv(LOG,log)
    summary={
        "dataset":"NAS science-core exact-DOB crosswalk v7 after manual conflict review",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "parent":"nas_science_core_dob_crosswalk_v6.csv",
        "science_core_rows":len(rows),
        "manual_review_rows":len(log),
        "manual_review_retained":sum(x["action"]=="retain" for x in log),
        "manual_review_replaced":sum(x["action"]=="replace" for x in log),
        "manual_review_withdrawn":sum(x["action"]=="withdraw" for x in log),
        "final_exact_dob_rows":exact,
        "final_exact_dob_coverage":round(exact/len(rows),6),
        "deceased_rows":len(deceased),
        "deceased_final_exact_dob_rows":deceased_exact,
        "deceased_final_exact_dob_coverage":round(deceased_exact/len(deceased),6),
        "living_rows":len(living),
        "living_final_exact_dob_rows":living_exact,
        "living_final_exact_dob_coverage":round(living_exact/len(living),6),
        "remaining_without_exact_dob":len(unresolved),
        "manual_unresolved_conflicts":[x["name"] for x in log if x["review_status"]=="unresolved_conflict"],
        "bazi_variables_computed":0,
        "policy_note":"Manual review never overwrites source columns. It changes only final_exact_dob/dob_status and appends explicit audit fields. Unresolved day-level source conflicts are withdrawn rather than guessed.",
        "files":{
            OUT_CSV.name:{"sha256":sha256(OUT_CSV),"bytes":OUT_CSV.stat().st_size},
            LOG.name:{"sha256":sha256(LOG),"bytes":LOG.stat().st_size},
            PATCH.name:{"sha256":sha256(PATCH),"bytes":PATCH.stat().st_size},
        },
    }
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
