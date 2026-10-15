#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-ndl-official-text-collection-v1"
DEFAULT_INPUT = Path("data/japan_academy_imperial_page_queue_freeze_v1/approved_member_page_queue_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_ndl_official_text_v1")
API_TEMPLATE = "https://lab.ndl.go.jp/dl/api/book/fulltext/{pid}"
UA = "bazi-public-figure-study/1.0 (Japan Academy official roster text collection; no roster acceptance)"
SLEEP_SECONDS = float(os.environ.get("JAPAN_ACADEMY_NDL_TEXT_SLEEP", "0.25"))
MAX_BYTES = int(os.environ.get("JAPAN_ACADEMY_NDL_TEXT_MAX_BYTES", str(150 * 1024 * 1024)))
RETRIES = int(os.environ.get("JAPAN_ACADEMY_NDL_TEXT_RETRIES", "4"))
EXPECTED_QUEUE_ROWS = 96
EXPECTED_PIDS = 32
PAGE_TXT_RE = re.compile(r"^(?P<pid>\d+)_(?P<page>\d{7})\.txt$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
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


def cache_paths(out: Path, pid: str) -> tuple[Path, Path]:
    base = out / "cache" / "fulltext"
    return base / f"{pid}.json", base / f"{pid}.zip"


def validate_cached(meta_path: Path, zip_path: Path, url: str) -> tuple[dict[str, Any], bytes] | None:
    if not meta_path.exists() or not zip_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    data = zip_path.read_bytes()
    if meta.get("url") != url:
        return None
    if meta.get("sha256") != sha256_bytes(data):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            bad = z.testzip()
            if bad:
                return None
    except zipfile.BadZipFile:
        return None
    meta = dict(meta)
    meta["cache_state"] = "cached_hash_verified"
    return meta, data


def fetch_zip(url: str) -> tuple[dict[str, Any], bytes]:
    last_error = ""
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/zip,application/octet-stream,*/*;q=0.5",
                    "Accept-Language": "ja,en;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                status = int(getattr(r, "status", 200) or 200)
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise RuntimeError(f"Response exceeds MAX_BYTES={MAX_BYTES}")
                    chunks.append(chunk)
                data = b"".join(chunks)
                if not zipfile.is_zipfile(io.BytesIO(data)):
                    preview = data[:200].decode("utf-8", "replace")
                    raise RuntimeError(f"Response is not ZIP; content_type={r.headers.get('Content-Type','')}; preview={preview!r}")
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    bad = z.testzip()
                    if bad:
                        raise RuntimeError(f"ZIP integrity failure at {bad}")
                return {
                    "url": url,
                    "final_url": r.geturl(),
                    "state": "fetched",
                    "http_status": status,
                    "error": "",
                    "bytes": len(data),
                    "sha256": sha256_bytes(data),
                    "content_type": r.headers.get("Content-Type", ""),
                    "cache_state": "new",
                }, data
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read(500)
            except Exception:
                pass
            last_error = f"HTTP {e.code}: {e.reason}; preview={body.decode('utf-8','replace')!r}"
            if e.code not in {408, 425, 429, 500, 502, 503, 504}:
                return {
                    "url": url, "final_url": url, "state": "http_error", "http_status": e.code,
                    "error": last_error, "bytes": 0, "sha256": "", "content_type": "", "cache_state": "",
                }, b""
        except Exception as e:
            last_error = repr(e)
        if attempt + 1 < RETRIES:
            time.sleep(min(16.0, 2.0 ** attempt))
    return {
        "url": url, "final_url": url, "state": "network_or_parse_error", "http_status": "",
        "error": last_error, "bytes": 0, "sha256": "", "content_type": "", "cache_state": "",
    }, b""


def extract_page_texts(data: bytes, pid: str) -> tuple[dict[int, str], list[str]]:
    pages: dict[int, str] = {}
    names: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        for name in names:
            base = name.rsplit("/", 1)[-1]
            m = PAGE_TXT_RE.fullmatch(base)
            if not m or m.group("pid") != pid:
                continue
            page = int(m.group("page"))
            text = z.read(name).decode("utf-8-sig", "replace")
            if page in pages and pages[page] != text:
                raise RuntimeError(f"Conflicting duplicate page text for PID {pid} page {page}")
            pages[page] = text
    return pages, names


def text_metrics(text: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", "", text)
    return {
        "ocr_text_chars": len(text),
        "ocr_text_nonspace_chars": len(compact),
        "ocr_text_lines": len(text.splitlines()),
        "contains_member_heading": int(bool(re.search(r"會員|会員", text))),
        "contains_section1_heading": int("第一部" in text),
        "contains_section2_heading": int("第二部" in text),
        "contains_guest_heading": int(bool(re.search(r"客員|客员", text))),
    }


def collect(input_path: Path, out: Path, refresh: bool = False, plan_only: bool = False) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Approved page queue not found: {input_path}")
    rows = read_csv(input_path)
    if len(rows) != EXPECTED_QUEUE_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_QUEUE_ROWS} approved page rows, got {len(rows)}")
    pids = sorted({r.get("pid", "") for r in rows}, key=int)
    if len(pids) != EXPECTED_PIDS or any(not p for p in pids):
        raise RuntimeError(f"Expected {EXPECTED_PIDS} unique nonblank PIDs, got {len(pids)}")
    keys = [(r.get("pid", ""), r.get("canvas_index", "")) for r in rows]
    if len(set(keys)) != len(keys):
        raise RuntimeError("Duplicate PID/canvas in approved queue")

    if plan_only:
        summary = {
            "dataset": SCRIPT_VERSION,
            "plan_only": 1,
            "approved_page_rows": len(rows),
            "unique_pids": len(pids),
            "fulltext_endpoints": [API_TEMPLATE.format(pid=p) for p in pids],
            "images_downloaded": 0,
            "local_ocr_performed": 0,
            "member_names_extracted": 0,
            "roster_rows_accepted": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary

    out.mkdir(parents=True, exist_ok=True)
    text_dir = out / "selected_page_text"
    text_dir.mkdir(parents=True, exist_ok=True)
    api_rows: list[dict[str, Any]] = []
    pages_by_pid: dict[str, dict[int, str]] = {}

    selected_by_pid: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        selected_by_pid[r["pid"]].append(int(r["canvas_index"]))

    for i, pid in enumerate(pids, 1):
        url = API_TEMPLATE.format(pid=pid)
        meta_path, zip_path = cache_paths(out, pid)
        cached = None if refresh else validate_cached(meta_path, zip_path, url)
        if cached:
            meta, data = cached
        else:
            meta, data = fetch_zip(url)
            if data:
                meta_path.parent.mkdir(parents=True, exist_ok=True)
                zip_path.write_bytes(data)
                write_json(meta_path, meta)
        page_map: dict[int, str] = {}
        zip_names: list[str] = []
        parse_error = ""
        if data:
            try:
                page_map, zip_names = extract_page_texts(data, pid)
            except Exception as e:
                parse_error = repr(e)
        selected = sorted(set(selected_by_pid[pid]))
        exact_hits = sum(x in page_map for x in selected)
        minus_one_hits = sum((x - 1) in page_map for x in selected)
        plus_one_hits = sum((x + 1) in page_map for x in selected)
        pages_by_pid[pid] = page_map
        api_rows.append({
            "pid": pid,
            "fulltext_url": url,
            "state": meta.get("state", ""),
            "http_status": meta.get("http_status", ""),
            "error": meta.get("error", ""),
            "parse_error": parse_error,
            "cache_state": meta.get("cache_state", ""),
            "response_bytes": meta.get("bytes", 0),
            "response_sha256": meta.get("sha256", ""),
            "zip_member_count": len(zip_names),
            "page_text_files": len(page_map),
            "selected_pages": len(selected),
            "selected_exact_page_hits": exact_hits,
            "selected_minus_one_hits": minus_one_hits,
            "selected_plus_one_hits": plus_one_hits,
            "page_index_offset_applied": 0,
            "images_downloaded": 0,
            "local_ocr_performed": 0,
            "roster_rows_accepted": 0,
        })
        print(f"[{i}/{len(pids)}] pid={pid} state={meta.get('state')} selected_text={exact_hits}/{len(selected)} cache={meta.get('cache_state','')}")
        if i < len(pids) and not cached:
            time.sleep(SLEEP_SECONDS)

    page_rows: list[dict[str, Any]] = []
    for r in rows:
        pid = r["pid"]
        canvas = int(r["canvas_index"])
        text = pages_by_pid.get(pid, {}).get(canvas, "")
        text_path = text_dir / f"{pid}_{canvas:07d}.txt"
        if text:
            text_path.write_text(text, encoding="utf-8")
            text_rel = str(text_path.relative_to(out)).replace("\\", "/")
            text_sha = sha256_file(text_path)
        else:
            text_rel = ""
            text_sha = ""
        metrics = text_metrics(text)
        api_state = next(a["state"] for a in api_rows if a["pid"] == pid)
        exact_found = int(bool(text))
        page_rows.append({
            "snapshot_year": r.get("snapshot_year", ""),
            "pid": pid,
            "bibliographic_title": r.get("bibliographic_title", ""),
            "range_label": r.get("range_label", ""),
            "range_classification": r.get("range_classification", ""),
            "selection_basis": r.get("selection_basis", ""),
            "canvas_index": canvas,
            "canvas_id": r.get("canvas_id", ""),
            "image_url": r.get("image_url", ""),
            "fulltext_url": API_TEMPLATE.format(pid=pid),
            "api_state": api_state,
            "exact_page_text_found": exact_found,
            "text_path": text_rel,
            "text_sha256": text_sha,
            **metrics,
            "official_text_review_required": int(not exact_found or metrics["ocr_text_nonspace_chars"] < 20),
            "image_fallback_candidate": int(not exact_found or metrics["ocr_text_nonspace_chars"] < 20),
            "member_names_extracted": 0,
            "roster_rows_accepted": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    api_fields = list(api_rows[0].keys())
    page_fields = list(page_rows[0].keys())
    write_csv(out / "fulltext_api_inventory_v1.csv", api_rows, api_fields)
    write_csv(out / "selected_page_text_inventory_v1.csv", page_rows, page_fields)
    fallback = [r for r in page_rows if int(r["image_fallback_candidate"]) == 1]
    write_csv(out / "image_fallback_page_queue_v1.csv", fallback, page_fields)

    state_counts = Counter(r["state"] for r in api_rows)
    cache_counts = Counter(r["cache_state"] for r in api_rows)
    exact_pages = sum(int(r["exact_page_text_found"]) for r in page_rows)
    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": "2026-10-14",
        "input_approved_page_rows": len(rows),
        "unique_pids": len(pids),
        "api_state_counts": dict(state_counts),
        "cache_state_counts": dict(cache_counts),
        "selected_pages_with_exact_official_ocr_text": exact_pages,
        "selected_pages_without_exact_official_ocr_text": len(page_rows) - exact_pages,
        "selected_pages_requiring_text_or_image_review": len(fallback),
        "all_selected_pages_exactly_mapped": int(exact_pages == len(page_rows)),
        "page_index_offset_applied": 0,
        "images_downloaded": 0,
        "local_ocr_performed": 0,
        "member_names_extracted": 0,
        "roster_rows_accepted": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "warning": (
            "NDL OCR text is an official machine-generated aid and may contain recognition or reading-order errors. "
            "No member identity or Section II classification is accepted in this collection step."
        ),
        "input_sha256": {"approved_member_page_queue": sha256_file(input_path)},
    }
    write_json(out / "summary.json", summary)

    output_files = [
        "fulltext_api_inventory_v1.csv",
        "selected_page_text_inventory_v1.csv",
        "image_fallback_page_queue_v1.csv",
        "summary.json",
    ]
    manifest = {
        "dataset": SCRIPT_VERSION,
        "files": {
            name: {"sha256": sha256_file(out / name), "bytes": (out / name).stat().st_size}
            for name in output_files
        },
        "selected_text_files": {
            str(p.relative_to(out)).replace("\\", "/"): {"sha256": sha256_file(p), "bytes": p.stat().st_size}
            for p in sorted(text_dir.glob("*.txt"))
        },
        "guardrails": {
            "images_downloaded": 0,
            "local_ocr_performed": 0,
            "member_names_extracted": 0,
            "roster_rows_accepted": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        },
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def self_test() -> None:
    pid = "123456"
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{pid}_0000007.txt", "第一部\n山田\n")
        z.writestr(f"{pid}_0000008.txt", "第二部\n会員\n佐藤\n")
        z.writestr(f"{pid}.txt", "combined")
        z.writestr(f"{pid}_0000008.json", "{}")
    pages, names = extract_page_texts(bio.getvalue(), pid)
    assert sorted(pages) == [7, 8]
    assert "第二部" in pages[8]
    assert len(names) == 4
    m = text_metrics(pages[8])
    assert m["contains_section2_heading"] == 1 and m["contains_member_heading"] == 1
    print("SELF-TEST OK: NDL full-text ZIP parsing and exact selected-page text mapping are consistent")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    collect(Path(args.input), Path(args.out), refresh=args.refresh, plan_only=args.plan_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
