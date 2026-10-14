#!/usr/bin/env python3
"""Resolve the five frozen Leopoldina official-profile/P569-candidate mismatches.

This is an offline, versioned closeout overlay. It does not rewrite any prior
candidate, verification, or official-profile file and performs no BaZi
calculation. Wrong-entity or invalid-crosswalk candidate records are preserved
as exclusions; corrected dates are applied only in the new closeout outputs.

Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

VERSION = "leopoldina-manual-adjudication-closeout-v1"
FROZEN_DATE = "2026-10-14"
YEAR_MIN = 1835
YEAR_MAX = 1985

EXPECTED = {
    "upstream_candidate_rows": 2407,
    "upstream_accepted_candidates": 721,
    "upstream_unresolved_candidates": 1686,
    "upstream_official_only": 52,
    "upstream_combined": 773,
    "upstream_mismatch_holds": 5,
    "decision_rows": 5,
    "accepted_candidate_rows": 724,
    "unresolved_candidate_rows": 1681,
    "excluded_invalid_candidate_rows": 2,
    "official_only_accepted_rows": 54,
    "combined_accepted_rows": 778,
    "remaining_mismatch_holds": 0,
    "automatic_acceptance_rows": 668,
    "manual_or_prior_explicit_acceptance_rows": 110,
    "candidate_date_corrections_total": 3,
    "new_candidate_date_corrections": 2,
    "identity_or_crosswalk_exclusions": 2,
}

EXPECTED_DECISIONS = {
    "candidate:Q15734524:1925-01-25": {
        "member_slug": "felix-eckstein",
        "candidate_exact_dob": "1925-01-25",
        "official_exact_dob": "1964-06-20",
        "adjudicated_exact_dob": "1964-06-20",
        "candidate_action": "exclude_candidate_wrong_person",
        "official_record_action": "accept_official_record_without_qid",
    },
    "candidate:Q61748241:1959-04-30": {
        "member_slug": "bernd-fleischmann",
        "candidate_exact_dob": "1959-04-30",
        "official_exact_dob": "1958-06-22",
        "adjudicated_exact_dob": "1958-06-22",
        "candidate_action": "exclude_candidate_crosswalk_invalid",
        "official_record_action": "accept_official_record_without_qid",
    },
    "candidate:Q16064079:1970-08-11": {
        "member_slug": "eicke-latz",
        "candidate_exact_dob": "1970-08-11",
        "official_exact_dob": "1970-07-11",
        "adjudicated_exact_dob": "1970-08-11",
        "candidate_action": "accept_candidate_retain_date",
        "official_record_action": "do_not_add_separate_official_record",
    },
    "candidate:Q55806710:1962-06-16": {
        "member_slug": "stefanie-ritz-timme",
        "candidate_exact_dob": "1962-06-16",
        "official_exact_dob": "1962-06-13",
        "adjudicated_exact_dob": "1962-06-13",
        "candidate_action": "accept_candidate_with_date_overlay",
        "official_record_action": "do_not_add_separate_official_record",
    },
    "candidate:Q21166426:1950-01-11": {
        "member_slug": "garret-a-fitzgerald",
        "candidate_exact_dob": "1950-01-11",
        "official_exact_dob": "1950-05-11",
        "adjudicated_exact_dob": "1950-05-11",
        "candidate_action": "accept_candidate_with_date_overlay",
        "official_record_action": "do_not_add_separate_official_record",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        if not rows:
            raise RuntimeError(f"Cannot infer columns for empty CSV: {path}")
        fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def append_group(raw: str, group: str) -> str:
    values = [x for x in str(raw or "").split("|") if x]
    if group and group not in values:
        values.append(group)
    return "|".join(values)


def validate_iso_date(value: str) -> None:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise RuntimeError(f"Not an ISO exact date: {value!r}")
    y, m, d = (int(x) for x in value.split("-"))
    if not (1 <= m <= 12 and 1 <= d <= 31 and YEAR_MIN <= y <= YEAR_MAX):
        raise RuntimeError(f"Date outside closeout constraints: {value!r}")


def self_test() -> None:
    assert append_group("", "a") == "a"
    assert append_group("a|b", "a") == "a|b"
    assert append_group("a|b", "c") == "a|b|c"
    assert EXPECTED["accepted_candidate_rows"] + EXPECTED["unresolved_candidate_rows"] + EXPECTED["excluded_invalid_candidate_rows"] == EXPECTED["upstream_candidate_rows"]
    assert EXPECTED["accepted_candidate_rows"] + EXPECTED["official_only_accepted_rows"] == EXPECTED["combined_accepted_rows"]
    for value in ("1925-01-25", "1964-06-20", "1958-06-22", "1970-08-11", "1962-06-13", "1950-05-11"):
        validate_iso_date(value)
    print("Leopoldina manual adjudication closeout v1 self-test OK")


def require_files(paths: dict[str, Path]) -> None:
    missing = [f"{k}: {p}" for k, p in paths.items() if not p.exists()]
    if missing:
        raise RuntimeError("Missing required inputs:\n" + "\n".join(missing))


def validate_decisions(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if len(rows) != EXPECTED["decision_rows"]:
        raise RuntimeError(f"Expected {EXPECTED['decision_rows']} mismatch decisions, got {len(rows)}")
    by_key: dict[str, dict[str, str]] = {}
    for r in rows:
        key = r["candidate_record_key"]
        if key in by_key:
            raise RuntimeError(f"Duplicate mismatch decision key: {key}")
        by_key[key] = r
        if r.get("resolution_status") != "resolved_manual":
            raise RuntimeError(f"Decision is not frozen as resolved_manual: {key}")
        if r.get("automatic_acceptance") != "0" or r.get("bazi_variables_computed") != "0":
            raise RuntimeError(f"Decision violates manual/no-BaZi rule: {key}")
    if set(by_key) != set(EXPECTED_DECISIONS):
        raise RuntimeError(f"Decision-key set differs from frozen expectation: {sorted(by_key)}")
    for key, expected in EXPECTED_DECISIONS.items():
        actual = by_key[key]
        for field, value in expected.items():
            if actual.get(field) != value:
                raise RuntimeError(f"Decision mismatch for {key} field {field}: {actual.get(field)!r} != {value!r}")
        for field in ("candidate_exact_dob", "official_exact_dob", "adjudicated_exact_dob"):
            validate_iso_date(actual[field])
    return by_key


def candidate_combined_row(r: dict[str, str]) -> dict:
    return {
        "record_key": r["candidate_record_key"],
        "record_origin": "adjudicated_candidate",
        "member_slug": r["member_slug"],
        "display_name": r["display_name"],
        "wikidata_qid": r["wikidata_qid"],
        "class": "",
        "section": "",
        "election_year": "",
        "final_exact_dob": r["final_exact_dob"],
        "acceptance_status": r["acceptance_status"],
        "acceptance_route": r["acceptance_route"],
        "decision_mode": r["decision_mode"],
        "source_url": "",
        "source_page": "",
        "automatic_acceptance": r["automatic_acceptance"],
        "primary_birthyear_eligible": 1,
        "prior_frozen_input_modified": 0,
        "bazi_variables_computed": 0,
    }


def run(args: argparse.Namespace) -> dict:
    freeze = Path(args.freeze_final)
    official_master_path = Path(args.official_master)
    decisions_path = Path(args.decisions)
    addendum_path = Path(args.domain_addendum)
    out = Path(args.out)

    paths = {
        "upstream_summary": freeze / "summary.json",
        "upstream_candidates": freeze / "candidate_final_dob_adjudication_v1.csv",
        "upstream_official_only": freeze / "official_only_accepted_dobs_v1.csv",
        "upstream_combined": freeze / "accepted_exact_dob_combined_primary_v1.csv",
        "upstream_mismatch": freeze / "official_master_candidate_mismatch_review_v1.csv",
        "upstream_domain_registry": freeze / "manual_source_domain_registry_v1.csv",
        "upstream_policy_categories": freeze / "manual_source_policy_categories_v1.csv",
        "upstream_archive_exceptions": freeze / "archive_exceptions_v1.csv",
        "upstream_conflicts": freeze / "conflict_adjudications_v1.csv",
        "upstream_evidence_ledger": freeze / "manual_source_evidence_ledger_v1.csv",
        "upstream_missingness": freeze / "manual_followup_missingness_freeze_v1.json",
        "upstream_rules": freeze / "final_dob_adjudication_rules_v1.json",
        "official_master": official_master_path,
        "decisions": decisions_path,
        "domain_addendum": addendum_path,
    }
    require_files(paths)

    upstream_summary = json.loads(paths["upstream_summary"].read_text(encoding="utf-8"))
    expected_upstream = {
        "candidate_adjudication_rows": EXPECTED["upstream_candidate_rows"],
        "accepted_candidate_rows": EXPECTED["upstream_accepted_candidates"],
        "unresolved_candidate_rows": EXPECTED["upstream_unresolved_candidates"],
        "official_only_accepted_primary_rows": EXPECTED["upstream_official_only"],
        "accepted_exact_dob_combined_primary_rows": EXPECTED["upstream_combined"],
        "official_candidate_mismatch_holds": EXPECTED["upstream_mismatch_holds"],
    }
    for field, value in expected_upstream.items():
        if int(upstream_summary.get(field, -1)) != value:
            raise RuntimeError(f"Unexpected upstream summary {field}: {upstream_summary.get(field)!r} != {value}")

    decisions = read_csv(decisions_path)
    decision_by_key = validate_decisions(decisions)
    decision_by_slug = {r["member_slug"]: r for r in decisions}
    if len(decision_by_slug) != len(decisions):
        raise RuntimeError("Mismatch decisions must be unique by member_slug")

    candidate_rows = read_csv(paths["upstream_candidates"])
    if len(candidate_rows) != EXPECTED["upstream_candidate_rows"]:
        raise RuntimeError("Unexpected upstream candidate-row count")
    candidate_fields = list(candidate_rows[0].keys())
    candidate_keys = {r["candidate_record_key"] for r in candidate_rows}
    if not set(decision_by_key).issubset(candidate_keys):
        raise RuntimeError("A frozen decision key is absent from candidate adjudication input")

    official_master = read_csv(official_master_path)
    official_by_slug: dict[str, list[dict[str, str]]] = {}
    for r in official_master:
        official_by_slug.setdefault(r["member_slug"], []).append(r)
    for slug, d in decision_by_slug.items():
        matches = [r for r in official_by_slug.get(slug, []) if r["candidate_dob"] == d["official_exact_dob"]]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one exact official-master row for {slug}, got {len(matches)}")

    resolved_candidates: list[dict] = []
    for original in candidate_rows:
        r = dict(original)
        d = decision_by_key.get(r["candidate_record_key"])
        if d:
            action = d["candidate_action"]
            r["automatic_acceptance"] = "0"
            r["prior_frozen_input_modified"] = "0"
            r["bazi_variables_computed"] = "0"
            if action in {"exclude_candidate_wrong_person", "exclude_candidate_crosswalk_invalid"}:
                r["final_evidence_status"] = "excluded_invalid_identity_or_crosswalk"
                r["conflict_status"] = "resolved_exclude_invalid_candidate"
                r["acceptance_route"] = "excluded_invalid_candidate_record"
                r["decision_mode"] = "manual_adjudication"
                r["acceptance_status"] = "excluded_invalid_candidate_record"
                r["adjudicated_exact_dob"] = ""
                r["final_exact_dob"] = ""
            elif action == "accept_candidate_retain_date":
                r["final_evidence_status"] = "tier_a_positive"
                r["targeted_manual_groups"] = append_group(r["targeted_manual_groups"], "uni_bonn_iii")
                r["conflict_status"] = "resolved_retain_candidate"
                r["acceptance_route"] = "manual_official_mismatch_resolved"
                r["decision_mode"] = "manual_adjudication"
                r["acceptance_status"] = "accepted_exact_dob"
                r["adjudicated_exact_dob"] = ""
                r["final_exact_dob"] = d["adjudicated_exact_dob"]
            elif action == "accept_candidate_with_date_overlay":
                r["final_evidence_status"] = "tier_a_positive"
                r["targeted_manual_groups"] = append_group(r["targeted_manual_groups"], "leopoldina_official_new_member_profile")
                r["conflict_status"] = "resolved_replace_candidate"
                r["acceptance_route"] = "manual_official_mismatch_corrected_overlay"
                r["decision_mode"] = "manual_adjudication"
                r["acceptance_status"] = "accepted_exact_dob"
                r["adjudicated_exact_dob"] = d["adjudicated_exact_dob"]
                r["final_exact_dob"] = d["adjudicated_exact_dob"]
            else:
                raise RuntimeError(f"Unsupported frozen candidate action: {action}")
        resolved_candidates.append(r)

    accepted_candidates = [r for r in resolved_candidates if r["acceptance_status"] == "accepted_exact_dob"]
    excluded_candidates = [r for r in resolved_candidates if r["acceptance_status"] == "excluded_invalid_candidate_record"]
    unresolved_candidates = [r for r in resolved_candidates if r["acceptance_status"] not in {"accepted_exact_dob", "excluded_invalid_candidate_record"}]
    if len(accepted_candidates) != EXPECTED["accepted_candidate_rows"]:
        raise RuntimeError(f"Accepted candidate rows {len(accepted_candidates)} != {EXPECTED['accepted_candidate_rows']}")
    if len(unresolved_candidates) != EXPECTED["unresolved_candidate_rows"]:
        raise RuntimeError(f"Unresolved candidate rows {len(unresolved_candidates)} != {EXPECTED['unresolved_candidate_rows']}")
    if len(excluded_candidates) != EXPECTED["excluded_invalid_candidate_rows"]:
        raise RuntimeError(f"Excluded candidate rows {len(excluded_candidates)} != {EXPECTED['excluded_invalid_candidate_rows']}")

    # Prior official-only records plus two official records whose candidate joins were invalid.
    official_only = [dict(r) for r in read_csv(paths["upstream_official_only"])]
    combined_fields = list(official_only[0].keys())
    new_official_records: list[dict] = []
    for d in decisions:
        if d["official_record_action"] != "accept_official_record_without_qid":
            continue
        o = [r for r in official_by_slug[d["member_slug"]] if r["candidate_dob"] == d["official_exact_dob"]][0]
        new_official_records.append({
            "record_key": f"official:{o['member_slug']}:{o['election_year']}:{o['candidate_dob']}",
            "record_origin": d["accepted_record_origin"],
            "member_slug": o["member_slug"],
            "display_name": o["display_name"],
            "wikidata_qid": d["accepted_wikidata_qid"],
            "class": o["class"],
            "section": o["section"],
            "election_year": o["election_year"],
            "final_exact_dob": d["adjudicated_exact_dob"],
            "acceptance_status": "accepted_exact_dob",
            "acceptance_route": d["accepted_record_origin"],
            "decision_mode": "manual_adjudication",
            "source_url": o["pdf_url"],
            "source_page": o["pdf_page"],
            "automatic_acceptance": 0,
            "primary_birthyear_eligible": 1,
            "prior_frozen_input_modified": 0,
            "bazi_variables_computed": 0,
        })
    official_only.extend(new_official_records)
    official_only.sort(key=lambda x: (x["final_exact_dob"], x["member_slug"], x["record_key"]))
    if len(official_only) != EXPECTED["official_only_accepted_rows"]:
        raise RuntimeError(f"Official-only rows {len(official_only)} != {EXPECTED['official_only_accepted_rows']}")

    combined = [candidate_combined_row(r) for r in accepted_candidates] + official_only
    combined.sort(key=lambda x: (x["final_exact_dob"], x["member_slug"], x["record_key"]))
    combined_keys = [r["record_key"] for r in combined]
    if len(combined_keys) != len(set(combined_keys)):
        raise RuntimeError("Duplicate accepted combined record_key")
    if len(combined) != EXPECTED["combined_accepted_rows"]:
        raise RuntimeError(f"Combined accepted rows {len(combined)} != {EXPECTED['combined_accepted_rows']}")
    if sum(int(r["automatic_acceptance"]) for r in combined) != EXPECTED["automatic_acceptance_rows"]:
        raise RuntimeError("Automatic acceptance total changed unexpectedly")

    # Resolve the old mismatch hold table without erasing its original values.
    old_mismatches = read_csv(paths["upstream_mismatch"])
    if len(old_mismatches) != EXPECTED["upstream_mismatch_holds"]:
        raise RuntimeError("Unexpected upstream mismatch-hold row count")
    resolved_review: list[dict] = []
    for old in old_mismatches:
        d = decision_by_slug[old["member_slug"]]
        resolved_review.append({
            **old,
            "hold_type": "resolved_manual_no_remaining_hold",
            "decision": d["resolution_type"],
            "final_exact_dob": d["adjudicated_exact_dob"],
            "resolution_id": d["resolution_id"],
            "resolution_status": d["resolution_status"],
            "candidate_action": d["candidate_action"],
            "official_record_action": d["official_record_action"],
            "automatic_acceptance": 0,
            "bazi_variables_computed": 0,
        })

    # Versioned correction overlay includes the prior Rudolf Benedikt correction plus two new corrections.
    correction_rows: list[dict] = []
    for r in resolved_candidates:
        if r["adjudicated_exact_dob"] and r["adjudicated_exact_dob"] != r["candidate_exact_dob_original"]:
            d = decision_by_key.get(r["candidate_record_key"])
            correction_rows.append({
                "candidate_record_key": r["candidate_record_key"],
                "member_slug": r["member_slug"],
                "wikidata_qid": r["wikidata_qid"],
                "old_candidate_exact_dob": r["candidate_exact_dob_original"],
                "adjudicated_exact_dob": r["adjudicated_exact_dob"],
                "resolution_source": d["resolution_id"] if d else "upstream_conflict_adjudication_v1",
                "resolution_status": "applied_in_versioned_overlay",
                "prior_frozen_input_modified": 0,
                "automatic_acceptance": 0,
                "bazi_variables_computed": 0,
            })
    correction_rows.sort(key=lambda x: x["member_slug"])
    if len(correction_rows) != EXPECTED["candidate_date_corrections_total"]:
        raise RuntimeError(f"Candidate corrections {len(correction_rows)} != {EXPECTED['candidate_date_corrections_total']}")

    exclusion_rows: list[dict] = []
    for r in excluded_candidates:
        d = decision_by_key[r["candidate_record_key"]]
        exclusion_rows.append({
            "candidate_record_key": r["candidate_record_key"],
            "member_slug": r["member_slug"],
            "wikidata_qid": r["wikidata_qid"],
            "candidate_exact_dob": r["candidate_exact_dob_original"],
            "exclusion_reason": d["resolution_type"],
            "replacement_official_exact_dob": d["adjudicated_exact_dob"],
            "replacement_record_origin": d["accepted_record_origin"],
            "resolution_id": d["resolution_id"],
            "resolution_status": "excluded_from_candidate_analysis_preserved_as_provenance",
            "prior_frozen_input_modified": 0,
            "automatic_acceptance": 0,
            "bazi_variables_computed": 0,
        })

    # Append two newly frozen official named-person source mappings.
    base_domains = read_csv(paths["upstream_domain_registry"])
    addenda = read_csv(addendum_path)
    base_ids = {r["mapping_id"] for r in base_domains}
    source_labels = {
        "uni_bonn_iii_named_person_cv_v1": "Institute of Innate Immunity official named-person CV",
        "uni_bonn_for926_named_person_cv_v1": "University of Bonn official CV",
    }
    domain_rows = [dict(r) for r in base_domains]
    for a in addenda:
        if a["mapping_id"] in base_ids:
            raise RuntimeError(f"Domain addendum mapping already exists: {a['mapping_id']}")
        if a["policy_category_id"] != "official_institution_named_person_record_v1" or a["policy_tier"] != "A":
            raise RuntimeError(f"Unexpected domain addendum category/tier: {a['mapping_id']}")
        domain_rows.append({
            "mapping_id": a["mapping_id"],
            "domain_or_source_family": a["domain_or_source_family"],
            "source_label": source_labels[a["mapping_id"]],
            "policy_category_id": a["policy_category_id"],
            "policy_tier": a["policy_tier"],
            "single_source_sufficient": a["single_source_sufficient"],
            "independence_group": a["independence_group"],
            "decision": "include",
            "decision_basis": "official_master_mismatch_adjudication_v1",
            "conflict_override": "yes",
            "decision_status": a["decision_status"],
            "frozen_date": a["frozen_date"],
        })
    if len({r["mapping_id"] for r in domain_rows}) != len(domain_rows):
        raise RuntimeError("Duplicate mapping_id in closeout domain registry")

    # Closeout rules explicitly cover wrong-entity/crosswalk exclusions and overlay corrections.
    rules = json.loads(paths["upstream_rules"].read_text(encoding="utf-8"))
    rules["dataset"] = "leopoldina-final-dob-adjudication-rules-v1-1"
    rules["closeout_additions"] = [
        "A frozen official/candidate mismatch may be resolved only by an explicit person-level adjudication row.",
        "A wrong-entity or invalid-crosswalk candidate is excluded from candidate analysis and preserved as provenance; a verified official member record may be accepted without assigning an unverified replacement QID.",
        "Candidate date corrections are applied only through versioned overlays; the superseded candidate value remains in provenance.",
        "No remaining official/candidate mismatch is silently merged by member_slug alone.",
    ]
    rules["remaining_official_candidate_mismatch_holds"] = 0
    rules["prior_inputs_modified"] = 0
    rules["bazi_variables_computed"] = 0

    missingness = json.loads(paths["upstream_missingness"].read_text(encoding="utf-8"))
    missingness["dataset"] = "leopoldina-manual-followup-missingness-freeze-v1-1"
    missingness["closeout_status"] = "complete"
    missingness["remaining_official_candidate_mismatch_holds"] = 0
    missingness["open_ended_person_search_allowed"] = 0

    out.mkdir(parents=True, exist_ok=True)
    # Immutable decision/policy ledgers copied into the closeout output.
    shutil.copy2(paths["upstream_policy_categories"], out / "manual_source_policy_categories_v1.csv")
    shutil.copy2(paths["upstream_archive_exceptions"], out / "archive_exceptions_v1.csv")
    shutil.copy2(paths["upstream_conflicts"], out / "conflict_adjudications_v1.csv")
    shutil.copy2(paths["upstream_evidence_ledger"], out / "manual_source_evidence_ledger_v1.csv")
    shutil.copy2(decisions_path, out / "official_master_mismatch_adjudications_v1.csv")
    shutil.copy2(addendum_path, out / "manual_source_domain_registry_addendum_v1.csv")

    write_csv(out / "manual_source_domain_registry_v1_1.csv", domain_rows)
    write_json(out / "final_dob_adjudication_rules_v1_1.json", rules)
    write_json(out / "manual_followup_missingness_freeze_v1_1.json", missingness)
    write_csv(out / "official_master_candidate_mismatch_review_v1_1.csv", resolved_review)
    write_csv(out / "candidate_dob_correction_overlay_v1_1.csv", correction_rows)
    write_csv(out / "excluded_invalid_candidate_records_v1.csv", exclusion_rows)
    write_csv(out / "candidate_final_dob_adjudication_v1_1.csv", resolved_candidates, candidate_fields)
    write_csv(out / "accepted_candidate_dobs_v1_1.csv", accepted_candidates, candidate_fields)
    write_csv(out / "unresolved_candidate_dobs_v1_1.csv", unresolved_candidates, candidate_fields)
    write_csv(out / "official_only_accepted_dobs_v1_1.csv", official_only, combined_fields)
    write_csv(out / "accepted_exact_dob_combined_primary_v1_1.csv", combined, combined_fields)

    final_status_counts = Counter(r["final_evidence_status"] for r in resolved_candidates)
    route_counts = Counter(r["acceptance_route"] for r in accepted_candidates)
    official_route_counts = Counter(r["acceptance_route"] for r in official_only)
    auto_count = sum(int(r["automatic_acceptance"]) for r in combined)
    summary = {
        "dataset": VERSION,
        "frozen_date": FROZEN_DATE,
        "primary_birthyear_window": [YEAR_MIN, YEAR_MAX],
        "candidate_adjudication_rows": len(resolved_candidates),
        "candidate_final_evidence_status_counts": dict(sorted(final_status_counts.items())),
        "accepted_candidate_rows": len(accepted_candidates),
        "unresolved_candidate_rows": len(unresolved_candidates),
        "excluded_invalid_candidate_rows": len(excluded_candidates),
        "candidate_partition_complete": int(len(accepted_candidates) + len(unresolved_candidates) + len(excluded_candidates) == len(resolved_candidates)),
        "accepted_candidate_route_counts": dict(sorted(route_counts.items())),
        "official_only_accepted_primary_rows": len(official_only),
        "official_only_route_counts": dict(sorted(official_route_counts.items())),
        "accepted_exact_dob_combined_primary_rows": len(combined),
        "official_candidate_mismatch_rows_resolved": len(decisions),
        "official_candidate_mismatch_holds_remaining": 0,
        "candidate_date_corrections_total": len(correction_rows),
        "candidate_date_corrections_added_in_closeout": EXPECTED["new_candidate_date_corrections"],
        "identity_or_crosswalk_candidate_exclusions": len(exclusion_rows),
        "archive_exceptions": len(read_csv(paths["upstream_archive_exceptions"])),
        "archive_exception_states": dict(Counter(r["exception_class"] for r in read_csv(paths["upstream_archive_exceptions"]))),
        "manual_followup_closed": 1,
        "open_ended_person_search_allowed": 0,
        "prior_frozen_inputs_modified": 0,
        "final_exact_dob_written_in_new_overlay": len(combined),
        "automatic_acceptance_rows": auto_count,
        "manual_or_prior_explicit_acceptance_rows": len(combined) - auto_count,
        "bazi_variables_computed": 0,
        "warning": "Versioned closeout overlay only. Wrong-entity/crosswalk candidate records are excluded rather than silently reassigned; all superseded dates and source conflicts remain in provenance. No prior frozen file was rewritten.",
        "input_sha256": {k: sha256(v) for k, v in paths.items() if v.is_file()},
    }
    for field, expected in {
        "accepted_candidate_rows": EXPECTED["accepted_candidate_rows"],
        "unresolved_candidate_rows": EXPECTED["unresolved_candidate_rows"],
        "excluded_invalid_candidate_rows": EXPECTED["excluded_invalid_candidate_rows"],
        "official_only_accepted_primary_rows": EXPECTED["official_only_accepted_rows"],
        "accepted_exact_dob_combined_primary_rows": EXPECTED["combined_accepted_rows"],
        "automatic_acceptance_rows": EXPECTED["automatic_acceptance_rows"],
        "manual_or_prior_explicit_acceptance_rows": EXPECTED["manual_or_prior_explicit_acceptance_rows"],
        "candidate_date_corrections_total": EXPECTED["candidate_date_corrections_total"],
        "identity_or_crosswalk_candidate_exclusions": EXPECTED["identity_or_crosswalk_exclusions"],
    }.items():
        if int(summary[field]) != expected:
            raise RuntimeError(f"Closeout invariant failed for {field}: {summary[field]} != {expected}")
    write_json(out / "summary.json", summary)

    output_files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {
        "dataset": VERSION,
        "frozen_date": FROZEN_DATE,
        "script_version": VERSION,
        "files": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in output_files},
        "invariants": EXPECTED,
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze-final", default="data/leopoldina_manual_adjudication_freeze_v1/final")
    p.add_argument("--official-master", default="data/leopoldina_manual_adjudication_freeze_v1/input_snapshots/accepted_exact_dob_2009_2019_v1.csv")
    p.add_argument("--decisions", default="data/leopoldina_manual_adjudication_closeout_v1/official_master_mismatch_adjudications_v1.csv")
    p.add_argument("--domain-addendum", default="data/leopoldina_manual_adjudication_closeout_v1/manual_source_domain_registry_addendum_v1.csv")
    p.add_argument("--out", default="data/leopoldina_manual_adjudication_closeout_v1/final")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, KeyError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
