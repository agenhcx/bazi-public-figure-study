#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining36-tierb-tobunken-p1-adjudication-closeout-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_CANDIDATES = Path(
    "data/japan_academy_remaining36_tierb_tobunken_targeted_discovery_v1/"
    "tobunken_targeted_candidates_v1.csv"
)
DEFAULT_HTML = Path(
    "data/japan_academy_remaining36_tierb_tobunken_targeted_discovery_v1/"
    "raw_sources/jpa-unlinked-3df2f47ee9476d2e_5657.html"
)
DEFAULT_TEXT = Path(
    "data/japan_academy_remaining36_tierb_tobunken_targeted_discovery_v1/"
    "raw_sources/jpa-unlinked-3df2f47ee9476d2e_5657_visible_text.txt"
)
DEFAULT_OUT = Path(
    "data/japan_academy_remaining36_tierb_tobunken_p1_adjudication_closeout_v1"
)

EXPECTED_CANDIDATES_SHA256 = "d80c580b794f918144755c315a9aa2b1feb948348bd7ad41adb70a84f79bd55e"
EXPECTED_HTML_SHA256 = "0ce268028eeaa3b789b811a280e7fa6bc8fe719277b146691f5e75542e33158a"
EXPECTED_TEXT_SHA256 = "8d99404cf6f2a5eb38d1032fdb954dbb8495513fc31c601b35d7346d29de5470"

TARGET_KEY = "jpa-unlinked-3df2f47ee9476d2e"
TARGET_NAME = "柳田 国男"
SOURCE_URL = "https://www.tobunken.go.jp/materials/nenshi/5657.html"
SOURCE_TITLE = "芸術院々長決定"
SOURCE_ORGANIZATION = "東京文化財研究所"
SOURCE_TIER = "B"

EXPECTED_CANDIDATE_ROWS = 42
EXPECTED_P1_ROWS = 1
EXPECTED_P2_ROWS = 0
EXPECTED_MEMBERS_WITH_CANDIDATES = 9

# Manual semantic reading of the preserved paragraph:
# - 第一部 / 第二部 / 第三部 modify 日本芸術院, not 日本学士院.
# - 学士院会員 modifies 高橋誠一郎, not 柳田国男.
# - 柳田国男 is only one of the candidates recommended for 日本芸術院長.
KEY_PHRASE_ART_ACADEMY = "日本芸術院々長の後任は第一部"
KEY_PHRASE_YANAGITA = "高橋誠一郎 ・柳田国男が推薦され"
KEY_PHRASE_JAPAN_ACADEMY_MEMBER = "前文部大臣学士院会員 高橋誠一郎 が決定"


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
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(s: str) -> str:
    return "".join((s or "").split())


def self_test() -> None:
    sample = (
        "日本芸術院々長の後任は第一部 和田英作・鏑木清方、第二部山本勇造・志賀直哉、"
        "第三部信時潔・喜多六平太の各部二名の候補者選考委員によつて"
        "高橋誠一郎・柳田国男が推薦され、更に全員の投票によつて"
        "前文部大臣学士院会員高橋誠一郎が決定、一一日発令された。"
    )
    n = norm(sample)
    assert norm(KEY_PHRASE_ART_ACADEMY) in n
    assert norm(KEY_PHRASE_YANAGITA) in n
    assert norm(KEY_PHRASE_JAPAN_ACADEMY_MEMBER) in n
    assert TARGET_KEY == "jpa-unlinked-3df2f47ee9476d2e"
    print("SELF-TEST OK: Tobunken P1 false-positive adjudication constants are consistent")


def run(
    candidates_path: Path,
    html_path: Path,
    text_path: Path,
    out: Path,
) -> None:
    for p in (candidates_path, html_path, text_path):
        if not p.exists():
            raise FileNotFoundError(p)

    if sha256_file(candidates_path) != EXPECTED_CANDIDATES_SHA256:
        raise RuntimeError("candidate CSV SHA256 mismatch")
    if sha256_file(html_path) != EXPECTED_HTML_SHA256:
        raise RuntimeError("preserved P1 HTML SHA256 mismatch")
    if sha256_file(text_path) != EXPECTED_TEXT_SHA256:
        raise RuntimeError("preserved P1 visible-text SHA256 mismatch")

    rows = read_csv(candidates_path)
    if len(rows) != EXPECTED_CANDIDATE_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_CANDIDATE_ROWS} candidate rows, found {len(rows)}"
        )

    p1 = [r for r in rows if r.get("review_priority", "").startswith("P1")]
    p2 = [r for r in rows if r.get("review_priority", "").startswith("P2")]
    members = {r.get("member_key", "") for r in rows if r.get("member_key")}

    if len(p1) != EXPECTED_P1_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_P1_ROWS} P1 row, found {len(p1)}")
    if len(p2) != EXPECTED_P2_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_P2_ROWS} P2 rows, found {len(p2)}")
    if len(members) != EXPECTED_MEMBERS_WITH_CANDIDATES:
        raise RuntimeError(
            f"Expected {EXPECTED_MEMBERS_WITH_CANDIDATES} members with candidates, found {len(members)}"
        )

    row = p1[0]
    if row.get("member_key") != TARGET_KEY:
        raise RuntimeError(f"Unexpected P1 member key: {row.get('member_key')}")
    if row.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Unexpected P1 target name: {row.get('name_jp')}")
    if row.get("source_url") != SOURCE_URL:
        raise RuntimeError(f"Unexpected P1 source URL: {row.get('source_url')}")
    if row.get("html_sha256") != EXPECTED_HTML_SHA256:
        raise RuntimeError("P1 CSV HTML SHA does not match preserved HTML")
    if row.get("visible_text_sha256") != EXPECTED_TEXT_SHA256:
        raise RuntimeError("P1 CSV visible-text SHA does not match preserved text")

    visible = text_path.read_text(encoding="utf-8")
    vn = norm(visible)
    for phrase in (
        KEY_PHRASE_ART_ACADEMY,
        KEY_PHRASE_YANAGITA,
        KEY_PHRASE_JAPAN_ACADEMY_MEMBER,
    ):
        if norm(phrase) not in vn:
            raise RuntimeError(f"Expected preserved phrase missing: {phrase}")

    adjudication = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": SOURCE_URL,
        "source_html_sha256": EXPECTED_HTML_SHA256,
        "visible_text_sha256": EXPECTED_TEXT_SHA256,
        "machine_priority": "P1_same_block_target_academy_section",
        "manual_semantic_finding": (
            "The section labels 第一部/第二部/第三部 belong to 日本芸術院 in a succession "
            "process for the Japan Art Academy presidency. 柳田国男 is named as one of the "
            "recommended candidates. The later phrase 学士院会員 modifies 高橋誠一郎, "
            "who was ultimately appointed. The paragraph does not bind 柳田国男 to "
            "日本学士院 Section I/II or a subsection."
        ),
        "adjudication": "remain_unresolved_cross_institution_context_false_positive",
        "accepted_broad_section": "",
        "accepted_exact_subsection": "",
        "direct_section_evidence_accepted": 0,
        "target_remains_unresolved": 1,
        "final_roster_row_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
    }]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "yanagita_tobunken_p1_adjudication_v1.csv", adjudication)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "effective_unresolved_before_this_layer": 36,
        "candidate_articles_with_exact_target": len(rows),
        "members_with_any_candidate": len(members),
        "p1_rows_reviewed": len(p1),
        "p2_rows": len(p2),
        "p1_target_member_key": TARGET_KEY,
        "p1_target_name_jp": TARGET_NAME,
        "p1_manual_adjudication": "cross_institution_context_false_positive",
        "p1_direct_section_evidence_accepted": 0,
        "members_resolved_by_this_layer": 0,
        "effective_unresolved_after_this_layer": 36,
        "tobunken_targeted_route_status": "closed_no_new_section_resolution",
        "route_interpretation": (
            "The systematic Tobunken targeted sweep of the 36 effective unresolved members "
            "returned 42 exact-name candidate articles across 9 members. Only one P1 same-block "
            "candidate was produced and no P2 candidate. Manual review shows the P1 to be a "
            "cross-institution false positive: its section labels are Japan Art Academy divisions, "
            "while the Japan Academy membership wording refers to Takahashi Seiichiro rather than "
            "Yanagita Kunio. No new Japan Academy section assignment is accepted from this route."
        ),
        "automatic_section_acceptance": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "tobunken_targeted_candidates_v1": sha256_file(candidates_path),
            "yanagita_5657_html": sha256_file(html_path),
            "yanagita_5657_visible_text": sha256_file(text_path),
        },
        "next_action": (
            "Deprioritize the Tobunken targeted-search route after this systematic closeout. "
            "Continue with other Tier-A/Tier-B institutional sources such as university archives, "
            "academic-society memorials, institutional chronologies, and Japan Academy publications. "
            "Keep all 36 effective unresolved members unresolved until direct person-to-section evidence is preserved."
        ),
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy remaining-36 Tobunken P1 adjudication and route closeout v1

The targeted Tobunken sweep produced 42 exact-name articles across 9 of the 36 effective unresolved members.

There was exactly one P1 same-block candidate: 柳田国男 in the 1948 article 「芸術院々長決定」.

Manual review shows this is a **cross-institution context false positive**:
- 第一部 / 第二部 / 第三部 refer to 日本芸術院, not 日本学士院.
- 柳田国男 is one of the candidates recommended for the Japan Art Academy presidency.
- the phrase 学士院会員 refers to 高橋誠一郎, who was ultimately appointed.

Therefore 柳田国男 remains unresolved for Japan Academy Section I/II.

The systematic Tobunken targeted route resolves no additional member and is closed/deprioritized.
No final roster row, DOB collection, or BaZi variable is written.
"""
    (out / "TOBUNKEN_P1_ADJUDICATION_CLOSEOUT_V1.md").write_text(
        md,
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    ap.add_argument("--html", default=str(DEFAULT_HTML))
    ap.add_argument("--text", default=str(DEFAULT_TEXT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(
        Path(args.candidates),
        Path(args.html),
        Path(args.text),
        Path(args.out),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
