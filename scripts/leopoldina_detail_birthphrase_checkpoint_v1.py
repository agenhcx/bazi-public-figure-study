#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import defaultdict
from datetime import date
from pathlib import Path

CAND=Path("data/leopoldina_detail_birthphrase_checkpoint_input/candidate_rows_v1.csv")
AUDIT=Path("data/leopoldina_detail_birthphrase_checkpoint_input/member_candidate_audit_v1.csv")
ADJ=Path("data/leopoldina_detail_birthphrase_multidate_adjudication_v1.csv")
STATIC=Path("data/leopoldina_official_static_dob_v1/accepted_exact_dob_static_volumes_v1.csv")
STRUCT=Path("data/leopoldina_structure_row_dob_accepted_v1/accepted_exact_dob_structure_tables_v1.csv")
ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
OUT=Path("data/leopoldina_detail_birthphrase_dob_accepted_v1")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=read_csv(CAND); audit=read_csv(AUDIT); adj=read_csv(ADJ)
    roster={r["member_slug"]:r for r in read_csv(ROSTER)}
    prior={r["member_slug"] for r in read_csv(STATIC)}|{r["member_slug"] for r in read_csv(STRUCT)}
    if len(rows)!=55 or len(audit)!=53:raise RuntimeError(f"Unexpected rebuilt candidate cardinality rows={len(rows)} members={len(audit)}")
    if prior & {r["member_slug"] for r in rows}:raise RuntimeError(f"Detail candidate unexpectedly overlaps prior official accepted set: {sorted(prior & {r['member_slug'] for r in rows})[:20]}")
    amap={r["member_slug"]:r for r in adj}
    if set(amap)!={"feodor-lynen","vladimir-prelog"}:raise RuntimeError("Unexpected multidate adjudication set")
    by=defaultdict(list)
    for r in rows:by[r["member_slug"]].append(r)
    accepted=[]; rejected=[]
    for slug,rs in sorted(by.items()):
        if slug not in roster:raise RuntimeError(f"Candidate outside frozen roster: {slug}")
        dates=sorted({r["candidate_dob"] for r in rs})
        if len(dates)==1:
            chosen=dates[0]
        elif slug in amap and len(dates)==2:
            chosen=amap[slug]["accepted_dob"]
            if chosen not in dates or amap[slug]["rejected_dob"] not in dates:raise RuntimeError(f"Adjudication dates do not match candidates for {slug}: {dates}")
        else:
            raise RuntimeError(f"Unresolved multiple candidate dates for {slug}: {dates}")
        date.fromisoformat(chosen)
        chosen_rows=[r for r in rs if r["candidate_dob"]==chosen]
        if not chosen_rows:raise RuntimeError(f"No chosen evidence row {slug}")
        # Candidate scan requires explicit birth phrase on the member's own official detail URL.
        if any(r["pattern_class"]!="explicit_birth_word" or r["http_status"]!="200" for r in chosen_rows):
            raise RuntimeError(f"Unexpected evidence class/status for {slug}")
        base=chosen_rows[0]
        accepted.append({
          **base,
          "final_exact_dob":chosen,
          "decision":"accept_official_leopoldina_detail_explicit_birth_phrase",
          "adjudication_note":amap.get(slug,{}).get("decision_reason","Unique exact date in an explicit born/geboren/date-of-birth phrase on the member's official Leopoldina detail page.")
        })
        for r in rs:
            if r["candidate_dob"]!=chosen:
                rejected.append({**r,"decision":"reject_nonbirth_date_from_broad_phrase_window","adjudication_note":amap[slug]["decision_reason"]})
    if len(accepted)!=53:raise RuntimeError(f"Expected 53 accepted members, got {len(accepted)}")
    if len(rejected)!=2:raise RuntimeError(f"Expected 2 rejected nonbirth dates, got {len(rejected)}")
    ap=OUT/"accepted_exact_dob_detail_birthphrases_v1.csv"
    write_csv(ap,accepted,list(accepted[0].keys()))
    rp=OUT/"rejected_nonbirth_dates_v1.csv"
    write_csv(rp,rejected,list(rejected[0].keys()))
    summary={
      "dataset":"Leopoldina official member-detail explicit-birth-phrase exact-DOB checkpoint v1",
      "source_run_id":38098749349,
      "source_artifact_id":11686587443,
      "source_artifact_name":"leopoldina-detail-birthphrase-candidates-rebuilt-v1",
      "source_artifact_zip_sha256":"28e16d8a4372b5a2de675de9df7e87dcd139c53e09d4f11c0899f45d8fae24d2",
      "target_rows_scanned":2640,
      "candidate_members":53,
      "accepted_exact_dob":53,
      "multidate_members_adjudicated":2,
      "rejected_nonbirth_date_rows":2,
      "overlap_with_prior_official_accepted":0,
      "accepted_csv_sha256":sha256(ap),"rejected_csv_sha256":sha256(rp),"adjudication_csv_sha256":sha256(ADJ),
      "acceptance_rule":"Exact day-month-year must be stated in an explicit born/geboren/date-of-birth phrase on the frozen member's own official Leopoldina detail page. Multiple dates are accepted only after row-level semantic adjudication identifying the actual birth sentence.",
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
