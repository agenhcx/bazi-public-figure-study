#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining39-tierb-yoshikawa-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path(
    "data/japan_academy_remaining40_direct_evidence_queue_v1/"
    "remaining40_direct_evidence_queue_v1.csv"
)
DEFAULT_INVENTORY = Path(
    "data/japan_academy_remaining39_tierb_yoshikawa_source_fetch_v1/"
    "tierb_yoshikawa_source_inventory_v1.csv"
)
DEFAULT_TEXT = Path(
    "data/japan_academy_remaining39_tierb_yoshikawa_source_fetch_v1/"
    "raw_sources/tobunken_1982_nenshi_visible_text.txt"
)
DEFAULT_OUT = Path("data/japan_academy_remaining39_tierb_yoshikawa_adjudication_v1")

TARGET_KEY = "jpa-unlinked-ff84801ab056cf46"
TARGET_NAME = "吉川 逸治"
SOURCE_TIER = "B"
SOURCE_ORGANIZATION = "東京文化財研究所"
SOURCE_TITLE = "学士院新会員決定"
SOURCE_LOCATOR = "1982年12月「学士院新会員決定」"
EXPECTED_SOURCE_SHA256 = "3926320e5309d49fd69b97ac4db7e52a32bd94c0835281f1557ca2957cd28e9c"
EXPECTED_TEXT_SHA256 = "52abd723b8f3f25705ab7d3831d858420d152096f5859e0d41067ac3a54014b9"
EXPECTED_REMAINING_SHA256 = "bd81f0b4d994833fa5d0d5b04e2dcd036f0670b87aecdcfa08ce9df159acda11"
EXPECTED_ROWS = 40

# The archived page inserts whitespace around the linked personal name. Match the
# preserved wording semantically while keeping the raw fetch layer untouched.
EVIDENCE_PATTERN = re.compile(
    r"美術関係では第1部（人文科学部門）に\s*吉川\s*逸治\s*が選ばれた"
)
EVIDENCE_SHORT = "第1部（人文科学部門）に吉川逸治が選ばれた"


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
    sample = "美術関係では第1部（人文科学部門）に 吉川逸治 が選ばれた。"
    assert EVIDENCE_PATTERN.search(sample)
    assert TARGET_KEY == "jpa-unlinked-ff84801ab056cf46"
    assert SOURCE_TIER == "B"
    assert len(EVIDENCE_SHORT) < 30
    print("SELF-TEST OK: Yoshikawa Tier-B Section I adjudication constants are consistent")


def run(remaining_path: Path, inventory_path: Path, text_path: Path, out: Path) -> None:
    for p in (remaining_path, inventory_path, text_path):
        if not p.exists():
            raise FileNotFoundError(p)

    if sha256_file(remaining_path) != EXPECTED_REMAINING_SHA256:
        raise RuntimeError("remaining40 queue SHA256 mismatch")
    if sha256_file(text_path) != EXPECTED_TEXT_SHA256:
        raise RuntimeError("preserved visible-text SHA256 mismatch")

    remaining = read_csv(remaining_path)
    inventory = read_csv(inventory_path)
    if len(remaining) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} remaining rows, found {len(remaining)}")

    target_rows = [r for r in remaining if r.get("member_key") == TARGET_KEY]
    if len(target_rows) != 1:
        raise RuntimeError(f"Expected one Yoshikawa target row, found {len(target_rows)}")
    target = target_rows[0]
    if target.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Target name mismatch: {target.get('name_jp')}")

    inv_rows = [r for r in inventory if r.get("member_key") == TARGET_KEY]
    if len(inv_rows) != 1:
        raise RuntimeError(f"Expected one source inventory row, found {len(inv_rows)}")
    inv = inv_rows[0]

    if inv.get("source_tier") != SOURCE_TIER:
        raise RuntimeError(f"Unexpected source tier: {inv.get('source_tier')}")
    if inv.get("sha256") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"Source SHA mismatch: expected {EXPECTED_SOURCE_SHA256}, found {inv.get('sha256')}"
        )
    if str(inv.get("target_name_present", "")) not in {"1", "1.0"}:
        raise RuntimeError("Target-name presence check did not pass")
    if str(inv.get("heading_present", "")) not in {"1", "1.0"}:
        raise RuntimeError("Source heading presence check did not pass")

    visible = text_path.read_text(encoding="utf-8")
    if not EVIDENCE_PATTERN.search(visible):
        raise RuntimeError("Preserved text does not contain the explicit Section I wording")

    adjudication = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "name_en": target.get("name_en", ""),
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": inv.get("source_url", ""),
        "source_locator": SOURCE_LOCATOR,
        "source_sha256": inv.get("sha256", ""),
        "visible_text_sha256": sha256_file(text_path),
        "direct_section_phrase": EVIDENCE_SHORT,
        "accepted_broad_section": "I",
        "accepted_exact_subsection": "",
        "decision": "accept_tier_b_direct_section_i_exclude_from_section_ii_cohort",
        "decision_basis": (
            "Tokyo National Research Institute for Cultural Properties archived text directly states "
            "that Yoshikawa Itsuji was selected to Japan Academy Section I (humanities). "
            "Whitespace around the linked name explains why the strict fetch-layer literal test was zero. "
            "No subsection is inferred from his field."
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
    write_csv(out / "yoshikawa_tierb_adjudication_v1.csv", adjudication)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_rows": len(remaining),
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "source_sha256_verified": 1,
        "visible_text_sha256_verified": 1,
        "manual_adjudication_performed": 1,
        "direct_section_evidence_accepted": 1,
        "accepted_broad_section": "I",
        "accepted_exact_subsection": "",
        "target_excluded_from_section_ii_science_cohort": 1,
        "members_resolved_by_this_layer": 1,
        "effective_unresolved_after_hiratsuka_and_yoshikawa_if_integrated": 38,
        "fetch_layer_expected_direct_phrase_present_was_zero_due_to_link_whitespace": 1,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(remaining_path),
            "tierb_yoshikawa_source_inventory_v1": sha256_file(inventory_path),
            "tobunken_1982_nenshi_visible_text": sha256_file(text_path),
        },
        "next_action": (
            "Preserve Yoshikawa as a Tier-B direct Section I exclusion. Continue the frozen non-J-STAGE "
            "Tier-B institutional search for the effective remaining 38 unresolved members. Do not write/freeze "
            "the final Japan Academy Section II roster until the remaining-member closeout is reconciled."
        ),
    }
    write_json(out / "summary.json", summary)

    md = f"""# Japan Academy remaining-39 Tier-B Yoshikawa adjudication v1

Target: {TARGET_NAME}

Source: {SOURCE_ORGANIZATION}, "{SOURCE_TITLE}", {SOURCE_LOCATOR}

Manual review of the preserved source finds a direct statement that Yoshikawa was selected to **Japan Academy Section I (humanities)**.

Decision: **accept broad Section I and exclude from the Section II science cohort** under the frozen Tier-B explicit-source policy.

The fetch-layer exact-string flag was zero only because the HTML-to-text output inserted whitespace around the linked name. The raw fetch result is not rewritten; this adjudication layer records the normalized manual decision.

No exact subsection is inferred from his discipline. No final roster row, DOB collection, or BaZi variable is written at this layer.
"""
    (out / "TIERB_YOSHIKAWA_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remaining", default=str(DEFAULT_REMAINING))
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    ap.add_argument("--text", default=str(DEFAULT_TEXT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.remaining), Path(args.inventory), Path(args.text), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
