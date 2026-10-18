#!/usr/bin/env python3
"""Rank 130 source-backed CTHS candidates for manual official directory checks.

No network calls. Each row is a citation/source lead, NOT verified DOB or
ordinary-member inclusion. Prioritize the member-only 1989 printed directory,
then 1979 index, and then 1993 mixed member/correspondent directory.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

SOURCE=Path("data/france_academy_cths_historical_source_citation_audit_v1/institutional_directory_citation_review_queue_v1.csv")
OUT=Path("data/france_academy_cths_historical_source_citation_audit_v1/historical_directory_entry_review_v1")
TOP=20

def load(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write(path,records,keys):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore")
        w.writeheader();w.writerows(records)

def choose_source(x):
    if x["academy_member_only_1989"]=="1":
        return "1989_MEMBER_ONLY_DIRECTORY",0
    if x["academy_bio_1979"]=="1":
        return "1979_ACADEMY_BIOGRAPHICAL_INDEX",1
    if x["academy_member_corr_1993"]=="1":
        return "1993_MIXED_MEMBERS_CORRESPONDENTS_DIRECTORY",2
    return "UNSUPPORTED",99

def main():
    rows=load(SOURCE)
    if len(rows)!=130 or len({x["cths_person_id"] for x in rows})!=130:
        raise RuntimeError("Expected 130 unique source-cited historical CTHS people")
    kinds=Counter()
    queue=[]
    for x in rows:
        citation,rank=choose_source(x)
        if rank>2:raise RuntimeError("Source index citation count drift")
        kinds[citation]+=1
        role=x["cths_membership_class_provisional"]
        dob=x["cths_date_claim_candidate_only"]
        if dob and len(dob)!=10:raise RuntimeError("Only day-precision source candidate allowed in DOB field")
        flag="historical_membership_promotion_review" if "correspondent_then" in role else (
            "foreign_to_full_manual" if "foreign" in role else "full_like_CTHS_only")
        work={
            "cths_person_id":x["cths_person_id"],"cths_name":x["cths_name"],
            "cths_birth_year_provisional":x["cths_birth_year_candidate"],
            "cths_DOB_candidate_unverified":dob,
            "CTHS_status_provisional":role,
            "ranked_preferred_historical_directory":citation,
            "membership_review_need":flag,
            "CTHS_original_biography_url":x["cths_source_url"],
            "CTHS_bibliography_source_sha256":x["cths_bibliography_sha256"],
            "official_Academy_notice_cited":x["official_academy_biography"],
            "institutional_CV_cited":x["institutional_CV"],
            "exact_original_index_entry_seen":0,
            "original_index_membership_type_confirmed":0,
            "original_index_date_text_checked":0,
            "independent_DOB_source_verified":0,
            "study_person_admitted":0,
            "bazi_variables_computed":0,
            "next_verification":"Obtain original cited print volume; locate person/page, inspect full-member vs correspondant/foreign wording and DOB if explicitly stated",
            "_rank":rank,
        }
        queue.append(work)
    queue.sort(key=lambda x:(x["_rank"],
              0 if x["CTHS_status_provisional"]=="full_like_only_candidate" else 1,
              0 if x["official_Academy_notice_cited"]=="1" else 1,
              0 if x["cths_DOB_candidate_unverified"] else 1,
              int(x["cths_birth_year_provisional"]),x["cths_person_id"]))
    for i,item in enumerate(queue,1):
        item.pop("_rank")
        item["review_order"]=i
    cols=["review_order"]+[x for x in queue[0] if x!="review_order"]
    OUT.mkdir(parents=True,exist_ok=True)
    write(OUT/"directory_entry_review_queue_all130_v1.csv",queue,cols)
    write(OUT/"first20_directory_entry_checks_v1.csv",queue[:TOP],cols)
    snapshot=Counter(x["ranked_preferred_historical_directory"] for x in queue[:TOP])
    summary={
        "version":"france-academy-historical-directory-entry-review-queue-v1",
        "generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "cited_historical_directory_people":len(queue),
        "primary_rank_family_counts":dict(kinds),
        "first20_reviews":TOP,
        "first20_by_source_family":dict(snapshot),
        "source_directory_entry_actually_opened_by_this_script":0,
        "people_with_accepted_independent_DOB":0,
        "people_with_accepted_official_Academy_membership":0,
        "bazi_variables_computed":0,
        "warning":"Bibliographical citation is NOT underlying book content nor independent proof of DOB or full Academy status. No original book pages obtained.",
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
