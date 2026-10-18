#!/usr/bin/env python3
"""Find France Academy *candidate identities* from Wikidata, not accepted full membership.

Source pathways:
  P6282 (French Academy of Sciences official profile slug, mixed member types)
  P463 = Q188771 (self-described membership; may include foreign/corresponding)
Does not accept day-precision DOB or modify final institutional roster.
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
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import requests

VERSION = "france-academy-wikidata-identity-candidates-v1"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "bazi-public-figure-study/1.0 (academic noncommercial roster discovery; research audit; contact via github.com/agenhcx/bazi-public-figure-study)"
QIDS = re.compile(r"^Q[1-9][0-9]*$")
QUERY = {
    "official_id_P6282": """
SELECT ?person ?memberId ?dob ?nameFr ?nameEn WHERE {
  ?person <http://www.wikidata.org/prop/direct/P6282> ?memberId .
  OPTIONAL { ?person <http://www.wikidata.org/prop/direct/P569> ?dob . }
  OPTIONAL { ?person <http://www.w3.org/2000/01/rdf-schema#label> ?nameFr .
             FILTER(LANG(?nameFr) = "fr") }
  OPTIONAL { ?person <http://www.w3.org/2000/01/rdf-schema#label> ?nameEn .
             FILTER(LANG(?nameEn) = "en") }
} LIMIT 10000
""",
    "membership_P463_Q188771": """
SELECT ?person ?dob ?nameFr ?nameEn WHERE {
  ?person <http://www.wikidata.org/prop/direct/P463> <http://www.wikidata.org/entity/Q188771> .
  OPTIONAL { ?person <http://www.wikidata.org/prop/direct/P569> ?dob . }
  OPTIONAL { ?person <http://www.w3.org/2000/01/rdf-schema#label> ?nameFr .
             FILTER(LANG(?nameFr) = "fr") }
  OPTIONAL { ?person <http://www.w3.org/2000/01/rdf-schema#label> ?nameEn .
             FILTER(LANG(?nameEn) = "en") }
} LIMIT 10000
""",
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def get_rows(session: requests.Session, label: str, query: str, output: Path, timeout: int, retries: int) -> tuple[list[dict], dict]:
    (output / "raw_sparql").mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(ENDPOINT, params={"query": query, "format": "json"},
                                   headers={"Accept": "application/sparql-results+json"},
                                   timeout=timeout)
            if response.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"retryable_status_{response.status_code}")
            response.raise_for_status()
            if len(response.content) > 32_000_000:
                raise RuntimeError("SPARQL JSON too large")
            data = response.json()
            bindings = data["results"]["bindings"]
            (output / "raw_sparql" / (label + ".json")).write_bytes(response.content)
            return bindings, {"source": label, "request_url": response.url[:200],
                              "http_status": response.status_code, "bindings": len(bindings),
                              "response_sha256": sha(response.content), "attempt": attempt}
        except (ValueError, KeyError, requests.RequestException, RuntimeError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(min(2 * attempt, 8))
    return [], {"source": label, "error": str(last_exc)[:600], "bindings": 0}


def field(row: dict, key: str) -> str:
    return str(row.get(key, {}).get("value", "") or "").strip()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/france_academy_wikidata_candidate_discovery_v1")
    ap.add_argument("--timeout", type=int, default=65)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    people: dict[str, dict] = defaultdict(lambda: {"slugs": set(), "dob_claims": set(),
                                                    "name_fr": set(), "name_en": set(),
                                                    "routes": set()})
    source_audit = []

    for label, query in QUERY.items():
        bindings, audit = get_rows(session, label, query, out, args.timeout, args.retries)
        source_audit.append(audit)
        print(json.dumps(audit, ensure_ascii=False), flush=True)
        for b in bindings:
            entity_uri = field(b, "person")
            qid = entity_uri.rsplit("/", 1)[-1]
            if not QIDS.match(qid):
                continue
            person = people[qid]
            person["routes"].add(label)
            for key, setkey in (("memberId", "slugs"), ("dob", "dob_claims"),
                                ("nameFr", "name_fr"), ("nameEn", "name_en")):
                value = field(b, key)
                if value:
                    person[setkey].add(value)

    recs = []
    for qid in sorted(people, key=lambda x: int(x[1:])):
        d = people[qid]
        name_fr = " | ".join(sorted(d["name_fr"]))
        name_en = " | ".join(sorted(d["name_en"]))
        slugs = sorted(d["slugs"])
        dob = sorted(d["dob_claims"])
        year_candidates = sorted({int(x[:4]) for x in dob if re.match(r"^\d{4}-\d{2}-\d{2}", x)})
        # Not safe for scientific time or date matching: Wikidata qualifiers, provenance and calendars need review.
        recs.append({
            "qid": qid,
            "name_candidate": name_fr or name_en or qid,
            "name_fr": name_fr,
            "name_en": name_en,
            "official_id_claims": " | ".join(slugs),
            "official_profile_urls_unverified": " | ".join("https://www.academie-sciences.fr/" + quote(s) for s in slugs),
            "wikidata_birthdate_claims_unverified": " | ".join(dob),
            "birth_year_candidates": " | ".join(map(str, year_candidates)),
            "discovery_routes": " | ".join(sorted(d["routes"])),
            "source_url": "https://www.wikidata.org/wiki/" + qid,
            "member_class": "UNRESOLVED",
            "election_year": "",
            "full_member_accepted": 0,
            "exact_dob_accepted": 0,
            "remarks": "Discovery lead only: P6282/P463 cannot prove French academy full status or source-certified DOB",
        })
    fields = [
        "qid", "name_candidate", "name_fr", "name_en",
        "official_id_claims", "official_profile_urls_unverified",
        "wikidata_birthdate_claims_unverified", "birth_year_candidates", "discovery_routes",
        "source_url", "member_class", "election_year", "full_member_accepted", "exact_dob_accepted", "remarks"
    ]
    write_csv(out / "candidate_people_v1.csv", recs, fields)
    write_csv(out / "source_request_audit_v1.csv", source_audit,
              ["source", "request_url", "http_status", "bindings", "response_sha256", "attempt", "error"])
    counts = Counter(tuple(x["discovery_routes"].split(" | ")) for x in recs)
    report = {
        "version": VERSION,
        "snapshot_date_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "endpoint": ENDPOINT,
        "requests": source_audit,
        "candidate_people": len(recs),
        "route_intersection_counts": {" + ".join(k): v for k, v in counts.items()},
        "any_official_id_claim": sum(bool(x["official_id_claims"]) for x in recs),
        "any_birthyear_claim": sum(bool(x["birth_year_candidates"]) for x in recs),
        "accepted_full_members": 0,
        "accepted_exact_dobs": 0,
        "historical_roster_complete": False,
        "final_roster_frozen": False,
        "bazi_variables_computed": 0,
        "read_me": "Candidate discovery only. No full member, exact DOB, election year or historical status was verified by official sources.",
    }
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if args.strict and not recs:
        raise SystemExit("Both Wikidata discovery routes unavailable or empty: see request audit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
