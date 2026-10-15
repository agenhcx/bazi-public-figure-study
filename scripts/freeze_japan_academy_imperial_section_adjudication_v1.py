#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-imperial-section-adjudication-v1"
DEFAULT_EVIDENCE = Path("data/japan_academy_imperial_section_evidence_v1")
DEFAULT_IMAGES = Path("data/japan_academy_imperial_manual_image_review_v1")
DEFAULT_OUT = Path("data/japan_academy_imperial_section_adjudication_v1")

DECISIONS: dict[str, dict[str, Any]] = {
    "jpa-unlinked-fdb2677e26e2f233": {
        "printed_name_jp": "中村 清二",
        "printed_section": "2",
        "manual_identity_decision": "same_person_confirmed",
        "manual_section_decision": "accept_section2",
        "decision_class": "manual_image_exact_canonical_name",
        "manual_reason": (
            "The explicit Section II member page visibly prints the canonical name 中村 清二. "
            "The repeated OCR form 中村〓二 is a recognition failure of 清, not a distinct person."
        ),
        "review_page_ids": "ndl:1094098:canvas:9",
        "historical_name_variant_jp": "",
        "historical_section_conflict": 0,
    },
    "jpa-unlinked-6f462d3a7bb1aacc": {
        "printed_name_jp": "平山 清次",
        "printed_section": "2",
        "manual_identity_decision": "same_person_confirmed",
        "manual_section_decision": "accept_section2",
        "decision_class": "manual_image_exact_canonical_name",
        "manual_reason": (
            "The explicit Section II member page visibly prints the canonical name 平山 清次. "
            "The repeated OCR form 平山〓次 is a recognition failure of 清, not a distinct person."
        ),
        "review_page_ids": "ndl:1094098:canvas:9",
        "historical_name_variant_jp": "",
        "historical_section_conflict": 0,
    },
    "jpa-unlinked-3df078a729d3c3ed": {
        "printed_name_jp": "藤浪 鑑",
        "printed_section": "2",
        "manual_identity_decision": "same_person_historical_name_variant_confirmed",
        "manual_section_decision": "accept_section2",
        "decision_class": "manual_image_historical_name_variant",
        "manual_reason": (
            "The explicit Section II member page visibly prints 藤浪 鑑. The frozen candidate is 藤波 鑑 "
            "with the same membership dates and specialty; preserve 藤浪 鑑 as the historical roster form."
        ),
        "review_page_ids": "ndl:1137220:canvas:10",
        "historical_name_variant_jp": "藤浪 鑑",
        "historical_section_conflict": 0,
    },
    "jpa-unlinked-5eaf3480c6129ce9": {
        "printed_name_jp": "松村 任三",
        "printed_section": "1",
        "manual_identity_decision": "same_person_confirmed",
        "manual_section_decision": "accept_section2_with_historical_conflict",
        "decision_class": "manual_historical_section_conflict",
        "manual_reason": (
            "The 1918 official page genuinely prints 第一部 for 松村任三; this is not an OCR error. "
            "However, 11 other exact official snapshots place the same member in 第二部, including the "
            "earliest observed post-election years and all observed years from 1920 through 1928. "
            "Accept Section II cohort eligibility while preserving the 1918 Section I entry as a real "
            "historical source conflict or temporary classification."
        ),
        "review_page_ids": "ndl:952911:canvas:33",
        "historical_name_variant_jp": "",
        "historical_section_conflict": 1,
    },
    "jpa-unlinked-1da6b5d6c2d71731": {
        "printed_name_jp": "",
        "printed_section": "",
        "manual_identity_decision": "official_member_identity_retained",
        "manual_section_decision": "section_unresolved_other_official_source_required",
        "decision_class": "manual_image_absence_not_section_evidence",
        "manual_reason": (
            "All three pages of the April 1936 official member-and-guest roster were visually reviewed; "
            "中山秀三郎 is not visibly listed. Absence from this snapshot is not evidence for Section I, "
            "Section II, or non-membership. Retain the official membership record and seek another formal source."
        ),
        "review_page_ids": "ndl:1073617:canvas:76|ndl:1073617:canvas:77|ndl:1073617:canvas:78",
        "historical_name_variant_jp": "",
        "historical_section_conflict": 0,
    },
    "jpa-unlinked-630652489d768951": {
        "printed_name_jp": "",
        "printed_section": "",
        "manual_identity_decision": "official_member_identity_retained",
        "manual_section_decision": "section_unresolved_other_official_source_required",
        "decision_class": "manual_image_absence_not_section_evidence",
        "manual_reason": (
            "All four pages of the June 1944 official member roster were visually reviewed; 平井毓太郎 "
            "is not visibly listed. Absence from this snapshot is not evidence for Section I, Section II, "
            "or non-membership. Retain the official membership record and seek another formal source."
        ),
        "review_page_ids": (
            "ndl:1070913:canvas:88|ndl:1070913:canvas:89|"
            "ndl:1070913:canvas:90|ndl:1070913:canvas:91"
        ),
        "historical_name_variant_jp": "",
        "historical_section_conflict": 0,
    },
}


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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def index_unique(rows: list[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        require(bool(value), f"Missing {key} in {label}")
        require(value not in out, f"Duplicate {key}={value!r} in {label}")
        out[value] = row
    return out


def verify_image_inventory(image_dir: Path, inventory: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_page = index_unique(inventory, "review_page_id", "image inventory")
    for row in inventory:
        require(row.get("retrieval_state") == "fetched", f"Image not fetched: {row.get('review_page_id')}")
        rel = row.get("local_image_path", "")
        require(bool(rel), f"Missing local image path: {row.get('review_page_id')}")
        p = image_dir / rel
        require(p.exists(), f"Missing local image file: {p}")
        require(sha256_file(p) == row.get("sha256"), f"Image SHA mismatch: {p}")
    return by_page


def run(evidence_dir: Path, image_dir: Path, out: Path) -> dict[str, Any]:
    evidence_summary = json.loads((evidence_dir / "summary.json").read_text(encoding="utf-8"))
    image_summary = json.loads((image_dir / "summary.json").read_text(encoding="utf-8"))

    require(evidence_summary.get("input_candidate_rows") == 332, "Expected 332 evidence candidates")
    require(evidence_summary.get("direct_section2_proposals") == 85, "Expected 85 direct Section II proposals")
    require(evidence_summary.get("direct_section1_exclusion_proposals") == 4, "Expected 4 Section I proposals")
    require(evidence_summary.get("section_conflicts_for_manual_review") == 1, "Expected 1 section conflict")
    require(evidence_summary.get("repeated_one_edit_reviews") == 3, "Expected 3 one-edit reviews")
    require(evidence_summary.get("manual_image_review_members") == 2, "Expected 2 missing-name image reviews")
    require(image_summary.get("approved_page_rows") == 10, "Expected 10 approved image pages")
    require(image_summary.get("manual_review_targets") == 6, "Expected 6 manual review targets")
    require(image_summary.get("all_images_available") == 1, "Expected all images available")
    require(image_summary.get("local_ocr_performed") == 0, "Local OCR must remain zero")

    candidates = read_csv(evidence_dir / "candidate_section_evidence_summary_v1.csv")
    direct2 = read_csv(evidence_dir / "direct_section2_proposals_v1.csv")
    direct1 = read_csv(evidence_dir / "direct_section1_exclusion_proposals_v1.csv")
    one_edit = read_csv(evidence_dir / "repeated_one_edit_review_v1.csv")
    conflicts = read_csv(evidence_dir / "section_conflict_review_v1.csv")
    prior_other = read_csv(evidence_dir / "other_official_source_required_v1.csv")
    unmatched = read_csv(evidence_dir / "unmatched_calendar_overlap_review_v1.csv")
    inventory = read_csv(image_dir / "image_inventory_v1.csv")
    template = read_csv(image_dir / "manual_adjudication_template_v1.csv")

    require(len(candidates) == 332, "Candidate row count mismatch")
    require(len(direct2) == 85, "Direct Section II row count mismatch")
    require(len(direct1) == 4, "Direct Section I row count mismatch")
    require(len(one_edit) == 3, "One-edit row count mismatch")
    require(len(conflicts) == 1, "Conflict row count mismatch")
    require(len(prior_other) == 237, "Prior other-source row count mismatch")
    require(len(template) == 6, "Manual template row count mismatch")

    candidate_by_key = index_unique(candidates, "member_key", "candidate summary")
    template_by_key = index_unique(template, "member_key", "manual template")
    inventory_by_page = verify_image_inventory(image_dir, inventory)
    require(set(template_by_key) == set(DECISIONS), "Manual decision keys do not match template")

    manual_rows: list[dict[str, Any]] = []
    for member_key in sorted(DECISIONS):
        base = candidate_by_key[member_key]
        t = template_by_key[member_key]
        d = DECISIONS[member_key]
        page_ids = d["review_page_ids"].split("|")
        for page_id in page_ids:
            require(page_id in inventory_by_page, f"Decision references missing page {page_id}")
        image_shas = "|".join(inventory_by_page[x]["sha256"] for x in page_ids)
        local_paths = "|".join(inventory_by_page[x]["local_image_path"] for x in page_ids)
        manual_rows.append({
            "member_key": member_key,
            "name_jp": base["name_jp"],
            "name_en": base["name_en"],
            "review_class": t["review_class"],
            "review_page_ids": d["review_page_ids"],
            "local_image_paths": local_paths,
            "source_image_sha256s": image_shas,
            "printed_name_jp": d["printed_name_jp"],
            "printed_section": d["printed_section"],
            "manual_identity_decision": d["manual_identity_decision"],
            "manual_section_decision": d["manual_section_decision"],
            "decision_class": d["decision_class"],
            "historical_name_variant_jp": d["historical_name_variant_jp"],
            "historical_section_conflict": d["historical_section_conflict"],
            "manual_reason": d["manual_reason"],
            "adjudication_status": "frozen_manual_visual_review",
            "roster_acceptance_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    manual_by_key = {r["member_key"]: r for r in manual_rows}

    accepted: list[dict[str, Any]] = []
    for r in direct2:
        accepted.append({
            **r,
            "section_evidence_outcome": "accepted_section2_evidence",
            "section_evidence_route": "exact_consensus_official_member_columns",
            "manual_adjudication_status": "not_required",
            "historical_name_variant_jp": "",
            "historical_section_conflict": 0,
            "final_section_evidence": 2,
            "final_roster_row_written": 0,
        })
    for r in one_edit:
        m = manual_by_key[r["member_key"]]
        require(m["manual_section_decision"] == "accept_section2", "One-edit decision must accept Section II")
        accepted.append({
            **r,
            "section_evidence_outcome": "accepted_section2_evidence",
            "section_evidence_route": m["decision_class"],
            "manual_adjudication_status": m["adjudication_status"],
            "historical_name_variant_jp": m["historical_name_variant_jp"],
            "historical_section_conflict": 0,
            "final_section_evidence": 2,
            "final_roster_row_written": 0,
        })
    for r in conflicts:
        m = manual_by_key[r["member_key"]]
        require(m["manual_section_decision"] == "accept_section2_with_historical_conflict", "Conflict decision mismatch")
        accepted.append({
            **r,
            "section_evidence_outcome": "accepted_section2_evidence_with_historical_conflict",
            "section_evidence_route": m["decision_class"],
            "manual_adjudication_status": m["adjudication_status"],
            "historical_name_variant_jp": "",
            "historical_section_conflict": 1,
            "final_section_evidence": 2,
            "final_roster_row_written": 0,
        })

    excluded: list[dict[str, Any]] = []
    for r in direct1:
        excluded.append({
            **r,
            "section_evidence_outcome": "excluded_from_section2_by_official_section1_evidence",
            "section_evidence_route": "exact_consensus_official_member_columns",
            "manual_adjudication_status": "not_required",
            "final_section_evidence": 1,
            "final_roster_row_written": 0,
        })

    unresolved = [dict(r) for r in prior_other]
    for member_key in ["jpa-unlinked-1da6b5d6c2d71731", "jpa-unlinked-630652489d768951"]:
        base = candidate_by_key[member_key]
        m = manual_by_key[member_key]
        unresolved.append({
            **base,
            "source_requirement_reason": "not_visibly_listed_in_precisely_dated_official_snapshot_after_manual_image_review",
            "section_evidence_outcome": "section_unresolved_other_official_source_required",
            "section_evidence_route": m["decision_class"],
            "manual_adjudication_status": m["adjudication_status"],
            "final_section_evidence": "",
            "final_roster_row_written": 0,
        })

    require(len(accepted) == 89, f"Expected 89 accepted Section II evidence rows, got {len(accepted)}")
    require(len(excluded) == 4, f"Expected 4 Section I exclusions, got {len(excluded)}")
    require(len(unresolved) == 239, f"Expected 239 unresolved rows, got {len(unresolved)}")
    require(len(accepted) + len(excluded) + len(unresolved) == 332, "Final partition does not sum to 332")

    outcome_by_key: dict[str, dict[str, Any]] = {}
    for r in accepted:
        outcome_by_key[r["member_key"]] = {
            "section_evidence_outcome": r["section_evidence_outcome"],
            "section_evidence_route": r["section_evidence_route"],
            "final_section_evidence": 2,
            "historical_name_variant_jp": r.get("historical_name_variant_jp", ""),
            "historical_section_conflict": r.get("historical_section_conflict", 0),
        }
    for r in excluded:
        outcome_by_key[r["member_key"]] = {
            "section_evidence_outcome": r["section_evidence_outcome"],
            "section_evidence_route": r["section_evidence_route"],
            "final_section_evidence": 1,
            "historical_name_variant_jp": "",
            "historical_section_conflict": 0,
        }
    for r in unresolved:
        outcome_by_key[r["member_key"]] = {
            "section_evidence_outcome": "section_unresolved_other_official_source_required",
            "section_evidence_route": r.get("section_evidence_route") or "other_official_source_required",
            "final_section_evidence": "",
            "historical_name_variant_jp": "",
            "historical_section_conflict": 0,
        }
    require(set(outcome_by_key) == set(candidate_by_key), "Final outcome keys do not cover all candidates")

    final_rows: list[dict[str, Any]] = []
    for r in candidates:
        o = outcome_by_key[r["member_key"]]
        final_rows.append({
            **r,
            **o,
            "imperial_evidence_layer_frozen": 1,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    historical_variants = [r for r in manual_rows if r["historical_name_variant_jp"]]
    historical_conflicts = [r for r in manual_rows if int(r["historical_section_conflict"]) == 1]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "manual_image_adjudications_v1.csv", manual_rows)
    write_csv(out / "accepted_section2_evidence_v1.csv", accepted)
    write_csv(out / "excluded_section1_evidence_v1.csv", excluded)
    write_csv(out / "unresolved_other_official_source_required_v1.csv", unresolved)
    write_csv(out / "candidate_imperial_section_evidence_final_v1.csv", final_rows)
    write_csv(out / "historical_name_variants_v1.csv", historical_variants)
    write_csv(out / "historical_section_conflicts_v1.csv", historical_conflicts)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": "2026-10-14",
        "candidate_rows": 332,
        "accepted_section2_evidence_rows": 89,
        "accepted_section2_route_counts": dict(sorted(Counter(r["section_evidence_route"] for r in accepted).items())),
        "excluded_section1_evidence_rows": 4,
        "unresolved_other_official_source_required_rows": 239,
        "manual_image_adjudication_rows": 6,
        "manual_image_decision_counts": dict(sorted(Counter(r["manual_section_decision"] for r in manual_rows).items())),
        "historical_name_variant_rows": len(historical_variants),
        "historical_section_conflict_rows": len(historical_conflicts),
        "manual_absence_reviews_routed_to_other_source": 2,
        "partition_complete": 1,
        "decision_guardrails": [
            "Absence from a dated roster page is not treated as Section I, Section II, or non-membership evidence.",
            "The 1918 松村任三 First Division entry is preserved as a real official-source conflict, not overwritten as OCR error.",
            "Historical printed name forms are preserved alongside the canonical Japan Academy index name.",
            "This layer freezes section evidence only; it does not write the final Japan Academy roster."
        ],
        "images_reviewed": 10,
        "local_ocr_performed": 0,
        "final_roster_rows_written": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "evidence_summary": sha256_file(evidence_dir / "summary.json"),
            "candidate_evidence_summary": sha256_file(evidence_dir / "candidate_section_evidence_summary_v1.csv"),
            "direct_section2": sha256_file(evidence_dir / "direct_section2_proposals_v1.csv"),
            "direct_section1": sha256_file(evidence_dir / "direct_section1_exclusion_proposals_v1.csv"),
            "repeated_one_edit": sha256_file(evidence_dir / "repeated_one_edit_review_v1.csv"),
            "section_conflict": sha256_file(evidence_dir / "section_conflict_review_v1.csv"),
            "prior_other_source": sha256_file(evidence_dir / "other_official_source_required_v1.csv"),
            "image_summary": sha256_file(image_dir / "summary.json"),
            "image_inventory": sha256_file(image_dir / "image_inventory_v1.csv"),
            "manual_template": sha256_file(image_dir / "manual_adjudication_template_v1.csv"),
        },
    }
    write_json(out / "summary.json", summary)

    readme = f"""# Japan Academy imperial section-evidence adjudication v1

This layer closes manual review of ten frozen official NDL scan pages for six members.

Final evidence partition of the 332 unresolved historical candidates:

- 89 accepted Section II evidence rows;
- 4 excluded by direct Section I evidence;
- 239 still requiring another official source.

Important adjudications:

- 中村清二 and 平山清次: scan confirms the canonical 清 character under explicit Section II.
- 藤波鑑: scan prints historical form 藤浪鑑 under explicit Section II; both forms are preserved.
- 松村任三: the 1918 scan genuinely prints First Division, while eleven other official snapshots print Second Division. Section II eligibility is accepted and the 1918 conflict is preserved.
- 中山秀三郎 and 平井毓太郎: absent from the reviewed dated roster pages; absence is not converted into section evidence.

No final roster row, DOB, or BaZi variable is written by this layer.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    output_files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {
        "dataset": SCRIPT_VERSION,
        "script_version": SCRIPT_VERSION,
        "files": {
            p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size}
            for p in output_files
        },
        "summary": summary,
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def self_test() -> None:
    # Test only the frozen decision-key structure; full source validation occurs in run().
    require(len(DECISIONS) == 6, "Expected six frozen manual decisions")
    require(sum(v["manual_section_decision"].startswith("accept_section2") for v in DECISIONS.values()) == 4,
            "Expected four Section II manual decisions")
    require(sum(v["manual_section_decision"].startswith("section_unresolved") for v in DECISIONS.values()) == 2,
            "Expected two unresolved manual decisions")
    require(sum(int(v["historical_section_conflict"]) for v in DECISIONS.values()) == 1,
            "Expected one historical section conflict")
    print("SELF-TEST OK: six frozen visual decisions and guardrail counts are consistent")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE))
    ap.add_argument("--image-dir", default=str(DEFAULT_IMAGES))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    run(Path(args.evidence_dir), Path(args.image_dir), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
