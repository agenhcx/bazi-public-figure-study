#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining36-wayback-official-subsection-discovery-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_QUEUE = Path(
    "data/japan_academy_remaining40_direct_evidence_queue_v1/"
    "remaining40_direct_evidence_queue_v1.csv"
)
DEFAULT_OUT = Path(
    "data/japan_academy_remaining36_wayback_official_subsection_discovery_v1"
)

EXPECTED_QUEUE_ROWS = 40
EXPECTED_TARGETS = 36

RESOLVED_KEYS = {
    "jpa-unlinked-67412ee03b08c5d2",  # 平塚 直秀: II / 6
    "jpa-unlinked-ff84801ab056cf46",  # 吉川 逸治: I
    "jpa-unlinked-6b0513d4d49815ad",  # 南原 繁: I
    "jpa-unlinked-f21fcc61cad96158",  # 土居 光知: I
}

SUBSECTIONS = {
    1: {"broad_section": "I", "label": "第1分科", "field": "文学・史学・哲学"},
    2: {"broad_section": "I", "label": "第2分科", "field": "法律学・政治学"},
    3: {"broad_section": "I", "label": "第3分科", "field": "経済学・商学"},
    4: {"broad_section": "II", "label": "第4分科", "field": "理学"},
    5: {"broad_section": "II", "label": "第5分科", "field": "工学"},
    6: {"broad_section": "II", "label": "第6分科", "field": "農学"},
    7: {"broad_section": "II", "label": "第7分科", "field": "医学・薬学・歯学"},
}

CDX_ENDPOINTS = [
    "https://web.archive.org/cdx/search/cdx",
    "http://web.archive.org/cdx/search/cdx",
]
ARCHIVE_BASE = "https://web.archive.org/web"
ORIGINAL_HOSTS = [
    "www.japan-acad.go.jp",
    "japan-acad.go.jp",
]
PATH_TEMPLATE = "/japanese/members/{n}bunka.html"

FROM_YEAR = 1996
TO_YEAR = 2010
MAX_CDX_ROWS_PER_URL = 500
SLEEP_SECONDS = 0.35
TIMEOUT = 90
MAX_BYTES = 8 * 1024 * 1024
UA = "bazi-public-figure-study/1.0 (noncommercial research)"


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


def normalize_jp(s: str) -> str:
    s = html.unescape(s or "")
    return re.sub(r"[\s\u3000]+", "", s)


def japanese_score(s: str) -> tuple[int, int]:
    jp = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]", s))
    bad = s.count("\ufffd")
    return jp, -bad


def decode_html(data: bytes) -> str:
    head = data[:8192].decode("ascii", errors="ignore")
    encs: list[str] = []
    for m in re.finditer(r"charset\s*=\s*[\"']?\s*([A-Za-z0-9._-]+)", head, re.I):
        encs.append(m.group(1))
    encs.extend(["utf-8", "cp932", "shift_jis", "euc_jp", "iso2022_jp"])

    seen = set()
    candidates: list[tuple[tuple[int, int], str]] = []
    for enc in encs:
        key = enc.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            text = data.decode(enc, errors="replace")
        except Exception:
            continue
        candidates.append((japanese_score(text), text))

    if not candidates:
        return data.decode("utf-8", errors="replace")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def html_to_visible_text(data: bytes) -> str:
    text = decode_html(data)
    text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def fetch_urllib(url: str, accept: str = "text/html,application/json,*/*;q=0.8") -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": accept},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"response exceeds MAX_BYTES={MAX_BYTES}")
    return body


def fetch_curl(url: str) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl/curl.exe not available")
    cmd = [
        curl,
        "--fail",
        "--location",
        "--retry", "5",
        "--retry-all-errors",
        "--connect-timeout", "30",
        "--max-time", "240",
        "--user-agent", UA,
        "--silent",
        "--show-error",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"curl failed rc={proc.returncode}: "
            f"{proc.stderr.decode('utf-8', errors='replace').strip()}"
        )
    body = bytes(proc.stdout)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"response exceeds MAX_BYTES={MAX_BYTES}")
    return body


def fetch(url: str) -> tuple[bytes, str]:
    try:
        return fetch_urllib(url), "urllib"
    except Exception as e1:
        try:
            return fetch_curl(url), "curl_fallback"
        except Exception as e2:
            raise RuntimeError(
                f"urllib failed [{type(e1).__name__}: {e1}]; "
                f"curl failed [{type(e2).__name__}: {e2}]"
            )


def parse_iso_date(s: str) -> dt.date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def parse_wayback_date(timestamp: str) -> dt.date | None:
    if len(timestamp) < 8:
        return None
    try:
        return dt.datetime.strptime(timestamp[:8], "%Y%m%d").date()
    except Exception:
        return None


def cdx_query(original_url: str) -> tuple[list[dict[str, str]], str]:
    params = [
        ("url", original_url),
        ("output", "json"),
        ("fl", "timestamp,original,statuscode,mimetype,digest,length"),
        ("filter", "statuscode:200"),
        ("filter", "mimetype:text/html"),
        ("from", str(FROM_YEAR)),
        ("to", str(TO_YEAR)),
        ("collapse", "digest"),
        ("limit", str(MAX_CDX_ROWS_PER_URL)),
    ]
    query = urllib.parse.urlencode(params)
    errors = []

    for endpoint in CDX_ENDPOINTS:
        url = endpoint + "?" + query
        try:
            body, transport = fetch(url)
            obj = json.loads(body.decode("utf-8", errors="replace"))
            if not isinstance(obj, list) or not obj:
                return [], transport
            header = obj[0]
            if not isinstance(header, list):
                return [], transport
            out: list[dict[str, str]] = []
            for row in obj[1:]:
                if not isinstance(row, list):
                    continue
                d = {str(header[i]): str(row[i]) for i in range(min(len(header), len(row)))}
                out.append(d)
            return out, transport
        except Exception as e:
            errors.append(f"{endpoint}: {type(e).__name__}: {e}")

    raise RuntimeError(" | ".join(errors))


def archive_url(timestamp: str, original: str) -> str:
    # id_ asks Wayback for the archived payload without toolbar rewriting.
    return f"{ARCHIVE_BASE}/{timestamp}id_/{original}"


def exact_target_present(visible: str, target_name: str) -> bool:
    return normalize_jp(target_name) in normalize_jp(visible)


def expected_page_identity(visible: str, subsection: int) -> bool:
    v = normalize_jp(visible)
    label = normalize_jp(SUBSECTIONS[subsection]["label"])
    academy = "日本学士院"
    return label in v and normalize_jp(academy) in v


def self_test() -> None:
    sample = """
    <html><head><title>第1分科(文学・史学・哲学) | 日本学士院</title></head>
    <body><h1>第1分科(文学・史学・哲学)</h1>
    <table><tr><td>入矢 義高</td><td>中国文学・中国禅学</td></tr></table></body></html>
    """.encode("utf-8")
    visible = html_to_visible_text(sample)
    assert exact_target_present(visible, "入矢 義高")
    assert expected_page_identity(visible, 1)
    assert SUBSECTIONS[1]["broad_section"] == "I"
    assert SUBSECTIONS[7]["broad_section"] == "II"
    assert len(RESOLVED_KEYS) == 4
    print("SELF-TEST OK: Wayback official subsection discovery guards are consistent")


def run(queue_path: Path, out: Path) -> None:
    if not queue_path.exists():
        raise FileNotFoundError(queue_path)

    queue = read_csv(queue_path)
    if len(queue) != EXPECTED_QUEUE_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_QUEUE_ROWS} queue rows, found {len(queue)}")

    targets = [r for r in queue if r.get("member_key") not in RESOLVED_KEYS]
    if len(targets) != EXPECTED_TARGETS:
        raise RuntimeError(
            f"Expected {EXPECTED_TARGETS} effective unresolved targets, found {len(targets)}"
        )

    target_by_key = {r["member_key"]: r for r in targets}
    raw_dir = out / "raw_sources"
    raw_dir.mkdir(parents=True, exist_ok=True)

    cdx_inventory: list[dict[str, Any]] = []
    snapshot_hits: list[dict[str, Any]] = []
    route_errors: list[dict[str, str]] = []

    # Avoid re-fetching the same archived payload if http/https or host aliases collapse to it.
    fetched_snapshot_keys: set[tuple[str, str]] = set()

    for subsection in range(1, 8):
        meta = SUBSECTIONS[subsection]
        print(
            f"[subsection {subsection}/7] {meta['label']} {meta['field']}",
            flush=True,
        )

        cdx_rows_all: list[dict[str, str]] = []
        cdx_seen: set[tuple[str, str]] = set()

        for host in ORIGINAL_HOSTS:
            for scheme in ("https", "http"):
                original_url = f"{scheme}://{host}{PATH_TEMPLATE.format(n=subsection)}"
                try:
                    rows, transport = cdx_query(original_url)
                    cdx_inventory.append({
                        "subsection": subsection,
                        "broad_section": meta["broad_section"],
                        "query_original_url": original_url,
                        "cdx_transport": transport,
                        "cdx_rows": len(rows),
                        "error": "",
                    })
                    for r in rows:
                        k = (r.get("timestamp", ""), r.get("digest", ""))
                        if k not in cdx_seen:
                            cdx_seen.add(k)
                            cdx_rows_all.append(r)
                except Exception as e:
                    msg = f"{type(e).__name__}: {e}"
                    cdx_inventory.append({
                        "subsection": subsection,
                        "broad_section": meta["broad_section"],
                        "query_original_url": original_url,
                        "cdx_transport": "",
                        "cdx_rows": 0,
                        "error": msg,
                    })
                    route_errors.append({
                        "stage": "cdx",
                        "subsection": str(subsection),
                        "url": original_url,
                        "error": msg,
                    })

                time.sleep(SLEEP_SECONDS)

        cdx_rows_all.sort(key=lambda r: r.get("timestamp", ""))
        print(f"  unique archived digests: {len(cdx_rows_all)}", flush=True)

        for idx, r in enumerate(cdx_rows_all, start=1):
            timestamp = r.get("timestamp", "")
            original = r.get("original", "")
            digest = r.get("digest", "")
            if not timestamp or not original:
                continue

            skey = (timestamp, digest or original)
            if skey in fetched_snapshot_keys:
                continue
            fetched_snapshot_keys.add(skey)

            aurl = archive_url(timestamp, original)
            safe_original = re.sub(r"[^A-Za-z0-9._-]+", "_", original)[-100:]
            raw_path = raw_dir / (
                f"sub{subsection}_{timestamp}_{digest[:12] or 'nodigest'}_{safe_original}.html"
            )
            text_path = raw_path.with_name(raw_path.stem + "_visible_text.txt")

            try:
                if raw_path.exists():
                    body = raw_path.read_bytes()
                    fetch_transport = "local_cache"
                else:
                    body, fetch_transport = fetch(aurl)
                    raw_path.write_bytes(body)

                visible = html_to_visible_text(body)
                text_path.write_text(visible + "\n", encoding="utf-8")

                if not expected_page_identity(visible, subsection):
                    continue

                snap_date = parse_wayback_date(timestamp)

                for key, target in target_by_key.items():
                    if not exact_target_present(visible, target.get("name_jp", "")):
                        continue

                    first = parse_iso_date(target.get("first_election_date", ""))
                    retire = parse_iso_date(target.get("final_retirement_date", ""))
                    temporal_overlap = int(
                        snap_date is not None
                        and (first is None or snap_date >= first)
                        and (retire is None or snap_date <= retire)
                    )

                    snapshot_hits.append({
                        "member_key": key,
                        "name_jp": target.get("name_jp", ""),
                        "name_en": target.get("name_en", ""),
                        "first_election_date": target.get("first_election_date", ""),
                        "final_retirement_date": target.get("final_retirement_date", ""),
                        "archive_timestamp": timestamp,
                        "archive_date": snap_date.isoformat() if snap_date else "",
                        "original_url": original,
                        "archive_url": aurl,
                        "source_tier": "A_archived_first_party_candidate",
                        "source_organization": "日本学士院",
                        "broad_section_candidate": meta["broad_section"],
                        "exact_subsection_candidate": subsection,
                        "subsection_label": meta["label"],
                        "subsection_field": meta["field"],
                        "exact_target_name_present": 1,
                        "expected_page_identity_present": 1,
                        "temporal_membership_overlap": temporal_overlap,
                        "fetch_transport": fetch_transport,
                        "bytes": len(body),
                        "sha256": sha256_bytes(body),
                        "local_html_path": str(raw_path),
                        "local_visible_text_path": str(text_path),
                        "manual_adjudication_performed": 0,
                        "direct_section_evidence_accepted": 0,
                        "final_roster_row_written": 0,
                        "dob_collection_started": 0,
                        "bazi_variables_computed": 0,
                    })

            except Exception as e:
                route_errors.append({
                    "stage": "snapshot_fetch",
                    "subsection": str(subsection),
                    "url": aurl,
                    "error": f"{type(e).__name__}: {e}",
                })

            if idx % 20 == 0 or idx == len(cdx_rows_all):
                print(
                    f"  fetched/reviewed {idx}/{len(cdx_rows_all)} snapshots",
                    flush=True,
                )
            time.sleep(SLEEP_SECONDS)

    snapshot_hits.sort(
        key=lambda r: (
            r["member_key"],
            -int(r["temporal_membership_overlap"]),
            int(r["exact_subsection_candidate"]),
            r["archive_timestamp"],
        )
    )

    hit_fields = [
        "member_key", "name_jp", "name_en",
        "first_election_date", "final_retirement_date",
        "archive_timestamp", "archive_date",
        "original_url", "archive_url",
        "source_tier", "source_organization",
        "broad_section_candidate", "exact_subsection_candidate",
        "subsection_label", "subsection_field",
        "exact_target_name_present", "expected_page_identity_present",
        "temporal_membership_overlap",
        "fetch_transport", "bytes", "sha256",
        "local_html_path", "local_visible_text_path",
        "manual_adjudication_performed", "direct_section_evidence_accepted",
        "final_roster_row_written", "dob_collection_started",
        "bazi_variables_computed",
    ]
    write_csv(out / "wayback_official_subsection_snapshot_hits_v1.csv", snapshot_hits, hit_fields)
    write_csv(out / "wayback_cdx_inventory_v1.csv", cdx_inventory)
    write_csv(out / "wayback_route_errors_v1.csv", route_errors, ["stage", "subsection", "url", "error"])

    # Aggregate only temporally valid hits for the strongest candidate summary.
    by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in snapshot_hits:
        if int(r["temporal_membership_overlap"]) == 1:
            by_member[r["member_key"]].append(r)

    candidates: list[dict[str, Any]] = []
    for key, target in target_by_key.items():
        rows = by_member.get(key, [])
        subsections = sorted({int(r["exact_subsection_candidate"]) for r in rows})
        broad_sections = sorted({r["broad_section_candidate"] for r in rows})
        timestamps = sorted({r["archive_timestamp"] for r in rows})
        urls = sorted({r["archive_url"] for r in rows})

        if not rows:
            status = "no_temporally_valid_archived_official_hit"
        elif len(subsections) == 1 and len(broad_sections) == 1:
            status = "P1_unique_official_subsection_candidate"
        else:
            status = "conflicting_archived_official_subsection_hits"

        candidates.append({
            "member_key": key,
            "name_jp": target.get("name_jp", ""),
            "name_en": target.get("name_en", ""),
            "first_election_date": target.get("first_election_date", ""),
            "final_retirement_date": target.get("final_retirement_date", ""),
            "candidate_status": status,
            "candidate_broad_sections": "|".join(broad_sections),
            "candidate_exact_subsections": "|".join(str(x) for x in subsections),
            "temporally_valid_snapshot_hits": len(rows),
            "archive_timestamps": "|".join(timestamps),
            "archive_urls": "|".join(urls),
            "manual_adjudication_performed": 0,
            "direct_section_evidence_accepted": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    candidates.sort(
        key=lambda r: (
            0 if r["candidate_status"] == "P1_unique_official_subsection_candidate" else
            1 if r["candidate_status"].startswith("conflicting") else 2,
            r["first_election_date"],
            r["name_jp"],
        )
    )
    write_csv(out / "wayback_member_subsection_candidates_v1.csv", candidates)

    p1 = [r for r in candidates if r["candidate_status"] == "P1_unique_official_subsection_candidate"]
    conflicts = [r for r in candidates if r["candidate_status"].startswith("conflicting")]

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_frozen_queue_rows": len(queue),
        "already_resolved_members_excluded": len(RESOLVED_KEYS),
        "effective_unresolved_search_targets": len(targets),
        "wayback_search_year_range": [FROM_YEAR, TO_YEAR],
        "subsection_pages_queried": 7,
        "cdx_query_variants": len(cdx_inventory),
        "archived_snapshot_exact_name_hits": len(snapshot_hits),
        "members_with_any_snapshot_hit": len({r["member_key"] for r in snapshot_hits}),
        "members_with_temporally_valid_snapshot_hit": len(by_member),
        "p1_unique_official_subsection_candidates": len(p1),
        "conflicting_member_candidates": len(conflicts),
        "automatic_section_acceptance": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "decision_rule": (
            "Discovery only. A P1 candidate requires the exact target name on an archived "
            "Japan Academy first-party subsection page, the expected subsection-page identity, "
            "and a Wayback capture date within the target's membership interval. "
            "No candidate is accepted automatically; preserved snapshots must be manually reviewed. "
            "Conflicts remain unresolved."
        ),
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(queue_path),
        },
        "route_errors": len(route_errors),
        "next_action": (
            "Upload summary.json and wayback_member_subsection_candidates_v1.csv. "
            "If P1 candidates exist, also upload wayback_official_subsection_snapshot_hits_v1.csv "
            "and the preserved raw HTML/text for one or more representative temporally valid snapshots "
            "per P1 member. Manually adjudicate before writing any final roster row."
        ),
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy remaining-36 Wayback official subsection discovery v1

This route searches archived first-party Japan Academy subsection pages for the 36 effective unresolved members.

Expected official page mapping:
- 1bunka.html -> Section I / subsection 1
- 2bunka.html -> Section I / subsection 2
- 3bunka.html -> Section I / subsection 3
- 4bunka.html -> Section II / subsection 4
- 5bunka.html -> Section II / subsection 5
- 6bunka.html -> Section II / subsection 6
- 7bunka.html -> Section II / subsection 7

A strong P1 candidate requires:
1. an archived Japan Academy first-party page;
2. the expected subsection page identity in the archived content;
3. the exact target name on that page;
4. a capture date within the member's membership interval;
5. no conflicting subsection hit.

This is discovery only. No section is accepted automatically.
No final roster, DOB collection, or BaZi variable is written here.
"""
    (out / "WAYBACK_OFFICIAL_SUBSECTION_DISCOVERY_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.queue), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
