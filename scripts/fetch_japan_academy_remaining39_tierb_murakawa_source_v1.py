#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining39-tierb-murakawa-source-fetch-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_QUEUE = Path(
    "data/japan_academy_remaining39_tierb_jstage_strong_institutional_intersection_v1/"
    "tierb_strong_institutional_intersection_candidates_v1.csv"
)
DEFAULT_OUT = Path("data/japan_academy_remaining39_tierb_murakawa_source_fetch_v1")

EXPECTED_DOI = "10.5955/jalha.2005.121"
EXPECTED_MEMBER_KEY = "jpa-unlinked-5eb8bdd403e08b8c"
EXPECTED_NAME = "村川 堅太郎"
EXPECTED_JOURNAL = "jalha1951"
EXPECTED_STRONG_TERM = "日本学士院第一部"

SOURCE_TIER = "B"
SOURCE_ORGANIZATION = "法制史学会"
SOURCE_TITLE = "古代ギリシア史研究と奴隷制"
PDF_URL = "https://www.jstage.jst.go.jp/article/jalha1951/2005/55/2005_55_121/_pdf/-char/ja/"

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
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/pdf,*/*;q=0.8"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"PDF exceeds MAX_BYTES={MAX_BYTES}")
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
        "--max-time", "300",
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
        raise RuntimeError(f"PDF exceeds MAX_BYTES={MAX_BYTES}")
    if not pdf_integrity_ok(body):
        raise RuntimeError(f"curl download incomplete_or_invalid bytes={len(body)}")
    tmp.replace(path)
    return body

def self_test() -> None:
    assert EXPECTED_DOI == "10.5955/jalha.2005.121"
    assert EXPECTED_NAME == "村川 堅太郎"
    assert SOURCE_TIER == "B"
    assert EXPECTED_STRONG_TERM == "日本学士院第一部"
    assert pdf_integrity_ok(b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF\n")
    print("SELF-TEST OK: Murakawa Tier-B source constants and PDF integrity checks are consistent")

def run(queue_path: Path, out: Path, refresh: bool = False) -> None:
    if not queue_path.exists():
        raise FileNotFoundError(queue_path)

    rows = read_csv(queue_path)
    if len(rows) != 1:
        raise RuntimeError(f"Expected one strong-intersection row, found {len(rows)}")
    row = rows[0]

    checks = {
        "doi": (row.get("doi", ""), EXPECTED_DOI),
        "member_key": (row.get("target_member_keys", ""), EXPECTED_MEMBER_KEY),
        "name": (row.get("target_members", ""), EXPECTED_NAME),
        "cdjournal": (row.get("cdjournal", ""), EXPECTED_JOURNAL),
        "strong_term": (row.get("matched_strong_terms", ""), EXPECTED_STRONG_TERM),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise RuntimeError(f"{label} mismatch: expected {expected!r}, found {actual!r}")

    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw_sources"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / "murakawa_candidate_jalha_2005_121.pdf"

    print(
        f"[start] target={EXPECTED_NAME} doi={EXPECTED_DOI} "
        f"source_tier={SOURCE_TIER} url={PDF_URL}",
        flush=True,
    )

    state = ""
    transport = ""
    urllib_primary_error = ""
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
                body = b""

        if not body:
            try:
                body = fetch_urllib(PDF_URL)
                if not pdf_integrity_ok(body):
                    raise RuntimeError(
                        f"urllib body failed PDF integrity check bytes={len(body)}"
                    )
                path.write_bytes(body)
                state = "fetched"
                transport = "urllib"
            except Exception as e:
                urllib_primary_error = f"{type(e).__name__}: {e}"
                print(
                    f"[fallback] urllib failed: {urllib_primary_error}; trying curl",
                    flush=True,
                )
                body = fetch_curl(PDF_URL, path)
                state = "fetched_curl_fallback"
                transport = "curl_fallback"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        state = "error"

    inventory = [{
        "member_key": EXPECTED_MEMBER_KEY,
        "name_jp": EXPECTED_NAME,
        "doi": EXPECTED_DOI,
        "matched_strong_term": EXPECTED_STRONG_TERM,
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_title": SOURCE_TITLE,
        "source_url": PDF_URL,
        "local_source_path": str(path),
        "fetch_state": state,
        "fetch_transport": transport,
        "urllib_primary_error": urllib_primary_error,
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
    write_csv(out / "tierb_murakawa_source_inventory_v1.csv", inventory)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_intersection_rows": len(rows),
        "target_member_key": EXPECTED_MEMBER_KEY,
        "target_name_jp": EXPECTED_NAME,
        "doi": EXPECTED_DOI,
        "matched_strong_term": EXPECTED_STRONG_TERM,
        "source_tier": SOURCE_TIER,
        "source_organization": SOURCE_ORGANIZATION,
        "source_fetched_valid_pdf": int(bool(body) and pdf_integrity_ok(body)),
        "manual_adjudication_performed": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "tierb_strong_institutional_intersection_candidates_v1": sha256_file(queue_path),
        },
        "next_action": (
            "Upload the preserved PDF and inventory. Manually inspect the exact occurrences of 村川堅太郎 "
            "and 日本学士院第一部. Accept only if the source directly binds the target person to Japan Academy "
            "Section I/II or a subsection; otherwise record a contextual false positive."
        ),
    }
    write_json(out / "summary.json", summary)

    print(
        f"[done] state={state} bytes={len(body)} "
        f"sha256={sha256_bytes(body) if body else ''}",
        flush=True,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.queue), Path(args.out), refresh=args.refresh)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
