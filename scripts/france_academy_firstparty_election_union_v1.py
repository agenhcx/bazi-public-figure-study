#!/usr/bin/env python3
"""Unify existing source-audited France Academy first-party election *candidates*.

Inputs: 66 prior official PDF electees, 58 new official PDF electees,
and 36 government-approved 2024/2025 member elections.
No network, no DOB from other sources, no BaZi, no claim of complete roster.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

A=Path("data/france_academy_official_election_pdf_pilot_v1/official_election_name_DOB_transcription_v1.csv")
A_AUDIT=Path("data/france_academy_official_election_pdf_pilot_v1/source_replay_validation_v1/source_fetch_audit_v1.csv")
B=Path("data/france_academy_elections_2019_2023_pilot_v2/source_validation_v2/candidate_official_member_election_v2.csv")
C=Path("data/france_academy_official_elected_2024_2025_v1/official_member_election_approval_roster_v1.csv")
OUT=Path("data/france_academy_firstparty_elected_union_v1")


def load(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def write(path,records,fields):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        w.writerows(records)


def norm(s):
    s=unicodedata.normalize("NFKD",(s or "").casefold())
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.replace("œ","oe").replace("æ","ae").replace("ø","o")
    return " ".join(sorted(re.findall(r"[a-z0-9]+",s)))


def main():
    a,b,c=load(A),load(B),load(C)
    audit={r["document_id"]:r for r in load(A_AUDIT)}
    if len(a)!=66 or len(b)!=58 or len(c)!=36:
        raise RuntimeError("Expected 66+58+36 audited elected-member source rows")
    if len(audit)!=5:
        raise RuntimeError("Earlier source audit incomplete: four regular + one negative")
    if len({r["person"] for r in b})!=58:
        raise RuntimeError("New official 58-name roster has literal duplicates")
    if any(r["name_matched"]!="1" or r["source_document_verified_as_election"]!="1" or
           r["source_DOB_claim"] or r["source_DOB_precision"]!="absent_in_election_pdf"
           for r in b):
        raise RuntimeError("New 58 rows do not have source-confirmed identity/DOB missingness")
    if any(r["official_member_election_approved"]!="1" or r["exact_dob_accepted"]!="0" for r in c):
        raise RuntimeError("Government source membership approvals incomplete")
    out=[]
    for x in a:
        ident=x["source_document_id"]
        if ident not in audit or audit[ident]["names_matched"] in ("","0"):
            raise RuntimeError("Earlier official source PDF audit missing: "+ident)
        prec=x["birth_precision"]
        dob=x["birth_as_stated_candidate"]
        year=dob[:4] if dob else ""
        if prec.startswith("day_precision"):
            dt.date.fromisoformat(dob)
        elif prec=="year_only":
            if not re.fullmatch(r"\d{4}",dob):
                raise RuntimeError("Year-only DOB precision invariant violated")
        elif prec=="absent_in_source":
            if dob:raise RuntimeError("DOB present in an absent field")
        else:raise RuntimeError("Unknown old source DOB precision")
        if x["exact_DOB_entered_frozen_analysis"]!="0" or x["bazi_variables_computed"]!="0":
            raise RuntimeError("Unblinding in old first-party PDF source")
        out.append({
            "name":x["person_name_transcribed"],
            "election_year":x["election_date_from_first_party"][:4],
            "source_document_id":ident,
            "announcement_or_source_event_date":x["election_date_from_first_party"],
            "day_is_explicit_election_day_in_source":"CHECK_ORIGINAL_DOC_IF_NEEDED",
            "primary_firstparty_member_category":"regular_member_election_announcement",
            "government_ratification_independently_verified":0,
            "section_original":x["science_group_original"],
            "source_url":audit[ident]["url"],
            "source_pdf_sha256":audit[ident]["source_sha256"],
            "official_source_birth_precision":prec,
            "birth_year_in_selected_source_candidate":year,
            "exact_DOB_in_selected_source_candidate":dob if len(dob)==10 else "",
            "firstparty_election_name_verified":1,
        })
    for x in b:
        out.append({
            "name":x["person"],
            "election_year":x["election_year"],
            "source_document_id":x["source_document_id"],
            "announcement_or_source_event_date":x["announcement_date"],
            "day_is_explicit_election_day_in_source":0,
            "primary_firstparty_member_category":"regular_member_election_announcement",
            "government_ratification_independently_verified":0,
            "section_original":x["science_section_in_source"],
            "source_url":x["source_url"],
            "source_pdf_sha256":x["source_sha256"],
            "official_source_birth_precision":"absent_in_source",
            "birth_year_in_selected_source_candidate":"",
            "exact_DOB_in_selected_source_candidate":"",
            "firstparty_election_name_verified":1,
        })
    for x in c:
        out.append({
            "name":x["person_name_academy"],
            "election_year":x["election_year"],
            "source_document_id":"JORF_ACADEMY_"+x["election_year"],
            "announcement_or_source_event_date":x["government_approval_date"],
            "day_is_explicit_election_day_in_source":0,
            "primary_firstparty_member_category":"government_approved_member_election",
            "government_ratification_independently_verified":1,
            "section_original":x["group_original_academy"],
            "source_url":x["government_decree_url"],
            "source_pdf_sha256":"",
            "official_source_birth_precision":"absent_in_source",
            "birth_year_in_selected_source_candidate":"",
            "exact_DOB_in_selected_source_candidate":"",
            "firstparty_election_name_verified":1,
        })
    if len(out)!=160:
        raise RuntimeError("Combined source rows do not total 160")

    for x in out:
        x["name_token_key"]=norm(x["name"])
        if not x["name_token_key"]:
            raise RuntimeError("Normalized identity key absent")
        x["known_birth_year_in_Nobel_support_range_candidate_only"]=(
            "yes" if x["birth_year_in_selected_source_candidate"] and
            1835<=int(x["birth_year_in_selected_source_candidate"])<=1985
            else "unknown" if not x["birth_year_in_selected_source_candidate"] else "no"
        )
        x["final_study_member_accepted"]=0
        x["final_study_exact_DOB_accepted"]=0
        x["bazi_variables_computed"]=0

    by_key={}
    collisions=[]
    for x in out:
        prev=by_key.get(x["name_token_key"])
        if prev:
            collisions.append({
                "name_normalized":x["name_token_key"],
                "first_source":prev["source_document_id"],
                "first_name":prev["name"],
                "second_source":x["source_document_id"],
                "second_name":x["name"],
                "review_status":"DUPLICATE_IDENTITIES_NOT_MERGED",
            })
        else:by_key[x["name_token_key"]]=x
    OUT.mkdir(parents=True,exist_ok=True)
    fields=list(out[0])
    write(OUT/"firstparty_member_election_candidate_union_v1.csv",out,fields)
    write(OUT/"name_collision_review_v1.csv",collisions,
          ["name_normalized","first_source","first_name","second_source","second_name","review_status"])
    counts=Counter(x["election_year"] for x in out)
    prec=Counter(
        "exact_day" if len(x["exact_DOB_in_selected_source_candidate"])==10
        else "year_only" if x["birth_year_in_selected_source_candidate"]
        else "not_stated_in_selected_official_source" for x in out)
    result={
        "version":"france-academy-selected-firstparty-election-union-v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_cohort_sizes":{"2010_to_2017_selected_pdfs":len(a),
                               "2019_to_2023_selected_pdfs":len(b),
                               "2024_and_2025_presidentially_approved":len(c)},
        "selected_firstparty_election_records":len(out),
        "strict_normalized_unique_person_names":len(by_key),
        "possible_name_collisions_unmerged":len(collisions),
        "election_year_counts":dict(sorted(counts.items())),
        "selected_official_document_DOB_claim_precision":dict(prec),
        "govt_approval_independently_verified":sum(x["government_ratification_independently_verified"] for x in out),
        "firstparty_elected_member_names_documented":len(out),
        "firstparty_document_years_not_a_complete_historical_coverage":True,
        "final_official_institutional_historical_roster_frozen":False,
        "independent_DOB_source_accepted_in_analysis":0,
        "bazi_variables_computed":0,
        "warning":"Selected official election-announcement records are NOT a continuous historical French Academy membership roster. Source DOB missingness is NOT final cohort DOB missingness.",
    }
    (OUT/"summary.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":main()
