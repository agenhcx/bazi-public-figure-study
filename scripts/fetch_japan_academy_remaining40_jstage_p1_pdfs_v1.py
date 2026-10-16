#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-jstage-p1-pdf-fetch-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-16"

DEFAULT_INPUT = Path("data/japan_academy_remaining40_jstage_triage_v1/jstage_priority1_pdf_fetch_queue_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_p1_pdf_fetch_v1")

EXPECTED_ROWS = 3
UA = "bazi-public-figure-study/1.0 (noncommercial research; Powered by J-STAGE)"
TIMEOUT = 90
MAX_BYTES = 80 * 1024 * 1024

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

def safe_pdf_name(doi: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", str(doi or "")).strip("._")
    return (s or "article") + ".pdf"

def self_test() -> None:
    assert safe_pdf_name("10.2183/tja1948.36.suppl_1") == "10.2183_tja1948.36.suppl_1.pdf"
    assert safe_pdf_name("10.2183/tja1948.50.129").endswith(".pdf")
    print("SELF-TEST OK: P1 PDF filename normalization is consistent")

def fetch_pdf(url: str) -> tuple[bytes, int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        status = getattr(resp, "status", 200)
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"PDF exceeds MAX_BYTES={MAX_BYTES}")
    return body, status, ctype

def run(inp: Path, out: Path, refresh: bool = False) -> None:
    if not inp.exists():
        raise FileNotFoundError(inp)

    rows = read_csv(inp)
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} P1 rows, found {len(rows)}")

    expected_dois = {
        "10.2183/tja1948.15.271",
        "10.2183/tja1948.36.suppl_1",
        "10.2183/tja1948.50.129",
    }
    actual_dois = {r.get("doi", "") for r in rows}
    if actual_dois != expected_dois:
        raise RuntimeError(f"Unexpected P1 DOI set: {sorted(actual_dois)}")

    pdf_dir = out / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, Any]] = []
    started = time.monotonic()

    print(f"[start] p1_pdfs={len(rows)} timeout={TIMEOUT}s output={out}", flush=True)

    for i, r in enumerate(rows, start=1):
        doi = r.get("doi", "")
        url = r.get("article_pdf_url", "")
        if not url:
            raise RuntimeError(f"Missing article_pdf_url for {doi}")

        path = pdf_dir / safe_pdf_name(doi)
        state = ""
        status: int | str = ""
        ctype = ""
        error = ""

        try:
            if path.exists() and not refresh:
                body = path.read_bytes()
                state = "cached_local"
            else:
                body, status, ctype = fetch_pdf(url)
                path.write_bytes(body)
                state = "fetched"

            pdf_magic_ok = int(body.startswith(b"%PDF-"))
            if not pdf_magic_ok:
                error = "downloaded_body_missing_pdf_magic"
                state = "invalid_pdf"
        except urllib.error.HTTPError as e:
            body = b""
            state = "http_error"
            status = e.code
            error = f"{e.code} {e.reason}"
            pdf_magic_ok = 0
        except Exception as e:
            body = b""
            state = "error"
            error = f"{type(e).__name__}: {e}"
            pdf_magic_ok = 0

        inventory.append({
            "doi": doi,
            "article_title_ja": r.get("article_title_ja", ""),
            "target_members": r.get("target_members", ""),
            "target_member_keys": r.get("target_member_keys", ""),
            "article_pdf_url": url,
            "local_pdf_path": str(path),
            "fetch_state": state,
            "http_status": status,
            "content_type": ctype,
            "bytes": len(body),
            "sha256": sha256_bytes(body) if body else "",
            "pdf_magic_ok": pdf_magic_ok,
            "error": error,
            "text_extraction_performed": 0,
            "ocr_performed": 0,
            "automatic_section_acceptance": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

        print(
            f"[progress] {i}/{len(rows)} doi={doi} state={state} "
            f"bytes={len(body)} elapsed={time.monotonic()-started:.1f}s",
            flush=True,
        )

    write_csv(out / "p1_pdf_fetch_inventory_v1.csv", inventory)

    ok = [r for r in inventory if r["pdf_magic_ok"] == 1]
    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_queue_rows": len(rows),
        "pdfs_valid": len(ok),
        "pdfs_failed_or_invalid": len(rows) - len(ok),
        "fetched_or_cached_states": {
            state: sum(1 for r in inventory if r["fetch_state"] == state)
            for state in sorted({r["fetch_state"] for r in inventory})
        },
        "text_extraction_performed": 0,
        "ocr_performed": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {"jstage_priority1_pdf_fetch_queue_v1": sha256_file(inp)},
        "next_action": (
            "Upload the three preserved PDFs plus inventory. Review PDF text/images for explicit Japan Academy "
            "Section I/II or subsection statements tied to the target persons; do not infer from discipline."
        ),
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.input), Path(args.out), refresh=args.refresh)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
