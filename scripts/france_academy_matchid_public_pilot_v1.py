#!/usr/bin/env python3
"""Small, public, rate-limited matchID/INSEE death index pilot (candidate evidence only).

Never certifies identity, exact DOB, or French Academy full-member status.
No token stored in source, stdout, or outputs. Python 3.10+, standard library.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from france_academy_insee_death_crosswalk_v1 import (
    load_targets, parse_cths_name, norm, official_date, sha_file, write_csv
)

VERSION = "france-academy-matchid-public-source-only-pilot-v1"
ENDPOINT = "https://deces.matchid.io/deces/api/v1/search"
DEFAULT_CTHS = "data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv"
DEFAULT_ROLES = "data/france_academy_cths_society_role_repair_v1_1/cths_academy_membership_candidates_corrected_v1_1.csv"
DEFAULT_PRIORITY = "data/france_academy_cths_historical_source_citation_audit_v1/institutional_directory_citation_review_queue_v1.csv"
DEFAULT_OUT = "local_runs/france_academy_matchid_public_pilot_v1"
COLUMNS = [
    "cths_person_id", "cths_name", "cths_birthyear", "cths_deathyear_candidate",
    "cths_exact_dob_candidate", "query_lastName", "query_firstName",
    "api_birthdate_claim", "api_deathdate_claim", "api_last_name",
    "api_first_name", "api_birthplace", "api_record_id",
    "name_birthyear_comparison", "deathyear_comparison", "dob_comparison",
    "evidence_status", "query_sha256", "response_sha256",
    "french_academy_full_member_accepted", "exact_dob_accepted",
    "bazi_variables_computed"
]


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def selected_targets(cths: str, roles: str, priority: str, ids: str, limit: int):
    targets, _keys, _invalid = load_targets(cths, roles)
    if ids:
        ordered = [part.strip() for part in ids.split(",") if part.strip()]
        if len(ordered) != len(set(ordered)):
            raise ValueError("Duplicate ID in --ids")
    else:
        with Path(priority).open(encoding="utf-8-sig", newline="") as f:
            ordered = [r["cths_person_id"] for r in csv.DictReader(f)
                       if r.get("academy_member_only_1989") == "1"]
        # Examine original CTHS DOB gaps first, not BaZi results or membership outcomes.
        ordered.sort(key=lambda i: (bool(targets[i]["dob"]), int(i)))
    picked = []
    for pid in ordered:
        if pid not in targets:
            raise ValueError("Unknown CTHS target person ID: " + pid)
        t = targets[pid]
        if not re.fullmatch(r"\d{4}", t["birthyear"]):
            continue
        if not t["deathyear"]:
            # Death-index search is not proof a living or unverified person is deceased.
            continue
        parsed = parse_cths_name(t["name"])
        if parsed is None:
            continue
        picked.append((t, parsed))
        if len(picked) == limit:
            break
    return picked


def search_params(t: dict, parsed: tuple[str, str]):
    surname, first_name = parsed
    year = int(t["birthyear"])
    if not 1835 <= year <= 1985:
        raise ValueError("Unexpected birthyear outside frozen research support")
    return {
        "firstName": first_name, "lastName": surname,
        "birthDate": f"01/01/{year:04d} - 31/12/{year:04d}",
        "size": "10", "fuzzy": "false"
    }


def unpack_hits(obj):
    """Handle common API result envelope shapes; unknown shape is NOT zero hits."""
    if isinstance(obj, list):
        return obj
    if not isinstance(obj, dict):
        return None
    for k in ("results", "result", "hits", "items", "matches", "data", "persons"):
        val = obj.get(k)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            for nested in ("hits", "results", "items", "data", "matches"):
                if isinstance(val.get(nested), list):
                    return val[nested]
    return None


def value(mapping, keys):
    for k in keys:
        v = mapping.get(k)
        if isinstance(v, (str, int)) and str(v).strip():
            return str(v).strip()
    return ""


def unwrap(hit):
    if not isinstance(hit, dict):
        return {}
    for k in ("_source", "person", "record", "identity"):
        if isinstance(hit.get(k), dict):
            return hit[k]
    source = hit.get("source")
    if isinstance(source, dict):
        return source
    return hit


def flat_date(raw):
    if isinstance(raw, dict):
        raw = raw.get("value", "")
    return official_date(str(raw or ""))[0]


def first_record(hit, t, params, queryhash, reshash):
    src = unwrap(hit)
    birth = flat_date(src.get("birthDate", src.get("dateNaissance", "")))
    death = flat_date(src.get("deathDate", src.get("dateDeces", "")))
    lname = value(src, ("lastName", "lastname", "nom", "familyName"))
    fname = value(src, ("firstName", "firstname", "prenoms", "prenom"))
    display_name = src.get("name")
    if isinstance(display_name, dict):
        lname = lname or value(display_name, ("lastName", "last", "family"))
        fname = fname or value(display_name, ("firstName", "first", "given"))
    record_id = value(src, ("id", "_id", "personId")) or value(hit, ("_id", "id"))
    birthcity = value(src, ("birthCity", "birthPlace", "placeOfBirth"))
    if not birthcity and isinstance(src.get("birth"), dict):
        birthcity = value(src["birth"], ("city", "location"))
    same_name = norm(lname) == norm(params["lastName"]) and norm(fname).split()[:1] == norm(params["firstName"]).split()[:1]
    same_birthyear = bool(birth and birth[:4] == t["birthyear"])
    deathyear_match = bool(death and death[:4] == t["deathyear"])
    name_birthyear = ("STRICT_NAME_AND_YEAR_CANDIDATE" if same_name and same_birthyear else
                      "MISMATCH_OR_UNPARSED_NAME_OR_YEAR_MANUAL")
    death_comparison = ("DEATHYEAR_AGREES_CTHS" if deathyear_match else "DEATHYEAR_DISAGREES_OR_UNKNOWN")
    dob_comparison = ("API_BIRTHDATE_NONEXACT" if not birth else
                      "CTHS_DOB_MISSING_NEW_LEAD" if not t["dob"] else
                      "API_DOB_AGREES_CTHS" if birth == t["dob"] else "API_DOB_CONFLICTS_CTHS")
    return {
        "cths_person_id": t["id"], "cths_name": t["name"],
        "cths_birthyear": t["birthyear"], "cths_deathyear_candidate": t["deathyear"],
        "cths_exact_dob_candidate": t["dob"],
        "query_lastName": params["lastName"], "query_firstName": params["firstName"],
        "api_birthdate_claim": birth, "api_deathdate_claim": death,
        "api_last_name": lname, "api_first_name": fname,
        "api_birthplace": birthcity[:160], "api_record_id": record_id[:100],
        "name_birthyear_comparison": name_birthyear, "deathyear_comparison": death_comparison,
        "dob_comparison": dob_comparison,
        "evidence_status": "MANUAL_REVIEW_ONLY",
        "query_sha256": queryhash, "response_sha256": reshash,
        "french_academy_full_member_accepted": "0", "exact_dob_accepted": "0",
        "bazi_variables_computed": "0"
    }


def get_api(params: dict, token: str, timeout: float) -> dict:
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json", "User-Agent": "bazi-public-figure-study/1.0 (public historical roster source review)"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("MatchID search response unexpectedly large")
        if response.status != 200:
            raise ValueError("Unexpected HTTP status " + str(response.status))
        return json.loads(raw)


def write_json_atomic(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(canon_json(value) + b"\n")
    tmp.replace(path)


def run(args, fetch=get_api):
    if not 1 <= args.limit <= 20:
        raise ValueError("--limit must be 1..20; start small")
    if args.delay < 1.1:
        raise ValueError("--delay must be >= 1.1 seconds (public search rate limit <= 1/s)")
    picked = selected_targets(args.cths, args.roles, args.priority, args.ids, args.limit)
    if not picked:
        raise ValueError("No eligible deceased CTHS targets selected; check IDs and source files")
    sources = {
        "cths_sha256": sha_file(Path(args.cths)),
        "roles_sha256": sha_file(Path(args.roles)),
    }
    if not args.ids:
        sources["priority_sha256"] = sha_file(Path(args.priority))
    fingerprint = hash_bytes(canon_json(sources))
    planned = [(t, search_params(t, parsed)) for t, parsed in picked]
    if args.dry_run:
        print(json.dumps({"selected": [{"id": t["id"], "name": t["name"], "birthyear": t["birthyear"],
                                        "deathyear_candidate": t["deathyear"], "query": params}
                                       for t, params in planned], "network_requests": 0},
                         ensure_ascii=False, indent=2))
        return
    token = os.environ.get("MATCHID_API_TOKEN", "").strip()
    outdir = Path(args.out)
    rawdir = outdir / "_responses"
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    outcomes = []
    last_request = None
    for t, params in planned:
        qhash = hash_bytes(canon_json({"version": VERSION, "fingerprint": fingerprint, "cths_person_id": t["id"], "params": params}))
        cache = rawdir / (t["id"] + "_" + qhash[:24] + ".json")
        if cache.exists() and not args.refetch:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            data = saved.get("response")
            status = saved.get("status", "UNRECOGNIZED_CACHE")
            print("CACHE", t["id"], t["name"], status)
        else:
            if last_request is not None:
                time.sleep(max(0, args.delay - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            try:
                data = fetch(params, token, args.timeout)
                status = "HTTP_200_JSON"
            except urllib.error.HTTPError as exc:
                # Never silently treat a failed query as a person not existing.
                status, data = "HTTP_ERROR_" + str(exc.code), None
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                status, data = "QUERY_FAILED_" + type(exc).__name__, None
            write_json_atomic(cache, {"version": VERSION, "query_sha256": qhash, "status": status, "response": data})
            print("SEARCH", t["id"], t["name"], status)
        hits = unpack_hits(data) if data is not None else None
        reshash = hash_bytes(canon_json(data)) if data is not None else ""
        if hits is None:
            finding = "API_RESPONSE_UNPARSED_OR_FAILED"
        elif not hits:
            finding = "ZERO_RESULTS_IN_SEARCH_NOT_PROOF_OF_NO_DEATH"
        else:
            finding = "CANDIDATES_FOUND_NEED_IDENTITY_ADJUDICATION"
            for item in hits[:20]:
                rows.append(first_record(item, t, params, qhash, reshash))
        outcomes.append({"cths_person_id": t["id"], "name": t["name"],
                         "query_status": status, "finding": finding,
                         "parsed_hit_count": len(hits) if hits is not None else None,
                         "cache_file": str(cache), "query_sha256": qhash, "response_sha256": reshash})
        if status in ("HTTP_ERROR_429", "HTTP_ERROR_401", "HTTP_ERROR_403"):
            print("STOP: authentication/rate-limit issue; do not retry continuously", file=sys.stderr)
            break
    rows.sort(key=lambda r: (int(r["cths_person_id"]), r["api_last_name"], r["api_first_name"], r["api_birthdate_claim"]))
    write_csv(outdir / "matchid_source_candidates_v1.csv", rows, COLUMNS)
    with (outdir / "person_query_status_v1.csv").open("w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["cths_person_id", "name", "query_status", "finding", "parsed_hit_count", "cache_file", "query_sha256", "response_sha256"])
        wr.writeheader()
        wr.writerows(outcomes)
    stats = Counter(x["finding"] for x in outcomes)
    summary = {"version": VERSION, "public_index": "INSEE deceased records indexed by matchID",
               "source_api_doc": "https://deces.matchid.io/deces/api/v1/docs/swagger.json",
               "cths_input_fingerprint": fingerprint, "source_hashes": sources,
               "target_people_selected": len(planned), "target_people_queried_or_cached": len(outcomes),
               "parsed_candidate_rows": len(rows), "finding_counts": dict(stats),
               "unrecognized_response_not_zero_hits": True, "final_exact_dob_accepted": 0,
               "final_academy_membership_accepted": 0, "bazi_variables_computed": 0}
    write_json_atomic(outdir / "summary.json", summary)
    print("SUMMARY", json.dumps({"people": len(outcomes), "candidate_rows": len(rows), "findings": dict(stats)}, ensure_ascii=False))
    return summary, rows


def fixtures():
    t = {"id": "112083", "name": "DIEUDONNÉ Jean", "birthyear": "1906", "deathyear": "1992", "dob": "", "class": "full_like_only_candidate"}
    parsed = parse_cths_name(t["name"])
    p = search_params(t, parsed)
    assert p["birthDate"] == "01/01/1906 - 31/12/1906"
    fake = {"hits": {"hits": [{"_id": "a", "_source": {"firstName": "Jean", "lastName": "Dieudonne",
              "birthDate": "19060701", "deathDate": "19921129", "birthCity": "Lille"}}]}}
    hits = unpack_hits(fake)
    assert hits is not None and len(hits) == 1
    row = first_record(hits[0], t, p, "f" * 64, "a" * 64)
    assert row["api_birthdate_claim"] == "1906-07-01"
    assert row["name_birthyear_comparison"] == "STRICT_NAME_AND_YEAR_CANDIDATE"
    assert row["deathyear_comparison"] == "DEATHYEAR_AGREES_CTHS"
    assert row["dob_comparison"] == "CTHS_DOB_MISSING_NEW_LEAD"
    assert all(row[k] == "0" for k in ("french_academy_full_member_accepted", "exact_dob_accepted", "bazi_variables_computed"))
    assert unpack_hits({"unexpected": [{"person": "X"}]}) is None
    assert unpack_hits({"results": []}) == []
    wrong = first_record({"_source": {"firstName": "Jean", "lastName": "Dubost", "birthDate": "19050518", "deathDate": "19921129"}}, t, p, "", "")
    assert wrong["name_birthyear_comparison"] != "STRICT_NAME_AND_YEAR_CANDIDATE"
    print("PASS: matchID synthetic schema, strict identity/year checks, API failures not negative evidence, zero accepted dates/memberships")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-check", action="store_true")
    ap.add_argument("--cths", default=DEFAULT_CTHS)
    ap.add_argument("--roles", default=DEFAULT_ROLES)
    ap.add_argument("--priority", default=DEFAULT_PRIORITY)
    ap.add_argument("--ids", default="", help="Comma-separated CTHS IDs; default prioritizes 17 1989 member-directory citation leads")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--delay", type=float, default=1.3)
    ap.add_argument("--timeout", type=float, default=25)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true", help="Print exact search plan with ZERO network calls")
    ap.add_argument("--refetch", action="store_true", help="Explicitly refetch previously cached queries")
    args = ap.parse_args()
    if args.fixture_check:
        fixtures()
    else:
        run(args)


if __name__ == "__main__":
    main()
