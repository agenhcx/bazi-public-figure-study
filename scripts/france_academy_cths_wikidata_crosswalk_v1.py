#!/usr/bin/env python3
"""Deterministic *identity candidate* crosswalk between source-audited France rosters.

The match is strictly name-token and single Wikidata birth year versus CTHS
lifespan year. Never use fuzzy matches for admission. No accepted DOBs here.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p: Path, rows: list[dict], headers: list[str]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def clean_text(s: str) -> str:
    s=unicodedata.normalize("NFKD", (s or "").casefold())
    s="".join(x for x in s if not unicodedata.combining(x))
    s=s.replace("œ","oe").replace("æ","ae").replace("ø","o").replace("ł","l")
    s=re.sub(r"[^a-z0-9 ]+"," ",s)
    return " ".join(s.split())


def key(name: str) -> str:
    return " ".join(sorted(clean_text(name).split()))


def filter_wd_names(r: dict) -> set[str]:
    vals=set()
    for k in ("name_fr","name_en","name_candidate"):
        for part in (r.get(k) or "").split(" | "):
            if (t:=key(part)):
                vals.add(t)
    return vals


def try_year_wd(r: dict) -> int|None:
    years=[int(x) for x in r["birth_year_candidates"].split(" | ") if x.strip().isdigit()]
    return years[0] if len(set(years))==1 else None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wd",default="data/france_academy_wikidata_candidate_discovery_v1/candidate_people_v1.csv")
    ap.add_argument("--cths",default="data/france_academy_cths_society_role_repair_v1_1/cths_academy_membership_candidates_corrected_v1_1.csv")
    ap.add_argument("--out",default="data/france_academy_cths_wikidata_crosswalk_v1")
    args=ap.parse_args()
    source_wd=read_csv(Path(args.wd));source_cths=read_csv(Path(args.cths))
    if len(source_wd)!=2220 or len(source_cths)!=2144:
        raise RuntimeError("Source census changed; version crosswalk explicitly before re-running")
    by_name=defaultdict(dict)
    for r in source_wd:
        for n in filter_wd_names(r):
            by_name[n][r["qid"]]=r
    matched=[]
    unmatched=[]
    warnings=[]
    matches_for_wd=defaultdict(list)
    for r in source_cths:
        ckey=key(r["name_fixed"])
        ids=list(by_name.get(ckey,{}).values())
        cyr=(int(r["birth_year_lifespan_candidate"])
             if r["birth_year_lifespan_candidate"].isdigit() else None)
        exacts=[w for w in ids if cyr is not None and try_year_wd(w)==cyr]
        if len(exacts)==1:
            w=exacts[0]
            kind="unique_token_name_and_year_candidate"
        elif len(exacts)>1:
            w=None;kind="collision_identical_name_and_year"
        elif not ids:
            w=None;kind="no_exact_token_name"
        elif not cyr:
            w=None;kind="exact_name_but_cths_birthyear_missing"
        elif any(try_year_wd(x) is None for x in ids):
            w=None;kind="exact_name_wd_year_missing_or_conflict"
        else:
            w=None;kind="exact_name_year_mismatch_manual_review"
        base={
            "cths_person_id":r["cths_person_id"],
            "cths_name_fixed":r["name_fixed"],
            "cths_year_candidate":cyr or "",
            "cths_status_candidate":r["status_source_text_candidate"],
            "cths_profile_url":r["cths_profile_url"],
            "match_class":kind,
            "wd_qid_candidate":w["qid"] if w else "",
            "wd_name_candidate":w["name_candidate"] if w else "",
            "wd_year_candidate":try_year_wd(w) if w else "",
            "wd_p6282_claim":w["official_id_claims"] if w else "",
            "wd_alt_qids_unresolved":" | ".join(sorted(x["qid"] for x in ids)) if not w else "",
            "identity_match_acceptance":"MATCH_FOR_MANUAL_SOURCE_REVIEW" if w else "UNRESOLVED",
            "full_membership_accepted":0,
            "exact_dob_accepted":0,
        }
        (matched if w else unmatched).append(base)
        if w:
            matches_for_wd[w["qid"]].append(r["cths_person_id"])
    for qid, personids in matches_for_wd.items():
        if len(personids)>1:
            warnings.append({"qid":qid,"linked_cths_ids":" | ".join(personids),
                             "issue":"one Wikidata QID matched multiple CTHS person IDs; quarantine"})
    if warnings:
        flagged={p for row in warnings for p in row["linked_cths_ids"].split(" | ")}
        reclassed=[]
        for row in matched:
            if row["cths_person_id"] in flagged:
                row["match_class"]="nonunique_identity_quarantined"
                row["identity_match_acceptance"]="UNRESOLVED"
                reclassed.append(row)
        matched=[r for r in matched if r["cths_person_id"] not in flagged]
        unmatched.extend(reclassed)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    columns=list((matched or unmatched)[0].keys())
    write_csv(out/"unique_strict_identity_candidates_v1.csv",matched,columns)
    write_csv(out/"unresolved_identity_review_v1.csv",unmatched,columns)
    write_csv(out/"many_to_one_quarantine_v1.csv",warnings,["qid","linked_cths_ids","issue"])
    c=Counter(r["match_class"] for r in matched+unmatched)
    statusmatched=Counter(r["cths_status_candidate"] for r in matched)
    result={
        "version":"france-academy-cths-wikidata-strict-identity-crosswalk-v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "cths_people":len(source_cths),"wikidata_qids":len(source_wd),
        "strict_unique_name_and_birthyear_candidate_links":len(matched),
        "unresolved_cths_people":len(unmatched),
        "matches_by_cths_role_candidate":dict(statusmatched),
        "statuses":dict(c),"many_to_one_identity_conflicts":len(warnings),
        "matching_rule":"alphabetized normalized name tokens + one unique matching birth year on both sides; no fuzzy/surname-only matching",
        "full_membership_accepted":0,"exact_dobs_accepted":0,"bazi_variables_computed":0,
        "WARNING":"Crosswalk is identity candidate only; CTHS and Wikidata may not be independent DOB sources.",
    }
    (out/"summary.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
