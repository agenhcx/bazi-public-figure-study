#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining38-tierb-nanbara-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path(
    "data/japan_academy_remaining40_direct_evidence_queue_v1/"
    "remaining40_direct_evidence_queue_v1.csv"
)
DEFAULT_INVENTORY = Path(
    "data/japan_academy_remaining38_tierb_nanbara_source_fetch_v1/"
    "tierb_nanbara_source_inventory_v1.csv"
)
DEFAULT_SOURCE = Path(
    "data/japan_academy_remaining38_tierb_nanbara_source_fetch_v1/"
    "raw_sources/utokyo_nanbara_history_2025.pdf"
)
DEFAULT_OUT = Path("data/japan_academy_remaining38_tierb_nanbara_adjudication_v1")

TARGET_KEY = "jpa-unlinked-6b0513d4d49815ad"
TARGET_NAME = "南原 繁"
SOURCE_TIER = "B"
SOURCE_ORGANIZATION = "東京大学附属図書館"
SOURCE_TITLE = "南原繁年譜"
SOURCE_LOCATOR = "PDF p.2, 1959年7月"
EXPECTED_REMAINING_SHA256 = "bd81f0b4d994833fa5d0d5b04e2dcd036f0670b87aecdcfa08ce9df159acda11"
EXPECTED_INVENTORY_SHA256 = "2fc9f8d70ca45e1d1daa8dd3f3dbaac5b1ba6d1d8444815add18dea5a6dc6354"
EXPECTED_SOURCE_SHA256 = "290d8272c76922000f9c61c8bd20977346fc7d10f11ed05924e2241a1f004f73"

EVIDENCE_MEMBER = "帝国学士院会員に選出される"
EVIDENCE_SECTION = "日本学士院第一部長に就任"
EVIDENCE_PRESIDENT = "日本学士院第9代院長に就任"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def self_test() -> None:
    assert TARGET_KEY == "jpa-unlinked-6b0513d4d49815ad"
    assert TARGET_NAME == "南原 繁"
    assert SOURCE_TIER == "B"
    assert "第一部長" in EVIDENCE_SECTION
    assert "第9代院長" in EVIDENCE_PRESIDENT
    print("SELF-TEST OK: Nanbara Tier-B Section I adjudication constants are consistent")


def run(
    remaining_path: Path,
    inventory_path: Path,
    source_path: Path,
    out: Path,
) -> None:
    for p in (remaining_path, inventory_path, source_path):
        if not p.exists():
            raise FileNotFoundError(p)

    if sha256_file(remaining_path) != EXPECTED_REMAINING_SHA256:
        raise RuntimeError("remaining40 queue SHA256 mismatch")
    if sha256_file(inventory_path) != EXPECTED_INVENTORY_SHA256:
        raise RuntimeError("Nanbara source inventory SHA256 mismatch")
    if sha256_file(source_path) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Nanbara preserved PDF SHA256 mismatch")

    remaining = read_csv(remaining_path)
    inventory = read_csv(inventory_path)

    target_rows = [r for r in remaining if r.get("member_key") == TARGET_KEY]
    if len(target_rows) != 1:
        raise RuntimeError(f"Expected one Nanbara target row, found {len(target_rows)}")
    target = target_rows[0]
    if target.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Target name mismatch: {target.get('name_jp')}")

    inv_rows = [r for r in inventory if r.get("member_key") == TARGET_KEY]
    if len(inv_rows) != 1:
        raise RuntimeError(f"Expected one Nanbara inventory row, found {len(inv_rows)}")
    inv = inv_rows[0]

    if inv.get("source_tier") != SOURCE_TIER:
        raise RuntimeError(f"Unexpected source tier: {inv.get('source_tier')}")
    if inv.get("sha256") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"Inventory source SHA mismatch: expected {EXPECTED_SOURCE_SHA256}, found {inv.get('sha256')}"
        )
    if str(inv.get("pdf_magic_ok", "")) not in {"1", "1.0"}:
        raise RuntimeError("PDF magic check failed")
    if str(inv.get("pdf_eof_ok", "")) not in {"1", "1.0"}:
        raise RuntimeError("PDF EOF check failed")

    adjudication = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "name_en": target.get("name_en", ""),
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": inv.get("source_url", ""),
        "source_locator": SOURCE_LOCATOR,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "direct_membership_phrase": EVIDENCE_MEMBER,
        "direct_section_phrase": EVIDENCE_SECTION,
        "supporting_president_phrase": EVIDENCE_PRESIDENT,
        "accepted_broad_section": "I",
        "accepted_exact_subsection": "",
        "decision": "accept_tier_b_direct_section_i_exclude_from_section_ii_cohort",
        "decision_basis": (
            "University of Tokyo Library chronology directly states that Nanbara Shigeru "
            "became head of Japan Academy Section I in July 1959. The same institutional "
            "source also records his Imperial Academy membership and later presidency of "
            "the Japan Academy, making the institutional identity unambiguous. "
            "No exact subsection is inferred from discipline."
        ),
        "manual_adjudication_performed": 1,
        "direct_section_evidence_accepted": 1,
        "include_in_section_ii_science_cohort": 0,
        "final_roster_row_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
    }]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "nanbara_tierb_adjudication_v1.csv", adjudication)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_rows": len(remaining),
        "effective_unresolved_before_this_layer": 38,
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "source_sha256_verified": 1,
        "inventory_sha256_verified": 1,
        "manual_adjudication_performed": 1,
        "direct_section_evidence_accepted": 1,
        "accepted_broad_section": "I",
        "accepted_exact_subsection": "",
        "target_excluded_from_section_ii_science_cohort": 1,
        "members_resolved_by_this_layer": 1,
        "effective_unresolved_after_hiratsuka_yoshikawa_nanbara_if_integrated": 37,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(remaining_path),
            "tierb_nanbara_source_inventory_v1": sha256_file(inventory_path),
            "utokyo_nanbara_history_2025_pdf": sha256_file(source_path),
        },
        "next_action": (
            "Preserve Nanbara as a Tier-B direct Section I exclusion. Continue the frozen non-J-STAGE "
            "Tier-B institutional search for the effective remaining 37 unresolved members. Do not "
            "write/freeze the final Japan Academy Section II roster until remaining-member closeout."
        ),
    }
    write_json(out / "summary.json", summary)

    md = f"""# Japan Academy remaining-38 Tier-B Nanbara adjudication v1

Target: {TARGET_NAME}

Source: {SOURCE_ORGANIZATION}, "{SOURCE_TITLE}", {SOURCE_LOCATOR}

Manual review of the preserved PDF finds a direct statement that Nanbara became **head of Japan Academy Section I** in July 1959.

The same institutional chronology also records his Imperial Academy membership in 1946 and his later presidency of the Japan Academy in 1970, so institutional identity is unambiguous.

Decision: **accept broad Section I and exclude from the Section II science cohort** under the frozen Tier-B explicit-source policy.

No exact subsection is inferred from his discipline. No final roster row, DOB collection, or BaZi variable is written at this layer.
"""
    (out / "TIERB_NANBARA_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remaining", default=str(DEFAULT_REMAINING))
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(
        Path(args.remaining),
        Path(args.inventory),
        Path(args.source),
        Path(args.out),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
