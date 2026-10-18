#!/usr/bin/env python3
"""Audit coverage of the 36 legally approved 2024-2025 France Academy electees.

The Academy (election cohort year) and Légifrance decrees (year+1) anchor
membership. Name matches against CTHS and Wikidata are identity *candidates*.
No DOB or historical category is accepted from a name match.
"""
from __future__ import annotations
import csv
import datetime as dt
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RECENT=Path("data/france_academy_official_elected_2024_2025_v1/official_member_election_approval_roster_v1.csv")
CTHS=Path("data/france_academy_cths_society_role_repair_v1_1/cths_academy_membership_candidates_corrected_v1_1.csv")
WD=Path("data/france_academy_wikidata_candidate_discovery_v1/candidate_people_v1.csv")
OUT=Path("data/france_academy_official_elected_2024_2025_v1")

def read(path):
    with path.open("r",newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))

def tokens(s):
    s=unicodedata.normalize("NFKD",s.casefold())
    s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join(sorted(re.findall(r"[a-z0-9]+",s)))

def main():
    officials,cths,wds=read(RECENT),read(CTHS),read(WD)
    assert len(officials)==36 and Counter(x["election_year"] for x in officials)=={"2024":18,"2025":18}
    assert len(cths)==2144 and len(wds)==2220
    assert len({tokens(x["person_name_academy"]) for x in officials})==36
    cm=defaultdict(list); wm=defaultdict(dict)
    for row in cths:cm[tokens(row["name_fixed"])].append(row)
    for row in wds:
        for col in ("name_candidate","name_fr","name_en"):
            for alt in row[col].split(" | "):
                if alt:wm[tokens(alt)][row["qid"]]=row

    joins=[]
    for source in officials:
        key=tokens(source["person_name_academy"])
        c=cm.get(key,[])
        w=list(wm.get(key,{}).values())
        joins.append({
            **source,
            "matched_cths_profile_count":len(c),
            "cths_person_id_exact_name_unique":c[0]["cths_person_id"] if len(c)==1 else "",
            "cths_role_candidate_if_unique":c[0]["status_source_text_candidate"] if len(c)==1 else "",
            "cths_year_if_unique":c[0]["birth_year_lifespan_candidate"] if len(c)==1 else "",
            "matched_wikidata_QID_count":len(w),
            "wikidata_qid_exact_name_unique":w[0]["qid"] if len(w)==1 else "",
            "wikidata_birthyear_claim_if_unique":w[0]["birth_year_candidates"] if len(w)==1 else "",
            "member_election_still_official":1,
            "historical_profile_match_is_not_acceptance":1,
            "dob_evidence_certified":0,
        })
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"official_election_vs_cths_wikidata_identity_audit_v1.csv").open(
        "w",newline="",encoding="utf-8-sig") as f:
        wr=csv.DictWriter(f,fieldnames=list(joins[0]));wr.writeheader();wr.writerows(joins)
    result={
        "version":"france-academy-government-election-two-source-identity-audit-v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "2024_govt_approved_electees":18,
        "2025_govt_approved_electees":18,
        "recent_official_electees_total":36,
        "cths_exact_normalized_name_single_matches":sum(r["matched_cths_profile_count"]==1 for r in joins),
        "cths_no_exact_name":sum(r["matched_cths_profile_count"]==0 for r in joins),
        "cths_multiple_exact_name":sum(r["matched_cths_profile_count"]>1 for r in joins),
        "wikidata_exact_normalized_name_single_matches":sum(r["matched_wikidata_QID_count"]==1 for r in joins),
        "wikidata_no_exact_name":sum(r["matched_wikidata_QID_count"]==0 for r in joins),
        "wikidata_multiple_exact_name":sum(r["matched_wikidata_QID_count"]>1 for r in joins),
        "matched_names_rule":"strict normalized token multiset only; reject ambiguous matches; no fuzzy acceptance",
        "birth_year_from_official_approvals":0,
        "exact_dob_accepted":0,
        "global_bazi_unblinded":False,
        "warning":"This matches official election names to discovery records; do not promote CTHS/Wikidata DOB or historical category to accepted evidence. JORF approvals occur the following year.",
    }
    (OUT/"identity_audit_summary_v1.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":main()
