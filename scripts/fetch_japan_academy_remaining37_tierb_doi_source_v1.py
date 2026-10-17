#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining37-tierb-doi-source-fetch-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path(
    "data/japan_academy_remaining40_direct_evidence_queue_v1/"
    "remaining40_direct_evidence_queue_v1.csv"
)
DEFAULT_OUT = Path("data/japan_academy_remaining37_tierb_doi_source_fetch_v1")

TARGET_KEY = "jpa-unlinked-f21fcc61cad96158"
TARGET_NAME = "土居 光知"
SOURCE_TIER = "B"
SOURCE_ORGANIZATION = "東京文化財研究所"
SOURCE_TITLE = "学士院新会員決る"
SOURCE_URL = "https://www.tobunken.go.jp/materials/nenshi/5759.html"
SOURCE_LOCATOR = "1949年10月「学士院新会員決る」"

# The archived page directly states that Doi was selected in Japan Academy Section I (literature).
EVIDENCE_PATTERN = re.compile(
    r"日本学士院.*第一部\s*文学では.*土居\s*光知\s*が選ばれた"
)

UA = "bazi-public-figure-study/1.0 (noncommercial research)"
TIMEOUT = 60
MAX_BYTES = 8 * 1024 * 1024


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def html_to_visible_text(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def fetch_urllib(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"HTML exceeds MAX_BYTES={MAX_BYTES}")
    return body


def fetch_curl(url: str, path: Path) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl/curl.exe not found")
    tmp = path.with_suffix(path.suffix + ".part")
    cmd = [
        curl,
        "--fail",
        "--location",
        "--retry", "5",
        "--retry-all-errors",
        "--connect-timeout", "30",
        "--max-time", "180",
        "--silent",
        "--show-error",
        "--output", str(tmp),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"curl failed rc={proc.returncode}: {(proc.stderr or proc.stdout).strip()}"
        )
    body = tmp.read_bytes()
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"HTML exceeds MAX_BYTES={MAX_BYTES}")
    tmp.replace(path)
    return body


def self_test() -> None:
    sample = (
        "五日日本学士院第四回総会で二九人の学士院新会員が当選した。"
        "第一部文学では、波多野精一、和辻哲郎、土居光知が選ばれた。"
    )
    assert EVIDENCE_PATTERN.search(sample)
    assert TARGET_KEY == "jpa-unlinked-f21fcc61cad96158"
    assert SOURCE_TIER == "B"
    print("SELF-TEST OK: Doi Tier-B source constants and direct Section I pattern are consistent")


def run(remaining_path: Path, out: Path, refresh: bool = False) -> None:
    if not remaining_path.exists():
        raise FileNotFoundError(remaining_path)

    remaining = read_csv(remaining_path)
    target_rows = [r for r in remaining if r.get("member_key") == TARGET_KEY]
    if len(target_rows) != 1:
        raise RuntimeError(f"Expected one Doi row, found {len(target_rows)}")
    target = target_rows[0]
    if target.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Target name mismatch: {target.get('name_jp')}")

    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw_sources"
    raw_dir.mkdir(parents=True, exist_ok=True)

    html_path = raw_dir / "tobunken_nenshi_5759_doi.html"
    text_path = raw_dir / "tobunken_nenshi_5759_doi_visible_text.txt"

    print(
        f"[start] target={TARGET_NAME} source_tier={SOURCE_TIER} url={SOURCE_URL}",
        flush=True,
    )

    body = b""
    state = ""
    transport = ""
    urllib_primary_error = ""
    error = ""

    try:
        if html_path.exists() and not refresh:
            body = html_path.read_bytes()
            state = "cached_local"
            transport = "local_cache"

        if not body:
            try:
                body = fetch_urllib(SOURCE_URL)
                html_path.write_bytes(body)
                state = "fetched"
                transport = "urllib"
            except Exception as e:
                urllib_primary_error = f"{type(e).__name__}: {e}"
                print(
                    f"[fallback] urllib failed: {urllib_primary_error}; trying curl",
                    flush=True,
                )
                body = fetch_curl(SOURCE_URL, html_path)
                state = "fetched_curl_fallback"
                transport = "curl_fallback"

        visible = html_to_visible_text(body)
        text_path.write_text(visible + "\n", encoding="utf-8")
        target_name_present = int("土居光知" in visible or "土居 光知" in visible)
        heading_present = int("学士院新会員決る" in visible)
        direct_section_statement_present = int(bool(EVIDENCE_PATTERN.search(visible)))
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        state = "error"
        visible = ""
        target_name_present = 0
        heading_present = 0
        direct_section_statement_present = 0

    inventory = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "name_en": target.get("name_en", ""),
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": SOURCE_URL,
        "source_locator": SOURCE_LOCATOR,
        "local_html_path": str(html_path),
        "local_visible_text_path": str(text_path),
        "fetch_state": state,
        "fetch_transport": transport,
        "urllib_primary_error": urllib_primary_error,
        "bytes": len(body),
        "sha256": sha256_bytes(body) if body else "",
        "visible_text_sha256": sha256_file(text_path) if text_path.exists() else "",
        "target_name_present": target_name_present,
        "heading_present": heading_present,
        "direct_section_statement_present": direct_section_statement_present,
        "manual_adjudication_performed": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_row_written": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "error": error,
    }]
    write_csv(out / "tierb_doi_source_inventory_v1.csv", inventory)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_rows": len(remaining),
        "effective_unresolved_before_this_layer": 37,
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_locator": SOURCE_LOCATOR,
        "source_fetched": int(bool(body)),
        "target_name_present": target_name_present,
        "heading_present": heading_present,
        "direct_section_statement_present": direct_section_statement_present,
        "manual_adjudication_performed": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(remaining_path),
        },
        "next_action": (
            "Upload the preserved HTML/text and inventory for manual adjudication. "
            "If the archived Tokyo National Research Institute for Cultural Properties page "
            "directly states that 土居光知 was selected under 日本学士院第一部文学, "
            "accept broad Section I only; do not infer an exact subsection."
        ),
    }
    write_json(out / "summary.json", summary)

    print(
        f"[done] state={state} bytes={len(body)} "
        f"direct_section_statement_present={direct_section_statement_present} "
        f"sha256={sha256_bytes(body) if body else ''}",
        flush=True,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remaining", default=str(DEFAULT_REMAINING))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.remaining), Path(args.out), refresh=args.refresh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
