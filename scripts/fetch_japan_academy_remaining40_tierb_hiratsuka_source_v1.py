#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-tierb-hiratsuka-source-fetch-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path("data/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_tierb_hiratsuka_source_fetch_v1")

TARGET_KEY = "jpa-unlinked-67412ee03b08c5d2"
TARGET_NAME = "平塚 直秀"
SOURCE_URL = "https://www.jstage.jst.go.jp/article/jjom/41/4/41_H11-175/_pdf/-char/ja"
SOURCE_ORGANIZATION = "日本菌学会"
SOURCE_TITLE = "平塚直秀先生を悼む"
SOURCE_TIER = "B"
UA = "bazi-public-figure-study/1.0 (noncommercial research)"
TIMEOUT = 90
MAX_BYTES = 20 * 1024 * 1024

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

def pdf_integrity_ok(body: bytes) -> bool:
    return bool(body.startswith(b"%PDF-") and b"%%EOF" in body[-65536:])

def fetch_urllib(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"source exceeds MAX_BYTES={MAX_BYTES}")
    return body

def fetch_curl(url: str, path: Path) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl/curl.exe not available")
    tmp = path.with_suffix(path.suffix + ".part")
    cmd = [
        curl, "--fail", "--location", "--retry", "5", "--retry-all-errors",
        "--connect-timeout", "30", "--max-time", "300",
        "--silent", "--show-error", "--output", str(tmp), url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed rc={proc.returncode}: {(proc.stderr or proc.stdout).strip()}")
    body = tmp.read_bytes()
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"source exceeds MAX_BYTES={MAX_BYTES}")
    tmp.replace(path)
    return body

def self_test() -> None:
    assert TARGET_NAME == "平塚 直秀"
    assert SOURCE_TIER == "B"
    assert "jstage.jst.go.jp/article/jjom/" in SOURCE_URL
    assert pdf_integrity_ok(b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF\n")
    print("SELF-TEST OK: Tier-B Hiratsuka source constants and PDF integrity checks are consistent")

def run(remaining_path: Path, out: Path, refresh: bool = False) -> None:
    if not remaining_path.exists():
        raise FileNotFoundError(remaining_path)

    rows = read_csv(remaining_path)
    hits = [r for r in rows if r.get("member_key") == TARGET_KEY]
    if len(hits) != 1:
        raise RuntimeError(f"Expected one target row for {TARGET_KEY}, found {len(hits)}")
    target = hits[0]
    if target.get("name_jp") != TARGET_NAME:
        raise RuntimeError(f"Target-name mismatch: {target.get('name_jp')}")

    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw_sources"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / "hiratsuka_naohide_jjom_41_4_obituary.pdf"

    print(f"[start] target={TARGET_NAME} source_tier={SOURCE_TIER} url={SOURCE_URL}", flush=True)

    state = ""
    transport = ""
    primary_error = ""
    error = ""
    body = b""

    try:
        if path.exists() and not refresh:
            body = path.read_bytes()
            if pdf_integrity_ok(body):
                state = "cached_local"
                transport = "local_cache"
            else:
                path.unlink()

        if not body:
            try:
                body = fetch_urllib(SOURCE_URL)
                if not pdf_integrity_ok(body):
                    raise RuntimeError(f"urllib body failed PDF integrity check bytes={len(body)}")
                path.write_bytes(body)
                state = "fetched"
                transport = "urllib"
            except Exception as e:
                primary_error = f"{type(e).__name__}: {e}"
                body = fetch_curl(SOURCE_URL, path)
                if not pdf_integrity_ok(body):
                    raise RuntimeError(f"curl body failed PDF integrity check bytes={len(body)}")
                state = "fetched_curl_fallback"
                transport = "curl_fallback"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        state = "error"

    inventory = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": SOURCE_URL,
        "local_source_path": str(path),
        "fetch_state": state,
        "fetch_transport": transport,
        "urllib_primary_error": primary_error,
        "bytes": len(body),
        "sha256": sha256_bytes(body) if body else "",
        "pdf_magic_ok": int(body.startswith(b"%PDF-")) if body else 0,
        "pdf_eof_ok": int(b"%%EOF" in body[-65536:]) if body else 0,
        "manual_adjudication_performed": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_row_written": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "error": error,
    }]

    write_csv(out / "tierb_hiratsuka_source_inventory_v1.csv", inventory)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_rows": len(rows),
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_fetched_valid_pdf": int(bool(body) and pdf_integrity_ok(body)),
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
            "Upload the preserved PDF and inventory for manual adjudication under the frozen Tier-B policy. "
            "Do not write a final roster row until the direct wording is archived and adjudicated."
        ),
    }
    write_json(out / "summary.json", summary)
    print(
        f"[done] state={state} bytes={len(body)} sha256={sha256_bytes(body) if body else ''}",
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
