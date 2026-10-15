#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-imperial-page-queue-freeze-v1"
DEFAULT_RANGE_REVIEW = Path("data/japan_academy_manifest_member_range_review_v1")
DEFAULT_ROSTER_REVIEW = Path("data/japan_academy_roster_discovery_review_v1")
DEFAULT_OUT = Path("data/japan_academy_imperial_page_queue_freeze_v1")

EXPECTED_SELECTED_SPANS = 39
EXPECTED_RAW_PAGES = 119
EXPECTED_SNAPSHOT_YEARS = 32
EXPECTED_APPROVED_SPANS = 32
EXPECTED_APPROVED_PAGES = 96
EXPECTED_FORMAL_REVIEW_ROWS = 332
EXPECTED_COVERED_PRE1948 = 115
EXPECTED_PRE1948_GAPS = 2
EXPECTED_POST1947 = 215

PREFERRED_PID_BY_YEAR = {
    1931: "1094109",
    1932: "1094110",
}

ERA_BASE = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018}
KANJI_DIGITS = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
ERA_RE = re.compile(r"(明治|大正|昭和|平成|令和)(元|[〇零一二三四五六七八九十百0-9]+)年?")
ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jp_number(raw: str) -> int:
    s = str(raw).strip()
    if s == "元":
        return 1
    if s.isdigit():
        return int(s)
    if "百" in s:
        left, right = s.split("百", 1)
        hundreds = KANJI_DIGITS.get(left, 1) if left else 1
        return hundreds * 100 + (jp_number(right) if right else 0)
    if "十" in s:
        left, right = s.split("十", 1)
        tens = KANJI_DIGITS.get(left, 1) if left else 1
        ones = jp_number(right) if right else 0
        return tens * 10 + ones
    value = 0
    for ch in s:
        if ch not in KANJI_DIGITS:
            raise ValueError(f"Unsupported Japanese numeral: {raw!r}")
        value = value * 10 + KANJI_DIGITS[ch]
    return value


def snapshot_year(title: str) -> int:
    years: list[int] = []
    for era, year_raw in ERA_RE.findall(str(title or "")):
        years.append(ERA_BASE[era] + jp_number(year_raw))
    if not years:
        raise RuntimeError(f"Could not derive snapshot year from title: {title!r}")
    # Compound titles and parenthetical 'as of' dates can contain more than one era year.
    # The latest mentioned year is the operative snapshot date.
    return max(years)


def year_from_iso(raw: str) -> int | None:
    s = str(raw or "").strip()
    if not s:
        return None
    m = ISO_DATE_RE.fullmatch(s)
    if not m:
        raise RuntimeError(f"Expected ISO date or blank, got {raw!r}")
    dt.date.fromisoformat(s)
    return int(m.group(1))


def range_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("pid", ""), row.get("range_id", ""))


def choose_span(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise RuntimeError("No spans supplied")
    year = int(rows[0]["snapshot_year"])
    preferred_pid = PREFERRED_PID_BY_YEAR.get(year)

    def rank(r: dict[str, Any]) -> tuple[int, int, int]:
        basis = str(r.get("selection_basis") or "")
        basis_rank = 0 if basis == "explicit_section2_preferred" else 1
        pid = str(r.get("pid") or "")
        manual_rank = 0 if preferred_pid and pid == preferred_pid else 1
        return (basis_rank, manual_rank, int(pid))

    return sorted(rows, key=rank)[0]


def build(range_review: Path, roster_review: Path, out: Path) -> dict[str, Any]:
    spans_path = range_review / "selected_member_list_spans_v1.csv"
    pages_path = range_review / "minimal_member_page_queue_v1.csv"
    range_summary_path = range_review / "summary.json"
    degree_path = roster_review / "formal_section2_evidence_queue_1906plus_v1.csv"
    unresolved_path = roster_review / "true_subsection_unresolved_1906plus_v1.csv"
    roster_summary_path = roster_review / "summary.json"

    for p in (spans_path, pages_path, range_summary_path, degree_path, unresolved_path, roster_summary_path):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    spans = read_csv(spans_path)
    pages = read_csv(pages_path)
    if len(spans) != EXPECTED_SELECTED_SPANS:
        raise RuntimeError(f"Expected {EXPECTED_SELECTED_SPANS} selected spans, got {len(spans)}")
    if len(pages) != EXPECTED_RAW_PAGES:
        raise RuntimeError(f"Expected {EXPECTED_RAW_PAGES} raw queued pages, got {len(pages)}")

    page_keys = [(r.get("pid", ""), r.get("range_label", ""), r.get("canvas_index", "")) for r in pages]
    if len(set(page_keys)) != len(page_keys):
        raise RuntimeError("Duplicate PID/range/canvas rows in raw page queue")
    if any(not r.get("image_url") for r in pages):
        raise RuntimeError("Blank image URL in raw page queue")

    enriched: list[dict[str, Any]] = []
    by_year: dict[int, list[dict[str, Any]]] = {}
    for r in spans:
        row: dict[str, Any] = dict(r)
        y = snapshot_year(r.get("bibliographic_title", ""))
        row["snapshot_year"] = y
        by_year.setdefault(y, []).append(row)
        enriched.append(row)

    if len(by_year) != EXPECTED_SNAPSHOT_YEARS:
        raise RuntimeError(f"Expected {EXPECTED_SNAPSHOT_YEARS} unique snapshot years, got {len(by_year)}")

    approved: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for y in sorted(by_year):
        chosen = choose_span(by_year[y])
        chosen_key = range_key(chosen)
        chosen = dict(chosen)
        chosen["queue_decision"] = "approved_one_snapshot_per_year"
        approved.append(chosen)
        for r in by_year[y]:
            if range_key(r) == chosen_key:
                continue
            er = dict(r)
            er["excluded_in_favor_of_pid"] = chosen.get("pid", "")
            er["excluded_in_favor_of_range_id"] = chosen.get("range_id", "")
            er["exclusion_reason"] = (
                "same_snapshot_year_explicit_section2_preferred"
                if chosen.get("selection_basis") == "explicit_section2_preferred"
                and r.get("selection_basis") != "explicit_section2_preferred"
                else "same_snapshot_year_duplicate_source"
            )
            excluded.append(er)

    if len(approved) != EXPECTED_APPROVED_SPANS:
        raise RuntimeError(f"Expected {EXPECTED_APPROVED_SPANS} approved spans, got {len(approved)}")
    if len(excluded) != EXPECTED_SELECTED_SPANS - EXPECTED_APPROVED_SPANS:
        raise RuntimeError("Unexpected excluded duplicate span count")

    page_by_span: dict[tuple[str, str], list[dict[str, str]]] = {}
    for p in pages:
        page_by_span.setdefault((p.get("pid", ""), p.get("range_label", "")), []).append(p)

    approved_pages: list[dict[str, Any]] = []
    for s in approved:
        key = (str(s.get("pid", "")), str(s.get("range_label", "")))
        rr = page_by_span.get(key, [])
        expected = int(s.get("page_count") or 0)
        if len(rr) != expected:
            raise RuntimeError(f"Page count mismatch for {key}: expected {expected}, got {len(rr)}")
        for p in sorted(rr, key=lambda x: int(x["canvas_index"])):
            q: dict[str, Any] = dict(p)
            q["snapshot_year"] = int(s["snapshot_year"])
            q["queue_freeze_status"] = "approved_official_text_probe_then_image_fallback"
            approved_pages.append(q)

    approved_pages.sort(key=lambda r: (int(r["snapshot_year"]), int(r["pid"]), int(r["canvas_index"])))
    if len(approved_pages) != EXPECTED_APPROVED_PAGES:
        raise RuntimeError(f"Expected {EXPECTED_APPROVED_PAGES} approved pages, got {len(approved_pages)}")
    if len({(r["pid"], r["canvas_index"]) for r in approved_pages}) != len(approved_pages):
        raise RuntimeError("Duplicate approved PID/canvas pages")

    degree = read_csv(degree_path)
    unresolved = read_csv(unresolved_path)
    review_rows = [("degree_suggested", r) for r in degree] + [("true_unresolved", r) for r in unresolved]
    if len(review_rows) != EXPECTED_FORMAL_REVIEW_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_FORMAL_REVIEW_ROWS} formal review rows, got {len(review_rows)}")
    member_keys = [r.get("member_key", "") for _, r in review_rows]
    if any(not k for k in member_keys) or len(set(member_keys)) != len(member_keys):
        raise RuntimeError("Formal review member_key uniqueness invariant failed")

    years = sorted(int(r["snapshot_year"]) for r in approved)
    coverage_rows: list[dict[str, Any]] = []
    for queue_type, r in review_rows:
        start = year_from_iso(r.get("first_election_date", ""))
        if start is None:
            raw = str(r.get("election_year") or "").strip()
            start = int(raw) if raw else None
        if start is None:
            raise RuntimeError(f"Missing election year for {r.get('member_key')}")
        end = year_from_iso(r.get("final_retirement_date", "")) or 2025
        overlap = [y for y in years if start <= y <= end]
        if overlap:
            state = "covered_by_approved_imperial_snapshot"
        elif start <= 1947:
            state = "pre1948_no_selected_snapshot"
        else:
            state = "post1947_official_source_required"
        coverage_rows.append({
            "member_key": r.get("member_key", ""),
            "name_jp": r.get("name_jp", ""),
            "name_en": r.get("name_en", ""),
            "degree_jp": r.get("degree_jp", ""),
            "specialty_jp": r.get("specialty_jp", ""),
            "queue_type": queue_type,
            "scope_status": r.get("scope_status", ""),
            "first_election_date": r.get("first_election_date", ""),
            "final_retirement_date": r.get("final_retirement_date", ""),
            "membership_start_year": start,
            "membership_end_year": end,
            "overlapping_snapshot_years": "|".join(map(str, overlap)),
            "overlapping_snapshot_count": len(overlap),
            "snapshot_coverage_state": state,
            "roster_acceptance_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    state_counts = Counter(r["snapshot_coverage_state"] for r in coverage_rows)
    expected_states = {
        "covered_by_approved_imperial_snapshot": EXPECTED_COVERED_PRE1948,
        "pre1948_no_selected_snapshot": EXPECTED_PRE1948_GAPS,
        "post1947_official_source_required": EXPECTED_POST1947,
    }
    if dict(state_counts) != expected_states:
        raise RuntimeError(f"Unexpected candidate snapshot coverage states: {dict(state_counts)}")

    gaps = [r for r in coverage_rows if r["snapshot_coverage_state"] == "pre1948_no_selected_snapshot"]
    postwar = [r for r in coverage_rows if r["snapshot_coverage_state"] == "post1947_official_source_required"]

    out.mkdir(parents=True, exist_ok=True)
    approved_span_fields = [
        "snapshot_year", "pid", "series", "bibliographic_title", "manifest_url", "range_id",
        "parent_range_id", "range_label", "range_classification", "selection_basis",
        "start_canvas_index", "end_canvas_index", "page_count", "queue_decision", "manual_scope_note",
    ]
    write_csv(out / "approved_member_list_spans_v1.csv", approved, approved_span_fields)
    write_csv(out / "excluded_duplicate_spans_v1.csv", excluded)
    approved_page_fields = [
        "snapshot_year", "pid", "series", "bibliographic_title", "range_label",
        "range_classification", "selection_basis", "canvas_index", "canvas_id", "canvas_label",
        "image_url", "queue_freeze_status", "downloaded", "ocr_performed",
        "member_names_extracted", "roster_rows_accepted",
    ]
    write_csv(out / "approved_member_page_queue_v1.csv", approved_pages, approved_page_fields)
    write_csv(out / "formal_candidate_snapshot_coverage_v1.csv", coverage_rows)
    write_csv(out / "pre1948_snapshot_gap_review_v1.csv", gaps)
    write_csv(out / "post1947_official_source_required_v1.csv", postwar)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": "2026-10-14",
        "input_selected_spans": len(spans),
        "input_minimal_pages": len(pages),
        "unique_snapshot_years": len(years),
        "snapshot_years": years,
        "approved_one_span_per_snapshot_year": len(approved),
        "excluded_duplicate_same_year_spans": len(excluded),
        "approved_page_queue_rows": len(approved_pages),
        "pages_removed_by_same_year_deduplication": len(pages) - len(approved_pages),
        "approved_span_basis_counts": dict(Counter(r.get("selection_basis", "") for r in approved)),
        "formal_unresolved_review_rows": len(coverage_rows),
        "formal_candidate_snapshot_coverage_counts": dict(state_counts),
        "pre1948_candidates": sum(int(r["membership_start_year"]) <= 1947 for r in coverage_rows),
        "pre1948_candidates_covered_by_snapshot": EXPECTED_COVERED_PRE1948,
        "pre1948_candidates_without_snapshot": EXPECTED_PRE1948_GAPS,
        "post1947_candidates_requiring_other_official_source": EXPECTED_POST1947,
        "pre1948_gap_member_keys": [r["member_key"] for r in gaps],
        "text_first_rule": (
            "Probe the official NDL Next Digital Library OCR/full-text API for approved pages first. "
            "Download IIIF images only for pages without usable official text or for manual verification."
        ),
        "images_downloaded": 0,
        "ocr_performed_locally": 0,
        "member_names_extracted": 0,
        "roster_rows_accepted": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "next_action": "Collect official NDL OCR text for the 32 approved PIDs and 96 selected pages; retain image URLs as fallback evidence.",
        "input_sha256": {
            "selected_member_list_spans": sha256_file(spans_path),
            "minimal_member_page_queue": sha256_file(pages_path),
            "range_review_summary": sha256_file(range_summary_path),
            "degree_suggested_formal_queue": sha256_file(degree_path),
            "true_unresolved_formal_queue": sha256_file(unresolved_path),
            "roster_discovery_review_summary": sha256_file(roster_summary_path),
        },
    }
    write_json(out / "summary.json", summary)

    readme = f"""# Japan Academy Imperial roster page queue freeze v1

This layer deduplicates the manifest-derived member-list spans to one official
snapshot per represented year. It does not accept any roster member.

- Raw selected spans: {len(spans)}
- Raw page queue: {len(pages)}
- Approved snapshot years: {len(years)}
- Approved spans: {len(approved)}
- Approved pages: {len(approved_pages)}
- Formal unresolved candidates covered by at least one 1906-1947 snapshot: {EXPECTED_COVERED_PRE1948}
- Short-lived 1946 candidates not covered by the available snapshots: {EXPECTED_PRE1948_GAPS}
- Post-1947 candidates requiring another official source: {EXPECTED_POST1947}

The approved queue follows a text-first policy: collect the official NDL OCR/full-text
API output before downloading images. IIIF image URLs remain frozen for fallback and
manual verification.

No image is downloaded, no local OCR is run, no name is extracted, no roster row is
accepted, no DOB is collected, and no BaZi variable is computed in this layer.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    output_files = [
        "approved_member_list_spans_v1.csv",
        "excluded_duplicate_spans_v1.csv",
        "approved_member_page_queue_v1.csv",
        "formal_candidate_snapshot_coverage_v1.csv",
        "pre1948_snapshot_gap_review_v1.csv",
        "post1947_official_source_required_v1.csv",
        "summary.json",
        "README.md",
    ]
    manifest = {
        "dataset": SCRIPT_VERSION,
        "files": {
            name: {"sha256": sha256_file(out / name), "bytes": (out / name).stat().st_size}
            for name in output_files
        },
        "guardrails": {
            "one_span_per_snapshot_year": 1,
            "text_first_before_image_download": 1,
            "images_downloaded": 0,
            "local_ocr_performed": 0,
            "member_names_extracted": 0,
            "roster_rows_accepted": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        },
    }
    write_json(out / "manifest.json", manifest)
    return summary


def self_test() -> None:
    assert jp_number("元") == 1
    assert jp_number("三十九") == 39
    assert snapshot_year("帝国学士院一覧 明治39年") == 1906
    assert snapshot_year("昭和十五年昭和十六年帝国学士院一覧 : (昭和十六年四月調)") == 1941
    assert snapshot_year("昭和八年帝国学士院一覧 : (昭和九年六月末調)") == 1934

    rows = [
        {"snapshot_year": 1931, "pid": "1137202", "selection_basis": "active_member_roster_fallback"},
        {"snapshot_year": 1931, "pid": "1137223", "selection_basis": "explicit_section2_preferred"},
        {"snapshot_year": 1931, "pid": "1094109", "selection_basis": "explicit_section2_preferred"},
    ]
    assert choose_span(rows)["pid"] == "1094109"
    print("SELF-TEST OK: year parsing, one-snapshot deduplication, and preferred Section II source selection are consistent")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range-review", default=str(DEFAULT_RANGE_REVIEW))
    ap.add_argument("--roster-review", default=str(DEFAULT_ROSTER_REVIEW))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    summary = build(Path(args.range_review), Path(args.roster_review), Path(args.out))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
