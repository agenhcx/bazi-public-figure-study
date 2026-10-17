#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining36-tierb-ota-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path(
    "data/japan_academy_remaining40_direct_evidence_queue_v1/"
    "remaining40_direct_evidence_queue_v1.csv"
)
DEFAULT_INVENTORY = Path(
    "data/japan_academy_remaining36_tierb_ota_source_fetch_v1/"
    "tierb_ota_source_inventory_v1.csv"
)
DEFAULT_SOURCE = Path(
    "data/japan_academy_remaining36_tierb_ota_source_fetch_v1/"
    "raw_sources/jsahj_30_123_ota_japan_academy_selection.pdf"
)
DEFAULT_OUT = Path("data/japan_academy_remaining36_tierb_ota_adjudication_v1")

TARGET_KEY = "jpa-unlinked-e0aae7738ae3f733"
TARGET_NAME = "太田 博太郎"
SOURCE_TIER = "B"
SOURCE_ORGANIZATION = "建築史学会"
SOURCE_TITLE = "太田博太郎先生の日本学士院会員選定"
SOURCE_LOCATOR = "建築史学 30巻 (1998), p.123"
SOURCE_DOI = "10.24574/jsahj.30.0_123"

EXPECTED_REMAINING_SHA256 = "bd81f0b4d994833fa5d0d5b04e2dcd036f0670b87aecdcfa08ce9df159acda11"
EXPECTED_INVENTORY_SHA256 = "8983664758e31844ff68bd9daee8c1034ddfc6b43368db529c9d84479bfc30e8"
EXPECTED_SOURCE_SHA256 = "19ca8afccdbef31fd2fa0071cc7e1867375ee3968b8ee08bf3fa66cd537303cf"

DIRECT_MEMBERSHIP_PHRASE = "平成九年十二月十二日、日本学士院会員に選ばれた"
FORBIDDEN_SECTION_TERMS = ("第一部", "第二部", "第1部", "第2部", "分科")


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
    assert TARGET_KEY == "jpa-unlinked-e0aae7738ae3f733"
    assert TARGET_NAME == "太田 博太郎"
    assert SOURCE_TIER == "B"
    assert SOURCE_DOI == "10.24574/jsahj.30.0_123"
    print("SELF-TEST OK: Ota membership-only adjudication constants are consistent")


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
        raise RuntimeError("Ota source inventory SHA256 mismatch")
    if sha256_file(source_path) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Ota preserved PDF SHA256 mismatch")

    remaining = read_csv(remaining_path)
    inventory = read_csv(inventory_path)

    target_rows = [r for r in remaining if r.get("member_key") == TARGET_KEY]
    if len(target_rows) != 1:
        raise RuntimeError(f"Expected one Ota target row, found {len(target_rows)}")
    target = target_rows[0]
    if target.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Target name mismatch: {target.get('name_jp')}")

    inv_rows = [r for r in inventory if r.get("member_key") == TARGET_KEY]
    if len(inv_rows) != 1:
        raise RuntimeError(f"Expected one Ota inventory row, found {len(inv_rows)}")
    inv = inv_rows[0]

    if inv.get("source_tier") != SOURCE_TIER:
        raise RuntimeError(f"Unexpected source tier: {inv.get('source_tier')}")
    if inv.get("sha256") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("Inventory PDF SHA does not match preserved PDF")
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
        "source_locator": SOURCE_LOCATOR,
        "source_doi": SOURCE_DOI,
        "source_url": inv.get("source_url", ""),
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "direct_membership_phrase": DIRECT_MEMBERSHIP_PHRASE,
        "section_terms_present_in_preserved_page": 0,
        "accepted_broad_section": "",
        "accepted_exact_subsection": "",
        "decision": "remain_unresolved_membership_only_no_section_statement",
        "decision_basis": (
            "The Architecture History Society article directly confirms Ota Hirotaro's "
            "selection as a Japan Academy member, but the preserved one-page article does "
            "not state Japan Academy Section I/II or a subsection. Under the frozen explicit-source "
            "policy, membership alone cannot resolve section, and architectural-history discipline "
            "must not be used as a proxy."
        ),
        "manual_adjudication_performed": 1,
        "direct_membership_evidence_accepted": 1,
        "direct_section_evidence_accepted": 0,
        "target_remains_unresolved": 1,
        "final_roster_row_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
    }]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "ota_tierb_adjudication_v1.csv", adjudication)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_rows": len(remaining),
        "effective_unresolved_before_this_layer": 36,
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "inventory_sha256_verified": 1,
        "source_pdf_sha256_verified": 1,
        "manual_adjudication_performed": 1,
        "direct_membership_evidence_accepted": 1,
        "direct_section_evidence_accepted": 0,
        "accepted_broad_section": "",
        "accepted_exact_subsection": "",
        "target_remains_unresolved": 1,
        "members_resolved_by_this_layer": 0,
        "effective_unresolved_after_this_layer": 36,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(remaining_path),
            "tierb_ota_source_inventory_v1": sha256_file(inventory_path),
            "jsahj_30_123_ota_japan_academy_selection_pdf": sha256_file(source_path),
        },
        "next_action": (
            "Keep Ota unresolved. Continue the frozen non-J-STAGE or other institutional Tier-B "
            "search for an explicit Japan Academy Section I/II or subsection statement. "
            "Do not infer section from architecture or architectural-history specialization."
        ),
    }
    write_json(out / "summary.json", summary)

    md = f"""# Japan Academy remaining-36 Tier-B Ota adjudication v1

Target: {TARGET_NAME}

Source: {SOURCE_ORGANIZATION}, "{SOURCE_TITLE}", {SOURCE_LOCATOR}

The preserved one-page article directly confirms that Ota Hirotaro was selected as a Japan Academy member.

However, the article contains **no explicit Japan Academy Section I/II or subsection statement**.

Decision: **remain unresolved** under the frozen explicit-source policy.

Membership alone is insufficient, and no section is inferred from architecture or architectural-history specialization. No final roster row, DOB collection, or BaZi variable is written at this layer.
"""
    (out / "TIERB_OTA_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

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
