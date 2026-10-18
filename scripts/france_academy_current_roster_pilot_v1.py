#!/usr/bin/env python3
"""Bounded, provenance-preserving pilot of the France Académie des sciences CURRENT site.

Not a historical master roster. Not an exact-DOB freeze. Not a BaZi calculation.
Member classes are derived from individual election wording, not page-card labels.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_VERSION = "france-academy-current-roster-pilot-v1"
BASE = "https://www.academie-sciences.fr"
INDEX = BASE + "/les-academiciens"
ARCHIVE_INDEX = "https://archives.academie-sciences.fr/n/fichier-des-membres-de-l-academie-issu-de-l-index-biographique-par-henri-leridon/n:155"
SOURCE_DATE = dt.date.today().isoformat()
AGENT = "PublicFigureStudy/1.0 (academic noncommercial source-discovery audit; GitHub agenHcx/bazi-public-figure-study)"
BIRTH_MIN, BIRTH_MAX = 1835, 1985
ELECTION_MAX = 2025
EXCLUDED_SLUGS = {
    "accueil", "les-academiciens", "academiciens", "recherche", "publications",
    "nos-archives", "librairie", "actualites-et-evenements", "nous-contacter",
}
FULL_RE = re.compile(
    r"\b[ée]lu(?:e)?\s+(?:acad[ée]micien(?:ne)?|membre\s+titulaire|membre\s+de\s+l.acad[ée]mie)\b"
    r"[^\n\r]{0,70}?\b(?:en|le)\s+[^\n\r]{0,30}?(?P<year>(?:18|19|20)\d{2})\b",
    re.I,
)
FOREIGN_RE = re.compile(
    r"\b[ée]lu(?:e)?\s+associ[ée](?:e)?\s+[ée]trang[èe]r(?:e)?\b"
    r"[^\n\r]{0,70}?(?P<year>(?:18|19|20)\d{2})\b",
    re.I,
)
CORRESP_RE = re.compile(
    r"\b[ée]lu(?:e)?\s+correspondant(?:e)?\b"
    r"[^\n\r]{0,70}?(?P<year>(?:18|19|20)\d{2})\b",
    re.I,
)
BIRTH_RE = re.compile(
    r"(?:Date de naissance|Date of birth)\s*:\s*(?P<value>[^\n]{1,80})",
    re.I,
)
YEAR_RE = re.compile(r"\b(1[6789]\d{2}|20[012]\d)\b")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def looks_like_person_name(value: str) -> bool:
    value = " ".join(value.split())
    if len(value) < 7 or len(value) > 95 or any(c.isdigit() for c in value):
        return False
    words = value.split()
    if len(words) < 2 or len(words) > 7:
        return False
    # Keep names in French, with apostrophes and hyphens; do not guess identity from slug.
    if sum(any(unicodedata.category(c).startswith("L") for c in w) for w in words) < 2:
        return False
    if value.lower().startswith(("tous ", "voir ", "comité ", "les ", "recherche ", "filtrer")):
        return False
    return True


def extract_index_links(html: bytes) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        name = " ".join(a.get_text(" ", strip=True).split())
        if not looks_like_person_name(name):
            continue
        url = urljoin(BASE, a["href"]).split("#")[0]
        parsed = urlparse(url)
        if parsed.hostname not in {"www.academie-sciences.fr", "academie-sciences.fr"}:
            continue
        slug = parsed.path.strip("/")
        if not slug or "/" in slug or slug.lower() in EXCLUDED_SLUGS:
            continue
        if not re.fullmatch(r"[a-z0-9_-]+", slug):
            continue
        results.setdefault(url, {"name_on_list": name, "profile_url": url})
    return list(results.values())


def get(session: requests.Session, url: str, delay: float, timeout: float) -> tuple[bytes, int]:
    time.sleep(delay)
    r = session.get(url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    if len(r.content) > 6_000_000:
        raise ValueError("HTML page too large")
    if not r.content.strip().startswith(b"<") or b"</html" not in r.content.lower():
        raise ValueError("Non-HTML response")
    return r.content, r.status_code


def member_record(html: bytes, link: dict, source_sha: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 is None:
        return None
    name = " ".join(h1.get_text(" ", strip=True).split())
    if not looks_like_person_name(name):
        return None
    # Limit to profile header, where birth and election metadata are authoritative.
    # Body biographies can name elections of unrelated people or other institutions.
    main = soup.find("main") or soup
    lines = [v.strip() for v in main.stripped_strings if v.strip()]
    try:
        idx = next(i for i, x in enumerate(lines) if x == name)
    except StopIteration:
        idx = 0
    header_lines = lines[idx: idx + 90]
    for i, value in enumerate(header_lines):
        if value.lower() in {"biographie", "biography", "partager avec:", "share with:"}:
            header_lines = header_lines[:i]
            break
    header = "\n".join(header_lines)
    # Do not turn an unverified historical-display label into accepted full membership.
    full = FULL_RE.search(header)
    foreign = FOREIGN_RE.search(header)
    corr = CORRESP_RE.search(header)
    if full:
        kind, election_year, match = "full_member", int(full.group("year")), full
    elif foreign:
        kind, election_year, match = "foreign_associate", int(foreign.group("year")), foreign
    elif corr:
        kind, election_year, match = "correspondant", int(corr.group("year")), corr
    else:
        kind, election_year, match = "unresolved", None, None

    birth = BIRTH_RE.search(header)
    birth_field = (birth.group("value").strip() if birth else "").split("Élu")[0].split("Élue")[0].strip()
    birth_year_m = YEAR_RE.search(birth_field)
    birth_year = int(birth_year_m.group(0)) if birth_year_m else None
    birth_precision = "missing"
    if birth_field:
        birth_precision = "year_only" if birth_field == str(birth_year or "") else "needs_manual_date_parse"
    election_phrase = " ".join(match.group(0).split()) if match else ""
    # A pilot's inclusion_candidate flag is preliminary. Never use as final eligibility.
    candidate = bool(
        kind == "full_member"
        and election_year is not None and election_year <= ELECTION_MAX
        and birth_year is not None and BIRTH_MIN <= birth_year <= BIRTH_MAX
    )
    return {
        "name": name,
        "list_name": link["name_on_list"],
        "url": link["profile_url"],
        "source_sha256": source_sha,
        "member_class_pilot": kind,
        "election_year_pilot": election_year if election_year else "",
        "election_phrase": election_phrase,
        "birth_raw": birth_field,
        "birth_year_pilot": birth_year if birth_year else "",
        "dob_precision": birth_precision,
        "primary_window_candidate_only": int(candidate),
        "header_excerpt": " | ".join(header_lines[:32])[:1000],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-profiles", type=int, default=45)
    parser.add_argument("--delay", type=float, default=0.7)
    parser.add_argument("--timeout", type=float, default=22.0)
    parser.add_argument("--out", default="data/france_academy_current_roster_pilot_v1")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 60 or not 1 <= args.max_profiles <= 2000:
        raise ValueError("max-pages must be 1-60 and max-profiles 1-2000")
    if args.delay < 0.2:
        raise ValueError("delay must be >=0.2 seconds")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw_html"
    raw.mkdir(exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": AGENT, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5"})
    listing_rows: list[dict] = []
    candidates: dict[str, dict] = {}
    failures: list[dict] = []
    records: list[dict] = []
    page_signatures: set[str] = set()
    for page in range(args.max_pages):
        url = INDEX if page == 0 else INDEX + f"?page={page}"
        try:
            body, status = get(session, url, args.delay, args.timeout)
            digest = sha(body)
            (raw / (digest + ".html")).write_bytes(body)
            links = extract_index_links(body)
            signature = sha("\n".join(sorted(x["profile_url"] for x in links)).encode())
            repeated = signature in page_signatures
            page_signatures.add(signature)
            listing_rows.append({"page": page, "url": url, "status": status, "sha256": digest,
                                 "potential_person_links": len(links), "repeated_link_set": int(repeated)})
            for link in links:
                candidates.setdefault(link["profile_url"], link)
            print(f"list page={page} candidates={len(links)} unique={len(candidates)} repeated={repeated}", flush=True)
            if repeated:
                break
        except Exception as exc:
            failures.append({"kind": "index", "url": url, "error": str(exc)[:350]})
            print(f"ERROR index {url}: {exc}", flush=True)
            if page == 0:
                break

    for i, link in enumerate(list(candidates.values())[:args.max_profiles], start=1):
        url = link["profile_url"]
        try:
            body, _ = get(session, url, args.delay, args.timeout)
            digest = sha(body)
            (raw / (digest + ".html")).write_bytes(body)
            result = member_record(body, link, digest)
            if result is None:
                failures.append({"kind": "nonprofile", "url": url, "error": "missing person h1"})
            else:
                records.append(result)
            if i % 10 == 0:
                print(f"profiles visited {i}/{min(len(candidates), args.max_profiles)} valid={len(records)}", flush=True)
        except Exception as exc:
            failures.append({"kind": "profile_fetch", "url": url, "error": str(exc)[:350]})
            print(f"ERROR profile {url}: {exc}", flush=True)

    write_csv(out / "index_page_fetches.csv", listing_rows,
              ["page", "url", "status", "sha256", "potential_person_links", "repeated_link_set"])
    write_csv(out / "listing_candidate_links.csv", list(candidates.values()), ["name_on_list", "profile_url"])
    write_csv(out / "profile_pilot_records.csv", records,
              ["name", "list_name", "url", "source_sha256", "member_class_pilot", "election_year_pilot",
               "election_phrase", "birth_raw", "birth_year_pilot", "dob_precision",
               "primary_window_candidate_only", "header_excerpt"])
    write_csv(out / "fetch_and_parse_errors.csv", failures, ["kind", "url", "error"])
    metrics = {
        "script_version": SCRIPT_VERSION,
        "run_date_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_url": INDEX,
        "archive_index_url_not_downloaded": ARCHIVE_INDEX,
        "historical_roster_complete": False,
        "final_roster_frozen": False,
        "exact_dob_frozen": False,
        "bazi_variables_computed": 0,
        "max_index_pages": args.max_pages,
        "max_profile_urls": args.max_profiles,
        "visited_list_pages": len(listing_rows),
        "listing_url_candidates": len(candidates),
        "profile_rows_valid": len(records),
        "primary_window_candidate_only": sum(int(x["primary_window_candidate_only"]) for x in records),
        "member_class_counts": dict(Counter(x["member_class_pilot"] for x in records)),
        "dob_precision_counts": dict(Counter(x["dob_precision"] for x in records)),
        "errors": len(failures),
        "warning": "pilot only; modern official site is NOT historical complete; no DOB day-precision verified",
    }
    write_json(out / "summary.json", metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)
    if args.strict and not records:
        raise SystemExit("No valid French Academy profile rows: inspect artifact and source responses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
