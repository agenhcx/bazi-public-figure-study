#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-postwar-digital-source-probe-v1"
SNAPSHOT_DATE = "2026-10-15"
DEFAULT_INPUT = Path("data/japan_academy_postwar_official_source_discovery_v1/official_postwar_publication_candidates_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_postwar_digital_source_probe_v1")
EXPECTED_DIGITAL_PIDS = 7
USER_AGENT = "bazi-public-figure-study/1.0 (+noncommercial reproducible research)"

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

def normalize_pid(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    m = re.search(r"\d+", s)
    return m.group(0) if m else ""

def fetch_prefix(url: str, max_bytes: int = 8192) -> tuple[int | None, str, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            status = getattr(r, "status", 200)
            ctype = r.headers.get("Content-Type", "")
            body = r.read(max_bytes)
            return status, ctype, body, ""
    except urllib.error.HTTPError as e:
        body = e.read(min(max_bytes, 8192))
        return e.code, e.headers.get("Content-Type", ""), body, f"HTTPError: {e.code} {e.reason}"
    except Exception as e:
        return None, "", b"", f"{type(e).__name__}: {e}"

def fetch_full(url: str, max_bytes: int = 2_000_000) -> tuple[int | None, str, bytes, str, bool]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            status = getattr(r, "status", 200)
            ctype = r.headers.get("Content-Type", "")
            body = r.read(max_bytes + 1)
            truncated = len(body) > max_bytes
            if truncated:
                body = body[:max_bytes]
            return status, ctype, body, "", truncated
    except urllib.error.HTTPError as e:
        body = e.read(min(max_bytes, 8192))
        return e.code, e.headers.get("Content-Type", ""), body, f"HTTPError: {e.code} {e.reason}", False
    except Exception as e:
        return None, "", b"", f"{type(e).__name__}: {e}", False

def flatten_labels(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        if "label" in obj:
            lab = obj["label"]
            if isinstance(lab, str):
                out.append(lab)
            elif isinstance(lab, dict):
                for v in lab.values():
                    if isinstance(v, list):
                        out.extend(str(x) for x in v)
                    else:
                        out.append(str(v))
        for v in obj.values():
            out.extend(flatten_labels(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(flatten_labels(v))
    return out

def manifest_metrics(body: bytes) -> dict[str, Any]:
    try:
        obj = json.loads(body.decode("utf-8-sig"))
    except Exception:
        return {"manifest_json_parsed": 0, "manifest_label_hits": "", "manifest_label_hit_count": 0}
    labels = []
    seen = set()
    for s in flatten_labels(obj):
        s = " ".join(str(s).split())
        if s and s not in seen:
            seen.add(s)
            if re.search(r"会員|會員|第二部|第2部|役員|名簿|客員", s):
                labels.append(s)
    ranges = obj.get("ranges")
    if isinstance(ranges, list):
        range_count = len(ranges)
    elif isinstance(obj.get("structures"), list):
        range_count = len(obj.get("structures") or [])
    else:
        range_count = 0
    seqs = obj.get("sequences") or []
    canvas_count = 0
    if seqs and isinstance(seqs, list) and isinstance(seqs[0], dict):
        canvas_count = len(seqs[0].get("canvases") or [])
    elif isinstance(obj.get("items"), list):
        canvas_count = len(obj.get("items") or [])
    return {
        "manifest_json_parsed": 1,
        "manifest_range_count": range_count,
        "manifest_canvas_count": canvas_count,
        "manifest_label_hit_count": len(labels),
        "manifest_label_hits": " | ".join(labels[:50]),
    }

def source_priority(source_class: str, title: str, pid: str) -> str:
    if source_class == "official_postwar_ichiran":
        return "primary_roster"
    if pid == "2988196":
        return "high_priority_official_history_member_roster"
    if source_class == "official_history_support":
        return "supporting_official_history"
    return "other"

def self_test() -> None:
    assert normalize_pid("2934795.0") == "2934795"
    assert normalize_pid("2988196") == "2988196"
    sample = '{"label":"x","ranges":[{"label":"第二 役員、会員、客員名簿"}],"sequences":[{"canvases":[1,2]}]}'.encode("utf-8")
    m = manifest_metrics(sample)
    assert m["manifest_json_parsed"] == 1
    assert m["manifest_canvas_count"] == 2
    assert m["manifest_label_hit_count"] >= 1
    print("SELF-TEST OK: PID normalization and IIIF manifest inspection are consistent")

def run(inp: Path, out: Path) -> None:
    rows = read_csv(inp)
    digital: dict[str, dict[str, str]] = {}
    for r in rows:
        pid = normalize_pid(r.get("pids", ""))
        if not pid:
            continue
        if pid not in digital:
            digital[pid] = r
    if len(digital) != EXPECTED_DIGITAL_PIDS:
        raise RuntimeError(f"Expected {EXPECTED_DIGITAL_PIDS} unique digital PIDs, found {len(digital)}")

    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "manifest_cache"
    raw_dir.mkdir(parents=True, exist_ok=True)

    probe_rows: list[dict[str, Any]] = []
    for pid, r in sorted(digital.items(), key=lambda kv: (kv[1].get("source_class", ""), kv[0])):
        manifest_url = f"https://dl.ndl.go.jp/api/iiif/{pid}/manifest.json"
        lab_book_url = f"https://lab.ndl.go.jp/dl/api/book/{pid}"
        lab_fulltext_url = f"https://lab.ndl.go.jp/dl/api/book/fulltext/{pid}"

        ms, mct, mb, me, mtr = fetch_full(manifest_url)
        mm = {"manifest_json_parsed": 0, "manifest_range_count": "", "manifest_canvas_count": "", "manifest_label_hit_count": 0, "manifest_label_hits": ""}
        manifest_sha = ""
        if ms == 200 and mb and not mtr:
            manifest_sha = sha256_bytes(mb)
            (raw_dir / f"{pid}.manifest.json").write_bytes(mb)
            mm = manifest_metrics(mb)

        bs, bct, bb, be = fetch_prefix(lab_book_url)
        fs, fct, fb, fe = fetch_prefix(lab_fulltext_url)
        fulltext_zip_magic = int(fb.startswith(b"PK"))

        probe_rows.append({
            "pid": pid,
            "source_class": r.get("source_class", ""),
            "source_priority": source_priority(r.get("source_class", ""), r.get("title", ""), pid),
            "issued_or_dates": r.get("issued_or_dates", ""),
            "title": r.get("title", ""),
            "creator": r.get("creator", ""),
            "manifest_url": manifest_url,
            "manifest_http_status": ms if ms is not None else "",
            "manifest_content_type": mct,
            "manifest_error": me,
            "manifest_truncated": int(mtr),
            "manifest_sha256": manifest_sha,
            **mm,
            "lab_book_url": lab_book_url,
            "lab_book_http_status": bs if bs is not None else "",
            "lab_book_content_type": bct,
            "lab_book_prefix_sha256": sha256_bytes(bb) if bb else "",
            "lab_book_error": be,
            "lab_fulltext_url": lab_fulltext_url,
            "lab_fulltext_http_status": fs if fs is not None else "",
            "lab_fulltext_content_type": fct,
            "lab_fulltext_zip_magic": fulltext_zip_magic,
            "lab_fulltext_prefix_sha256": sha256_bytes(fb) if fb else "",
            "lab_fulltext_error": fe,
            "images_downloaded": 0,
            "local_ocr_performed": 0,
            "member_names_extracted": 0,
            "roster_rows_accepted": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    write_csv(out / "digital_source_probe_inventory_v1.csv", probe_rows)
    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SNAPSHOT_DATE,
        "input_digital_pids": len(probe_rows),
        "source_priority_counts": {},
        "manifest_http_status_counts": {},
        "lab_book_http_status_counts": {},
        "lab_fulltext_http_status_counts": {},
        "manifests_parsed": sum(int(r["manifest_json_parsed"]) for r in probe_rows),
        "manifests_with_member_related_labels": sum(int(r["manifest_label_hit_count"]) > 0 for r in probe_rows),
        "fulltext_endpoints_with_zip_magic": sum(int(r["lab_fulltext_zip_magic"]) for r in probe_rows),
        "primary_roster_pid": "2934795",
        "high_priority_history_roster_pid": "2988196",
        "images_downloaded": 0,
        "local_ocr_performed": 0,
        "member_names_extracted": 0,
        "roster_rows_accepted": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "next_action": "Review digital accessibility and manifest labels before any text/image extraction or member classification.",
    }
    from collections import Counter
    summary["source_priority_counts"] = dict(Counter(r["source_priority"] for r in probe_rows))
    summary["manifest_http_status_counts"] = dict(Counter(str(r["manifest_http_status"]) for r in probe_rows))
    summary["lab_book_http_status_counts"] = dict(Counter(str(r["lab_book_http_status"]) for r in probe_rows))
    summary["lab_fulltext_http_status_counts"] = dict(Counter(str(r["lab_fulltext_http_status"]) for r in probe_rows))
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    run(Path(args.input), Path(args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
