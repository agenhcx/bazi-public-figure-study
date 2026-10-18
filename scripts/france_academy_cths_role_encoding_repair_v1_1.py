#!/usr/bin/env python3
"""Correct CTHS society source double mojibake; re-triage membership without admission.

Input v1 is immutable. Output v1_1 is a *candidate-role ledger*, never a
definitive full membership or exact-DOB source. Original HTML sha stays tracked.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from ftfy import fix_text
from france_academy_cths_society_roster_v1 import parse_roster

RULE_VERSION = "france-academy-cths-society-role-encoding-repair-v1_1"
MIN_YEAR, MAX_YEAR = 1835, 1985

def fold(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(c))

def read_csv(path: Path) -> list[dict[str,str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def write_csv(path:Path, rows:list[dict],fields:list[str]) -> None:
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

FOREIGN = re.compile(
    r"\b(?:associee?\s+etrangere?|membre\s+(?:associee?\s+|correspondante?\s+)?etrangere?|"
    r"correspondante?\s+etrangere?)\b"
)
CORRESPONDENT = re.compile(r"\bcorrespondante?\b")
FULL = re.compile(
    r"\b(?:academicien(?:ne)?(?:\s+libre)?|membre\s+libre|membre\s+(?:non[- ]residant|residant|titulaire)|"
    r"membre\b(?!\s+(?:associee?|correspondante?|etrangere?)))"
)

def role(phrase: str) -> tuple[str,str]:
    s = fold(phrase)
    foreign = bool(FOREIGN.search(s))
    correspondent = bool(CORRESPONDENT.search(s))
    full = bool(FULL.search(s))
    if full and foreign:
        return "full_and_foreign_mixed_manual", "Full-like and foreign role both present; historical transitions require adjudication"
    if full and correspondent:
        return "correspondent_then_full_candidate", "Both corresponding and full-like memberships"
    if full:
        return "full_like_only_candidate", "Full-like role mentioned, pending independent evidence"
    if correspondent and foreign:
        return "foreign_corresponding_only_candidate", "No full-like role mentioned"
    if foreign:
        return "foreign_only_candidate", "No full-like role mentioned"
    if correspondent:
        return "correspondent_only_candidate", "No full-like role mentioned"
    return "unresolved_membership_type", "Role word absent/unrecognized"

def selftest() -> None:
    cases = [
        ("(1835-1910) - correspondant étranger (section d'anatomie) 1887, membre associé étranger 1904-1910","foreign_corresponding_only_candidate"),
        ("(1914-2011) - Académicien libre 1973, Membre étranger section de physique 1976-2011","full_and_foreign_mixed_manual"),
        ("(1921-2007) - Membre associé étranger dans la section de biologie moléculaire","foreign_only_candidate"),
        ("(1933- ) - membre 1995","full_like_only_candidate"),
        ("(1948- ) - correspondant 1990, membre 1991","correspondent_then_full_candidate"),
        ("(1806-1886) - Membre correspondant étranger section de minéralogie","foreign_corresponding_only_candidate"),
        ("(1936-2022) - Correspondant dans la section de Biologie moléculaire et cellulaire","correspondent_only_candidate"),
        ("(1810-1897) - correspondant 1852 ; membre 1867 ; président 1892","correspondent_then_full_candidate"),
        ("(1883-1960) - Membre, 1921","full_like_only_candidate"),
    ]
    for note, expected in cases:
        got=role(note)[0]
        if got!=expected: raise AssertionError((note,expected,got))
    assert fix_text("gÃ©ographie") == "géographie"
    assert fix_text("Membre Ã©tranger") == "Membre étranger"

def main():
    selftest()
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-folder",default="data/france_academy_cths_society_roster_v1")
    ap.add_argument("--out-folder",default="data/france_academy_cths_society_role_repair_v1_1")
    args=ap.parse_args()
    source=Path(args.source_folder)
    out=Path(args.out_folder);out.mkdir(parents=True,exist_ok=True)
    input_path=source/"cths_academy_society_membership_candidates_v1.csv"
    input_bytes=input_path.read_bytes()
    original_summary=json.loads((source/'summary.json').read_text(encoding='utf-8'))
    source_snapshot=source/'raw_html'/(original_summary['source_html_sha256']+'.html')
    # The source is mixed/invalid UTF-8 despite a UTF-8 HTML meta tag. Decode as
    # cp1252 with replacement of the rare undefined bytes; ftfy repairs fieldwise.
    # Never use BeautifulSoup's probabilistic charset guess (produced ÃĐtranger).
    people, roster_parse_audit=parse_roster(source_snapshot.read_bytes().decode('cp1252',errors='replace'))
    fixed=[]
    for p in people:
        note=fix_text(p["membership_note_raw"])
        name=fix_text(p["name_raw"])
        newrole,rationale=role(note)
        yr=p["birth_year_lifespan_candidate"].strip()
        birthyear=int(yr) if yr.isdigit() else None
        in_window=(MIN_YEAR<=birthyear<=MAX_YEAR) if birthyear is not None else False
        fixed.append({
            "cths_person_id":p["cths_person_id"],
            "cths_profile_url":p["cths_profile_url"],
            "name_fixed":name,
            "membership_note_fixed":note,
            "birth_year_lifespan_candidate":yr,
            "in_birthyear_window_candidate_only":int(in_window),
            "status_source_text_candidate":newrole,
            "status_conservative_reason":rationale,
            "original_role_tag_v1":p["cths_status_candidate"],
            "name_text_changed":int(name != p["name_raw"]),
            "membership_text_changed":int(note != p["membership_note_raw"]),
            "status_classification_changed":int(newrole != p["cths_status_candidate"]),
            "full_member_accepted":0,
            "exact_dob_accepted":0,
        })
    if len(fixed)!=2144 or len({x["cths_person_id"] for x in fixed})!=2144:
        raise RuntimeError("Frozen v1 CTHS roster row count/uniqueness changed unexpectedly")
    by_id={r["cths_person_id"]:r for r in fixed}
    original={p["name_fixed"]:p for p in fixed}
    expected_names={
        "ABICH Hermann":"foreign_corresponding_only_candidate",
        "ABRAGAM Anatole":"full_and_foreign_mixed_manual",
        "AGASSIZ Alexandre":"foreign_corresponding_only_candidate",
        "BENZER Seymour":"foreign_only_candidate",
        "BALIAN Roger":"full_like_only_candidate",
        "BISMUT Jean-Michel":"correspondent_then_full_candidate",
        "ASCHER Philippe":"correspondent_only_candidate",
    }
    problems=[]
    for name,cls in expected_names.items():
        if name not in original:
            problems.append("missing "+name)
        elif original[name]["status_source_text_candidate"]!=cls:
            problems.append(name+" got "+original[name]["status_source_text_candidate"]+" expected "+cls)
    if problems: raise RuntimeError("Known example validation: "+" | ".join(problems))
    keys=list(fixed[0])
    write_csv(out/"cths_academy_membership_candidates_corrected_v1_1.csv",fixed,keys)
    review=[p for p in fixed if p["status_source_text_candidate"] in (
        "full_and_foreign_mixed_manual","unresolved_membership_type")]
    write_csv(out/"mixed_foreign_unresolved_manual_review_v1_1.csv",review,keys)
    report={
        "rule_version":RULE_VERSION,
        "source_v1_sha256_csv":hashlib.sha256(input_bytes).hexdigest(),
        "source_html_sha256":original_summary["source_html_sha256"],
        "source_decoding_strategy":"cp1252_then_ftfy_fix_text_per_field",
        "source_raw_roster_parse_audit":roster_parse_audit,
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "input_people":len(people),
        "fixed_name_strings":sum(r["name_text_changed"] for r in fixed),
        "fixed_membership_note_strings":sum(r["membership_text_changed"] for r in fixed),
        "classification_candidate_counts":dict(Counter(r["status_source_text_candidate"] for r in fixed)),
        "candidate_birthyears_inside_1835_1985":sum(r["in_birthyear_window_candidate_only"] for r in fixed),
        "mixed_or_unresolved_review_rows":len(review),
        "advertised_cths_members":2177,
        "extracted_unique_cths_profile_links":2144,
        "advertised_minus_extracted":33,
        "remaining_gap_state":"unresolved; do not assert these 33 are excluded/nonexistent until separately audited",
        "full_membership_accepted":0,
        "exact_dobs_accepted":0,
        "bazi_variables_computed":0,
        "source_warning":"CTHS metadata is secondary, dates may borrow Wiki; use official membership status and independent DOB provenance before cohort inclusion. Historical mixed role must be manually inspected.",
    }
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
