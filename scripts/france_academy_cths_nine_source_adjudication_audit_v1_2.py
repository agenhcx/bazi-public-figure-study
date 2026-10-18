#!/usr/bin/env python3
"""Audit CTHS 9-person source adjudication against prior immutable 562-person snapshot.

This is source/identity QA, NOT birthdate acceptance, NOT a membership cohort
freeze, and NEVER computes BaZi features. No network.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

SOURCE = Path("data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv")
ROOT = Path("data/france_academy_cths_nine_source_adjudication_v1_2")
PERSON = ROOT / "person_evidence_triage_v1_2.csv"
CLAIMS = ROOT / "source_claim_evidence_ledger_v1_2.csv"
OUT = Path("local_runs/france_academy_cths_nine_source_adjudication_v1_2")
IDS = {"2092","107677","110681","112913","128379","111758","117565","117620","125186"}
DATE_EXTERNAL = {"112913","128379","111758","125186"}
MEMBER_FIRSTPARTY = {"112913","128379","125186"}
MEMBER_INSTITUTIONAL = {"111758"}
DOB_CONFLICT = {"2092","110681"}
PROVISIONAL_FOREIGN = {"117565","117620"}
PROVISIONAL_CORRESP = {"110681"}
ROLE_NOT_FIRSTPARTY = {"2092","107677"}
UNRESOLVED_DOB = {"2092","107677","110681","117565","117620"}
DOB_UNKNOWN_FROM_ORIGINAL = {"2092","107677","128379"}

def read(path:Path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write(path:Path,rows:list[dict],fields:list[str]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)

def sha(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=OUT)
    args=ap.parse_args()
    old=read(SOURCE)
    people=read(PERSON)
    claims=read(CLAIMS)
    base={r["cths_person_id"]:r for r in old}
    ids=[r["cths_person_id"] for r in people]
    if len(old)!=562 or len(base)!=562:
        raise RuntimeError("Original 562-person CTHS snapshot has changed")
    if set(ids)!=IDS or len(ids)!=9:
        raise RuntimeError("Missing or duplicate people in 9-person source adjudication")
    if len(claims)!=29:
        raise RuntimeError("Unexpected source evidence row count, review the additions")
    groups={}
    for c in claims:
        pid=c["cths_person_id"]
        if pid not in IDS:
            raise RuntimeError("Claim linked to unknown CTHS person: "+pid)
        url=c["source_url"]
        if urlparse(url).scheme!="https" or not urlparse(url).hostname:
            raise RuntimeError("Invalid source URL: "+url)
        if c["included_in_frozen_analysis"]!="0":
            raise RuntimeError("Claim was included in frozen analysis without global freeze")
        groups.setdefault(pid,[]).append(c)
    if set(groups)!=IDS:
        raise RuntimeError("A person lacks source provenance")

    existing_date_verified=set()
    existing_member_firstparty=set()
    existing_member_institutional=set()
    existing_provisional_foreign=set()
    existing_provisional_corr=set()
    existing_conflicts=set()
    detail=[]
    for r in people:
        pid=r["cths_person_id"]
        src=base[pid]
        if r["frozen_study_membership_accepted"]!="0" or r["frozen_study_DOB_accepted"]!="0" or r["bazi_variables_computed"]!="0":
            raise RuntimeError("Unexpected premature cohort or DOB acceptance")
        if r["name"].casefold()!=src["name"].casefold():
            raise RuntimeError("Name identity mismatch for "+pid)
        claimed=r["source_verified_birthdate_candidate"]
        if claimed:
            dt.date.fromisoformat(claimed)
            if claimed[:4]!=src["CTHS_roster_year_provisional"]:
                raise RuntimeError("Year mismatch in external DOB claim: "+pid)
        if r["independent_DOB_claim_verified"]=="1":
            existing_date_verified.add(pid)
        if r["official_full_member_evidence_verified"]=="1":
            existing_member_firstparty.add(pid)
        if r["primary_full_membership_evidence_status"]=="FULL_MEMBERSHIP_1973_INSTITUTIONALLY_CORROBORATED":
            existing_member_institutional.add(pid)
        if r["primary_full_membership_evidence_status"].startswith("FOREIGN_ASSOCIATE_ONLY_"):
            existing_provisional_foreign.add(pid)
        if r["primary_full_membership_evidence_status"]=="CORRESPONDING_ONLY_STRONG_INSTITUTIONAL_EVIDENCE":
            existing_provisional_corr.add(pid)
        if "CONFLICT" in r["birthdate_evidence_status"]:
            existing_conflicts.add(pid)
        # A CTHS exact date need not agree with later credible conflicting sources.
        if pid in DOB_UNKNOWN_FROM_ORIGINAL and src["cths_birth_parser_status"]=="candidate_exact_day":
            raise RuntimeError("Expected original CTHS date to be absent/nonexact: "+pid)
        detail.append({
            "cths_person_id":pid,"name":r["name"],
            "new_source_evidence_links":len(groups[pid]),
            "birth_date_candidate":claimed,
            "date_evidence_status":r["birthdate_evidence_status"],
            "member_evidence_status":r["primary_full_membership_evidence_status"],
            "official_member_evidence_verified":r["official_full_member_evidence_verified"],
            "external_birthdate_evidence_verified":r["independent_DOB_claim_verified"],
            "frozen_study_member_accepted":0,"frozen_study_DOB_accepted":0,
        })
    if existing_date_verified!=DATE_EXTERNAL:
        raise RuntimeError("External DOB source decisions changed: "+str(existing_date_verified))
    if existing_member_firstparty!=MEMBER_FIRSTPARTY:
        raise RuntimeError("Official Academy membership evidence decisions changed")
    if existing_member_institutional!=MEMBER_INSTITUTIONAL:
        raise RuntimeError("Institutional-only membership evidence decisions changed")
    if existing_provisional_foreign!=PROVISIONAL_FOREIGN or existing_provisional_corr!=PROVISIONAL_CORRESP:
        raise RuntimeError("Provisional foreign/corresponding exclusions changed")
    if existing_conflicts!=DOB_CONFLICT:
        raise RuntimeError("Conflict set changed")
    args.out.mkdir(parents=True,exist_ok=True)
    write(args.out/"nine_person_source_qc.csv",detail,list(detail[0]))
    review=[r for r in detail if r["cths_person_id"] not in (DATE_EXTERNAL & (MEMBER_FIRSTPARTY|MEMBER_INSTITUTIONAL))]
    # Separate test pass from final scientific acceptance: verified evidence is NOT a frozen study dataset.
    write(args.out/"unresolved_status_or_dob_review.csv",review,list(detail[0]))
    summary={
        "audit":"france-academy-cths-nine-source-adjudication-v1_2",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "network_requests":0,
        "frozen_562_person_source_sha256":sha(SOURCE),
        "person_overlay_sha256":sha(PERSON),
        "evidence_ledger_sha256":sha(CLAIMS),
        "review_people":len(people),
        "evidence_claims":len(claims),
        "source_corroborated_DOB_people":len(existing_date_verified),
        "first_party_Academy_full_election_people":len(existing_member_firstparty),
        "institutional_member_corroborated_Academy_firstparty_still_pending":len(existing_member_institutional),
        "provisional_foreign_member_only_people":len(existing_provisional_foreign),
        "provisional_corresponding_only_people":len(existing_provisional_corr),
        "unresolved_conflicting_DOB_people":len(existing_conflicts),
        "strict_source_evidence_both_covered_people":len(DATE_EXTERNAL & (MEMBER_FIRSTPARTY|MEMBER_INSTITUTIONAL)),
        "unresolved_status_or_dob_review_people":len(review),
        "final_frozen_study_DOB_accepted":0,
        "final_frozen_study_cohort_admitted":0,
        "bazi_variables_computed":0,
        "warning":"Source corroboration count is NOT final study DOB coverage; selection/election class and archive mismatches must be resolved before global freeze.",
    }
    (args.out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
