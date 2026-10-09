#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

BASE=Path("data/royal_society_past_dob_closeout_inputs_v1")
OUT=Path("data/royal_society_past_dob_closeout_v1")
NA4812_SUPPORT="https://doi.org/10.1098/rsbm.2019.0036"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)

    full=read_csv(next(BASE.rglob("royal_society_past_dob_official_v1.csv")))
    conflicts=read_csv(next(BASE.rglob("exact_dob_birthyear_conflict_review_v1.csv")))
    errs=read_csv(next(BASE.rglob("http_error_retry_queue_v1.csv")))
    if len(full)!=7099 or len(conflicts)!=17 or len(errs)!=4:
        raise RuntimeError(f"Input invariant failed full={len(full)} conflicts={len(conflicts)} errs={len(errs)}")

    audit_files=sorted(BASE.rglob("internal_audit.csv"))
    if len(audit_files)!=3:
        raise RuntimeError(f"Expected 3 audit shard CSVs, found {len(audit_files)}")
    audit=[]
    for p in audit_files:audit.extend(read_csv(p))
    if len(audit)!=21:
        raise RuntimeError(f"Expected 21 audit rows, got {len(audit)}")

    ca=[r for r in audit if r["audit_kind"]=="conflict"]
    ha=[r for r in audit if r["audit_kind"]=="http_retry"]
    if len(ca)!=17 or len(ha)!=4:
        raise RuntimeError(f"Audit split mismatch conflicts={len(ca)} http={len(ha)}")
    supported=[r for r in ca if str(r.get("age_supports_exact_dob",""))=="1"]
    contrad=[r for r in ca if str(r.get("age_supports_exact_dob",""))=="0"]
    noage=[r for r in ca if str(r.get("age_supports_exact_dob",""))==""]
    if len(supported)!=16 or contrad or len(noage)!=1 or noage[0]["record_id"]!="NA4812":
        raise RuntimeError(f"Unexpected conflict audit outcome supported={len(supported)} contrad={len(contrad)} noage={[r['record_id'] for r in noage]}")

    # Adjudication rule fixed before any BaZi computation:
    # the explicit structured 'Date of birth' field is the authoritative DOB field.
    # The generic top-level 'Dates' lifespan summary is secondary metadata and does not
    # veto an internally coherent exact DOB. This is empirically supported by 16/16
    # auditable conflicts matching the page's own Age at election.
    exact=[r for r in full if r.get("dob_precision")=="exact_day" and not r.get("error")]
    if len(exact)!=4884:
        raise RuntimeError(f"Expected 4884 exact-day official records, got {len(exact)}")

    accepted=[]
    conflict_ids={r["record_id"] for r in conflicts}
    support_by_id={r["record_id"]:r for r in ca}
    for r in exact:
        x=dict(r)
        if r["record_id"] in conflict_ids:
            ar=support_by_id[r["record_id"]]
            if r["record_id"]=="NA4812":
                x["dob_adjudication"]="accepted_explicit_dob_field_with_external_corroboration"
                x["adjudication_support"]=NA4812_SUPPORT
            else:
                x["dob_adjudication"]="accepted_explicit_dob_field_age_at_election_corroborated"
                x["adjudication_support"]=f"Royal Society same-page Age at election={ar.get('page_age_numeric','')}"
        else:
            x["dob_adjudication"]="accepted_explicit_dob_field_no_conflict"
            x["adjudication_support"]=""
        accepted.append(x)

    unresolved=[r for r in full if r.get("dob_precision")!="exact_day" and not r.get("error")]
    http=[r for r in full if r.get("error")]
    if len(unresolved)!=2211 or len(http)!=4:
        raise RuntimeError(f"Expected unresolved=2211 and http=4, got {len(unresolved)} and {len(http)}")
    if sum(bool(r.get("retry_exact_iso")) for r in ha)!=0 or sum(bool(r.get("error")) for r in ha)!=4:
        raise RuntimeError("All four HTTP retries were expected to remain unresolved")

    afields=list(accepted[0].keys())
    ap=OUT/"accepted_exact_dob_final_v1.csv";write_csv(ap,accepted,afields)
    up=OUT/"nonexact_unresolved_final_v1.csv";write_csv(up,unresolved,list(unresolved[0].keys()))
    hp=OUT/"persistent_http_error_queue_v1.csv";write_csv(hp,http,list(http[0].keys()))

    adjud=[]
    for r in conflicts:
        ar=support_by_id[r["record_id"]]
        adjud.append({
          "record_id":r["record_id"],"cohort_key":r["cohort_key"],"display_name":r["display_name"],
          "dob_exact_iso":r["dob_exact_iso"],"dates_summary_birth_year":r["catalogue_lifespan_birth_year"],
          "age_at_election_check":ar.get("age_supports_exact_dob",""),
          "decision":"accept_explicit_date_of_birth",
          "rationale":"Structured Date of birth field outranks generic Dates lifespan summary; no audited age contradiction.",
          "secondary_support":NA4812_SUPPORT if r["record_id"]=="NA4812" else ""
        })
    jp=OUT/"conflict_adjudication_v1.csv";write_csv(jp,adjud,list(adjud[0].keys()))

    summary={
      "dataset":"Royal Society past Fellow exact-DOB closeout v1",
      "roster_past_fellows":7099,
      "official_exact_dob_final":len(accepted),
      "official_exact_dob_coverage":len(accepted)/7099,
      "nonexact_unresolved":len(unresolved),
      "persistent_http_errors":len(http),
      "initial_dates_summary_conflicts":17,
      "conflicts_age_check_available":16,
      "conflicts_age_check_supports_exact_dob":16,
      "conflicts_age_check_contradicts_exact_dob":0,
      "conflict_without_age_check":"NA4812",
      "conflict_without_age_check_secondary_support":NA4812_SUPPORT,
      "field_precedence_rule":"Explicit Royal Society Date of birth field > generic top-level Dates lifespan summary.",
      "accepted_csv_sha256":sha256(ap),
      "unresolved_csv_sha256":sha256(up),
      "http_queue_sha256":sha256(hp),
      "conflict_adjudication_sha256":sha256(jp),
      "dob_collection_stage":"official Royal Society past-Fellow source pass closed; secondary-source enrichment remains allowed for unresolved records",
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
