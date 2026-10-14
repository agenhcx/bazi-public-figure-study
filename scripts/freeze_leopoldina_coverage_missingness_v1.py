#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_VERSION = "leopoldina-coverage-missingness-freeze-v1"
BUILDER_REVISION = "member-qid-provenance-hotfix-v1.1"
FROZEN_DATE = "2026-10-14"
SOURCE_CLOSEOUT_TAG = "leopoldina-manual-dob-closeout-v1"
PRIMARY_BIRTHYEAR_MIN = 1835
PRIMARY_BIRTHYEAR_MAX = 1985
EXPECTED_ROSTER_ROWS = 2888
EXPECTED_CANDIDATE_ROWS = 2407
EXPECTED_ACCEPTED_CANDIDATE_ROWS = 724
EXPECTED_UNRESOLVED_CANDIDATE_ROWS = 1681
EXPECTED_EXCLUDED_CANDIDATE_ROWS = 2
EXPECTED_OFFICIAL_ONLY_ROWS = 54
EXPECTED_ACCEPTED_COMBINED_ROWS = 778
EXPECTED_AUTOMATIC_ACCEPTED_ROWS = 668
EXPECTED_MANUAL_ACCEPTED_ROWS = 110
EXPECTED_ACCEPTED_ROWS_WITHOUT_VERIFIED_QID = 54
EXPECTED_EXCLUDED_QID_PROVENANCE_ROWS = 2
EXPECTED_CLASS_COUNTS = {
    "Class I: Mathematics, Natural Sciences and Engineering": 1131,
    "Class II: Life Sciences": 946,
    "Class III: Medicine": 811,
}
EXPECTED_DECEASED_ROWS = 1527
EXPECTED_NONDECEASED_ROWS = 1361

DEFAULT_ROSTER = Path(
    "data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv"
)
DEFAULT_ROSTER_META = Path("data/leopoldina_roster_freeze_v1.json")
DEFAULT_CLOSEOUT = Path("data/leopoldina_manual_adjudication_closeout_v1/final")
DEFAULT_OUT = Path("data/leopoldina_coverage_missingness_freeze_v1")

CANDIDATE_FILE = "candidate_final_dob_adjudication_v1_1.csv"
ACCEPTED_FILE = "accepted_exact_dob_combined_primary_v1_1.csv"
OFFICIAL_ONLY_FILE = "official_only_accepted_dobs_v1_1.csv"
UNRESOLVED_FILE = "unresolved_candidate_dobs_v1_1.csv"
EXCLUDED_FILE = "excluded_invalid_candidate_records_v1.csv"
CLOSEOUT_SUMMARY_FILE = "summary.json"
CLOSEOUT_MANIFEST_FILE = "manifest.json"

OUTPUT_FILES = [
    "member_level_primary_window_coverage_v1.csv",
    "coverage_overall_v1.csv",
    "coverage_by_class_v1.csv",
    "coverage_by_section_v1.csv",
    "coverage_by_deceased_status_v1.csv",
    "coverage_by_election_era_v1.csv",
    "coverage_by_election_decade_v1.csv",
    "coverage_by_class_election_era_v1.csv",
    "candidate_acceptance_by_birth_year_v1.csv",
    "candidate_acceptance_by_birth_decade_v1.csv",
    "accepted_primary_by_birth_year_v1.csv",
    "accepted_primary_by_birth_decade_v1.csv",
    "accepted_route_counts_v1.csv",
    "candidate_evidence_status_counts_v1.csv",
    "edge_case_audit_v1.csv",
    "summary.json",
    "README.md",
]


class FreezeError(RuntimeError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FreezeError(f"Missing input CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FreezeError(f"Missing input JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def as_int(value: Any, *, default: int | None = None) -> int | None:
    s = str(value if value is not None else "").strip()
    if not s:
        return default
    try:
        return int(s)
    except ValueError as exc:
        raise FreezeError(f"Expected integer, got {value!r}") from exc


def bool01(value: Any) -> int:
    s = str(value if value is not None else "").strip().casefold()
    return int(s in {"1", "true", "yes", "y"})


def parse_iso_date(value: str, *, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except Exception as exc:
        raise FreezeError(f"Invalid ISO date in {field}: {value!r}") from exc


def ratio(n: int, d: int) -> str:
    return "" if d == 0 else f"{n / d:.6f}"


def pct(n: int, d: int) -> str:
    return "" if d == 0 else f"{100.0 * n / d:.3f}"


def election_era(year: int) -> str:
    if year <= 1900:
        return "<=1900"
    if year <= 1950:
        return "1901-1950"
    if year <= 2000:
        return "1951-2000"
    return "2001-2025"


def decade_label(year: int) -> str:
    return f"{(year // 10) * 10}s"


def sorted_group_values(values: Iterable[str]) -> list[str]:
    def key(v: str) -> tuple[int, int, str]:
        if v == "<=1900":
            return (0, 0, v)
        if v == "1901-1950":
            return (0, 1, v)
        if v == "1951-2000":
            return (0, 2, v)
        if v == "2001-2025":
            return (0, 3, v)
        if v.endswith("s") and v[:-1].isdigit():
            return (1, int(v[:-1]), v)
        return (2, 0, v.casefold())

    return sorted(set(values), key=key)


def require_fields(rows: Sequence[Mapping[str, str]], fields: Sequence[str], label: str) -> None:
    if not rows:
        raise FreezeError(f"{label} has no rows")
    missing = [f for f in fields if f not in rows[0]]
    if missing:
        raise FreezeError(f"{label} missing required columns: {missing}")


def unique_map(rows: Sequence[dict[str, str]], key_field: str, label: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    duplicates: list[str] = []
    for row in rows:
        key = row.get(key_field, "").strip()
        if not key:
            raise FreezeError(f"{label} has blank {key_field}")
        if key in out:
            duplicates.append(key)
        out[key] = row
    if duplicates:
        raise FreezeError(f"{label} duplicate {key_field}: {sorted(set(duplicates))[:10]}")
    return out


def closeout_manifest_hash_check(closeout: Path, manifest: Mapping[str, Any], filename: str) -> None:
    entry = manifest.get("files", {}).get(filename)
    if not entry:
        raise FreezeError(f"Closeout manifest lacks {filename}")
    actual = sha256_file(closeout / filename)
    expected = str(entry.get("sha256", ""))
    if actual != expected:
        raise FreezeError(
            f"Closeout input hash mismatch for {filename}: expected {expected}, got {actual}"
        )


def candidate_outcome(row: Mapping[str, str]) -> str:
    acceptance = row.get("acceptance_status", "").strip()
    evidence = row.get("final_evidence_status", "").strip()
    if acceptance == "accepted_exact_dob":
        return "accepted_candidate"
    if acceptance.startswith("unresolved"):
        return "unresolved_candidate"
    if evidence == "excluded_invalid_identity_or_crosswalk":
        return "excluded_candidate"
    raise FreezeError(
        "Unrecognized candidate outcome for "
        f"{row.get('member_slug')}: acceptance_status={acceptance!r}, "
        f"final_evidence_status={evidence!r}"
    )


def accepted_origin_category(row: Mapping[str, str]) -> str:
    origin = row.get("record_origin", "").strip()
    if origin == "adjudicated_candidate":
        return "candidate"
    return "official_only"


def member_missingness_state(
    candidate: Mapping[str, str] | None,
    accepted: Mapping[str, str] | None,
) -> str:
    c_outcome = candidate_outcome(candidate) if candidate else "no_candidate"
    if accepted:
        origin = accepted_origin_category(accepted)
        if origin == "candidate" and c_outcome == "accepted_candidate":
            return "accepted_candidate_primary"
        if origin == "official_only" and c_outcome == "excluded_candidate":
            return "accepted_official_after_candidate_exclusion"
        if origin == "official_only" and c_outcome == "unresolved_candidate":
            return "accepted_official_over_unresolved_candidate"
        if origin == "official_only" and c_outcome == "no_candidate":
            return "accepted_official_only_primary"
        raise FreezeError(
            f"Inconsistent accepted/candidate state: origin={origin}, candidate={c_outcome}"
        )
    if c_outcome == "unresolved_candidate":
        return "unresolved_primary_candidate"
    if c_outcome == "excluded_candidate":
        return "excluded_candidate_without_official_acceptance"
    if c_outcome == "no_candidate":
        return "no_primary_candidate_or_official_acceptance"
    raise FreezeError("Accepted candidate row is missing from accepted combined table")


def build_member_rows(
    roster_rows: Sequence[dict[str, str]],
    candidates: Mapping[str, dict[str, str]],
    accepted: Mapping[str, dict[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, r in enumerate(roster_rows, 1):
        slug = r["member_slug"].strip()
        c = candidates.get(slug)
        a = accepted.get(slug)
        state = member_missingness_state(c, a)
        ey = as_int(r.get("election_year"))
        if ey is None:
            raise FreezeError(f"Roster row lacks election_year: {slug}")
        final_dob = a.get("final_exact_dob", "").strip() if a else ""
        candidate_dob = c.get("candidate_exact_dob_original", "").strip() if c else ""
        final_year = parse_iso_date(final_dob, field="final_exact_dob").year if final_dob else None
        candidate_year = (
            parse_iso_date(candidate_dob, field="candidate_exact_dob_original").year
            if candidate_dob
            else None
        )
        accepted_flag = int(a is not None)
        candidate_flag = int(c is not None)
        candidate_out = candidate_outcome(c) if c else "no_candidate"
        candidate_qid = c.get("wikidata_qid", "").strip() if c else ""
        accepted_qid = a.get("wikidata_qid", "").strip() if a else ""
        # The unified analysis QID must never inherit a QID from a candidate
        # explicitly excluded for wrong identity or invalid crosswalk. Preserve
        # that value only in candidate_wikidata_qid for provenance.
        analysis_qid = accepted_qid or (candidate_qid if candidate_out != "excluded_candidate" else "")
        automatic = bool01(a.get("automatic_acceptance", "0")) if a else 0
        row = {
            "roster_row_number": i,
            "roster_record_key": f"roster:{slug}",
            "member_slug": slug,
            "display_name": r.get("display_name", ""),
            "class": r.get("class", ""),
            "section": r.get("section", ""),
            "election_year": ey,
            "election_era": election_era(ey),
            "election_decade": decade_label(ey),
            "deceased_marker": str(bool01(r.get("deceased_marker", "0"))),
            "candidate_record_present": candidate_flag,
            "candidate_record_key": c.get("candidate_record_key", "") if c else "",
            "candidate_wikidata_qid": candidate_qid,
            "accepted_wikidata_qid": accepted_qid,
            "wikidata_qid": analysis_qid,
            "candidate_exact_dob_original": candidate_dob,
            "candidate_birth_year": candidate_year if candidate_year is not None else "",
            "candidate_birth_decade": decade_label(candidate_year) if candidate_year is not None else "",
            "candidate_final_evidence_status": c.get("final_evidence_status", "") if c else "",
            "candidate_outcome": candidate_out,
            "candidate_acceptance_route": c.get("acceptance_route", "") if c else "",
            "candidate_decision_mode": c.get("decision_mode", "") if c else "",
            "candidate_conflict_status": c.get("conflict_status", "") if c else "",
            "official_new_member_same_date_overlay": c.get("official_new_member_same_date_overlay", "") if c else "",
            "archive_exception": c.get("archive_exception", "") if c else "",
            "accepted_primary_exact_dob": accepted_flag,
            "accepted_record_key": a.get("record_key", "") if a else "",
            "accepted_record_origin": a.get("record_origin", "") if a else "",
            "final_exact_dob": final_dob,
            "final_birth_year": final_year if final_year is not None else "",
            "final_birth_decade": decade_label(final_year) if final_year is not None else "",
            "accepted_acceptance_route": a.get("acceptance_route", "") if a else "",
            "accepted_decision_mode": a.get("decision_mode", "") if a else "",
            "automatic_acceptance": automatic,
            "manual_or_prior_explicit_acceptance": int(accepted_flag and not automatic),
            "member_missingness_state": state,
            "age_at_election_from_candidate_year": ey - candidate_year if candidate_year is not None else "",
            "age_at_election_from_final_year": ey - final_year if final_year is not None else "",
            "primary_analysis_included": accepted_flag,
            "bazi_variables_computed": 0,
        }
        out.append(row)
    return out


MEMBER_FIELDS = [
    "roster_row_number",
    "roster_record_key",
    "member_slug",
    "display_name",
    "class",
    "section",
    "election_year",
    "election_era",
    "election_decade",
    "deceased_marker",
    "candidate_record_present",
    "candidate_record_key",
    "candidate_wikidata_qid",
    "accepted_wikidata_qid",
    "wikidata_qid",
    "candidate_exact_dob_original",
    "candidate_birth_year",
    "candidate_birth_decade",
    "candidate_final_evidence_status",
    "candidate_outcome",
    "candidate_acceptance_route",
    "candidate_decision_mode",
    "candidate_conflict_status",
    "official_new_member_same_date_overlay",
    "archive_exception",
    "accepted_primary_exact_dob",
    "accepted_record_key",
    "accepted_record_origin",
    "final_exact_dob",
    "final_birth_year",
    "final_birth_decade",
    "accepted_acceptance_route",
    "accepted_decision_mode",
    "automatic_acceptance",
    "manual_or_prior_explicit_acceptance",
    "member_missingness_state",
    "age_at_election_from_candidate_year",
    "age_at_election_from_final_year",
    "primary_analysis_included",
    "bazi_variables_computed",
]


COVERAGE_FIELDS = [
    "stratum_type",
    "stratum_value",
    "roster_n",
    "accepted_primary_n",
    "accepted_primary_rate",
    "accepted_primary_percent",
    "accepted_candidate_n",
    "accepted_official_only_n",
    "automatic_acceptance_n",
    "manual_or_prior_explicit_acceptance_n",
    "candidate_universe_n",
    "candidate_accepted_n",
    "candidate_unresolved_n",
    "candidate_excluded_n",
    "candidate_acceptance_rate_all",
    "candidate_acceptance_percent_all",
    "candidate_acceptance_rate_excluding_invalid",
    "candidate_acceptance_percent_excluding_invalid",
    "no_primary_candidate_or_official_acceptance_n",
    "bazi_variables_computed",
]


def summarize_member_group(
    rows: Sequence[Mapping[str, Any]], stratum_type: str, stratum_value: str
) -> dict[str, Any]:
    n = len(rows)
    accepted_n = sum(int(r["accepted_primary_exact_dob"]) for r in rows)
    candidate_n = sum(int(r["candidate_record_present"]) for r in rows)
    c_acc = sum(r["candidate_outcome"] == "accepted_candidate" for r in rows)
    c_unres = sum(r["candidate_outcome"] == "unresolved_candidate" for r in rows)
    c_excl = sum(r["candidate_outcome"] == "excluded_candidate" for r in rows)
    denom_valid = candidate_n - c_excl
    official_only_n = sum(
        int(r["accepted_primary_exact_dob"])
        and r["accepted_record_origin"] != "adjudicated_candidate"
        for r in rows
    )
    return {
        "stratum_type": stratum_type,
        "stratum_value": stratum_value,
        "roster_n": n,
        "accepted_primary_n": accepted_n,
        "accepted_primary_rate": ratio(accepted_n, n),
        "accepted_primary_percent": pct(accepted_n, n),
        "accepted_candidate_n": accepted_n - official_only_n,
        "accepted_official_only_n": official_only_n,
        "automatic_acceptance_n": sum(int(r["automatic_acceptance"]) for r in rows),
        "manual_or_prior_explicit_acceptance_n": sum(
            int(r["manual_or_prior_explicit_acceptance"]) for r in rows
        ),
        "candidate_universe_n": candidate_n,
        "candidate_accepted_n": c_acc,
        "candidate_unresolved_n": c_unres,
        "candidate_excluded_n": c_excl,
        "candidate_acceptance_rate_all": ratio(c_acc, candidate_n),
        "candidate_acceptance_percent_all": pct(c_acc, candidate_n),
        "candidate_acceptance_rate_excluding_invalid": ratio(c_acc, denom_valid),
        "candidate_acceptance_percent_excluding_invalid": pct(c_acc, denom_valid),
        "no_primary_candidate_or_official_acceptance_n": sum(
            r["member_missingness_state"] == "no_primary_candidate_or_official_acceptance"
            for r in rows
        ),
        "bazi_variables_computed": 0,
    }


def grouped_member_summary(
    rows: Sequence[Mapping[str, Any]], field: str, stratum_type: str
) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field, ""))].append(row)
    return [
        summarize_member_group(groups[value], stratum_type, value)
        for value in sorted_group_values(groups)
    ]


def grouped_member_summary_two_fields(
    rows: Sequence[Mapping[str, Any]], field1: str, field2: str, stratum_type: str
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row.get(field1, "")), str(row.get(field2, "")))].append(row)
    out: list[dict[str, Any]] = []
    era_order = {"<=1900": 0, "1901-1950": 1, "1951-2000": 2, "2001-2025": 3}
    for v1, v2 in sorted(groups, key=lambda x: (x[0].casefold(), era_order.get(x[1], 99), x[1])):
        rec = summarize_member_group(groups[(v1, v2)], stratum_type, f"{v1} | {v2}")
        rec["stratum_value_1"] = v1
        rec["stratum_value_2"] = v2
        out.append(rec)
    return out


def candidate_temporal_rows(
    candidates: Sequence[dict[str, str]],
    roster_by_slug: Mapping[str, dict[str, str]],
    *,
    by_decade: bool,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for c in candidates:
        d = parse_iso_date(c["candidate_exact_dob_original"], field="candidate_exact_dob_original")
        key = decade_label(d.year) if by_decade else str(d.year)
        groups[key].append(c)
    keys = sorted_group_values(groups) if by_decade else [str(y) for y in range(PRIMARY_BIRTHYEAR_MIN, PRIMARY_BIRTHYEAR_MAX + 1)]
    out: list[dict[str, Any]] = []
    for key in keys:
        rr = groups.get(key, [])
        acc = sum(candidate_outcome(x) == "accepted_candidate" for x in rr)
        unres = sum(candidate_outcome(x) == "unresolved_candidate" for x in rr)
        excl = sum(candidate_outcome(x) == "excluded_candidate" for x in rr)
        valid = len(rr) - excl
        out.append(
            {
                "birth_time_bin": key,
                "candidate_n": len(rr),
                "accepted_n": acc,
                "unresolved_n": unres,
                "excluded_invalid_n": excl,
                "acceptance_rate_all": ratio(acc, len(rr)),
                "acceptance_percent_all": pct(acc, len(rr)),
                "acceptance_rate_excluding_invalid": ratio(acc, valid),
                "acceptance_percent_excluding_invalid": pct(acc, valid),
                "deceased_marker_n": sum(
                    bool01(roster_by_slug[x["member_slug"]].get("deceased_marker", "0")) for x in rr
                ),
                "bazi_variables_computed": 0,
            }
        )
    return out


TEMPORAL_CANDIDATE_FIELDS = [
    "birth_time_bin",
    "candidate_n",
    "accepted_n",
    "unresolved_n",
    "excluded_invalid_n",
    "acceptance_rate_all",
    "acceptance_percent_all",
    "acceptance_rate_excluding_invalid",
    "acceptance_percent_excluding_invalid",
    "deceased_marker_n",
    "bazi_variables_computed",
]


def accepted_temporal_rows(
    accepted_rows: Sequence[dict[str, str]], *, by_decade: bool
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in accepted_rows:
        d = parse_iso_date(row["final_exact_dob"], field="final_exact_dob")
        key = decade_label(d.year) if by_decade else str(d.year)
        groups[key].append(row)
    keys = sorted_group_values(groups) if by_decade else [str(y) for y in range(PRIMARY_BIRTHYEAR_MIN, PRIMARY_BIRTHYEAR_MAX + 1)]
    out: list[dict[str, Any]] = []
    for key in keys:
        rr = groups.get(key, [])
        out.append(
            {
                "birth_time_bin": key,
                "accepted_primary_n": len(rr),
                "accepted_candidate_n": sum(r["record_origin"] == "adjudicated_candidate" for r in rr),
                "accepted_official_only_n": sum(r["record_origin"] != "adjudicated_candidate" for r in rr),
                "automatic_acceptance_n": sum(bool01(r.get("automatic_acceptance", "0")) for r in rr),
                "manual_or_prior_explicit_acceptance_n": sum(
                    not bool01(r.get("automatic_acceptance", "0")) for r in rr
                ),
                "bazi_variables_computed": 0,
            }
        )
    return out


TEMPORAL_ACCEPTED_FIELDS = [
    "birth_time_bin",
    "accepted_primary_n",
    "accepted_candidate_n",
    "accepted_official_only_n",
    "automatic_acceptance_n",
    "manual_or_prior_explicit_acceptance_n",
    "bazi_variables_computed",
]


def count_table(rows: Sequence[Mapping[str, Any]], field: str, count_field_name: str) -> list[dict[str, Any]]:
    counts = Counter(str(r.get(field, "")) for r in rows)
    total = sum(counts.values())
    return [
        {
            field: key,
            count_field_name: counts[key],
            "share": ratio(counts[key], total),
            "percent": pct(counts[key], total),
            "bazi_variables_computed": 0,
        }
        for key in sorted_group_values(counts)
    ]


def edge_audit(
    member_rows: Sequence[Mapping[str, Any]],
    candidates: Sequence[dict[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_slug = {r["member_slug"]: r for r in member_rows}
    for row in member_rows:
        slug = str(row["member_slug"])
        final_year = as_int(row.get("final_birth_year"))
        if final_year is not None and not (PRIMARY_BIRTHYEAR_MIN <= final_year <= PRIMARY_BIRTHYEAR_MAX):
            out.append(
                {
                    "audit_type": "accepted_birthyear_outside_primary_window",
                    "severity": "error",
                    "member_slug": slug,
                    "display_name": row.get("display_name", ""),
                    "observed_value": final_year,
                    "note": "Accepted primary record falls outside the frozen 1835-1985 window.",
                }
            )
        age = as_int(row.get("age_at_election_from_final_year"))
        if age is not None and not (15 <= age <= 110):
            out.append(
                {
                    "audit_type": "accepted_age_at_election_outside_15_110",
                    "severity": "review",
                    "member_slug": slug,
                    "display_name": row.get("display_name", ""),
                    "observed_value": age,
                    "note": "Year-only age approximation; inspect before any temporal model.",
                }
            )
        c_age = as_int(row.get("age_at_election_from_candidate_year"))
        if c_age is not None and not (15 <= c_age <= 110):
            out.append(
                {
                    "audit_type": "candidate_age_at_election_outside_15_110",
                    "severity": "review",
                    "member_slug": slug,
                    "display_name": row.get("display_name", ""),
                    "observed_value": c_age,
                    "note": "Candidate-year diagnostic only; unresolved dates remain excluded.",
                }
            )
        if row["member_missingness_state"] == "accepted_official_after_candidate_exclusion":
            out.append(
                {
                    "audit_type": "candidate_excluded_official_record_accepted",
                    "severity": "documented_resolution",
                    "member_slug": slug,
                    "display_name": row.get("display_name", ""),
                    "observed_value": row.get("final_exact_dob", ""),
                    "note": "Wrong-identity/crosswalk candidate preserved as excluded provenance; official record accepted separately.",
                }
            )
    for c in candidates:
        original = c.get("candidate_exact_dob_original", "")
        final = c.get("final_exact_dob", "")
        if c.get("acceptance_status") == "accepted_exact_dob" and original and final and original != final:
            r = by_slug[c["member_slug"]]
            out.append(
                {
                    "audit_type": "accepted_versioned_dob_overlay",
                    "severity": "documented_resolution",
                    "member_slug": c["member_slug"],
                    "display_name": r.get("display_name", ""),
                    "observed_value": f"{original} -> {final}",
                    "note": "Superseded date remains in provenance; final date was applied only through the frozen overlay.",
                }
            )
    return sorted(out, key=lambda r: (r["severity"], r["audit_type"], r["member_slug"]))


EDGE_FIELDS = [
    "audit_type",
    "severity",
    "member_slug",
    "display_name",
    "observed_value",
    "note",
]


def validate_canonical_counts(
    roster_rows: Sequence[dict[str, str]],
    candidate_rows: Sequence[dict[str, str]],
    accepted_rows: Sequence[dict[str, str]],
    official_only_rows: Sequence[dict[str, str]],
    unresolved_rows: Sequence[dict[str, str]],
    excluded_rows: Sequence[dict[str, str]],
    closeout_summary: Mapping[str, Any],
    roster_meta: Mapping[str, Any],
) -> None:
    checks = {
        "roster_rows": (len(roster_rows), EXPECTED_ROSTER_ROWS),
        "candidate_rows": (len(candidate_rows), EXPECTED_CANDIDATE_ROWS),
        "accepted_combined_rows": (len(accepted_rows), EXPECTED_ACCEPTED_COMBINED_ROWS),
        "official_only_rows": (len(official_only_rows), EXPECTED_OFFICIAL_ONLY_ROWS),
        "unresolved_rows": (len(unresolved_rows), EXPECTED_UNRESOLVED_CANDIDATE_ROWS),
        "excluded_rows": (len(excluded_rows), EXPECTED_EXCLUDED_CANDIDATE_ROWS),
        "summary_candidate_rows": (
            int(closeout_summary.get("candidate_adjudication_rows", -1)),
            EXPECTED_CANDIDATE_ROWS,
        ),
        "summary_accepted_combined": (
            int(closeout_summary.get("accepted_exact_dob_combined_primary_rows", -1)),
            EXPECTED_ACCEPTED_COMBINED_ROWS,
        ),
        "summary_official_only": (
            int(closeout_summary.get("official_only_accepted_primary_rows", -1)),
            EXPECTED_OFFICIAL_ONLY_ROWS,
        ),
        "roster_meta_rows": (int(roster_meta.get("roster_rows", -1)), EXPECTED_ROSTER_ROWS),
    }
    bad = {k: v for k, v in checks.items() if v[0] != v[1]}
    if bad:
        raise FreezeError(f"Canonical count invariant failed: {bad}")

    class_counts = Counter(r["class"] for r in roster_rows)
    if dict(class_counts) != EXPECTED_CLASS_COUNTS:
        raise FreezeError(f"Roster class counts changed: {dict(class_counts)}")
    deceased = sum(bool01(r.get("deceased_marker", "0")) for r in roster_rows)
    if deceased != EXPECTED_DECEASED_ROWS or len(roster_rows) - deceased != EXPECTED_NONDECEASED_ROWS:
        raise FreezeError(
            f"Roster deceased-status counts changed: deceased={deceased}, nondeceased={len(roster_rows)-deceased}"
        )


def build_pipeline(
    roster_path: Path,
    roster_meta_path: Path,
    closeout: Path,
    out_dir: Path,
    *,
    canonical: bool,
) -> dict[str, Any]:
    roster_meta = read_json(roster_meta_path)
    closeout_summary = read_json(closeout / CLOSEOUT_SUMMARY_FILE)
    closeout_manifest = read_json(closeout / CLOSEOUT_MANIFEST_FILE)

    roster_rows = read_csv(roster_path)
    candidate_rows = read_csv(closeout / CANDIDATE_FILE)
    accepted_rows = read_csv(closeout / ACCEPTED_FILE)
    official_only_rows = read_csv(closeout / OFFICIAL_ONLY_FILE)
    unresolved_rows = read_csv(closeout / UNRESOLVED_FILE)
    excluded_rows = read_csv(closeout / EXCLUDED_FILE)

    require_fields(
        roster_rows,
        ["member_slug", "display_name", "class", "section", "election_year", "deceased_marker"],
        "roster",
    )
    require_fields(
        candidate_rows,
        [
            "candidate_record_key",
            "member_slug",
            "candidate_exact_dob_original",
            "final_evidence_status",
            "acceptance_status",
            "final_exact_dob",
            "automatic_acceptance",
            "bazi_variables_computed",
        ],
        "candidate adjudication",
    )
    require_fields(
        accepted_rows,
        [
            "record_key",
            "record_origin",
            "member_slug",
            "final_exact_dob",
            "acceptance_status",
            "acceptance_route",
            "decision_mode",
            "automatic_acceptance",
            "primary_birthyear_eligible",
            "bazi_variables_computed",
        ],
        "accepted combined",
    )

    if canonical:
        expected_roster_sha = roster_meta.get("checksums", {}).get("roster_csv_sha256", "")
        actual_roster_sha = sha256_file(roster_path)
        if actual_roster_sha != expected_roster_sha:
            raise FreezeError(
                f"Frozen roster hash mismatch: expected {expected_roster_sha}, got {actual_roster_sha}"
            )
        for filename in [
            CANDIDATE_FILE,
            ACCEPTED_FILE,
            OFFICIAL_ONLY_FILE,
            UNRESOLVED_FILE,
            EXCLUDED_FILE,
            CLOSEOUT_SUMMARY_FILE,
        ]:
            closeout_manifest_hash_check(closeout, closeout_manifest, filename)
        validate_canonical_counts(
            roster_rows,
            candidate_rows,
            accepted_rows,
            official_only_rows,
            unresolved_rows,
            excluded_rows,
            closeout_summary,
            roster_meta,
        )

    roster_by_slug = unique_map(roster_rows, "member_slug", "roster")
    candidate_by_slug = unique_map(candidate_rows, "member_slug", "candidate adjudication")
    accepted_by_slug = unique_map(accepted_rows, "member_slug", "accepted combined")
    official_only_by_slug = unique_map(official_only_rows, "member_slug", "official-only")
    unique_map(accepted_rows, "record_key", "accepted combined record keys")
    unique_map(candidate_rows, "candidate_record_key", "candidate record keys")

    missing_candidate_roster = sorted(set(candidate_by_slug) - set(roster_by_slug))
    missing_accepted_roster = sorted(set(accepted_by_slug) - set(roster_by_slug))
    missing_official_roster = sorted(set(official_only_by_slug) - set(roster_by_slug))
    if missing_candidate_roster or missing_accepted_roster or missing_official_roster:
        raise FreezeError(
            "Roster join failed: "
            f"candidate={missing_candidate_roster[:5]}, "
            f"accepted={missing_accepted_roster[:5]}, "
            f"official_only={missing_official_roster[:5]}"
        )

    for label, rows_to_check in [
        ("candidate adjudication", candidate_rows),
        ("accepted combined", accepted_rows),
        ("official-only accepted", official_only_rows),
        ("unresolved candidates", unresolved_rows),
        ("excluded candidates", excluded_rows),
    ]:
        for row in rows_to_check:
            if bool01(row.get("bazi_variables_computed", "0")) != 0:
                raise FreezeError(f"{label} contains bazi_variables_computed=1 for {row.get('member_slug', '')}")
            if bool01(row.get("prior_frozen_input_modified", "0")) != 0:
                raise FreezeError(f"{label} contains prior_frozen_input_modified=1 for {row.get('member_slug', '')}")

    for a in accepted_rows:
        d = parse_iso_date(a["final_exact_dob"], field="final_exact_dob")
        if not (PRIMARY_BIRTHYEAR_MIN <= d.year <= PRIMARY_BIRTHYEAR_MAX):
            raise FreezeError(f"Accepted DOB outside primary window: {a['record_key']} {d}")
        if a["acceptance_status"] != "accepted_exact_dob":
            raise FreezeError(f"Accepted table has nonaccepted row: {a['record_key']}")
        if bool01(a.get("primary_birthyear_eligible", "0")) != 1:
            raise FreezeError(f"Accepted table has ineligible row: {a['record_key']}")
        if bool01(a.get("bazi_variables_computed", "0")) != 0:
            raise FreezeError(f"BaZi variable flag is nonzero: {a['record_key']}")

    member_rows = build_member_rows(roster_rows, candidate_by_slug, accepted_by_slug)

    excluded_qid_leaks = [
        r for r in member_rows
        if r["candidate_outcome"] == "excluded_candidate"
        and str(r.get("wikidata_qid", "")).strip()
        and str(r.get("wikidata_qid", "")).strip() == str(r.get("candidate_wikidata_qid", "")).strip()
        and str(r.get("wikidata_qid", "")).strip() != str(r.get("accepted_wikidata_qid", "")).strip()
    ]
    if excluded_qid_leaks:
        raise FreezeError(
            "Excluded candidate QID leaked into analysis identity for: "
            + ", ".join(str(r["member_slug"]) for r in excluded_qid_leaks[:10])
        )

    accepted_without_verified_qid = sum(
        int(r["accepted_primary_exact_dob"]) and not str(r.get("wikidata_qid", "")).strip()
        for r in member_rows
    )
    excluded_qid_provenance_rows = sum(
        r["candidate_outcome"] == "excluded_candidate"
        and bool(str(r.get("candidate_wikidata_qid", "")).strip())
        and not bool(str(r.get("wikidata_qid", "")).strip())
        for r in member_rows
    )

    accepted_candidate_n = sum(candidate_outcome(c) == "accepted_candidate" for c in candidate_rows)
    unresolved_n = sum(candidate_outcome(c) == "unresolved_candidate" for c in candidate_rows)
    excluded_n = sum(candidate_outcome(c) == "excluded_candidate" for c in candidate_rows)
    automatic_n = sum(bool01(a.get("automatic_acceptance", "0")) for a in accepted_rows)
    manual_n = len(accepted_rows) - automatic_n

    if canonical:
        invariants = {
            "accepted_candidate_n": (accepted_candidate_n, EXPECTED_ACCEPTED_CANDIDATE_ROWS),
            "unresolved_n": (unresolved_n, EXPECTED_UNRESOLVED_CANDIDATE_ROWS),
            "excluded_n": (excluded_n, EXPECTED_EXCLUDED_CANDIDATE_ROWS),
            "automatic_n": (automatic_n, EXPECTED_AUTOMATIC_ACCEPTED_ROWS),
            "manual_n": (manual_n, EXPECTED_MANUAL_ACCEPTED_ROWS),
            "accepted_without_verified_qid": (
                accepted_without_verified_qid, EXPECTED_ACCEPTED_ROWS_WITHOUT_VERIFIED_QID
            ),
            "excluded_qid_provenance_rows": (
                excluded_qid_provenance_rows, EXPECTED_EXCLUDED_QID_PROVENANCE_ROWS
            ),
        }
        bad = {k: v for k, v in invariants.items() if v[0] != v[1]}
        if bad:
            raise FreezeError(f"Closeout invariant failed: {bad}")

    overall = [summarize_member_group(member_rows, "overall", "all")]
    by_class = grouped_member_summary(member_rows, "class", "class")
    by_section = grouped_member_summary(member_rows, "section", "section")
    by_deceased = grouped_member_summary(member_rows, "deceased_marker", "deceased_marker")
    by_era = grouped_member_summary(member_rows, "election_era", "election_era")
    by_decade = grouped_member_summary(member_rows, "election_decade", "election_decade")
    by_class_era = grouped_member_summary_two_fields(
        member_rows, "class", "election_era", "class_x_election_era"
    )

    candidate_by_year = candidate_temporal_rows(
        candidate_rows, roster_by_slug, by_decade=False
    )
    candidate_by_decade = candidate_temporal_rows(
        candidate_rows, roster_by_slug, by_decade=True
    )
    accepted_by_year = accepted_temporal_rows(accepted_rows, by_decade=False)
    accepted_by_decade = accepted_temporal_rows(accepted_rows, by_decade=True)
    route_counts = count_table(accepted_rows, "acceptance_route", "accepted_n")
    evidence_counts = count_table(candidate_rows, "final_evidence_status", "candidate_n")
    edges = edge_audit(member_rows, candidate_rows)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(out_dir / OUTPUT_FILES[0], member_rows, MEMBER_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[1], overall, COVERAGE_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[2], by_class, COVERAGE_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[3], by_section, COVERAGE_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[4], by_deceased, COVERAGE_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[5], by_era, COVERAGE_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[6], by_decade, COVERAGE_FIELDS)
    write_csv(
        out_dir / OUTPUT_FILES[7],
        by_class_era,
        ["stratum_value_1", "stratum_value_2"] + COVERAGE_FIELDS,
    )
    write_csv(out_dir / OUTPUT_FILES[8], candidate_by_year, TEMPORAL_CANDIDATE_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[9], candidate_by_decade, TEMPORAL_CANDIDATE_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[10], accepted_by_year, TEMPORAL_ACCEPTED_FIELDS)
    write_csv(out_dir / OUTPUT_FILES[11], accepted_by_decade, TEMPORAL_ACCEPTED_FIELDS)
    write_csv(
        out_dir / OUTPUT_FILES[12],
        route_counts,
        ["acceptance_route", "accepted_n", "share", "percent", "bazi_variables_computed"],
    )
    write_csv(
        out_dir / OUTPUT_FILES[13],
        evidence_counts,
        ["final_evidence_status", "candidate_n", "share", "percent", "bazi_variables_computed"],
    )
    write_csv(out_dir / OUTPUT_FILES[14], edges, EDGE_FIELDS)

    official_overlap = set(candidate_by_slug) & set(official_only_by_slug)
    candidate_or_official_union = set(candidate_by_slug) | set(official_only_by_slug)
    no_candidate_or_official = len(roster_rows) - len(candidate_or_official_union)
    state_counts = Counter(r["member_missingness_state"] for r in member_rows)
    edge_counts = Counter(r["audit_type"] for r in edges)

    summary = {
        "dataset": SCRIPT_VERSION,
        "builder_revision": BUILDER_REVISION,
        "frozen_date": FROZEN_DATE,
        "source_closeout_tag": SOURCE_CLOSEOUT_TAG,
        "primary_birthyear_window": [PRIMARY_BIRTHYEAR_MIN, PRIMARY_BIRTHYEAR_MAX],
        "universe_definitions": {
            "roster_universe": "All 2,888 frozen Leopoldina Class I-III members elected through 2025.",
            "candidate_universe": "The 2,407 exact-day P569 candidates inside the 1835-1985 birthyear window, before evidence acceptance.",
            "accepted_primary_universe": "The 778 final exact-DOB records accepted inside the 1835-1985 window after the frozen closeout overlay.",
        },
        "counts": {
            "roster_rows": len(roster_rows),
            "candidate_adjudication_rows": len(candidate_rows),
            "accepted_candidate_rows": accepted_candidate_n,
            "unresolved_candidate_rows": unresolved_n,
            "excluded_invalid_candidate_rows": excluded_n,
            "official_only_accepted_rows": len(official_only_rows),
            "official_only_rows_overlapping_candidate_universe": len(official_overlap),
            "candidate_or_official_primary_evidence_union_members": len(candidate_or_official_union),
            "roster_members_without_primary_candidate_or_official_acceptance_record": no_candidate_or_official,
            "accepted_exact_dob_combined_primary_rows": len(accepted_rows),
            "automatic_acceptance_rows": automatic_n,
            "manual_or_prior_explicit_acceptance_rows": manual_n,
        },
        "rates": {
            "accepted_primary_inclusion_rate_full_roster": float(ratio(len(accepted_rows), len(roster_rows))),
            "accepted_primary_inclusion_percent_full_roster": float(pct(len(accepted_rows), len(roster_rows))),
            "candidate_acceptance_rate_all_candidates": float(ratio(accepted_candidate_n, len(candidate_rows))),
            "candidate_acceptance_percent_all_candidates": float(pct(accepted_candidate_n, len(candidate_rows))),
            "candidate_acceptance_rate_excluding_invalid_crosswalks": float(
                ratio(accepted_candidate_n, len(candidate_rows) - excluded_n)
            ),
            "candidate_acceptance_percent_excluding_invalid_crosswalks": float(
                pct(accepted_candidate_n, len(candidate_rows) - excluded_n)
            ),
        },
        "member_missingness_state_counts": dict(sorted(state_counts.items())),
        "edge_case_audit_counts": dict(sorted(edge_counts.items())),
        "qid_provenance_counts": {
            "accepted_primary_rows_with_verified_wikidata_qid": len(accepted_rows) - accepted_without_verified_qid,
            "accepted_primary_rows_without_verified_wikidata_qid": accepted_without_verified_qid,
            "excluded_candidate_qids_preserved_only_in_candidate_wikidata_qid": excluded_qid_provenance_rows,
            "excluded_candidate_qid_leaks_into_analysis_wikidata_qid": len(excluded_qid_leaks),
        },
        "stratifications_frozen": [
            "class",
            "section",
            "deceased_marker",
            "election_era: <=1900, 1901-1950, 1951-2000, 2001-2025",
            "election_decade",
            "class x election_era",
            "candidate birth year and birth decade",
            "accepted birth year and birth decade (descriptive numerator only)",
            "acceptance route",
            "candidate final evidence status",
        ],
        "interpretation_guardrail": (
            "The 778/2888 quantity is the accepted primary-window inclusion rate, not an all-years DOB availability rate. "
            "Members without an accepted 1835-1985 exact DOB include unresolved in-window candidates, people with no exact-day candidate, "
            "and potentially people outside the primary birthyear window."
        ),
        "candidate_missingness_guardrail": (
            "Candidate acceptance rates condition on entering the exact-day P569 candidate universe and therefore do not measure full-roster DOB coverage."
        ),
        "inferential_tests_run": 0,
        "missingness_model_fit": 0,
        "bazi_variables_computed": 0,
        "prior_frozen_inputs_modified": 0,
        "open_ended_person_search_allowed": 0,
        "input_sha256": {
            "roster_csv": sha256_file(roster_path),
            "roster_metadata": sha256_file(roster_meta_path),
            "closeout_summary": sha256_file(closeout / CLOSEOUT_SUMMARY_FILE),
            "closeout_manifest": sha256_file(closeout / CLOSEOUT_MANIFEST_FILE),
            "candidate_adjudication": sha256_file(closeout / CANDIDATE_FILE),
            "accepted_combined": sha256_file(closeout / ACCEPTED_FILE),
            "official_only_accepted": sha256_file(closeout / OFFICIAL_ONLY_FILE),
            "unresolved_candidates": sha256_file(closeout / UNRESOLVED_FILE),
            "excluded_candidates": sha256_file(closeout / EXCLUDED_FILE),
        },
    }
    write_json(out_dir / "summary.json", summary)

    readme = f"""# Leopoldina coverage and missingness freeze v1

Frozen: {FROZEN_DATE}

Source DOB closeout tag: `{SOURCE_CLOSEOUT_TAG}`

## Purpose

This layer freezes descriptive coverage and missingness diagnostics before any
Leopoldina BaZi variables are computed or any hierarchy outcome is inspected.
It does not reopen DOB collection and does not alter prior frozen inputs.

## Three distinct universes

1. **Roster universe**: {len(roster_rows):,} official Class I-III members elected through 2025.
2. **Candidate universe**: {len(candidate_rows):,} exact-day P569 candidates in the 1835-1985 birthyear window.
3. **Accepted primary universe**: {len(accepted_rows):,} accepted exact DOBs in the same birthyear window.

The full-roster accepted-primary inclusion rate is **{pct(len(accepted_rows), len(roster_rows))}%**.
This is not an all-years DOB availability rate. The candidate evidence acceptance
rate is **{pct(accepted_candidate_n, len(candidate_rows))}%** and conditions on
having entered the exact-day candidate universe.

## Frozen counts

- Accepted candidate rows: {accepted_candidate_n:,}
- Unresolved candidate rows: {unresolved_n:,}
- Excluded invalid identity/crosswalk rows: {excluded_n:,}
- Accepted official-only rows: {len(official_only_rows):,}
- Automatic acceptances: {automatic_n:,}
- Manual or prior explicit acceptances: {manual_n:,}

## Outputs

- `member_level_primary_window_coverage_v1.csv`: one row per frozen roster member
- `coverage_overall_v1.csv`
- `coverage_by_class_v1.csv`
- `coverage_by_section_v1.csv`
- `coverage_by_deceased_status_v1.csv`
- `coverage_by_election_era_v1.csv`
- `coverage_by_election_decade_v1.csv`
- `coverage_by_class_election_era_v1.csv`
- `candidate_acceptance_by_birth_year_v1.csv`
- `candidate_acceptance_by_birth_decade_v1.csv`
- `accepted_primary_by_birth_year_v1.csv`
- `accepted_primary_by_birth_decade_v1.csv`
- `accepted_route_counts_v1.csv`
- `candidate_evidence_status_counts_v1.csv`
- `edge_case_audit_v1.csv`
- `summary.json`
- `manifest.json`

## Guardrails

- No inferential missingness model is fitted in this step.
- No BaZi variables are computed.
- No person-specific search is reopened.
- Unresolved means the frozen evidence threshold was not met; it does not mean the candidate date is false.
- Accepted birth-year tables are numerator descriptions only, because unknown DOBs cannot be assigned to birth-year denominators.
- QIDs from candidates excluded for wrong identity/crosswalk remain only in `candidate_wikidata_qid`; they are never copied into the unified analysis `wikidata_qid`.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    output_hashes: dict[str, dict[str, Any]] = {}
    for name in OUTPUT_FILES:
        p = out_dir / name
        output_hashes[name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    manifest = {
        "dataset": SCRIPT_VERSION,
        "builder_revision": BUILDER_REVISION,
        "frozen_date": FROZEN_DATE,
        "source_closeout_tag": SOURCE_CLOSEOUT_TAG,
        "inputs": summary["input_sha256"],
        "outputs": output_hashes,
        "invariants": {
            "roster_rows": len(roster_rows),
            "candidate_partition_complete": int(
                accepted_candidate_n + unresolved_n + excluded_n == len(candidate_rows)
            ),
            "accepted_combined_decomposition_complete": int(
                accepted_candidate_n + len(official_only_rows) == len(accepted_rows)
            ),
            "member_rows_equal_roster_rows": int(len(member_rows) == len(roster_rows)),
            "accepted_slugs_unique": int(len(accepted_by_slug) == len(accepted_rows)),
            "candidate_slugs_unique": int(len(candidate_by_slug) == len(candidate_rows)),
            "all_accepted_inside_primary_window": 1,
            "accepted_primary_rows_without_verified_wikidata_qid": accepted_without_verified_qid,
            "excluded_candidate_qids_preserved_only_in_candidate_wikidata_qid": excluded_qid_provenance_rows,
            "excluded_candidate_qid_leaks_into_analysis_wikidata_qid": len(excluded_qid_leaks),
            "inferential_tests_run": 0,
            "bazi_variables_computed": 0,
            "prior_frozen_inputs_modified": 0,
        },
    }
    write_json(out_dir / "manifest.json", manifest)
    return summary


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="leopoldina_cov_test_") as td:
        root = Path(td)
        roster = root / "roster.csv"
        roster_meta = root / "roster.json"
        closeout = root / "closeout"
        out = root / "out"
        closeout.mkdir(parents=True)

        roster_rows = [
            {"member_slug": "a", "display_name": "A", "class": "Class I", "section": "S1", "election_year": "1900", "deceased_marker": "1"},
            {"member_slug": "b", "display_name": "B", "class": "Class I", "section": "S1", "election_year": "1950", "deceased_marker": "1"},
            {"member_slug": "c", "display_name": "C", "class": "Class II", "section": "S2", "election_year": "2000", "deceased_marker": "0"},
            {"member_slug": "d", "display_name": "D", "class": "Class II", "section": "S2", "election_year": "2001", "deceased_marker": "0"},
            {"member_slug": "e", "display_name": "E", "class": "Class III", "section": "S3", "election_year": "2010", "deceased_marker": "0"},
            {"member_slug": "f", "display_name": "F", "class": "Class III", "section": "S3", "election_year": "2020", "deceased_marker": "0"},
        ]
        write_csv(roster, roster_rows, ["member_slug", "display_name", "class", "section", "election_year", "deceased_marker"])
        write_json(roster_meta, {"roster_rows": 6, "checksums": {"roster_csv_sha256": sha256_file(roster)}})

        candidate_rows = [
            {
                "candidate_record_key": "candidate:q1:1900-01-01", "member_slug": "a", "display_name": "A", "wikidata_qid": "Q1",
                "candidate_exact_dob_original": "1900-01-01", "adjudicated_exact_dob": "", "initial_machine_evidence_status": "tier_a_positive",
                "status_after_round1_policy_freeze": "tier_a_positive", "final_evidence_status": "tier_a_positive", "machine_tier_a_groups": "x",
                "machine_tier_b_groups": "", "round1_new_tier_a_groups": "", "round1_new_tier_b_groups": "", "targeted_manual_groups": "",
                "official_new_member_same_date_overlay": "0", "archive_exception": "0", "conflict_status": "none", "acceptance_route": "machine_tier_a",
                "decision_mode": "frozen_rule", "acceptance_status": "accepted_exact_dob", "final_exact_dob": "1900-01-01", "automatic_acceptance": "1",
                "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0",
            },
            {
                "candidate_record_key": "candidate:q2:1910-01-01", "member_slug": "b", "display_name": "B", "wikidata_qid": "Q2",
                "candidate_exact_dob_original": "1910-01-01", "adjudicated_exact_dob": "", "initial_machine_evidence_status": "one_tier_b_positive",
                "status_after_round1_policy_freeze": "one_tier_b_positive", "final_evidence_status": "one_tier_b_positive", "machine_tier_a_groups": "",
                "machine_tier_b_groups": "x", "round1_new_tier_a_groups": "", "round1_new_tier_b_groups": "", "targeted_manual_groups": "",
                "official_new_member_same_date_overlay": "0", "archive_exception": "0", "conflict_status": "none", "acceptance_route": "insufficient_evidence",
                "decision_mode": "unresolved", "acceptance_status": "unresolved_one_tier_b", "final_exact_dob": "", "automatic_acceptance": "0",
                "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0",
            },
            {
                "candidate_record_key": "candidate:q3:1920-01-01", "member_slug": "c", "display_name": "C", "wikidata_qid": "Q3",
                "candidate_exact_dob_original": "1920-01-01", "adjudicated_exact_dob": "", "initial_machine_evidence_status": "one_tier_b_positive",
                "status_after_round1_policy_freeze": "one_tier_b_positive", "final_evidence_status": "excluded_invalid_identity_or_crosswalk", "machine_tier_a_groups": "",
                "machine_tier_b_groups": "x", "round1_new_tier_a_groups": "", "round1_new_tier_b_groups": "", "targeted_manual_groups": "",
                "official_new_member_same_date_overlay": "0", "archive_exception": "0", "conflict_status": "resolved", "acceptance_route": "excluded_invalid_crosswalk",
                "decision_mode": "manual", "acceptance_status": "excluded_invalid_identity_or_crosswalk", "final_exact_dob": "", "automatic_acceptance": "0",
                "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0",
            },
            {
                "candidate_record_key": "candidate:q4:1930-01-01", "member_slug": "d", "display_name": "D", "wikidata_qid": "Q4",
                "candidate_exact_dob_original": "1930-01-01", "adjudicated_exact_dob": "1930-01-02", "initial_machine_evidence_status": "one_tier_b_positive",
                "status_after_round1_policy_freeze": "one_tier_b_positive", "final_evidence_status": "tier_a_positive", "machine_tier_a_groups": "",
                "machine_tier_b_groups": "x", "round1_new_tier_a_groups": "x", "round1_new_tier_b_groups": "", "targeted_manual_groups": "",
                "official_new_member_same_date_overlay": "0", "archive_exception": "0", "conflict_status": "resolved", "acceptance_route": "manual_conflict_corrected_overlay",
                "decision_mode": "manual", "acceptance_status": "accepted_exact_dob", "final_exact_dob": "1930-01-02", "automatic_acceptance": "0",
                "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0",
            },
        ]
        candidate_fields = list(candidate_rows[0])
        write_csv(closeout / CANDIDATE_FILE, candidate_rows, candidate_fields)

        official_only = [
            {"record_key": "official:c", "record_origin": "official_profile_resolved_crosswalk", "member_slug": "c", "display_name": "C", "wikidata_qid": "",
             "class": "Class II", "section": "S2", "election_year": "2000", "final_exact_dob": "1920-01-03", "acceptance_status": "accepted_exact_dob",
             "acceptance_route": "official_profile_resolved_crosswalk", "decision_mode": "manual", "source_url": "u", "source_page": "", "automatic_acceptance": "0",
             "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0"},
            {"record_key": "official:e", "record_origin": "official_new_member_profile_only", "member_slug": "e", "display_name": "E", "wikidata_qid": "",
             "class": "Class III", "section": "S3", "election_year": "2010", "final_exact_dob": "1940-01-01", "acceptance_status": "accepted_exact_dob",
             "acceptance_route": "official_new_member_profile_only", "decision_mode": "prior_explicit_official_acceptance", "source_url": "u", "source_page": "", "automatic_acceptance": "0",
             "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0"},
        ]
        accepted_rows = [
            {"record_key": "candidate:q1:1900-01-01", "record_origin": "adjudicated_candidate", "member_slug": "a", "display_name": "A", "wikidata_qid": "Q1",
             "class": "", "section": "", "election_year": "", "final_exact_dob": "1900-01-01", "acceptance_status": "accepted_exact_dob", "acceptance_route": "machine_tier_a",
             "decision_mode": "frozen_rule", "source_url": "", "source_page": "", "automatic_acceptance": "1", "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0"},
            {"record_key": "candidate:q4:1930-01-01", "record_origin": "adjudicated_candidate", "member_slug": "d", "display_name": "D", "wikidata_qid": "Q4",
             "class": "", "section": "", "election_year": "", "final_exact_dob": "1930-01-02", "acceptance_status": "accepted_exact_dob", "acceptance_route": "manual_conflict_corrected_overlay",
             "decision_mode": "manual", "source_url": "", "source_page": "", "automatic_acceptance": "0", "primary_birthyear_eligible": "1", "prior_frozen_input_modified": "0", "bazi_variables_computed": "0"},
        ] + official_only
        accepted_fields = list(accepted_rows[0])
        write_csv(closeout / ACCEPTED_FILE, accepted_rows, accepted_fields)
        write_csv(closeout / OFFICIAL_ONLY_FILE, official_only, accepted_fields)
        unresolved = [candidate_rows[1]]
        write_csv(closeout / UNRESOLVED_FILE, unresolved, candidate_fields)
        excluded_fields = ["candidate_record_key", "member_slug", "wikidata_qid", "candidate_exact_dob", "exclusion_reason", "replacement_official_exact_dob", "replacement_record_origin", "resolution_id", "resolution_status", "prior_frozen_input_modified", "automatic_acceptance", "bazi_variables_computed"]
        write_csv(closeout / EXCLUDED_FILE, [{"candidate_record_key": candidate_rows[2]["candidate_record_key"], "member_slug": "c", "wikidata_qid": "Q3", "candidate_exact_dob": "1920-01-01", "exclusion_reason": "wrong_entity", "replacement_official_exact_dob": "1920-01-03", "replacement_record_origin": "official", "resolution_id": "r", "resolution_status": "resolved", "prior_frozen_input_modified": "0", "automatic_acceptance": "0", "bazi_variables_computed": "0"}], excluded_fields)
        write_json(closeout / CLOSEOUT_SUMMARY_FILE, {"candidate_adjudication_rows": 4, "accepted_exact_dob_combined_primary_rows": 4, "official_only_accepted_primary_rows": 2})
        files = {}
        for fn in [CANDIDATE_FILE, ACCEPTED_FILE, OFFICIAL_ONLY_FILE, UNRESOLVED_FILE, EXCLUDED_FILE, CLOSEOUT_SUMMARY_FILE]:
            p = closeout / fn
            files[fn] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
        write_json(closeout / CLOSEOUT_MANIFEST_FILE, {"files": files})

        summary = build_pipeline(roster, roster_meta, closeout, out, canonical=False)
        assert summary["counts"]["roster_rows"] == 6
        assert summary["counts"]["candidate_adjudication_rows"] == 4
        assert summary["counts"]["accepted_exact_dob_combined_primary_rows"] == 4
        assert summary["member_missingness_state_counts"]["accepted_candidate_primary"] == 2
        assert summary["member_missingness_state_counts"]["accepted_official_after_candidate_exclusion"] == 1
        assert summary["member_missingness_state_counts"]["accepted_official_only_primary"] == 1
        assert summary["member_missingness_state_counts"]["unresolved_primary_candidate"] == 1
        assert summary["member_missingness_state_counts"]["no_primary_candidate_or_official_acceptance"] == 1
        member_test_rows = read_csv(out / "member_level_primary_window_coverage_v1.csv")
        member_test_by_slug = {r["member_slug"]: r for r in member_test_rows}
        assert member_test_by_slug["a"]["candidate_wikidata_qid"] == "Q1"
        assert member_test_by_slug["a"]["accepted_wikidata_qid"] == "Q1"
        assert member_test_by_slug["a"]["wikidata_qid"] == "Q1"
        assert member_test_by_slug["b"]["candidate_wikidata_qid"] == "Q2"
        assert member_test_by_slug["b"]["wikidata_qid"] == "Q2"
        assert member_test_by_slug["c"]["candidate_wikidata_qid"] == "Q3"
        assert member_test_by_slug["c"]["accepted_wikidata_qid"] == ""
        assert member_test_by_slug["c"]["wikidata_qid"] == ""
        assert summary["qid_provenance_counts"]["excluded_candidate_qid_leaks_into_analysis_wikidata_qid"] == 0
        assert summary["qid_provenance_counts"]["excluded_candidate_qids_preserved_only_in_candidate_wikidata_qid"] == 1
        manifest = read_json(out / "manifest.json")
        assert manifest["invariants"]["candidate_partition_complete"] == 1
        assert manifest["invariants"]["accepted_combined_decomposition_complete"] == 1
        assert manifest["invariants"]["bazi_variables_computed"] == 0
        assert manifest["invariants"]["excluded_candidate_qid_leaks_into_analysis_wikidata_qid"] == 0
        print("SELF-TEST OK: synthetic roster/candidate/official-only partition and QID provenance are consistent")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Freeze Leopoldina DOB coverage and missingness diagnostics v1")
    p.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    p.add_argument("--roster-meta", type=Path, default=DEFAULT_ROSTER_META)
    p.add_argument("--closeout", type=Path, default=DEFAULT_CLOSEOUT)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    summary = build_pipeline(
        args.roster,
        args.roster_meta,
        args.closeout,
        args.out,
        canonical=True,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
