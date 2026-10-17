#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-tierb-hiratsuka-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path("data/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv")
DEFAULT_INVENTORY = Path("data/japan_academy_remaining40_tierb_hiratsuka_source_fetch_v1/tierb_hiratsuka_source_inventory_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_tierb_hiratsuka_adjudication_v1")

TARGET_KEY = "jpa-unlinked-67412ee03b08c5d2"
TARGET_NAME = "平塚 直秀"
EXPECTED_SOURCE_SHA256 = "3ff7af0021e5470011b134caa1c3f5c2e639a6fea4f4b93ab70bcddd507310df"
SOURCE_TIER = "B"
SOURCE_ORGANIZATION = "日本菌学会"
SOURCE_TITLE = "平塚直秀先生を悼む"
SOURCE_LOCATOR = "日菌報 41:175-176 (2000), p.176"

# Keep exact quotations short. The decisive wording is direct and does not require discipline inference.
EVIDENCE_MEMBER = "昭和48年11月日本学士院会員に選出"
EVIDENCE_SUBSECTION = "本院第六分科代表"
EVIDENCE_SECTION = "平成6年から日本学士院第二部部長"

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
    assert TARGET_NAME == "平塚 直秀"
    assert SOURCE_TIER == "B"
    assert "日本学士院第二部部長" in EVIDENCE_SECTION
    assert "第六分科" in EVIDENCE_SUBSECTION
    assert len(EVIDENCE_SECTION) < 25
    assert len(EVIDENCE_SUBSECTION) < 25
    print("SELF-TEST OK: Hiratsuka Tier-B adjudication constants and short evidence phrases are consistent")

def run(remaining_path: Path, inventory_path: Path, out: Path) -> None:
    for p in (remaining_path, inventory_path):
        if not p.exists():
            raise FileNotFoundError(p)

    remaining = read_csv(remaining_path)
    inventory = read_csv(inventory_path)

    target_rows = [r for r in remaining if r.get("member_key") == TARGET_KEY]
    if len(target_rows) != 1:
        raise RuntimeError(f"Expected one remaining target row, found {len(target_rows)}")
    target = target_rows[0]
    if target.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Target name mismatch: {target.get('name_jp')}")

    inv_rows = [r for r in inventory if r.get("member_key") == TARGET_KEY]
    if len(inv_rows) != 1:
        raise RuntimeError(f"Expected one source inventory row, found {len(inv_rows)}")
    inv = inv_rows[0]

    if inv.get("sha256") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"Source SHA mismatch: expected {EXPECTED_SOURCE_SHA256}, found {inv.get('sha256')}"
        )
    if str(inv.get("pdf_magic_ok", "")) not in {"1", "1.0"}:
        raise RuntimeError("Source PDF magic check did not pass")
    if str(inv.get("pdf_eof_ok", "")) not in {"1", "1.0"}:
        raise RuntimeError("Source PDF EOF check did not pass")
    if inv.get("source_tier") != SOURCE_TIER:
        raise RuntimeError(f"Unexpected source tier: {inv.get('source_tier')}")

    accepted = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "name_en": target.get("name_en", ""),
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": inv.get("source_url", ""),
        "source_locator": SOURCE_LOCATOR,
        "source_sha256": inv.get("sha256", ""),
        "direct_membership_phrase": EVIDENCE_MEMBER,
        "direct_subsection_phrase": EVIDENCE_SUBSECTION,
        "direct_section_phrase": EVIDENCE_SECTION,
        "accepted_broad_section": "II",
        "accepted_exact_subsection": "6",
        "decision": "accept_tier_b_direct_japan_academy_section_ii_subsection_6",
        "decision_basis": (
            "Recognized academic-society obituary directly states Japan Academy membership, "
            "Sixth Subsection representation, and Japan Academy Second Division leadership for the exact person. "
            "No discipline inference is used."
        ),
        "direct_section_evidence_accepted": 1,
        "final_roster_row_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
    }]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "accepted_direct_section_evidence_v1.csv", accepted)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_rows": len(remaining),
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "source_sha256_verified": 1,
        "direct_membership_evidence_present": 1,
        "direct_section_evidence_present": 1,
        "direct_subsection_evidence_present": 1,
        "accepted_broad_section": "II",
        "accepted_exact_subsection": "6",
        "direct_section_evidence_accepted": 1,
        "members_resolved_by_this_layer": 1,
        "remaining40_count_after_this_acceptance_if_integrated": len(remaining) - 1,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(remaining_path),
            "tierb_hiratsuka_source_inventory_v1": sha256_file(inventory_path),
        },
        "next_action": (
            "Preserve this as an accepted Tier-B evidence layer. Continue Tier-B search for the other 39 unresolved members. "
            "Do not write/freeze the final Japan Academy roster until the full remaining-member closeout is reconciled."
        ),
    }
    write_json(out / "summary.json", summary)

    md = f"""# Japan Academy Tier-B Hiratsuka adjudication v1

Target: {TARGET_NAME}

Source: {SOURCE_ORGANIZATION}, "{SOURCE_TITLE}", {SOURCE_LOCATOR}

Accepted evidence:
- Japan Academy membership is stated directly.
- The source identifies him as representative of the Academy's Sixth Subsection.
- The source identifies him directly as head of the Japan Academy Second Division from 1994.

Decision: **accept broad Section II and exact subsection 6** under the frozen Tier-B explicit-source policy.

This layer does not write or freeze the final Japan Academy roster. DOB collection and BaZi computation remain blocked.
"""
    (out / "TIERB_HIRATSUKA_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remaining", default=str(DEFAULT_REMAINING))
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.remaining), Path(args.inventory), Path(args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
