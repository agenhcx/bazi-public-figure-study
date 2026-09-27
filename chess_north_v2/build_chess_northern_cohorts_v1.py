#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_chess_northern_cohorts_v1.py

PRE-REVEAL PREREGISTRATION AMENDMENT BUILDER
============================================

This script DOES NOT calculate BaZi.

It constructs new Northern-Hemisphere-only chess cohorts BEFORE any chess
BaZi reveal, in order to avoid the Southern-Hemisphere month/season inversion
dispute without introducing a month-branch transformation.

Primary v2 population rule
--------------------------
For each snapshot and sex:

  1994-01:
    - start from the FULL augmented active population
      (official FIDE list + manually restored Kasparov and Short);
    - rank by classical Elo descending;
    - a player is eligible only if:
        * exact DOB is available and clean;
        * birthplace hemisphere is CONFIRMED NORTH;
    - confirmed south is skipped;
    - unknown/ambiguous hemisphere is skipped;
    - unresolved/conflicting exact DOB is skipped;
    - continue down the ranking until 500 eligible men / 200 eligible women
      have been reached;
    - include every additional eligible player tied at that resulting Elo
      cutoff.

  2013-01:
    - same rule using the full active official FIDE population.

No GM-title requirement is added.
No Southern-Hemisphere month/season inversion is performed.

1994 identity/DOB rule
----------------------
Old 1994 FIDE Player_ID values are not assumed to equal modern FIDE IDs.
For ordinary 1994 rows:

    Jan-1994 row
      -> exact OlimpBase player hyperlink
      -> OlimpBase profile
      -> "Most recent ID"
      -> Wikidata P1440 lookup

DOB:
  - OlimpBase profile exact DOB and Wikidata exact DOB agree -> eligible.
  - OlimpBase profile exact DOB, Wikidata has no exact DOB -> eligible.
  - profile lacks exact DOB, Wikidata has one unique day-precision DOB -> eligible.
  - profile explicitly reports conflicting dates -> NOT eligible.
  - profile exact DOB and Wikidata exact DOB disagree -> NOT eligible.
  - multiple modern Wikidata entities/exact DOBs -> NOT eligible.
  - missing exact DOB -> NOT eligible.

The manually restored Kasparov/Short rows keep their already audited DOBs.

2013 DOB rule
-------------
The current FIDE ID is queried in Wikidata:
  - exactly one Wikidata person;
  - exactly one day-precision DOB;
  - DOB year must agree with the official 2013 FIDE birth year if present.
Otherwise the candidate is skipped.

Hemisphere rule
---------------
Birthplace, not federation/nationality:

  Wikidata P1440 -> person
  person P19 -> place of birth
  birthplace P625 -> latitude

  latitude > 0  -> north
  latitude < 0  -> south
  latitude == 0 -> equator (not north; skipped)
  missing/ambiguous -> unknown (skipped)

The script resolves candidates in Elo order and stops after the first complete
rating group that reaches the required eligible-N. This guarantees cutoff ties.

Outputs
-------
By default outputs go INTO the selected Git repo under:

  chess_north_v2/
    primary_north_top_1994_M.csv
    primary_north_top_1994_F.csv
    primary_north_top_2013_M.csv
    primary_north_top_2013_F.csv
    candidate_audit_1994_M.csv
    candidate_audit_1994_F.csv
    candidate_audit_2013_M.csv
    candidate_audit_2013_F.csv
    northern_cohort_summary.json
    CHESS_PREREGISTRATION_AMENDMENT_V2.md
    build_chess_northern_cohorts_v1.py

Caches remain in the local chess project directory under:
  chess_north_cache/

Git
---
Default example from:
  C:\\chenxi\\bazi_project\\chess

Run:
  python build_chess_northern_cohorts_v1.py --repo ..\\1986wiki

The script then:
  - generates and validates the v2 north-only cohorts;
  - stages ONLY chess_north_v2/;
  - commits;
  - creates annotated tag: chess-preregister-v2-hemisphere;
  - pushes current branch and tag.

Use --no-git for generation only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
OLIMPBASE_BASE = "https://www.olimpbase.org/Elo/"
UA = (
    "chess-bazi-study/northern-cohort-v1 "
    "(pre-reveal historical chess cohort construction)"
)

TARGETS = {"M": 500, "F": 200}

MANUAL_1994 = {
    4100018: {
        "name": "Kasparov, Garry",
        "dob": "1963-04-13",
        "modern_fide_id": "4100018",
    },
    400025: {
        "name": "Short, Nigel D.",
        "dob": "1965-06-01",
        "modern_fide_id": "400025",
    },
}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def norm_space(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def norm_name(s: Any) -> str:
    return norm_space(s).casefold()


def norm_id(v: Any) -> str | None:
    if pd.isna(v):
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return str(int(float(s)))
    except Exception:
        return s


def norm_dob(v: Any) -> str | None:
    if pd.isna(v) or not str(v).strip():
        return None
    dt = pd.to_datetime(str(v).strip(), errors="coerce")
    if pd.isna(dt):
        return None
    return dt.strftime("%Y-%m-%d")


def boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def chunks(xs: list[str], n: int):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]


def run(cmd: list[str], cwd: Path, check: bool = True) -> str:
    print("$", " ".join(cmd))
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}"
        )
    return p.stdout.strip()


def validate_git_repo(path: Path) -> Path:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    top = run(
        ["git", "rev-parse", "--show-toplevel"],
        path,
    ).splitlines()[-1]
    return Path(top).resolve()


def find_existing(candidates: list[Path], label: str) -> Path:
    for p in candidates:
        if p.exists():
            return p.resolve()
    raise FileNotFoundError(
        f"Could not find {label}. Tried:\n  "
        + "\n  ".join(str(p) for p in candidates)
    )


def read_population(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    required = {"fide_id", "name", "rating", "sex"}
    missing = required - set(d.columns)
    if missing:
        raise RuntimeError(
            f"{path}: missing required columns {sorted(missing)}"
        )
    d["fide_id"] = pd.to_numeric(
        d["fide_id"], errors="raise"
    ).astype(int)
    d["rating"] = pd.to_numeric(
        d["rating"], errors="raise"
    ).astype(int)
    d["sex"] = d["sex"].astype(str).str.upper().str.strip()

    if "active" in d.columns:
        active_mask = d["active"].map(boolish)
        d = d[active_mask].copy()

    if d["fide_id"].duplicated().any():
        x = d[d["fide_id"].duplicated(False)][
            ["fide_id", "name", "rating", "sex"]
        ]
        raise RuntimeError(
            f"{path}: duplicate FIDE IDs:\n{x.to_string(index=False)}"
        )

    return d.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Network sessions
# ---------------------------------------------------------------------------

def build_session(proxy: str | None) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "application/sparql-results+json, application/json",
        }
    )
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    else:
        s.trust_env = False
    return s


def direct_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    s.trust_env = False
    return s


def get_olimpbase(
    configured: requests.Session,
    url: str,
    timeout: int,
) -> tuple[bytes, str]:
    errors = []
    # Old OlimpBase previously worked more reliably direct than through the
    # user's HTTP CONNECT proxy, so try direct first.
    for label, sess in [
        ("DIRECT", direct_session()),
        ("CONFIGURED", configured),
    ]:
        try:
            r = sess.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            if not r.content:
                raise RuntimeError("empty response")
            return r.content, r.url
        except Exception as e:
            errors.append(f"{label}: {type(e).__name__}: {e}")

    raise RuntimeError(
        f"OlimpBase download failed for {url}\n  "
        + "\n  ".join(errors)
    )


# ---------------------------------------------------------------------------
# OlimpBase 1994 identity bridge
# ---------------------------------------------------------------------------

def build_profile_link_index(html_path: Path) -> dict[str, list[str]]:
    raw = html_path.read_bytes()
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("latin-1", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    idx: dict[str, list[str]] = {}

    for a in soup.find_all("a", href=True):
        text = norm_space(a.get_text(" ", strip=True))
        href = str(a.get("href", "")).strip()
        if not text or not href:
            continue

        low = href.lower()
        if (
            "player" not in low
            and "/elo/" not in low
            and not low.endswith(".html")
        ):
            continue

        url = urljoin(OLIMPBASE_BASE, href)
        key = norm_name(text)
        idx.setdefault(key, [])
        if url not in idx[key]:
            idx[key].append(url)

    return idx


def choose_profile_url(
    name: str,
    idx: dict[str, list[str]],
) -> tuple[str | None, str]:
    key = norm_name(name)
    urls = idx.get(key, [])

    if len(urls) == 1:
        return urls[0], "exact_anchor"

    if len(urls) > 1:
        preferred = [
            x for x in urls
            if "/elo/player/" in x.lower()
        ]
        if len(preferred) == 1:
            return preferred[0], "exact_anchor_preferred"
        return None, f"ambiguous_anchor:{len(urls)}"

    # Conservative fallback for suffix differences.
    cand = []
    for k, us in idx.items():
        if k.startswith(key) or key.startswith(k):
            cand.extend(us)

    unique = sorted(set(cand))
    if len(unique) == 1:
        return unique[0], "prefix_anchor_unique"

    return None, "no_unique_anchor"


def table_field(soup: BeautifulSoup, label: str) -> str | None:
    target = label.casefold().rstrip(":")
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        vals = [norm_space(c.get_text(" ", strip=True)) for c in cells]
        for i, val in enumerate(vals):
            if val.casefold().rstrip(":") == target and i + 1 < len(vals):
                x = vals[i + 1]
                return x or None
    return None


def parse_profile_dob(raw: str | None) -> tuple[str | None, str]:
    if raw is None:
        return None, "missing"

    s = norm_space(raw)
    sl = s.casefold()
    if not s:
        return None, "missing"

    if any(
        p in sl
        for p in [
            "different date",
            "different dates",
            "various date",
            "unknown",
            "not known",
            "n/a",
            "no data",
        ]
    ):
        if "different" in sl or "various" in sl:
            return None, "profile_reports_conflicting_dobs"
        return None, "profile_no_exact_dob"

    if re.fullmatch(r"\d{4}", s):
        return None, "year_only"

    dt = pd.to_datetime(s, errors="coerce", dayfirst=False)
    if pd.isna(dt):
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return None, "unparsed_profile_dob"

    return dt.strftime("%Y-%m-%d"), "exact"


def parse_olimpbase_profile(
    content: bytes,
    final_url: str,
) -> dict[str, Any]:
    try:
        html = content.decode("utf-8")
    except UnicodeDecodeError:
        html = content.decode("latin-1", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    name = table_field(soup, "Player name")
    dob_raw = table_field(soup, "Date of birth")
    recent_raw = table_field(soup, "Most recent ID")
    fed = table_field(soup, "Most recent federation")
    sex = table_field(soup, "Sex")

    dob, dob_status = parse_profile_dob(dob_raw)

    recent_id = None
    if recent_raw:
        m = re.search(r"\d+", recent_raw.replace(",", ""))
        if m:
            recent_id = m.group()

    return {
        "profile_url": final_url,
        "profile_player_name": name,
        "profile_dob_raw": dob_raw,
        "profile_dob": dob,
        "profile_dob_status": dob_status,
        "profile_most_recent_id": recent_id,
        "profile_federation": fed,
        "profile_sex": sex,
    }


def load_json_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    x = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(x, dict):
        raise RuntimeError(f"Cache root is not object: {path}")
    return x


def save_json_cache(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def get_1994_profile(
    row: pd.Series,
    link_index: dict[str, list[str]],
    cache: dict,
    cache_path: Path,
    session: requests.Session,
    timeout: int,
) -> dict[str, Any]:
    fid = int(row["fide_id"])

    if fid in MANUAL_1994:
        m = MANUAL_1994[fid]
        return {
            "profile_url": "",
            "profile_player_name": m["name"],
            "profile_dob_raw": m["dob"],
            "profile_dob": m["dob"],
            "profile_dob_status": "manual_restored_exact",
            "profile_most_recent_id": m["modern_fide_id"],
            "link_status": "manual_restored",
        }

    key = str(fid)
    if key in cache:
        return cache[key]

    url, link_status = choose_profile_url(str(row["name"]), link_index)
    if not url:
        rec = {
            "profile_url": "",
            "profile_player_name": "",
            "profile_dob_raw": "",
            "profile_dob": None,
            "profile_dob_status": "no_profile_link",
            "profile_most_recent_id": None,
            "link_status": link_status,
        }
        cache[key] = rec
        save_json_cache(cache_path, cache)
        return rec

    try:
        content, final_url = get_olimpbase(
            session, url, timeout
        )
        rec = parse_olimpbase_profile(content, final_url)
        rec["link_status"] = link_status
    except Exception as e:
        rec = {
            "profile_url": url,
            "profile_player_name": "",
            "profile_dob_raw": "",
            "profile_dob": None,
            "profile_dob_status": f"download_error:{type(e).__name__}",
            "profile_most_recent_id": None,
            "link_status": link_status,
            "error": str(e),
        }

    cache[key] = rec
    save_json_cache(cache_path, cache)
    return rec


# ---------------------------------------------------------------------------
# Wikidata identity/DOB/birthplace query
# ---------------------------------------------------------------------------

def make_wikidata_query(ids: list[str]) -> str:
    values = " ".join(json.dumps(x) for x in ids)
    return f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT ?fide ?person ?dob ?precision
       ?birthplace ?birthplaceLabel ?lat ?lon WHERE {{
  VALUES ?fide {{ {values} }}

  ?person wdt:P1440 ?fide .

  OPTIONAL {{
    ?person p:P569 ?dobStatement .
    ?dobStatement psv:P569 ?dobValue .
    ?dobValue wikibase:timeValue ?dob ;
              wikibase:timePrecision ?precision .
  }}

  OPTIONAL {{
    ?person wdt:P19 ?birthplace .
    OPTIONAL {{
      ?birthplace p:P625/psv:P625 ?coordNode .
      ?coordNode wikibase:geoLatitude ?lat ;
                 wikibase:geoLongitude ?lon .
    }}
  }}

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en,zh".
    ?birthplace rdfs:label ?birthplaceLabel .
  }}
}}
ORDER BY ?fide ?person ?birthplace
""".strip()


def query_wikidata_batch(
    session: requests.Session,
    ids: list[str],
    timeout: int,
    retries: int,
) -> list[dict[str, Any]]:
    q = make_wikidata_query(ids)
    last = None

    for attempt in range(1, retries + 1):
        try:
            r = session.get(
                SPARQL_ENDPOINT,
                params={"query": q, "format": "json"},
                timeout=timeout,
            )

            if r.status_code == 429:
                wait = min(30.0, 2.0 * attempt)
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    wait = float(ra)
                print(
                    f"[wikidata] 429; sleep {wait:.1f}s "
                    f"({attempt}/{retries})"
                )
                time.sleep(wait)
                continue

            r.raise_for_status()
            return r.json()["results"]["bindings"]

        except Exception as e:
            last = e
            if attempt == retries:
                break
            wait = min(30.0, 2.0 * attempt)
            print(
                f"[wikidata] {type(e).__name__}: {e}; "
                f"retry in {wait:.1f}s"
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Wikidata batch failed after {retries} attempts: {last}"
    )


def parse_wikidata_bindings(
    bindings: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}

    for b in bindings:
        fid = b["fide"]["value"]
        person = b["person"]["value"].rsplit("/", 1)[-1]

        raw_dob = b.get("dob", {}).get("value")
        raw_prec = b.get("precision", {}).get("value")
        precision = (
            int(float(raw_prec))
            if raw_prec is not None
            else None
        )

        dob = None
        if raw_dob:
            clean = raw_dob.lstrip("+")
            dt = pd.to_datetime(
                clean, errors="coerce", utc=True
            )
            if pd.notna(dt):
                dob = dt.strftime("%Y-%m-%d")
            else:
                dob = clean[:10]

        bp_raw = b.get("birthplace", {}).get("value")
        bp_qid = (
            bp_raw.rsplit("/", 1)[-1]
            if bp_raw
            else None
        )
        bp_label = b.get(
            "birthplaceLabel", {}
        ).get("value")

        lat_raw = b.get("lat", {}).get("value")
        lon_raw = b.get("lon", {}).get("value")

        lat = (
            float(lat_raw)
            if lat_raw is not None
            else None
        )
        lon = (
            float(lon_raw)
            if lon_raw is not None
            else None
        )

        out.setdefault(fid, []).append(
            {
                "person_qid": person,
                "dob": dob,
                "precision": precision,
                "birthplace_qid": bp_qid,
                "birthplace_label": bp_label,
                "lat": lat,
                "lon": lon,
            }
        )

    return out


def fetch_wikidata_ids(
    ids: list[str],
    session: requests.Session,
    cache: dict,
    cache_path: Path,
    batch_size: int,
    timeout: int,
    retries: int,
    delay: float,
) -> None:
    wanted = sorted(set(x for x in ids if x))
    missing = [x for x in wanted if x not in cache]

    if not missing:
        return

    batches = list(chunks(missing, batch_size))
    for i, batch in enumerate(batches, 1):
        print(
            f"[wikidata] fetch batch {i}/{len(batches)} "
            f"({len(batch)} IDs)"
        )
        parsed = parse_wikidata_bindings(
            query_wikidata_batch(
                session,
                batch,
                timeout=timeout,
                retries=retries,
            )
        )

        for fid in batch:
            cache[fid] = parsed.get(fid, [])

        save_json_cache(cache_path, cache)

        if delay > 0 and i < len(batches):
            time.sleep(delay)


def summarize_wikidata(
    matches: list[dict[str, Any]],
) -> dict[str, Any]:
    if not matches:
        return {
            "person_qids": [],
            "exact_dobs": [],
            "all_dobs": [],
            "birthplace_qids": [],
            "birthplace_labels": [],
            "latitudes": [],
            "longitudes": [],
            "hemisphere": "unknown",
            "hemisphere_status": "no_wikidata_match",
        }

    persons = sorted(
        {
            x["person_qid"]
            for x in matches
            if x.get("person_qid")
        }
    )

    exact_dobs = sorted(
        {
            x["dob"]
            for x in matches
            if x.get("dob")
            and x.get("precision") is not None
            and int(x["precision"]) >= 11
        }
    )

    all_dobs = sorted(
        {
            x["dob"]
            for x in matches
            if x.get("dob")
        }
    )

    bp_qids = sorted(
        {
            x["birthplace_qid"]
            for x in matches
            if x.get("birthplace_qid")
        }
    )
    bp_labels = sorted(
        {
            x["birthplace_label"]
            for x in matches
            if x.get("birthplace_label")
        }
    )

    lats = sorted(
        {
            round(float(x["lat"]), 8)
            for x in matches
            if x.get("lat") is not None
            and math.isfinite(float(x["lat"]))
        }
    )
    lons = sorted(
        {
            round(float(x["lon"]), 8)
            for x in matches
            if x.get("lon") is not None
            and math.isfinite(float(x["lon"]))
        }
    )

    if len(persons) != 1:
        hemi = "unknown"
        hstatus = (
            "multiple_wikidata_people"
            if len(persons) > 1
            else "no_wikidata_person"
        )
    elif not bp_qids:
        hemi = "unknown"
        hstatus = "person_no_birthplace"
    elif not lats:
        hemi = "unknown"
        hstatus = "birthplace_no_coordinates"
    else:
        hs = sorted(
            {
                "north" if x > 0
                else "south" if x < 0
                else "equator"
                for x in lats
            }
        )
        if len(hs) == 1:
            hemi = hs[0]
            hstatus = (
                "resolved_unique_birthplace"
                if len(bp_qids) == 1
                else "multiple_birthplaces_same_hemisphere"
            )
        else:
            hemi = "unknown"
            hstatus = "birthplaces_cross_hemispheres"

    return {
        "person_qids": persons,
        "exact_dobs": exact_dobs,
        "all_dobs": all_dobs,
        "birthplace_qids": bp_qids,
        "birthplace_labels": bp_labels,
        "latitudes": lats,
        "longitudes": lons,
        "hemisphere": hemi,
        "hemisphere_status": hstatus,
    }


# ---------------------------------------------------------------------------
# Candidate adjudication
# ---------------------------------------------------------------------------

def known_birth_year_2013(row: pd.Series) -> int | None:
    for col in ["birth_year", "source_birth_year"]:
        if col in row.index and pd.notna(row[col]):
            try:
                y = int(float(row[col]))
                if y > 0:
                    return y
            except Exception:
                pass
    return None


def adjudicate_1994(
    row: pd.Series,
    profile: dict[str, Any],
    wd: dict[str, Any],
) -> dict[str, Any]:
    fid = int(row["fide_id"])
    profile_dob = norm_dob(profile.get("profile_dob"))
    profile_status = str(
        profile.get("profile_dob_status", "")
    )

    modern_id = norm_id(
        profile.get("profile_most_recent_id")
    )

    # Manual institutional restorations are already audited for DOB.
    manual_restore = fid in MANUAL_1994
    if manual_restore:
        profile_dob = MANUAL_1994[fid]["dob"]
        modern_id = MANUAL_1994[fid]["modern_fide_id"]

    exacts = wd.get("exact_dobs", [])
    persons = wd.get("person_qids", [])

    wd_exact = (
        exacts[0]
        if len(persons) == 1 and len(exacts) == 1
        else None
    )

    dob = None
    dob_status = ""

    if profile_status == "profile_reports_conflicting_dobs":
        dob_status = "profile_explicit_dob_conflict"

    elif manual_restore:
        # Keep the manually restored/audited DOB; Wikidata is identity/birthplace
        # support, not a reason to reopen the institutional omission.
        dob = profile_dob
        dob_status = "manual_restored_audited_dob"

    elif profile_dob and wd_exact:
        if profile_dob == wd_exact:
            dob = profile_dob
            dob_status = "profile_wikidata_agree"
        else:
            dob_status = "profile_wikidata_exact_conflict"

    elif profile_dob and not wd_exact:
        if len(persons) <= 1 and len(exacts) <= 1:
            dob = profile_dob
            dob_status = "profile_exact_wikidata_no_unique_exact"
        else:
            dob_status = "wikidata_identity_or_dob_ambiguous"

    elif (not profile_dob) and wd_exact:
        dob = wd_exact
        dob_status = "wikidata_exact_via_modern_id"

    else:
        if len(persons) > 1:
            dob_status = "multiple_wikidata_people"
        elif len(exacts) > 1:
            dob_status = "multiple_wikidata_exact_dobs"
        elif wd.get("all_dobs"):
            dob_status = "wikidata_non_day_precision"
        else:
            dob_status = "no_exact_dob"

    hemi = wd.get("hemisphere", "unknown")
    eligible = bool(
        dob is not None
        and hemi == "north"
        and dob_status not in {
            "profile_explicit_dob_conflict",
            "profile_wikidata_exact_conflict",
            "wikidata_identity_or_dob_ambiguous",
            "multiple_wikidata_people",
            "multiple_wikidata_exact_dobs",
        }
    )

    if eligible:
        exclusion = ""
    elif dob is None:
        exclusion = f"dob:{dob_status}"
    elif hemi != "north":
        exclusion = f"hemisphere:{hemi}:{wd.get('hemisphere_status','')}"
    else:
        exclusion = "other"

    return {
        "identity_bridge_modern_fide_id": modern_id,
        "exact_dob_north_v2": dob,
        "dob_status_north_v2": dob_status,
        "birthplace_hemisphere": hemi,
        "hemisphere_status": wd.get("hemisphere_status", ""),
        "wikidata_person_qids": ";".join(wd.get("person_qids", [])),
        "birthplace_qids": ";".join(wd.get("birthplace_qids", [])),
        "birthplace_labels": ";".join(wd.get("birthplace_labels", [])),
        "birthplace_latitudes": ";".join(
            map(str, wd.get("latitudes", []))
        ),
        "birthplace_longitudes": ";".join(
            map(str, wd.get("longitudes", []))
        ),
        "olimpbase_profile_url": profile.get("profile_url", ""),
        "olimpbase_profile_dob": profile_dob,
        "eligible_north_primary_v2": eligible,
        "north_v2_exclusion_reason": exclusion,
    }


def adjudicate_2013(
    row: pd.Series,
    wd: dict[str, Any],
) -> dict[str, Any]:
    persons = wd.get("person_qids", [])
    exacts = wd.get("exact_dobs", [])

    dob = None
    dob_status = ""

    if len(persons) != 1:
        dob_status = (
            "multiple_wikidata_people"
            if len(persons) > 1
            else "no_wikidata_match"
        )
    elif len(exacts) != 1:
        if len(exacts) > 1:
            dob_status = "multiple_wikidata_exact_dobs"
        elif wd.get("all_dobs"):
            dob_status = "wikidata_non_day_precision"
        else:
            dob_status = "no_exact_dob"
    else:
        dob = exacts[0]
        known_year = known_birth_year_2013(row)
        if known_year is not None and int(dob[:4]) != known_year:
            dob_status = "wikidata_year_mismatch"
            dob = None
        else:
            dob_status = "wikidata_exact_year_agrees"

    hemi = wd.get("hemisphere", "unknown")
    eligible = bool(
        dob is not None
        and hemi == "north"
        and dob_status == "wikidata_exact_year_agrees"
    )

    if eligible:
        exclusion = ""
    elif dob is None:
        exclusion = f"dob:{dob_status}"
    elif hemi != "north":
        exclusion = f"hemisphere:{hemi}:{wd.get('hemisphere_status','')}"
    else:
        exclusion = "other"

    return {
        "identity_bridge_modern_fide_id": norm_id(row["fide_id"]),
        "exact_dob_north_v2": dob,
        "dob_status_north_v2": dob_status,
        "birthplace_hemisphere": hemi,
        "hemisphere_status": wd.get("hemisphere_status", ""),
        "wikidata_person_qids": ";".join(wd.get("person_qids", [])),
        "birthplace_qids": ";".join(wd.get("birthplace_qids", [])),
        "birthplace_labels": ";".join(wd.get("birthplace_labels", [])),
        "birthplace_latitudes": ";".join(
            map(str, wd.get("latitudes", []))
        ),
        "birthplace_longitudes": ";".join(
            map(str, wd.get("longitudes", []))
        ),
        "olimpbase_profile_url": "",
        "olimpbase_profile_dob": None,
        "eligible_north_primary_v2": eligible,
        "north_v2_exclusion_reason": exclusion,
    }


# ---------------------------------------------------------------------------
# Elo-order scanner
# ---------------------------------------------------------------------------

def scan_northern_cohort(
    year: int,
    sex: str,
    population: pd.DataFrame,
    target: int,
    link_index: dict[str, list[str]] | None,
    profile_cache: dict,
    profile_cache_path: Path,
    wd_cache: dict,
    wd_cache_path: Path,
    olimp_session: requests.Session,
    wd_session: requests.Session,
    batch_size: int,
    timeout: int,
    retries: int,
    delay: float,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    pop = population[
        population["sex"].eq(sex)
    ].copy()

    pop.sort_values(
        ["rating", "name", "fide_id"],
        ascending=[False, True, True],
        inplace=True,
    )
    pop.reset_index(drop=True, inplace=True)

    eligible_rows = []
    audit_rows = []
    cutoff = None

    # Resolve by complete Elo groups so the final eligible cohort naturally
    # includes all eligible ties at the cutoff.
    for rating, group in pop.groupby(
        "rating",
        sort=False,
    ):
        group = group.copy()

        if year == 1994:
            profiles = {}
            modern_ids = []

            for idx, row in group.iterrows():
                p = get_1994_profile(
                    row=row,
                    link_index=link_index or {},
                    cache=profile_cache,
                    cache_path=profile_cache_path,
                    session=olimp_session,
                    timeout=timeout,
                )
                profiles[idx] = p
                mid = norm_id(
                    p.get("profile_most_recent_id")
                )
                if mid:
                    modern_ids.append(mid)

            fetch_wikidata_ids(
                modern_ids,
                session=wd_session,
                cache=wd_cache,
                cache_path=wd_cache_path,
                batch_size=batch_size,
                timeout=timeout,
                retries=retries,
                delay=delay,
            )

            for idx, row in group.iterrows():
                p = profiles[idx]
                mid = norm_id(
                    p.get("profile_most_recent_id")
                )
                ws = summarize_wikidata(
                    wd_cache.get(mid, [])
                    if mid
                    else []
                )
                meta = adjudicate_1994(
                    row=row,
                    profile=p,
                    wd=ws,
                )

                rec = row.to_dict()
                rec.update(meta)
                rec["snapshot"] = "1994-01"
                rec["analysis_sex"] = sex
                audit_rows.append(rec)

                if meta["eligible_north_primary_v2"]:
                    eligible_rows.append(rec)

        elif year == 2013:
            ids = [
                norm_id(x)
                for x in group["fide_id"].tolist()
            ]
            ids = [x for x in ids if x]

            fetch_wikidata_ids(
                ids,
                session=wd_session,
                cache=wd_cache,
                cache_path=wd_cache_path,
                batch_size=batch_size,
                timeout=timeout,
                retries=retries,
                delay=delay,
            )

            for _, row in group.iterrows():
                fid = norm_id(row["fide_id"])
                ws = summarize_wikidata(
                    wd_cache.get(fid, [])
                    if fid
                    else []
                )
                meta = adjudicate_2013(
                    row=row,
                    wd=ws,
                )

                rec = row.to_dict()
                rec.update(meta)
                rec["snapshot"] = "2013-01"
                rec["analysis_sex"] = sex
                audit_rows.append(rec)

                if meta["eligible_north_primary_v2"]:
                    eligible_rows.append(rec)

        else:
            raise ValueError(year)

        print(
            f"[{year} {sex}] processed Elo={rating}; "
            f"eligible north exact-DOB={len(eligible_rows)}/{target}; "
            f"candidates audited={len(audit_rows)}"
        )

        if len(eligible_rows) >= target:
            cutoff = int(rating)
            break

    if cutoff is None:
        raise RuntimeError(
            f"{year} {sex}: exhausted population before reaching target {target}"
        )

    cohort = pd.DataFrame(eligible_rows)
    audit = pd.DataFrame(audit_rows)

    # Because scanning stopped after a complete Elo group, every eligible tie
    # at the cutoff is included.
    if (cohort["rating"] < cutoff).any():
        raise RuntimeError(
            f"{year} {sex}: cohort contains rating below cutoff"
        )

    n_above = int((cohort["rating"] > cutoff).sum())
    n_cutoff = int((cohort["rating"] == cutoff).sum())

    if n_above >= target:
        raise RuntimeError(
            f"{year} {sex}: target was already met above cutoff; "
            "scanner/tie logic inconsistent"
        )
    if n_above + n_cutoff < target:
        raise RuntimeError(
            f"{year} {sex}: target not reached at cutoff"
        )

    cohort.sort_values(
        ["rating", "name", "fide_id"],
        ascending=[False, True, True],
        inplace=True,
    )
    cohort.reset_index(drop=True, inplace=True)

    cohort["analysis_rank_within_sex"] = (
        cohort["rating"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )

    sd = cohort["rating"].std(ddof=1)
    cohort["elo_z_within_snapshot_sex"] = (
        (cohort["rating"] - cohort["rating"].mean()) / sd
        if sd and pd.notna(sd)
        else 0.0
    )

    n = len(cohort)
    cohort["rank_percentile_within_snapshot_sex"] = (
        (n - cohort["analysis_rank_within_sex"]) / (n - 1)
        if n > 1
        else 1.0
    )

    cohort["exact_dob_frozen"] = cohort[
        "exact_dob_north_v2"
    ]

    audit.sort_values(
        ["rating", "name", "fide_id"],
        ascending=[False, True, True],
        inplace=True,
    )
    audit.reset_index(drop=True, inplace=True)

    return cohort, audit, cutoff


# ---------------------------------------------------------------------------
# Preregistration amendment
# ---------------------------------------------------------------------------

def amendment_text(summary: dict[str, Any]) -> str:
    def x(key):
        return summary["cohorts"][key]

    return f"""# Chess BaZi Study — Preregistration Amendment v2
## Northern-Hemisphere Primary Cohorts

**Status:** written and committed before the first chess BaZi calculation/reveal.

This amendment does not delete or rewrite `chess-preregister-v1`.
The v1 frozen cohorts remain available as sensitivity analyses.

## Reason for amendment

The purpose of the hemisphere restriction is to avoid a methodological dispute
over whether Southern-Hemisphere births should use a season/month inversion.

No such inversion is applied in this study.

Instead, the v2 primary analysis is restricted to players with a confirmed
Northern-Hemisphere birthplace.

This rule was frozen before calculating any chess BaZi variables.

## Hemisphere definition

Hemisphere is determined by **birthplace latitude**, not federation,
citizenship, residence, or chess federation.

Data path:

- FIDE ID -> Wikidata `P1440`
- person -> place of birth `P19`
- birthplace -> coordinates `P625`

Classification:

- latitude > 0: North
- latitude < 0: South
- latitude = 0: Equator
- missing/ambiguous identity, birthplace, or coordinates: Unknown

Only confirmed North is eligible for the v2 primary cohorts.

South, Equator, and Unknown are skipped. They are not relabeled.

## Population construction

For each historical snapshot and sex, players are ranked by classical Elo.

The scanner proceeds downward through the FULL active population and includes
only players satisfying BOTH:

1. clean exact Gregorian DOB;
2. confirmed Northern-Hemisphere birthplace.

It continues until at least:

- 500 men;
- 200 women

have been obtained, and then includes every additional eligible player tied at
the resulting Elo cutoff.

No GM-title requirement is imposed.

### Frozen v2 cohorts

- 1994 men: **{x("1994_M")["n"]}**, cutoff Elo **{x("1994_M")["cutoff_elo"]}**
- 1994 women: **{x("1994_F")["n"]}**, cutoff Elo **{x("1994_F")["cutoff_elo"]}**
- 2013 men: **{x("2013_M")["n"]}**, cutoff Elo **{x("2013_M")["cutoff_elo"]}**
- 2013 women: **{x("2013_F")["n"]}**, cutoff Elo **{x("2013_F")["cutoff_elo"]}**

## 1994 historical identity rule

Raw January-1994 `Player_ID` values are not assumed to equal modern FIDE IDs.

Identity bridge:

January-1994 row -> exact OlimpBase player profile -> `Most recent ID` ->
Wikidata.

Kasparov and Short remain restored before ranking because their 1994 official
FIDE-list absence resulted from the FIDE/PCA split rather than chess strength.

## Exact-DOB rule

### 1994

- OlimpBase profile and Wikidata exact DOB agree: eligible.
- Exact OlimpBase profile DOB with no unique conflicting Wikidata exact DOB:
  eligible.
- No profile exact DOB but one unique day-level Wikidata DOB through the
  identity-bridged modern FIDE ID: eligible.
- Explicit profile DOB conflict: excluded.
- Profile vs Wikidata exact-date disagreement: excluded.
- Multiple identities/exact dates or missing exact DOB: excluded.

### 2013

Exactly one identity-matched day-level Wikidata DOB is required, and its year
must agree with the official 2013 FIDE birth year when that year is available.

## Primary analysis

The v2 Northern-Hemisphere cohorts are the primary population for the
preregistered chess hypotheses.

The previously frozen `chess-preregister-v1` cohorts are retained as
sensitivity analyses.

No month/season inversion is performed for any player.

## Performance endpoint

The primary continuous performance endpoint remains:

`elo_z_within_snapshot_sex`

computed inside each frozen snapshot x sex cohort.

## Hypotheses

The substantive hypotheses remain those frozen in v1. This amendment changes
the population rule for the primary analysis; it does not add a BaZi-derived
hypothesis.

The principal headline tests remain:

1. temporal Day-Master element gradient, including the predefined Metal/Earth
   comparison;
2. 1994 vs 2013 Day-Master element distribution;
3. predefined measurable three-pillar 伤官 / 偏印 exposure analyses;
4. preregistered performance analyses.

## Reveal rule

After this amendment is committed/tagged:

- v2 north-only cohort membership is immutable for primary analysis;
- BaZi is calculated from `exact_dob_frozen`;
- any newly noticed BaZi pattern is exploratory;
- South/Unknown players cannot be selectively restored after seeing results.

**No chess BaZi values were used to construct this amendment.**
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--project-dir",
        default=".",
        help="local chess working directory",
    )
    ap.add_argument(
        "--repo",
        default=r"..\1986wiki",
        help="existing Git repo receiving the amendment/frozen cohorts",
    )
    ap.add_argument(
        "--output-subdir",
        default="chess_north_v2",
        help="output directory inside Git repo",
    )
    ap.add_argument(
        "--proxy",
        default=None,
        help="optional proxy, e.g. http://127.0.0.1:10808",
    )
    ap.add_argument(
        "--tag",
        default="chess-preregister-v2-hemisphere",
    )
    ap.add_argument(
        "--commit-message",
        default=(
            "Freeze northern-hemisphere chess cohorts before BaZi reveal"
        ),
    )
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--no-git", action="store_true")

    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--delay", type=float, default=0.35)

    args = ap.parse_args()

    project = Path(args.project_dir).resolve()
    repo = validate_git_repo(Path(args.repo))

    print("Chess project:", project)
    print("Git repo:     ", repo)

    remote_url = run(
        ["git", "remote", "get-url", args.remote],
        repo,
        check=False,
    ).strip()
    if remote_url:
        print(f"Git remote {args.remote}: {remote_url}")

    # Resolve inputs.
    p1994_path = find_existing(
        [
            project / "chess_dob" / "augmented_active_1994.csv",
            project / "chess_crawl" / "augmented_active_1994.csv",
        ],
        "augmented_active_1994.csv",
    )

    p2013_path = find_existing(
        [
            project / "chess_crawl" / "active_2013.csv",
            project / "chess_dob" / "active_2013.csv",
        ],
        "active_2013.csv",
    )

    html_path = find_existing(
        [
            project / "Elo199401e.html",
            project / "chess_crawl" / "Elo199401e.html",
        ],
        "Elo199401e.html",
    )

    print("1994 population:", p1994_path)
    print("2013 population:", p2013_path)
    print("1994 HTML:      ", html_path)

    pop94 = read_population(p1994_path)
    pop13 = read_population(p2013_path)

    # Basic anchor counts from the already frozen source population.
    if len(pop94) < 12000:
        raise RuntimeError(
            f"1994 augmented active population unexpectedly small: {len(pop94)}"
        )
    if len(pop13) < 80000:
        raise RuntimeError(
            f"2013 active population unexpectedly small: {len(pop13)}"
        )

    cache_dir = project / "chess_north_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    profile_cache_path = (
        cache_dir / "olimpbase_1994_profile_cache_north_v2.json"
    )
    wd_cache_path = (
        cache_dir / "wikidata_identity_dob_birthplace_cache_north_v2.json"
    )

    # Seed profile cache with the previously collected cache when available.
    if not profile_cache_path.exists():
        prior = project / "chess_dob" / "olimpbase_1994_profile_cache.json"
        if prior.exists():
            shutil.copy2(prior, profile_cache_path)
            print("Seeded 1994 profile cache from prior enrichment.")

    # Seed Wikidata cache is deliberately not copied from older split-purpose
    # caches because this script needs DOB + birthplace coordinates together.

    profile_cache = load_json_cache(profile_cache_path)
    wd_cache = load_json_cache(wd_cache_path)

    link_index = build_profile_link_index(html_path)
    print(
        f"1994 local HTML profile-link keys: {len(link_index):,}"
    )

    olimp_session = build_session(args.proxy)
    wd_session = build_session(args.proxy)

    results = {}
    audits = {}
    cutoffs = {}

    for year, population in [(1994, pop94), (2013, pop13)]:
        for sex in ["M", "F"]:
            print(
                f"\n=== BUILD {year} {sex} NORTH TOP-{TARGETS[sex]} ==="
            )
            cohort, audit, cutoff = scan_northern_cohort(
                year=year,
                sex=sex,
                population=population,
                target=TARGETS[sex],
                link_index=link_index if year == 1994 else None,
                profile_cache=profile_cache,
                profile_cache_path=profile_cache_path,
                wd_cache=wd_cache,
                wd_cache_path=wd_cache_path,
                olimp_session=olimp_session,
                wd_session=wd_session,
                batch_size=args.batch_size,
                timeout=args.timeout,
                retries=args.retries,
                delay=args.delay,
            )
            key = f"{year}_{sex}"
            results[key] = cohort
            audits[key] = audit
            cutoffs[key] = cutoff

    outdir = (repo / args.output_subdir).resolve()
    try:
        outdir.relative_to(repo)
    except ValueError:
        raise RuntimeError(
            f"Output resolves outside Git repo: {outdir}"
        )
    outdir.mkdir(parents=True, exist_ok=True)

    generated = []

    for key, df in results.items():
        year, sex = key.split("_")
        p = outdir / f"primary_north_top_{year}_{sex}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")
        generated.append(p)

    for key, df in audits.items():
        year, sex = key.split("_")
        p = outdir / f"candidate_audit_{year}_{sex}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")
        generated.append(p)

    def cohort_summary(key: str) -> dict[str, Any]:
        d = results[key]
        a = audits[key]
        year, sex = key.split("_")
        cutoff = int(cutoffs[key])

        exclusions = (
            a.loc[
                ~a["eligible_north_primary_v2"].map(boolish),
                "north_v2_exclusion_reason",
            ]
            .value_counts()
            .to_dict()
        )

        return {
            "year": int(year),
            "sex": sex,
            "target": TARGETS[sex],
            "n": int(len(d)),
            "cutoff_elo": cutoff,
            "n_above_cutoff": int((d["rating"] > cutoff).sum()),
            "n_at_cutoff": int((d["rating"] == cutoff).sum()),
            "candidates_scanned": int(len(a)),
            "highest_elo": int(d["rating"].max()),
            "lowest_elo": int(d["rating"].min()),
            "mean_elo": float(d["rating"].mean()),
            "birth_year_min": int(
                pd.to_datetime(d["exact_dob_frozen"]).dt.year.min()
            ),
            "birth_year_max": int(
                pd.to_datetime(d["exact_dob_frozen"]).dt.year.max()
            ),
            "exclusion_reason_counts_scanned": {
                str(k): int(v)
                for k, v in exclusions.items()
            },
        }

    summary = {
        "stage": (
            "pre-reveal northern-hemisphere cohort amendment; no BaZi"
        ),
        "analysis_role": "primary population amendment v2",
        "rule": {
            "hemisphere_basis": "birthplace latitude via Wikidata P19/P625",
            "eligible_hemisphere": "north only (latitude > 0)",
            "south": "excluded",
            "equator": "excluded",
            "unknown": "excluded",
            "season_month_inversion": "none",
            "gm_requirement": "none",
            "selection": (
                "scan full active Elo ranking downward until target number "
                "of clean exact-DOB confirmed-north players; include eligible "
                "cutoff ties"
            ),
        },
        "cohorts": {
            key: cohort_summary(key)
            for key in ["1994_M", "1994_F", "2013_M", "2013_F"]
        },
        "inputs": {
            "1994_population": str(p1994_path),
            "2013_population": str(p2013_path),
            "1994_olimpbase_html": str(html_path),
        },
        "cache_files": {
            "olimpbase_profiles": str(profile_cache_path),
            "wikidata_identity_dob_birthplace": str(wd_cache_path),
        },
    }

    summary_path = outdir / "northern_cohort_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    generated.append(summary_path)

    amendment_path = (
        outdir / "CHESS_PREREGISTRATION_AMENDMENT_V2.md"
    )
    amendment_path.write_text(
        amendment_text(summary),
        encoding="utf-8",
    )
    generated.append(amendment_path)

    # Preserve the exact generator in the Git snapshot.
    generator_copy = (
        outdir / "build_chess_northern_cohorts_v1.py"
    )
    shutil.copy2(Path(__file__).resolve(), generator_copy)
    generated.append(generator_copy)

    print("\n=== NORTHERN COHORT SUMMARY ===")
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\nGenerated:")
    for p in generated:
        print(" ", p.relative_to(repo))

    if args.no_git:
        print("\n--no-git: generated/validated; Git untouched.")
        return

    # Git safety: allow staged files only if they are already inside this
    # amendment output subtree (e.g. from a previously interrupted run).
    prefix = args.output_subdir.replace("\\", "/").strip("/") + "/"

    staged_pre = [
        x.strip().replace("\\", "/")
        for x in run(
            ["git", "diff", "--cached", "--name-only"],
            repo,
        ).splitlines()
        if x.strip()
    ]
    unrelated = [
        x for x in staged_pre
        if not x.startswith(prefix)
    ]
    if unrelated:
        raise RuntimeError(
            "Git index has staged files outside the north-v2 freeze:\n"
            + "\n".join(unrelated)
        )

    if run(
        ["git", "tag", "--list", args.tag],
        repo,
    ).strip():
        raise RuntimeError(
            f"Git tag already exists: {args.tag}"
        )

    add_paths = [
        str(p.relative_to(repo))
        for p in generated
    ]

    run(
        ["git", "add", "--", *add_paths],
        repo,
    )

    staged = {
        x.strip().replace("\\", "/")
        for x in run(
            ["git", "diff", "--cached", "--name-only"],
            repo,
        ).splitlines()
        if x.strip()
    }
    expected = {
        Path(x).as_posix()
        for x in add_paths
    }

    if staged != expected:
        raise RuntimeError(
            "Staged-file safety mismatch.\n"
            f"Expected={sorted(expected)}\n"
            f"Actual={sorted(staged)}"
        )

    run(
        ["git", "commit", "-m", args.commit_message],
        repo,
    )

    run(
        [
            "git", "tag", "-a", args.tag,
            "-m",
            (
                "Freeze Northern-Hemisphere chess cohorts and "
                "preregistration amendment before BaZi reveal"
            ),
        ],
        repo,
    )

    branch = run(
        ["git", "branch", "--show-current"],
        repo,
    ).splitlines()[-1].strip()
    if not branch:
        raise RuntimeError(
            "Detached HEAD; refusing automatic push."
        )

    run(
        ["git", "push", args.remote, branch],
        repo,
    )
    run(
        ["git", "push", args.remote, args.tag],
        repo,
    )

    commit = run(
        ["git", "rev-parse", "HEAD"],
        repo,
    ).splitlines()[-1]

    print("\n=== DONE ===")
    print(f"Commit: {commit}")
    print(f"Tag:    {args.tag}")
    print(f"Branch: {branch}")
    print(
        "Northern-Hemisphere cohorts are frozen before BaZi reveal."
    )


if __name__ == "__main__":
    main()
