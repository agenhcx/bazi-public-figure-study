#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining37-tierb-doi-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path(
    "data/japan_academy_remaining40_direct_evidence_queue_v1/"
    "remaining40_direct_evidence_queue_v1.csv"
)
DEFAULT_INVENTORY = Path(
    "data/japan_academy_remaining37_tierb_doi_source_fetch_v1/"
    "tierb_doi_source_inventory_v1.csv"
)
DEFAULT_TEXT = Path(
    "data/japan_academy_remaining37_tierb_doi_source_fetch_v1/"
    "raw_sources/tobunken_nenshi_5759_doi_visible_text.txt"
)
DEFAULT_HTML = Path(
    "data/japan_academy_remaining37_tierb_doi_source_fetch_v1/"
    "raw_sources/tobunken_nenshi_5759_doi.html"
)
DEFAULT_OUT = Path("data/japan_academy_remaining37_tierb_doi_adjudication_v1")

TARGET_KEY = "jpa-unlinked-f21fcc61cad96158"
TARGET_NAME = "土居 光知"
SOURCE_TIER = "B"
SOURCE_ORGANIZATION = "東京文化財研究所"
SOURCE_TITLE = "学士院新会員決る"
SOURCE_LOCATOR = "1949年10月「学士院新会員決る」"

EXPECTED_REMAINING_SHA256 = "bd81f0b4d994833fa5d0d5b04e2dcd036f0670b87aecdcfa08ce9df159acda11"
EXPECTED_INVENTORY_SHA256 = "10731efeff14fbf35846bd3de3c628c4159650cdd315945a075cbfc42de39668"
EXPECTED_HTML_SHA256 = "ab8ed478736ffdb475bc2a7fda3d5855626cebc7f2540a42bf76d4994a53e1e4"
EXPECTED_TEXT_SHA256 = "67735a9aa57aacfe7817bff1c1a8a8cddde2cb01b5fd9258638731f5969cf540"

EVIDENCE_PATTERN = re.compile(
    r"五日日本学士院第四回総会で二九人の学士院新会員が当選した。"
    r"第一部文学では、波多野精一、\s*和辻哲郎\s*、土居光知が選ばれた。"
)
EVIDENCE_SHORT = "第一部文学では、波多野精一、和辻哲郎、土居光知が選ばれた"


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
    sample = (
        "五日日本学士院第四回総会で二九人の学士院新会員が当選した。"
        "第一部文学では、波多野精一、 和辻哲郎 、土居光知が選ばれた。"
    )
    assert EVIDENCE_PATTERN.search(sample)
    assert TARGET_KEY == "jpa-unlinked-f21fcc61cad96158"
    assert SOURCE_TIER == "B"
    print("SELF-TEST OK: Doi Tier-B Section I adjudication constants are consistent")


def run(
    remaining_path: Path,
    inventory_path: Path,
    text_path: Path,
    html_path: Path,
    out: Path,
) -> None:
    for p in (remaining_path, inventory_path, text_path, html_path):
        if not p.exists():
            raise FileNotFoundError(p)

    if sha256_file(remaining_path) != EXPECTED_REMAINING_SHA256:
        raise RuntimeError("remaining40 queue SHA256 mismatch")
    if sha256_file(inventory_path) != EXPECTED_INVENTORY_SHA256:
        raise RuntimeError("Doi source inventory SHA256 mismatch")
    if sha256_file(html_path) != EXPECTED_HTML_SHA256:
        raise RuntimeError("Doi preserved HTML SHA256 mismatch")
    if sha256_file(text_path) != EXPECTED_TEXT_SHA256:
        raise RuntimeError("Doi preserved visible-text SHA256 mismatch")

    remaining = read_csv(remaining_path)
    inventory = read_csv(inventory_path)

    target_rows = [r for r in remaining if r.get("member_key") == TARGET_KEY]
    if len(target_rows) != 1:
        raise RuntimeError(f"Expected one Doi target row, found {len(target_rows)}")
    target = target_rows[0]
    if target.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Target name mismatch: {target.get('name_jp')}")

    inv_rows = [r for r in inventory if r.get("member_key") == TARGET_KEY]
    if len(inv_rows) != 1:
        raise RuntimeError(f"Expected one Doi inventory row, found {len(inv_rows)}")
    inv = inv_rows[0]

    if inv.get("source_tier") != SOURCE_TIER:
        raise RuntimeError(f"Unexpected source tier: {inv.get('source_tier')}")
    if inv.get("sha256") != EXPECTED_HTML_SHA256:
        raise RuntimeError("Inventory source SHA does not match preserved HTML")
    if inv.get("visible_text_sha256") != EXPECTED_TEXT_SHA256:
        raise RuntimeError("Inventory visible-text SHA does not match preserved text")
    if str(inv.get("target_name_present", "")) not in {"1", "1.0"}:
        raise RuntimeError("Target-name presence check did not pass")
    if str(inv.get("heading_present", "")) not in {"1", "1.0"}:
        raise RuntimeError("Heading presence check did not pass")
    if str(inv.get("direct_section_statement_present", "")) not in {"1", "1.0"}:
        raise RuntimeError("Fetch-layer direct section statement check did not pass")

    visible = text_path.read_text(encoding="utf-8")
    if not EVIDENCE_PATTERN.search(visible):
        raise RuntimeError("Preserved visible text does not contain the direct Section I statement")

    adjudication = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "name_en": target.get("name_en", ""),
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": inv.get("source_url", ""),
        "source_locator": SOURCE_LOCATOR,
        "source_html_sha256": EXPECTED_HTML_SHA256,
        "visible_text_sha256": EXPECTED_TEXT_SHA256,
        "direct_section_phrase": EVIDENCE_SHORT,
        "accepted_broad_section": "I",
        "accepted_exact_subsection": "",
        "decision": "accept_tier_b_direct_section_i_exclude_from_section_ii_cohort",
        "decision_basis": (
            "Tokyo National Research Institute for Cultural Properties archived article explicitly "
            "states that at the Japan Academy fourth general meeting Doi Kochi was selected under "
            "Section I literature. The target person and Japan Academy Section I are directly bound "
            "in the same sentence; no discipline inference is used. Exact subsection is not inferred."
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
    write_csv(out / "doi_tierb_adjudication_v1.csv", adjudication)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_rows": len(remaining),
        "effective_unresolved_before_this_layer": 37,
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "inventory_sha256_verified": 1,
        "source_html_sha256_verified": 1,
        "visible_text_sha256_verified": 1,
        "manual_adjudication_performed": 1,
        "direct_section_evidence_accepted": 1,
        "accepted_broad_section": "I",
        "accepted_exact_subsection": "",
        "target_excluded_from_section_ii_science_cohort": 1,
        "members_resolved_by_this_layer": 1,
        "effective_unresolved_after_hiratsuka_yoshikawa_nanbara_doi_if_integrated": 36,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(remaining_path),
            "tierb_doi_source_inventory_v1": sha256_file(inventory_path),
            "tobunken_nenshi_5759_doi_html": sha256_file(html_path),
            "tobunken_nenshi_5759_doi_visible_text": sha256_file(text_path),
        },
        "next_action": (
            "Preserve Doi as a Tier-B direct Section I exclusion. Continue the frozen non-J-STAGE "
            "Tier-B institutional search for the effective remaining 36 unresolved members. Do not "
            "write/freeze the final Japan Academy Section II roster until remaining-member closeout."
        ),
    }
    write_json(out / "summary.json", summary)

    md = f"""# Japan Academy remaining-37 Tier-B Doi adjudication v1

Target: {TARGET_NAME}

Source: {SOURCE_ORGANIZATION}, "{SOURCE_TITLE}", {SOURCE_LOCATOR}

Manual review of the preserved source finds a direct statement that at the Japan Academy fourth general meeting, Doi Kochi was selected under **Section I literature**.

Decision: **accept broad Section I and exclude from the Section II science cohort** under the frozen Tier-B explicit-source policy.

No exact subsection is inferred from his discipline. No final roster row, DOB collection, or BaZi variable is written at this layer.
"""
    (out / "TIERB_DOI_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remaining", default=str(DEFAULT_REMAINING))
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    ap.add_argument("--text", default=str(DEFAULT_TEXT))
    ap.add_argument("--html", default=str(DEFAULT_HTML))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(
        Path(args.remaining),
        Path(args.inventory),
        Path(args.text),
        Path(args.html),
        Path(args.out),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
