#!/usr/bin/env python3
"""Download a frozen Nobel science master roster from the official Nobel Prize API.

Scope (frozen for the current study):
  - Award years: 1901-2025 inclusive
  - Categories: Physics, Chemistry, Physiology or Medicine
  - Source: Nobel Prize API v2.1
  - No BaZi conversion or outcome statistics are performed here.

Outputs:
  raw/*.json                  Official API responses, one category per file
  nobel_science_awards.csv    One row per laureate-award
  nobel_science_people.csv    One row per unique laureate/person
  nobel_science_summary.csv   Data-quality/count summary
  manifest.json               Retrieval metadata + SHA256 hashes

Uses Python standard library only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.nobelprize.org/2.1/laureates"
YEAR_MIN = 1901
YEAR_MAX = 2025

# Nobel API code -> canonical English label expected inside laureate.nobelPrizes[].category.en
CATEGORIES = {
    "phy": "Physics",
    "che": "Chemistry",
    "med": "Physiology or Medicine",
}

USER_AGENT = "bazi-academic-selection-study/1.0 (research data collection; Nobel Prize public API)"


def en(obj: Any) -> str:
    """Return English label from Nobel multilingual object, else a safe string."""
    if obj is None:
        return ""
    if isinstance(obj, dict):
        v = obj.get("en")
        if v is not None:
            return str(v).strip()
        # Sometimes a link object is stored instead of a label.
        for key in ("name", "label", "href"):
            if key in obj and obj[key] is not None:
                return str(obj[key]).strip()
        return ""
    return str(obj).strip()


def nested(d: Any, *keys: str, default: Any = "") -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def link_value(obj: Any) -> str:
    """Extract a URL-ish value from a Nobel link field regardless of exact schema shape."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        for k in ("href", "url", "en"):
            if obj.get(k):
                return str(obj[k]).strip()
        return ""
    if isinstance(obj, list):
        vals = [link_value(x) for x in obj]
        return "; ".join(x for x in vals if x)
    return str(obj).strip()


def exact_iso_date(s: str) -> bool:
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    if s[5:7] == "00" or s[8:10] == "00":
        return False
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def api_get(params: dict[str, Any], retries: int = 5) -> dict[str, Any]:
    url = API + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=60) as r:
                if getattr(r, "status", 200) != 200:
                    raise RuntimeError(f"HTTP {getattr(r, 'status', '?')} for {url}")
                return json.loads(r.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as e:
            last = e
            if attempt == retries - 1:
                break
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {retries} attempts: {url}\n{last}")


def fetch_category(code: str, label: str) -> dict[str, Any]:
    # Current official API category codes are phy/che/med. Some third-party docs have
    # historically shown 'chem'; keep a chemistry fallback so a docs/API mismatch
    # cannot silently yield an empty cohort.
    codes_to_try = [code]
    if code == "che":
        codes_to_try.append("chem")

    for candidate in codes_to_try:
        payload = api_get({
            "nobelPrizeCategory": candidate,
            "limit": 1000,
            "offset": 0,
            "sort": "asc",
            "format": "json",
        })
        laureates = payload.get("laureates", [])
        if laureates:
            payload.setdefault("_study_meta", {})["requested_category_code"] = candidate
            payload["_study_meta"]["requested_category_label"] = label
            return payload
    raise RuntimeError(f"API returned no laureates for category {label} ({code})")


def prize_code_from_label(label: str) -> str:
    low = label.strip().lower()
    if low == "physics":
        return "phy"
    if low == "chemistry":
        return "che"
    if low in {"physiology or medicine", "physiology or medicin", "medicine"}:
        return "med"
    return ""


def flatten_affiliations(prize: dict[str, Any]) -> tuple[str, str, str]:
    affs = prize.get("affiliations") or []
    names, cities, countries = [], [], []
    for a in affs:
        if not isinstance(a, dict):
            continue
        names.append(en(a.get("name")))
        cities.append(en(nested(a, "city", default={})))
        countries.append(en(nested(a, "country", default={})))
    clean = lambda xs: "; ".join(x for x in xs if x)
    return clean(names), clean(cities), clean(countries)


def flatten_rows(raw_by_cat: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    # Laureates may appear in more than one category response. Deduplicate award rows
    # using laureate_id + award_year + canonical category code.
    rows: dict[tuple[str, int, str], dict[str, Any]] = {}

    for source_code, payload in raw_by_cat.items():
        for p in payload.get("laureates", []):
            laureate_id = str(p.get("id", "")).strip()
            known_name = en(p.get("knownName"))
            full_name = en(p.get("fullName")) or known_name
            given_name = en(p.get("givenName"))
            family_name = en(p.get("familyName"))
            gender = str(p.get("gender", "")).strip()

            birth_date = str(nested(p, "birth", "date", default="") or "").strip()
            birth_city = en(nested(p, "birth", "place", "city", default={}))
            birth_country = en(nested(p, "birth", "place", "country", default={}))
            birth_continent = en(nested(p, "birth", "place", "continent", default={}))

            wikidata = link_value(p.get("wikidata"))
            wikipedia = link_value(p.get("wikipedia"))
            same_as = link_value(p.get("sameAs"))

            for prize in p.get("nobelPrizes", []) or []:
                label = en(prize.get("category"))
                code = prize_code_from_label(label)
                if code not in CATEGORIES:
                    continue
                try:
                    year = int(str(prize.get("awardYear", "")))
                except ValueError:
                    continue
                if not (YEAR_MIN <= year <= YEAR_MAX):
                    continue

                aff_names, aff_cities, aff_countries = flatten_affiliations(prize)
                row = {
                    "laureate_id": laureate_id,
                    "known_name": known_name,
                    "full_name": full_name,
                    "given_name": given_name,
                    "family_name": family_name,
                    "gender": gender,
                    "birth_date": birth_date,
                    "birth_date_exact": int(exact_iso_date(birth_date)),
                    "birth_city": birth_city,
                    "birth_country": birth_country,
                    "birth_continent": birth_continent,
                    "wikidata": wikidata,
                    "wikipedia": wikipedia,
                    "same_as": same_as,
                    "award_year": year,
                    "prize_category": CATEGORIES[code],
                    "prize_category_code": code,
                    "prize_portion": str(prize.get("portion", "") or ""),
                    "prize_motivation": en(prize.get("motivation")),
                    "prize_amount_sek": prize.get("prizeAmount", ""),
                    "prize_amount_adjusted_sek": prize.get("prizeAmountAdjusted", ""),
                    "award_affiliation_names": aff_names,
                    "award_affiliation_cities": aff_cities,
                    "award_affiliation_countries": aff_countries,
                    # Reserved for later blinded enrichment; intentionally blank now.
                    "discovery_year_start": "",
                    "discovery_year_end": "",
                    "discovery_institution": "",
                    "discovery_country": "",
                    "discovery_location_confidence": "",
                    "discovery_source": "",
                    "birth_latitude": "",
                    "hemisphere": "",
                    "academy_memberships": "",
                    "notes": "",
                }
                key = (laureate_id, year, code)
                rows[key] = row

    return sorted(rows.values(), key=lambda r: (r["award_year"], r["prize_category_code"], r["laureate_id"]))


def build_people(award_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    people: dict[str, dict[str, Any]] = {}
    for r in award_rows:
        lid = r["laureate_id"]
        if lid not in people:
            people[lid] = {
                k: r[k] for k in [
                    "laureate_id", "known_name", "full_name", "given_name", "family_name",
                    "gender", "birth_date", "birth_date_exact", "birth_city", "birth_country",
                    "birth_continent", "wikidata", "wikipedia", "same_as"
                ]
            }
            people[lid].update({
                "science_prize_count": 0,
                "science_prize_years": [],
                "science_prize_categories": [],
                "first_science_prize_year": None,
                "last_science_prize_year": None,
                "birth_latitude": "",
                "hemisphere": "",
                "notes": "",
            })
        p = people[lid]
        p["science_prize_count"] += 1
        p["science_prize_years"].append(str(r["award_year"]))
        p["science_prize_categories"].append(r["prize_category"])
        y = int(r["award_year"])
        p["first_science_prize_year"] = y if p["first_science_prize_year"] is None else min(p["first_science_prize_year"], y)
        p["last_science_prize_year"] = y if p["last_science_prize_year"] is None else max(p["last_science_prize_year"], y)

    out = []
    for p in people.values():
        p["science_prize_years"] = "; ".join(p["science_prize_years"])
        p["science_prize_categories"] = "; ".join(p["science_prize_categories"])
        out.append(p)
    return sorted(out, key=lambda p: (p["first_science_prize_year"], p["laureate_id"]))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"Refusing to write empty CSV: {path}")
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="nobel_science_master", help="output directory")
    args = ap.parse_args()

    out = Path(args.out)
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_by_cat: dict[str, dict[str, Any]] = {}
    print(f"Downloading Nobel science laureates for {YEAR_MIN}-{YEAR_MAX}...")
    for code, label in CATEGORIES.items():
        print(f"  {label} ({code})")
        payload = fetch_category(code, label)
        raw_by_cat[code] = payload
        raw_path = raw_dir / f"nobel_laureates_{code}_api_v2_1.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    API laureates returned: {len(payload.get('laureates', []))}")

    awards = flatten_rows(raw_by_cat)
    people = build_people(awards)

    awards_path = out / "nobel_science_awards.csv"
    people_path = out / "nobel_science_people.csv"
    summary_path = out / "nobel_science_summary.csv"

    write_csv(awards_path, awards)
    write_csv(people_path, people)

    summary_rows: list[dict[str, Any]] = []
    for code, label in CATEGORIES.items():
        subset = [r for r in awards if r["prize_category_code"] == code]
        summary_rows.append({
            "group": label,
            "award_rows_1901_2025": len(subset),
            "unique_people": len({r['laureate_id'] for r in subset}),
            "exact_birth_dates": sum(int(r["birth_date_exact"]) for r in subset),
            "missing_or_inexact_birth_dates": sum(1 - int(r["birth_date_exact"]) for r in subset),
            "earliest_award_year": min((r["award_year"] for r in subset), default=""),
            "latest_award_year": max((r["award_year"] for r in subset), default=""),
        })
    summary_rows.append({
        "group": "ALL_SCIENCE",
        "award_rows_1901_2025": len(awards),
        "unique_people": len(people),
        "exact_birth_dates": sum(int(p["birth_date_exact"]) for p in people),
        "missing_or_inexact_birth_dates": sum(1 - int(p["birth_date_exact"]) for p in people),
        "earliest_award_year": min((r["award_year"] for r in awards), default=""),
        "latest_award_year": max((r["award_year"] for r in awards), default=""),
    })
    write_csv(summary_path, summary_rows)

    # Sanity checks that do not inspect any BaZi outcome.
    if not awards or not people:
        raise RuntimeError("Empty science cohort after filtering")
    bad_year = [r for r in awards if not (YEAR_MIN <= int(r["award_year"]) <= YEAR_MAX)]
    if bad_year:
        raise RuntimeError(f"Found out-of-range award rows: {len(bad_year)}")
    bad_cat = [r for r in awards if r["prize_category_code"] not in CATEGORIES]
    if bad_cat:
        raise RuntimeError(f"Found out-of-scope categories: {len(bad_cat)}")

    files = [awards_path, people_path, summary_path] + sorted(raw_dir.glob("*.json"))
    manifest = {
        "study": "Professor -> Academy -> Nobel/Fields academic-selection study",
        "dataset": "Nobel science master roster",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "Official Nobel Prize API v2.1",
        "api_endpoint": API,
        "award_year_min": YEAR_MIN,
        "award_year_max": YEAR_MAX,
        "categories": CATEGORIES,
        "blinding_note": "No BaZi variables or hypothesis outcomes are computed by this crawler.",
        "award_row_count": len(awards),
        "unique_person_count": len(people),
        "exact_birth_date_person_count": sum(int(p["birth_date_exact"]) for p in people),
        "files": {str(p.relative_to(out)): {"sha256": sha256(p), "bytes": p.stat().st_size} for p in files},
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDone.")
    print(f"  award rows:   {len(awards)}")
    print(f"  unique people:{len(people)}")
    print(f"  exact DOB:    {manifest['exact_birth_date_person_count']}/{len(people)}")
    print(f"  output:       {out.resolve()}")
    print("\nIMPORTANT: Do not compute BaZi outcomes yet; finish cohort enrichment and freeze first.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)