#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path

IN=Path("data/royal_society_past_dob_official_v1_inputs")
OUT=Path("data/royal_society_past_dob_official_v1_consolidated")

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"nonempty output {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)

    files=sorted(IN.rglob("past_fellows_official_dob.csv"))
    if len(files)!=8:
        raise RuntimeError(f"Expected 8 chunk CSVs, found {len(files)}: {files}")

    rows=[]
    chunk_meta=[]
    for p in files:
        rr=read_csv(p)
        rows.extend(rr)
        chunk_meta.append({"file":str(p),"rows":len(rr),"sha256":sha256(p)})

    keys=[r["cohort_key"] for r in rows]
    dup=[k for k,v in Counter(keys).items() if v>1]
    if len(rows)!=7099 or len(set(keys))!=7099 or dup:
        raise RuntimeError(f"Roster invariant failed rows={len(rows)} unique={len(set(keys))} dup={dup[:20]}")

    rows=sorted(rows,key=lambda r:r["cohort_key"])
    exact_candidates=[r for r in rows if r.get("dob_precision")=="exact_day"]
    accepted=[r for r in exact_candidates if str(r.get("birth_year_consistent","")).strip()!="0" and not r.get("error")]
    inconsistent=[r for r in exact_candidates if str(r.get("birth_year_consistent","")).strip()=="0"]
    errors=[r for r in rows if r.get("error")]
    unresolved=[r for r in rows if r not in accepted and r not in inconsistent and not r.get("error")]

    precision=Counter((r.get("dob_precision") or "").strip() for r in rows)

    fields=list(rows[0].keys())
    fullp=OUT/"royal_society_past_dob_official_v1.csv"
    write_csv(fullp,rows,fields)
    accp=OUT/"accepted_exact_dob_v1.csv"
    write_csv(accp,accepted,fields)
    errp=OUT/"http_error_retry_queue_v1.csv"
    write_csv(errp,errors,fields)
    incp=OUT/"exact_dob_birthyear_conflict_review_v1.csv"
    write_csv(incp,inconsistent,fields)
    unp=OUT/"nonexact_unresolved_v1.csv"
    write_csv(unp,unresolved,fields)

    summary={
      "dataset":"Royal Society past Fellow official exact-DOB consolidated v1",
      "rows":len(rows),
      "unique_cohort_keys":len(set(keys)),
      "precision_counts":dict(sorted(precision.items())),
      "exact_day_candidates":len(exact_candidates),
      "accepted_exact_dob":len(accepted),
      "accepted_exact_dob_coverage":len(accepted)/len(rows),
      "birth_year_conflicts_rejected":len(inconsistent),
      "http_error_retry_queue":len(errors),
      "nonexact_unresolved":len(unresolved),
      "chunk_files":chunk_meta,
      "full_csv_sha256":sha256(fullp),
      "accepted_csv_sha256":sha256(accp),
      "error_queue_sha256":sha256(errp),
      "conflict_review_sha256":sha256(incp),
      "bazi_variables_computed":0,
      "acceptance_rule":"Exact day-month-year parsed from the official Royal Society Date of birth field. If a catalogue lifespan birth year is present, it must agree. Network errors and conflicts remain unresolved and are excluded."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
