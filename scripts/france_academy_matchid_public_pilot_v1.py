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

VERSION = "france-academy-matchid-public-source-only-pilot-v1_3"
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
    """Validated matchID advanced GET /search: name + compact birth-year range.

    API live 2026-10-18: q + birthDate => HTTP400 (mixed simple/complex);
    firstName + lastName + `01/01/YYYY - 31/12/YYYY` => HTTP400 (invalid date);
    firstName + lastName + `01/01/YYYY-31/12/YYYY` => HTTP200.
    All returned identities and dates still require LOCAL independent checks.
    """
    surname, first_name = parsed
    year = int(t["birthyear"])
    if not 1835 <= year <= 1985:
        raise ValueError("Unexpected birthyear outside frozen research support")
    return {"firstName": first_name, "lastName": surname,
            "birthDate": f"01/01/{year:04d}-31/12/{year:04d}",
            "size": "20", "page": "1"}


def unpack_hits(obj):
    """Return the documented response.persons array; None means unparsed.

    A schema/HTTP failure is never equal to an empty search result.
    """
    if not isinstance(obj, dict):
        return None
    response = obj.get("response")
    if isinstance(response, dict) and isinstance(response.get("persons"), list):
        return response["persons"]
    return None


def get_field(mapping, keys):
    if not isinstance(mapping, dict):
        return ""
    for k in keys:
        v = mapping.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            return str(v).strip()
    return ""


def first_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(str(x).strip() for x in value if isinstance(x, str) and x.strip())
    return ""


def parse_api_date(value):
    """Parse only complete calendar dates, no imputed month or day."""
    if isinstance(value, dict):
        value = value.get("value", "")
    return official_date(str(value or ""))[0]


def first_record(person, t, params, queryhash, reshash):
    """Extract the documented Person model: name.first/last, birth.date/death.date."""
    src = person if isinstance(person, dict) else {}
    nm = src.get("name") if isinstance(src.get("name"), dict) else {}
    birth = src.get("birth") if isinstance(src.get("birth"), dict) else {}
    death = src.get("death") if isinstance(src.get("death"), dict) else {}
    lname = first_value(nm.get("last"))
    fname = first_value(nm.get("first"))
    dob = parse_api_date(birth.get("date"))
    death_date = parse_api_date(death.get("date"))
    birthplace = birth.get("location") if isinstance(birth.get("location"), dict) else {}
    city = get_field(birthplace, ("city",))
    record_id = get_field(src, ("id",))
    query_given, query_surname = params["firstName"], params["lastName"]
    same_name = (norm(lname) == norm(query_surname)
                 and bool(norm(fname).split())
                 and norm(fname).split()[0] == norm(query_given).split()[0])
    same_birthyear = bool(dob and dob[:4] == t["birthyear"])
    deathyear_match = bool(death_date and death_date[:4] == t["deathyear"])
    return {
        "cths_person_id": t["id"], "cths_name": t["name"],
        "cths_birthyear": t["birthyear"], "cths_deathyear_candidate": t["deathyear"],
        "cths_exact_dob_candidate": t["dob"],
        "query_lastName": query_surname, "query_firstName": query_given,
        "api_birthdate_claim": dob, "api_deathdate_claim": death_date,
        "api_last_name": lname[:160], "api_first_name": fname[:160],
        "api_birthplace": city[:160], "api_record_id": record_id[:120],
        "name_birthyear_comparison": ("STRICT_NAME_AND_YEAR_CANDIDATE" if same_name and same_birthyear
                                      else "MISMATCH_OR_UNPARSED_NAME_OR_YEAR_MANUAL"),
        "deathyear_comparison": ("DEATHYEAR_AGREES_CTHS" if deathyear_match
                                  else "DEATHYEAR_DISAGREES_OR_UNKNOWN"),
        "dob_comparison": ("API_BIRTHDATE_NONEXACT" if not dob else
                           "CTHS_DOB_MISSING_NEW_LEAD" if not t["dob"] else
                           "API_DOB_AGREES_CTHS" if dob == t["dob"] else
                           "API_DOB_CONFLICTS_CTHS"),
        "evidence_status": "MANUAL_REVIEW_ONLY",
        "query_sha256": queryhash, "response_sha256": reshash,
        "french_academy_full_member_accepted": "0", "exact_dob_accepted": "0",
        "bazi_variables_computed": "0"
    }


def get_api(params: dict, token: str, timeout: float):
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json",
               "User-Agent": "bazi-public-figure-study/1.0 (public historical roster source review)"}
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


def error_preview(e):
    """Preserve a short server explanation, without URLs, headers or tokens."""
    if isinstance(e, urllib.error.HTTPError):
        raw = e.read(2048)
        detail = raw.decode("utf-8", errors="replace")
        if not detail:
            detail = str(e.reason)
    elif isinstance(e, urllib.error.URLError):
        detail = type(e.reason).__name__ + ": " + str(e.reason)
    else:
        detail = type(e).__name__ + ": " + str(e)
    # Avoid line-break escapes or terminal control chars in CSV/log summaries.
    return "".join(ch if ch.isprintable() else " " for ch in detail)[:480]


def write_json_atomic(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(canon_json(value) + b"\n")
    tmp.replace(path)


def run(args, fetch=get_api):
    if not 1 <= args.limit <= 20:
        raise ValueError("--limit must be 1..20; start with --limit 1")
    if args.delay < 1.1:
        raise ValueError("--delay must be >= 1.1 seconds (public search rate <= 1/s)")
    picked = selected_targets(args.cths, args.roles, args.priority, args.ids, args.limit)
    if not picked:
        raise ValueError("No eligible deceased CTHS targets selected")
    sources = {"cths_sha256": sha_file(Path(args.cths)),
               "roles_sha256": sha_file(Path(args.roles))}
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
    new_network_requests = 0
    stopped_early = False
    for t, params in planned:
        qhash = hash_bytes(canon_json({"version": VERSION, "fingerprint": fingerprint,
                                       "cths_person_id": t["id"], "params": params}))
        cache = rawdir / (t["id"] + "_" + qhash[:24] + ".json")
        cache_used = False
        if cache.exists() and not args.refetch:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved.get("version") != VERSION or saved.get("query_sha256") != qhash:
                raise ValueError("Unexpected stale response cache record " + str(cache))
            data = saved.get("response")
            status = saved.get("status", "UNRECOGNIZED_CACHE")
            detail = saved.get("error_preview", "")
            cache_used = True
            print("CACHE", t["id"], t["name"], status)
        else:
            if last_request is not None:
                time.sleep(max(0, args.delay - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            new_network_requests += 1
            detail = ""
            try:
                data = fetch(params, token, args.timeout)
                status = "HTTP_200_JSON"
            except urllib.error.HTTPError as exc:
                status, data = "HTTP_ERROR_" + str(exc.code), None
                detail = error_preview(exc)
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                status, data = "QUERY_FAILED_" + type(exc).__name__, None
                detail = error_preview(exc)
            write_json_atomic(cache, {"version": VERSION, "query_sha256": qhash, "status": status,
                                      "error_preview": detail, "response": data})
            print("SEARCH", t["id"], t["name"], status)
        hits = unpack_hits(data) if data is not None else None
        reshash = hash_bytes(canon_json(data)) if data is not None else ""
        if hits is None:
            finding = "API_RESPONSE_UNPARSED_OR_FAILED"
            if status == "HTTP_200_JSON":
                detail = detail or ("Unrecognized response top-level keys: " +
                                    ",".join(sorted(data.keys())) if isinstance(data, dict)
                                    else "Unrecognized response type")
        elif not hits:
            finding = "ZERO_RESULTS_IN_SEARCH_NOT_PROOF_OF_NO_DEATH"
        else:
            finding = "CANDIDATES_FOUND_NEED_IDENTITY_ADJUDICATION"
            for person in hits[:20]:
                rows.append(first_record(person, t, params, qhash, reshash))
        resp = data.get("response", {}) if isinstance(data, dict) else {}
        declared_total = resp.get("total") if isinstance(resp, dict) else None
        outcomes.append({"cths_person_id": t["id"], "name": t["name"],
                         "query_status": status, "finding": finding,
                         "parsed_hit_count": len(hits) if hits is not None else None,
                         "api_total_claim": declared_total,
                         "first_page_may_be_incomplete": (
                             isinstance(declared_total, (int, float)) and
                             declared_total > len(hits) if hits is not None else ""),
                         "error_preview": detail,
                         "cache_used": "1" if cache_used else "0",
                         "cache_file": str(cache), "query_sha256": qhash,
                         "response_sha256": reshash})
        # First request must succeed and yield recognized structure before expanding;
        # never bombard a service with invalid queries or interpret 4xx as no death.
        if status != "HTTP_200_JSON" or hits is None:
            stopped_early = len(outcomes) < len(planned)
            print("STOP: server error or unrecognized schema; see person_query_status_v1.csv.",
                  file=sys.stderr)
            break
    rows.sort(key=lambda r: (int(r["cths_person_id"]), r["api_last_name"],
                             r["api_first_name"], r["api_birthdate_claim"]))
    write_csv(outdir / "matchid_source_candidates_v1.csv", rows, COLUMNS)
    status_headers = ["cths_person_id", "name", "query_status", "finding",
                      "parsed_hit_count", "api_total_claim", "first_page_may_be_incomplete",
                      "error_preview", "cache_used", "cache_file",
                      "query_sha256", "response_sha256"]
    write_csv(outdir / "person_query_status_v1.csv", outcomes, status_headers)
    stats = Counter(x["finding"] for x in outcomes)
    code_counts = Counter(x["query_status"] for x in outcomes)
    summary = {"version": VERSION, "public_index": "INSEE deceased records indexed by matchID",
               "source_api_doc": "https://deces.matchid.io/deces/api/v1/docs/swagger.json",
               "cths_input_fingerprint": fingerprint, "source_hashes": sources,
               "target_people_selected": len(planned), "target_people_queried_or_cached": len(outcomes),
               "new_network_requests": new_network_requests, "stopped_early": stopped_early,
               "query_status_counts": dict(code_counts),
               "parsed_candidate_rows": len(rows), "finding_counts": dict(stats),
               "unrecognized_response_not_zero_hits": True,
               "final_exact_dob_accepted": 0,
               "final_academy_membership_accepted": 0, "bazi_variables_computed": 0}
    write_json_atomic(outdir / "summary.json", summary)
    print("SUMMARY", json.dumps({"people": len(outcomes), "new_requests": new_network_requests,
                                  "candidate_rows": len(rows),
                                  "statuses": dict(code_counts)}, ensure_ascii=False))
    return summary, rows


def fixtures():
    t = {"id": "112083", "name": "DIEUDONNÉ Jean", "birthyear": "1906",
         "deathyear": "1992", "dob": "", "class": "full_like_only_candidate"}
    parsed = parse_cths_name(t["name"])
    p = search_params(t, parsed)
    assert p["firstName"] == "jean" and p["lastName"] == "dieudonne"
    assert p["birthDate"] == "01/01/1906-31/12/1906" and "q" not in p
    # Use ACTUAL published OpenAPI Person / Result nesting, not invented fields.
    example = {"request": p, "response": {"total": 1, "size": 1, "page": 1,
               "persons": [{"id": "original-record", "name": {"first": ["Jean", "Pierre"], "last": "Dieudonne"},
                            "birth": {"date": "19060701", "location": {"city": "Lille"}},
                            "death": {"date": "19921129"}}]}}
    hits = unpack_hits(example)
    assert hits is not None and len(hits) == 1
    row = first_record(hits[0], t, p, "f" * 64, "a" * 64)
    assert row["api_birthdate_claim"] == "1906-07-01"
    assert row["api_birthplace"] == "Lille"
    assert row["api_first_name"] == "Jean Pierre"
    assert row["name_birthyear_comparison"] == "STRICT_NAME_AND_YEAR_CANDIDATE"
    assert row["deathyear_comparison"] == "DEATHYEAR_AGREES_CTHS"
    assert row["dob_comparison"] == "CTHS_DOB_MISSING_NEW_LEAD"
    assert all(row[k] == "0" for k in ("french_academy_full_member_accepted",
                                      "exact_dob_accepted", "bazi_variables_computed"))
    assert unpack_hits({"hits": []}) is None  # old unsupported assumptions
    assert unpack_hits({"response": {"persons": []}}) == []  # true zero results
    wrong = first_record({"name": {"first": ["Jean"], "last": "Dubost"},
                          "birth": {"date": "19050518"},
                          "death": {"date": "19921129"}}, t, p, "", "")
    assert wrong["name_birthyear_comparison"] != "STRICT_NAME_AND_YEAR_CANDIDATE"

    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        c = base / "cths.csv"
        roles = base / "roles.csv"
        priority = base / "priority.csv"
        write_csv(c, [{"cths_person_id": "112083", "name": "DIEUDONNÉ Jean",
                       "CTHS_roster_year_provisional": "1906",
                       "CTHS_roster_membership_class_provisional": "full_like_only_candidate",
                       "cths_exact_dob_claim_candidate_only": ""}],
                  ["cths_person_id", "name", "CTHS_roster_year_provisional",
                   "CTHS_roster_membership_class_provisional", "cths_exact_dob_claim_candidate_only"])
        write_csv(roles, [{"cths_person_id": "112083", "name_fixed": "DIEUDONNÉ Jean",
                           "membership_note_fixed": "(1906-1992) - membre 1968"}],
                  ["cths_person_id", "name_fixed", "membership_note_fixed"])
        write_csv(priority, [{"cths_person_id": "112083", "academy_member_only_1989": "1"}],
                  ["cths_person_id", "academy_member_only_1989"])
        test = argparse.Namespace(cths=str(c), roles=str(roles), priority=str(priority),
                                  ids="", limit=1, delay=1.3, timeout=5, dry_run=False,
                                  refetch=False, out=str(base / "out"))
        calls = []
        def success(params, token, timeout):
            calls.append(params)
            return example
        summary, records = run(test, fetch=success)
        assert len(calls) == 1 and len(records) == 1 and not summary["stopped_early"]
        assert summary["final_exact_dob_accepted"] == 0
        summary2, records2 = run(test, fetch=lambda *_: (_ for _ in ()).throw(AssertionError("cache reused")))
        assert summary2["new_network_requests"] == 0 and len(records2) == 1
        # HTTP 422 should write a source diagnostic, stop and never produce false negatives.
        test.out = str(base / "error_out")
        def bad_request(*_):
            import io
            raise urllib.error.HTTPError(ENDPOINT, 422, "Unprocessable Entity", {},
                                         io.BytesIO(b'{"msg":"Invalid birthDate query"}'))
        summary3, records3 = run(test, fetch=bad_request)
        assert summary3["query_status_counts"] == {"HTTP_ERROR_422": 1}
        assert records3 == []
        with (Path(test.out) / "person_query_status_v1.csv").open(encoding="utf-8-sig", newline="") as f:
            audit = list(csv.DictReader(f))
        assert "Invalid birthDate query" in audit[0]["error_preview"]
        assert audit[0]["finding"] == "API_RESPONSE_UNPARSED_OR_FAILED"
    print("PASS: matchID official nested schema, source-only matching, error diagnostics, cache and zero acceptance")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-check", action="store_true")
    ap.add_argument("--cths", default=DEFAULT_CTHS)
    ap.add_argument("--roles", default=DEFAULT_ROLES)
    ap.add_argument("--priority", default=DEFAULT_PRIORITY)
    ap.add_argument("--ids", default="",
                    help="Comma-separated CTHS IDs; default starts with 1989 directory leads")
    ap.add_argument("--limit", type=int, default=1,
                    help="Default 1 until first real 200 JSON + recognized schema is verified")
    ap.add_argument("--delay", type=float, default=1.3)
    ap.add_argument("--timeout", type=float, default=25)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print exact query with ZERO network calls")
    ap.add_argument("--refetch", action="store_true",
                    help="Explicitly refetch cached query, including previous failures")
    args = ap.parse_args()
    if args.fixture_check:
        fixtures()
    else:
        run(args)


if __name__ == "__main__":
    main()
