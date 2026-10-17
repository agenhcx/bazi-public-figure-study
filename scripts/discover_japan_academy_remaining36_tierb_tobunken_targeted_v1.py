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
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining36-tierb-tobunken-targeted-discovery-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_QUEUE = Path(
    "data/japan_academy_remaining40_direct_evidence_queue_v1/"
    "remaining40_direct_evidence_queue_v1.csv"
)
DEFAULT_OUT = Path(
    "data/japan_academy_remaining36_tierb_tobunken_targeted_discovery_v1"
)

EXPECTED_QUEUE_ROWS = 40
EXPECTED_TARGETS = 36

# These four rows have already been resolved by preserved direct evidence.
RESOLVED_KEYS = {
    "jpa-unlinked-67412ee03b08c5d2",  # 平塚 直秀: Section II / subsection 6
    "jpa-unlinked-ff84801ab056cf46",  # 吉川 逸治: Section I
    "jpa-unlinked-6b0513d4d49815ad",  # 南原 繁: Section I
    "jpa-unlinked-f21fcc61cad96158",  # 土居 光知: Section I
}

BASE = "https://www.tobunken.go.jp/materials/"
REST_SEARCH = BASE + "wp-json/wp/v2/search"
HTML_SEARCH = BASE
UA = "bazi-public-figure-study/1.0 (noncommercial research)"
TIMEOUT = 60
MAX_BYTES = 8 * 1024 * 1024
SLEEP_SECONDS = 0.20
MAX_CANDIDATES_PER_TARGET = 20

NENSHI_URL_RE = re.compile(
    r"https?://www\.tobunken\.go\.jp/materials/nenshi/(?:\d+)(?:\.html)?",
    re.I,
)
NENSHI_HREF_RE = re.compile(
    r"""href=["']([^"']*/materials/nenshi/(?:\d+)(?:\.html)?[^"']*)["']""",
    re.I,
)
SECTION_RE = re.compile(
    r"(?:第一部|第二部|第1部|第2部|第[一二三四五六七1-7]分科)"
)
ACADEMY_RE = re.compile(r"(?:日本学士院|帝国学士院|学士院)")
NEW_MEMBER_RE = re.compile(r"(?:新会員|会員.*選|選ばれ|選定|当選)")


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
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def html_to_visible_text(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def html_blocks(data: bytes) -> list[str]:
    raw = data.decode("utf-8", errors="replace")
    blocks = []
    for m in re.finditer(
        r"(?is)<(?:p|li|h1|h2|h3|h4|td|div)\b[^>]*>(.*?)</(?:p|li|h1|h2|h3|h4|td|div)>",
        raw,
    ):
        x = re.sub(r"(?is)<script\b.*?</script>", " ", m.group(1))
        x = re.sub(r"(?is)<style\b.*?</style>", " ", x)
        x = re.sub(r"(?s)<[^>]+>", " ", x)
        x = " ".join(html.unescape(x).split())
        if x:
            blocks.append(x)
    return blocks


def fetch_urllib(url: str, accept: str = "text/html,*/*;q=0.8") -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": accept},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"response exceeds MAX_BYTES={MAX_BYTES}")
    return body


def fetch_curl(url: str, path: Path | None = None) -> bytes:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl/curl.exe not found")

    if path is None:
        cmd = [
            curl, "--fail", "--location", "--retry", "4", "--retry-all-errors",
            "--connect-timeout", "30", "--max-time", "180",
            "--user-agent", UA, "--silent", "--show-error", url,
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"curl failed rc={proc.returncode}: "
                f"{proc.stderr.decode('utf-8', errors='replace').strip()}"
            )
        body = bytes(proc.stdout)
    else:
        tmp = path.with_suffix(path.suffix + ".part")
        cmd = [
            curl, "--fail", "--location", "--retry", "4", "--retry-all-errors",
            "--connect-timeout", "30", "--max-time", "180",
            "--user-agent", UA, "--silent", "--show-error",
            "--output", str(tmp), url,
        ]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"curl failed rc={proc.returncode}: "
                f"{proc.stderr.decode('utf-8', errors='replace').strip()}"
            )
        body = tmp.read_bytes()
        tmp.replace(path)

    if len(body) > MAX_BYTES:
        raise RuntimeError(f"response exceeds MAX_BYTES={MAX_BYTES}")
    return body


def fetch(url: str, cache_path: Path | None = None) -> tuple[bytes, str, str]:
    if cache_path is not None and cache_path.exists():
        return cache_path.read_bytes(), "cached_local", "local_cache"

    primary_error = ""
    try:
        body = fetch_urllib(url)
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(body)
        return body, "fetched", "urllib"
    except Exception as e:
        primary_error = f"{type(e).__name__}: {e}"

    try:
        body = fetch_curl(url, cache_path)
        return body, "fetched_curl_fallback", "curl_fallback"
    except Exception as e:
        raise RuntimeError(
            f"urllib failed [{primary_error}]; curl failed [{type(e).__name__}: {e}]"
        )


def canonical_nenshi_url(url: str) -> str:
    url = html.unescape(url)
    url = urllib.parse.urljoin(BASE, url)
    m = re.search(r"(https?://www\.tobunken\.go\.jp/materials/nenshi/\d+)(?:\.html)?", url, re.I)
    if not m:
        return ""
    return m.group(1) + ".html"


def discover_via_rest(query: str) -> tuple[list[str], str]:
    # WordPress REST search may or may not expose the custom nenshi post type.
    params = {
        "search": query,
        "per_page": 100,
        "subtype": "nenshi",
    }
    url = REST_SEARCH + "?" + urllib.parse.urlencode(params)
    body, state, transport = fetch(url)
    obj = json.loads(body.decode("utf-8", errors="replace"))
    urls: list[str] = []
    if isinstance(obj, list):
        for item in obj:
            if not isinstance(item, dict):
                continue
            u = canonical_nenshi_url(str(item.get("url", "")))
            if u:
                urls.append(u)
    return sorted(set(urls)), f"{state}:{transport}"


def discover_via_html(query: str) -> tuple[list[str], str]:
    # The site supports ordinary WordPress search; restrict to nenshi if the theme honors post_type[].
    qs = urllib.parse.urlencode(
        [("s", query), ("post_type[]", "nenshi")]
    )
    url = HTML_SEARCH + "?" + qs
    body, state, transport = fetch(url)
    raw = body.decode("utf-8", errors="replace")
    urls: set[str] = set()

    for m in NENSHI_URL_RE.finditer(raw):
        u = canonical_nenshi_url(m.group(0))
        if u:
            urls.add(u)
    for m in NENSHI_HREF_RE.finditer(raw):
        u = canonical_nenshi_url(m.group(1))
        if u:
            urls.add(u)

    return sorted(urls), f"{state}:{transport}"


def candidate_context(
    body: bytes,
    target_name: str,
) -> dict[str, Any]:
    visible = html_to_visible_text(body)
    target_norm = normalize_jp(target_name)
    visible_norm = normalize_jp(visible)

    target_present = int(target_norm in visible_norm)
    academy_present = int(bool(ACADEMY_RE.search(visible)))
    section_present = int(bool(SECTION_RE.search(visible)))
    new_member_present = int(bool(NEW_MEMBER_RE.search(visible)))

    strongest = ""
    same_block_target_section = 0
    same_block_target_academy = 0
    same_block_target_academy_section = 0

    for block in html_blocks(body):
        bnorm = normalize_jp(block)
        has_target = target_norm in bnorm
        has_section = bool(SECTION_RE.search(block))
        has_academy = bool(ACADEMY_RE.search(block))
        if has_target and has_section:
            same_block_target_section = 1
        if has_target and has_academy:
            same_block_target_academy = 1
        if has_target and has_section and has_academy:
            same_block_target_academy_section = 1
        if has_target and (has_section or has_academy):
            if len(block) > len(strongest):
                strongest = block

    if len(strongest) > 600:
        strongest = strongest[:600] + " …"

    return {
        "visible": visible,
        "target_name_present": target_present,
        "academy_term_present": academy_present,
        "section_term_present": section_present,
        "new_member_term_present": new_member_present,
        "same_block_target_section": same_block_target_section,
        "same_block_target_academy": same_block_target_academy,
        "same_block_target_academy_section": same_block_target_academy_section,
        "strongest_context": strongest,
    }


def self_test() -> None:
    sample = """
    <html><body><article>
    <h3>学士院新会員決る</h3>
    <p>五日日本学士院第四回総会で新会員が当選した。
    第一部文学では、和辻哲郎、土居光知が選ばれた。</p>
    </article></body></html>
    """.encode("utf-8")
    x = candidate_context(sample, "土居 光知")
    assert x["target_name_present"] == 1
    assert x["academy_term_present"] == 1
    assert x["section_term_present"] == 1
    assert x["same_block_target_academy_section"] == 1
    assert len(RESOLVED_KEYS) == 4
    print("SELF-TEST OK: Tobunken targeted discovery and direct-evidence flags are consistent")


def run(queue_path: Path, out: Path) -> None:
    if not queue_path.exists():
        raise FileNotFoundError(queue_path)

    queue = read_csv(queue_path)
    if len(queue) != EXPECTED_QUEUE_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_QUEUE_ROWS} frozen queue rows, found {len(queue)}"
        )

    targets = [r for r in queue if r.get("member_key") not in RESOLVED_KEYS]
    if len(targets) != EXPECTED_TARGETS:
        raise RuntimeError(
            f"Expected {EXPECTED_TARGETS} effective unresolved targets, found {len(targets)}"
        )

    out.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw_sources"
    raw_dir.mkdir(parents=True, exist_ok=True)

    candidate_rows: list[dict[str, Any]] = []
    target_audit: list[dict[str, Any]] = []

    for idx, target in enumerate(targets, start=1):
        key = target.get("member_key", "")
        name = target.get("name_jp", "")
        query = normalize_jp(name)
        print(
            f"[{idx:02d}/{len(targets)}] {name} query={query}",
            flush=True,
        )

        urls: set[str] = set()
        rest_state = ""
        html_state = ""
        rest_error = ""
        html_error = ""

        try:
            found, rest_state = discover_via_rest(query)
            urls.update(found)
        except Exception as e:
            rest_error = f"{type(e).__name__}: {e}"

        # Always run the HTML search too; the two discovery surfaces are complementary.
        try:
            found, html_state = discover_via_html(query)
            urls.update(found)
        except Exception as e:
            html_error = f"{type(e).__name__}: {e}"

        urls_sorted = sorted(urls)[:MAX_CANDIDATES_PER_TARGET]
        accepted_candidate_count = 0
        strong_candidate_count = 0
        fetch_errors = 0

        for j, url in enumerate(urls_sorted, start=1):
            article_id_m = re.search(r"/nenshi/(\d+)\.html", url)
            article_id = article_id_m.group(1) if article_id_m else f"x{j}"
            stem = f"{key}_{article_id}"
            html_path = raw_dir / f"{stem}.html"
            text_path = raw_dir / f"{stem}_visible_text.txt"

            try:
                body, fetch_state, fetch_transport = fetch(url, html_path)
                ctx = candidate_context(body, name)
                text_path.write_text(ctx["visible"] + "\n", encoding="utf-8")

                # Keep rows only when the actual archived article contains the exact target.
                if not ctx["target_name_present"]:
                    continue

                accepted_candidate_count += 1
                direct_review_priority = (
                    "P1_same_block_target_academy_section"
                    if ctx["same_block_target_academy_section"]
                    else "P2_target_and_page_section"
                    if ctx["academy_term_present"] and ctx["section_term_present"]
                    else "P3_membership_or_name_context_only"
                )
                if direct_review_priority.startswith("P1"):
                    strong_candidate_count += 1

                candidate_rows.append({
                    "member_key": key,
                    "name_jp": name,
                    "name_en": target.get("name_en", ""),
                    "first_election_date": target.get("first_election_date", ""),
                    "source_tier": "B_candidate",
                    "source_organization": "東京文化財研究所",
                    "source_collection": "美術界年史（彙報）",
                    "source_url": url,
                    "article_id": article_id,
                    "fetch_state": fetch_state,
                    "fetch_transport": fetch_transport,
                    "bytes": len(body),
                    "html_sha256": sha256_bytes(body),
                    "visible_text_sha256": sha256_file(text_path),
                    "target_name_present": ctx["target_name_present"],
                    "academy_term_present": ctx["academy_term_present"],
                    "section_term_present": ctx["section_term_present"],
                    "new_member_term_present": ctx["new_member_term_present"],
                    "same_block_target_section": ctx["same_block_target_section"],
                    "same_block_target_academy": ctx["same_block_target_academy"],
                    "same_block_target_academy_section": ctx["same_block_target_academy_section"],
                    "review_priority": direct_review_priority,
                    "strongest_context": ctx["strongest_context"],
                    "local_html_path": str(html_path),
                    "local_visible_text_path": str(text_path),
                    "manual_adjudication_performed": 0,
                    "direct_section_evidence_accepted": 0,
                    "final_roster_row_written": 0,
                    "dob_collection_started": 0,
                    "bazi_variables_computed": 0,
                })
            except Exception as e:
                fetch_errors += 1
                print(
                    f"  [candidate fetch error] {url}: {type(e).__name__}: {e}",
                    flush=True,
                )

            time.sleep(SLEEP_SECONDS)

        target_audit.append({
            "member_key": key,
            "name_jp": name,
            "name_en": target.get("name_en", ""),
            "search_query": query,
            "rest_search_state": rest_state,
            "rest_search_error": rest_error,
            "html_search_state": html_state,
            "html_search_error": html_error,
            "discovered_unique_urls": len(urls),
            "urls_reviewed_after_cap": len(urls_sorted),
            "articles_with_exact_target": accepted_candidate_count,
            "p1_strong_direct_candidates": strong_candidate_count,
            "candidate_fetch_errors": fetch_errors,
        })

        time.sleep(SLEEP_SECONDS)

    candidate_rows.sort(
        key=lambda r: (
            0 if r["review_priority"].startswith("P1") else
            1 if r["review_priority"].startswith("P2") else 2,
            r["first_election_date"],
            r["name_jp"],
            r["source_url"],
        )
    )

    candidate_fields = [
        "member_key", "name_jp", "name_en", "first_election_date",
        "source_tier", "source_organization", "source_collection",
        "source_url", "article_id", "fetch_state", "fetch_transport",
        "bytes", "html_sha256", "visible_text_sha256",
        "target_name_present", "academy_term_present", "section_term_present",
        "new_member_term_present", "same_block_target_section",
        "same_block_target_academy", "same_block_target_academy_section",
        "review_priority", "strongest_context",
        "local_html_path", "local_visible_text_path",
        "manual_adjudication_performed", "direct_section_evidence_accepted",
        "final_roster_row_written", "dob_collection_started",
        "bazi_variables_computed",
    ]
    write_csv(
        out / "tobunken_targeted_candidates_v1.csv",
        candidate_rows,
        candidate_fields,
    )
    write_csv(
        out / "tobunken_target_search_audit_v1.csv",
        target_audit,
    )

    p1_rows = [r for r in candidate_rows if r["review_priority"].startswith("P1")]
    p2_rows = [r for r in candidate_rows if r["review_priority"].startswith("P2")]

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_frozen_queue_rows": len(queue),
        "already_resolved_members_excluded": len(RESOLVED_KEYS),
        "effective_unresolved_search_targets": len(targets),
        "targets_with_any_exact_name_article": len({
            r["member_key"] for r in candidate_rows
        }),
        "candidate_articles_with_exact_target": len(candidate_rows),
        "p1_same_block_target_academy_section_rows": len(p1_rows),
        "p1_unique_members": len({r["member_key"] for r in p1_rows}),
        "p2_target_and_page_section_rows": len(p2_rows),
        "p2_unique_members": len({r["member_key"] for r in p2_rows}),
        "automatic_section_acceptance": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "decision_rule": (
            "Discovery only. Tokyo National Research Institute for Cultural Properties is a "
            "Tier-B institutional source, but no candidate is accepted automatically. "
            "Manual review must directly bind the exact target person to Japan Academy "
            "Section I/II or a subsection. Membership alone and discipline inference are insufficient."
        ),
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(queue_path),
        },
        "next_action": (
            "Upload summary.json plus tobunken_targeted_candidates_v1.csv. "
            "If P1 rows exist, also upload the corresponding preserved HTML/text files for "
            "manual adjudication. Review P1 first, then P2; keep all others unresolved."
        ),
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy remaining-36 Tobunken targeted Tier-B discovery v1

This layer systematically searches the Tokyo National Research Institute for Cultural Properties
(Tobunken) historical news archive for each of the 36 effective unresolved Japan Academy targets.

It is a **discovery layer only**.

Priority:
- P1: target name + Japan Academy term + section/subsection term in the same HTML block.
- P2: target name is present and the page contains both Academy and section terms, but not in the same block.
- P3: membership/name context only.

No section is accepted automatically. No discipline inference is allowed.
No final roster, DOB collection, or BaZi computation is written here.
"""
    (out / "TOBUNKEN_TARGETED_DISCOVERY_V1.md").write_text(md, encoding="utf-8")

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
