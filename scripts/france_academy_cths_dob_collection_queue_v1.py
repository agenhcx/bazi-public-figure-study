#!/usr/bin/env python3
"""Freeze only a source-collection queue for French historical CTHS profiles.

Preserves Academy category pending verification. Keeps CTHS historical dates
outside the study as archival but prioritizes 1835-1985 birthyear full-like
roles. Creates deterministic source-fetch shards; does NOT accept DOB evidence.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path

SOURCE=Path("data/france_academy_cths_society_role_repair_v1_1/cths_academy_membership_candidates_corrected_v1_1.csv")
OUT=Path("data/france_academy_cths_dob_collection_queue_v1")
TYPES={"full_like_only_candidate","correspondent_then_full_candidate","full_and_foreign_mixed_manual"}
MIN_YEAR,MAX_YEAR=1835,1985
SHARDS=4

def read(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def save(path,rows,fields):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def main():
    data=read(SOURCE)
    if len(data)!=2144:raise RuntimeError("Unexpected corrected CTHS roster count")
    people=[]
    for r in data:
        yeartext=r["birth_year_lifespan_candidate"]
        year=int(yeartext) if yeartext.isdigit() else None
        if r["status_source_text_candidate"] not in TYPES or year is None or not (MIN_YEAR<=year<=MAX_YEAR):
            continue
        pid=r["cths_person_id"]
        shard=int(hashlib.sha256(pid.encode()).hexdigest()[:8],16)%SHARDS
        people.append({
            "cths_person_id":pid,
            "cths_profile_url":r["cths_profile_url"],
            "cths_name":r["name_fixed"],
            "birth_year_provisional":year,
            "membership_type_provisional":r["status_source_text_candidate"],
            "source_fetch_shard":shard,
            "source_evidence_priority":"MIXED_MEMBERSHIP_MANUAL" if r["status_source_text_candidate"]=="full_and_foreign_mixed_manual" else "FULL_ROLE_SOURCE_REVIEW",
            "eligible_for_primary_roster":0,
            "exact_dob_accepted":0,
            "dob_missingness_denominator_not_final":1,
        })
    people.sort(key=lambda r:(int(r["source_fetch_shard"]),r["cths_person_id"].zfill(12)))
    if len(people)<200 or len(people)>1200:raise RuntimeError(f"Unusual provisional DOB target count: {len(people)}")
    OUT.mkdir(parents=True,exist_ok=True)
    fields=list(people[0])
    save(OUT/"cths_provisional_member_source_fetch_queue_v1.csv",people,fields)
    for shard in range(SHARDS):
        save(OUT/f"source_fetch_shard_{shard:02d}_of_{SHARDS:02d}.csv",
             [r for r in people if r["source_fetch_shard"]==shard],fields)
    manifest={
        "version":"france-academy-cths-provisional-source-fetch-queue-v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "birthyear_priority_window":[MIN_YEAR,MAX_YEAR],
        "original_cths_profiles":len(data),
        "target_people":len(people),
        "target_role_counts":dict(Counter(r["membership_type_provisional"] for r in people)),
        "shard_counts":dict(Counter(str(r["source_fetch_shard"]) for r in people)),
        "membership_evidence_accepted":0,
        "exact_dobs_accepted":0,
        "global_bazi_unblinded":False,
        "warning":"Only for fetching CTHS biographies and date-source citations. Academy membership and DOB accuracy still require primary-source checks and missingness audit; queue excludes foreign/corresponding-only people from collection priority, not master roster.",
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
