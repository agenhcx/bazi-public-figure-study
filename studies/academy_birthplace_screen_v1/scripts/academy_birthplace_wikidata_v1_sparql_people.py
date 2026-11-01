#!/usr/bin/env python3
"""Read-only P19 -> direct Earth P625 supplement; no name matching or DOB edits."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
QID = re.compile(r"Q[1-9][0-9]*\Z")
PID = re.compile(r"P[1-9][0-9]*\Z")
# Broad place types require geographic extent, not a representative point.
BROAD_PLACE_TYPES = {
    "Q6256", "Q3624078", "Q7275", "Q3024240", "Q3336843", "Q15634554",
    "Q161243", "Q1048835", "Q5107", "Q35657", "Q10864048", "Q13220204",
    "Q82794", "Q4835091", "Q28575", "Q34876", "Q149621", "Q33837", "Q23442",
}
USER_AGENT = "AcademyBirthplaceScreen/1.0 (public research; github.com/agenhcx/bazi-public-figure-study)"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(json_bytes(value))
    temporary.replace(path)


class FetchFailure(Exception):
    pass


class Client:
    def __init__(self, cache, interval=0.35, retries=3, timeout=45, max_requests=600, max_runtime_seconds=1500,
                 person_sparql=False, person_sparql_batch_size=200):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.interval = interval
        self.retries = retries
        self.timeout = timeout
        self.max_requests = max_requests
        self.request_count = 0
        self.last_request = 0.0
        self.deadline = time.monotonic() + max_runtime_seconds
        self.person_sparql = person_sparql
        self.person_sparql_batch_size = person_sparql_batch_size

    def request_json(self, url):
        key = sha(url.encode("utf-8"))
        raw_file = self.cache / (key + ".body.json")
        meta_file = self.cache / (key + ".meta.json")
        if raw_file.exists() and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                body = raw_file.read_bytes()
                if meta.get("ok") and meta.get("url") == url and sha(body) == meta.get("response_sha256"):
                    return json.loads(body), meta
            except (OSError, ValueError, TypeError, AttributeError):
                pass  # Corrupt cache is not accepted as evidence; retry the original request.
        last_error = "request_not_attempted"
        for attempt in range(self.retries + 1):
            if self.request_count >= self.max_requests:
                raise FetchFailure("request_budget_exhausted")
            if time.monotonic() >= self.deadline:
                raise FetchFailure("runtime_budget_exhausted")
            pause = self.interval - (time.monotonic() - self.last_request)
            if pause > 0:
                time.sleep(pause)
            self.request_count += 1
            self.last_request = time.monotonic()
            retry_after = None
            try:
                req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                with urlopen(req, timeout=min(self.timeout, max(0.01, self.deadline - time.monotonic()))) as response:
                    body = response.read()
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise FetchFailure("response_is_not_object")
                if data.get("error"):
                    code = str(data["error"].get("code", "api_error"))
                    if code not in {"maxlag", "ratelimited", "readonly"}:
                        raise FetchFailure("api_error:" + code)
                    last_error = "api_error:" + code
                else:
                    meta = {"ok": True, "url": url, "retrieved_utc": utc_now(),
                            "response_sha256": sha(body), "response_bytes": len(body),
                            "raw_response_file": raw_file.name}
                    raw_file.write_bytes(body)
                    write_json(meta_file, meta)
                    return data, meta
            except HTTPError as exc:
                last_error = "http_error:" + str(exc.code)
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise FetchFailure(last_error) from exc
                value = exc.headers.get("Retry-After") if exc.headers else None
                if value:
                    try:
                        retry_after = float(value)
                    except ValueError:
                        try:
                            retry_after = max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
                        except (ValueError, TypeError, OverflowError):
                            retry_after = None
            except (URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = type(exc).__name__ + ":" + str(exc)[:250]
            if attempt == self.retries:
                break
            # Do not retry before a long server-requested delay; leave records unknown instead.
            if retry_after is not None and retry_after > 60:
                raise FetchFailure(last_error + ":retry_after_deferred")
            wait_seconds = max(min(2 ** (attempt + 1), 20), retry_after or 0)
            if time.monotonic() + wait_seconds >= self.deadline:
                raise FetchFailure("runtime_budget_exhausted")
            time.sleep(wait_seconds)
        raise FetchFailure(last_error)

    def entities(self, qids):
        result, evidence, errors = {}, {}, {}
        ordered = sorted(set(qids), key=lambda q: int(q[1:]))
        for start in range(0, len(ordered), 50):
            batch = ordered[start:start + 50]
            url = API + "?" + urlencode({"action": "wbgetentities", "format": "json", "ids": "|".join(batch),
                                        "props": "claims|labels", "languages": "en", "languagefallback": "1", "maxlag": "5"})
            try:
                payload, meta = self.request_json(url)
                entities = payload.get("entities")
                if not isinstance(entities, dict):
                    raise FetchFailure("malformed_entities_response")
                for qid in batch:
                    entity = entities.get(qid)
                    if not isinstance(entity, dict) or "missing" in entity:
                        errors[qid] = "entity_missing"
                    else:
                        result[qid], evidence[qid] = entity, meta
            except FetchFailure as exc:
                errors.update({qid: str(exc) for qid in batch})
            print(json.dumps({"stage": "entities", "processed": min(start + 50, len(ordered)),
                              "total": len(ordered), "failed": len(errors)}, ensure_ascii=False), flush=True)
        return result, evidence, errors

    def people(self, qids):
        if not self.person_sparql:
            return self.entities(qids)
        result, evidence, errors = {}, {}, {}
        ordered = sorted(set(qids), key=lambda q: int(q[1:]))
        size = self.person_sparql_batch_size
        for start in range(0, len(ordered), size):
            batch = ordered[start:start + size]
            query = person_p19_query(batch)
            url = SPARQL + "?" + urlencode({"query": query, "format": "json"})
            try:
                payload, meta = self.request_json(url)
                entities = parse_person_p19_response(batch, payload)
                result.update(entities)
                evidence.update({qid: meta for qid in entities})
            except FetchFailure as exc:
                errors.update({qid: str(exc) for qid in batch})
            print(json.dumps({"stage": "people_P19_sparql", "processed": min(start + size, len(ordered)),
                              "total": len(ordered), "failed": len(errors)}, ensure_ascii=False), flush=True)
        return result, evidence, errors


def person_p19_query(qids):
    if not qids or any(not QID.fullmatch(q) for q in qids):
        raise ValueError("SPARQL person seeds must be existing QIDs")
    values = " ".join("wd:" + q for q in qids)
    # No label, date, nationality or name is queried. OPTIONAL preserves absent P19s.
    return """SELECT ?person ?statement ?rank ?birthplace ?isNoValue WHERE {
      VALUES ?person { """ + values + """ }
      OPTIONAL {
        ?person p:P19 ?statement .
        OPTIONAL { ?statement wikibase:rank ?rank . }
        OPTIONAL { ?statement ps:P19 ?birthplace . }
        BIND(EXISTS { ?statement a wdno:P19 } AS ?isNoValue)
      }
    }"""


def parse_person_p19_response(qids, payload):
    bindings = payload.get("results", {}).get("bindings")
    if not isinstance(bindings, list):
        raise FetchFailure("malformed_person_sparql_response")
    requested = set(qids)
    # A VALUES solution may also describe a nonexistent QID with no P19. Both are
    # unresolved geographic records; presence in this dictionary is not identity approval.
    entities = {q: {"id": q, "claims": {"P19": []}, "labels": {}} for q in qids}
    seen = set()
    ranks = {"PreferredRank": "preferred", "NormalRank": "normal", "DeprecatedRank": "deprecated"}
    for binding in bindings:
        person = binding.get("person", {}).get("value", "").rsplit("/", 1)[-1]
        if person not in requested:
            raise FetchFailure("unexpected_person_in_sparql_response")
        statement_uri = binding.get("statement", {}).get("value")
        if not statement_uri:
            continue
        rank_uri = binding.get("rank", {}).get("value", "")
        rank = ranks.get(rank_uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1], "unresolved")
        birthplace = binding.get("birthplace", {})
        value = birthplace.get("value", "")
        no_value = binding.get("isNoValue", {}).get("value", "").lower() in {"true", "1"}
        candidate_qid = value.rsplit("/", 1)[-1]
        if no_value:
            snak = {"snaktype": "novalue"}
        elif birthplace.get("type") == "bnode" or "/.well-known/genid/" in value:
            snak = {"snaktype": "somevalue"}
        elif birthplace.get("type") == "uri" and QID.fullmatch(candidate_qid) and value.startswith(("http://www.wikidata.org/entity/", "https://www.wikidata.org/entity/")):
            snak = {"snaktype": "value", "datavalue": {"value": {"id": candidate_qid}}}
        else:
            snak = {"snaktype": "unresolved"}
        snak["property"] = "P19"
        identity = (person, statement_uri, rank, snak["snaktype"], value)
        if identity in seen:
            continue
        seen.add(identity)
        guid = statement_uri.rsplit("/", 1)[-1].replace("-", "$", 1)
        # Missing/unrecognised ranks must never silently count as normal.
        if rank == "unresolved":
            snak = {"property": "P19", "snaktype": "unresolved_rank"}
        entities[person]["claims"]["P19"].append({"id": guid, "statement_uri": statement_uri,
                "rank": rank, "mainsnak": snak, "sparql_rank_uri": rank_uri})
    return entities


def active_claims(entity, prop):
    return [c for c in entity.get("claims", {}).get(prop, []) if c.get("rank") != "deprecated"]


def item_values(entity, prop):
    out = []
    for claim in active_claims(entity, prop):
        snak = claim.get("mainsnak", {})
        value = snak.get("datavalue", {}).get("value")
        if snak.get("snaktype") == "value" and isinstance(value, dict) and QID.fullmatch(str(value.get("id", ""))):
            out.append({"qid": value["id"], "claim_id": claim.get("id"), "rank": claim.get("rank"),
                        "reference_count": len(claim.get("references", []))})
    return out


def entity_label(entity):
    labels = entity.get("labels", {})
    value = labels.get("en") or next(iter(labels.values()), {})
    return value.get("value", "") if isinstance(value, dict) else ""


def resolve_external_seeds(seeds, client):
    """Exact external-ID join only; no labels, dates, or names participate."""
    required = defaultdict(set)
    for seed in seeds:
        prop, external_id = seed.get("external_id_property"), seed.get("external_id")
        if not seed.get("qid") and prop and external_id and PID.fullmatch(str(prop)):
            required[prop].add(str(external_id))
    matches, provenance, errors = {}, {}, {}
    for prop, ids in required.items():
        query = "SELECT ?person ?externalId WHERE { ?person wdt:" + prop + " ?externalId. }"
        url = SPARQL + "?" + urlencode({"query": query, "format": "json"})
        try:
            data, meta = client.request_json(url)
            bindings = data.get("results", {}).get("bindings")
            if not isinstance(bindings, list):
                raise FetchFailure("malformed_external_id_response")
            observed = defaultdict(set)
            for binding in bindings:
                value = binding.get("externalId", {}).get("value")
                qid = binding.get("person", {}).get("value", "").rsplit("/", 1)[-1]
                if value in ids and QID.fullmatch(qid):
                    observed[value].add(qid)
            reverse = defaultdict(set)
            for external_id, qids in observed.items():
                for qid in qids:
                    reverse[qid].add(external_id)
            for external_id in ids:
                key = (prop, external_id)
                qids = observed[external_id]
                if len(qids) != 1:
                    errors[key] = "external_id_no_match" if not qids else "external_id_multiple_qids"
                    continue
                qid = next(iter(qids))
                if len(reverse[qid]) != 1:
                    errors[key] = "qid_multiple_input_external_ids"
                    continue
                matches[key] = qid
                provenance[key] = {"method": "exact_external_id_unique_one_to_one", "property": prop,
                                   "external_id": external_id, "source_grade": "S3", "response": meta}
        except FetchFailure as exc:
            for external_id in ids:
                errors[(prop, external_id)] = "external_id_query_failed:" + str(exc)
    return matches, provenance, errors


def coordinate_values(entity):
    coordinates, skipped = [], []
    for claim in active_claims(entity, "P625"):
        snak = claim.get("mainsnak", {})
        value = snak.get("datavalue", {}).get("value")
        if snak.get("snaktype") != "value" or not isinstance(value, dict):
            skipped.append("non_value_coordinate")
            continue
        if value.get("globe") not in {"http://www.wikidata.org/entity/Q2", "https://www.wikidata.org/entity/Q2"}:
            skipped.append("non_earth_or_missing_globe")
            continue
        lat, lon = value.get("latitude"), value.get("longitude")
        if isinstance(lat, bool) or isinstance(lon, bool) or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            skipped.append("non_numeric_coordinate")
            continue
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            skipped.append("out_of_range_coordinate")
            continue
        coordinates.append({"lat": lat, "lon": lon, "precision": value.get("precision"),
                            "globe": value["globe"], "claim_id": claim.get("id"), "rank": claim.get("rank"),
                            "reference_count": len(claim.get("references", []))})
    return coordinates, skipped


def screen(seeds, client):
    external_matches, external_provenance, external_errors = resolve_external_seeds(seeds, client)
    resolved = []
    for seed in seeds:
        supplied = str(seed.get("qid") or "")
        external_key = (seed.get("external_id_property"), str(seed.get("external_id") or ""))
        qid = supplied if QID.fullmatch(supplied) else external_matches.get(external_key, "")
        error = "" if qid else ("invalid_qid" if supplied else external_errors.get(external_key, "no_safe_qid"))
        resolved.append((qid, error, external_provenance.get(external_key)))
    people_method = getattr(client, "people", client.entities)
    people, people_meta, people_errors = people_method([r[0] for r in resolved if r[0]])
    place_qids = {p["qid"] for entity in people.values() for p in item_values(entity, "P19")}
    places, places_meta, places_errors = client.entities(place_qids)
    keys = Counter((s.get("cohort"), s.get("record_id")) for s in seeds)
    rows = []
    for index, (seed, (qid, identity_error, resolver_provenance)) in enumerate(zip(seeds, resolved)):
        row = {"seed_index": index, "cohort": seed.get("cohort", ""), "record_id": seed.get("record_id", ""),
               "name": seed.get("name", ""), "dob": seed.get("dob", ""), "seed_qid": seed.get("qid", ""),
               "qid": qid, "identity_link_provenance": seed.get("identity_link_provenance"),
               "external_id_resolution": resolver_provenance,
               "duplicate_record_key": keys[(seed.get("cohort"), seed.get("record_id"))] > 1,
               "birthplace_source_grade": "S3", "hemisphere": "unknown", "reason": identity_error,
               "status": "unresolved", "raw_birthplace": "", "lat": None, "lon": None,
               "birthplace_claims": [], "place_evidence": [], "birthplace_source_urls": [],
               "dob_or_acceptance_modified": False}
        if identity_error:
            rows.append(row)
            continue
        if qid not in people:
            row["reason"] = "person_fetch_failed:" + people_errors.get(qid, "unknown_error")
            rows.append(row)
            continue
        person = people[qid]
        row["person_birthplace_statement_inventory"] = [{"claim_id": c.get("id"), "statement_uri": c.get("statement_uri"),
                "rank": c.get("rank"), "snaktype": c.get("mainsnak", {}).get("snaktype"),
                "value_qid": c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")}
                for c in person.get("claims", {}).get("P19", [])]
        claims = item_values(person, "P19")
        row["birthplace_claims"] = claims
        row["person_response"] = people_meta[qid]
        row["birthplace_source_urls"].append("https://www.wikidata.org/wiki/" + qid + "#P19")
        place_ids = sorted({c["qid"] for c in claims})
        for place_id in place_ids:
            if place_id not in places:
                row["place_evidence"].append({"qid": place_id, "error": places_errors.get(place_id, "unknown_error")})
                continue
            place = places[place_id]
            coords, skipped = coordinate_values(place)
            row["place_evidence"].append({"qid": place_id, "label": entity_label(place),
                                           "coordinates": coords, "skipped_coordinate_reasons": skipped,
                                           "instance_of_claims": item_values(place, "P31"),
                                           "country_claims_descriptive_only": item_values(place, "P17"),
                                           "response": places_meta[place_id]})
            row["birthplace_source_urls"].append("https://www.wikidata.org/wiki/" + place_id + "#P625")
        row["raw_birthplace"] = " | ".join(p.get("label") or p["qid"] for p in row["place_evidence"])
        if not place_ids:
            row["reason"] = "no_value_birthplace_P19"
        elif any(c.get("mainsnak", {}).get("snaktype") != "value" for c in active_claims(person, "P19")):
            row["reason"] = "unresolved_non_value_birthplace_claim"
        elif len(place_ids) != 1:
            row["reason"] = "multiple_distinct_birthplace_P19_conflict"
        elif "error" in row["place_evidence"][0]:
            row["reason"] = "birthplace_fetch_failed:" + row["place_evidence"][0]["error"]
        else:
            place_evidence = row["place_evidence"][0]
            place_types = {c["qid"] for c in place_evidence["instance_of_claims"]}
            self_country = any(c["qid"] == place_ids[0] for c in place_evidence["country_claims_descriptive_only"])
            coords = place_evidence["coordinates"]
            unique = {(c["lat"], c["lon"]) for c in coords}
            if place_types.intersection(BROAD_PLACE_TYPES) or self_country:
                row["reason"] = "broad_birthplace_needs_extent"
            elif not unique:
                row["reason"] = "no_valid_direct_earth_P625"
            elif len(unique) != 1:
                row["reason"] = "multiple_distinct_direct_coordinates_conflict"
            else:
                row["lat"], row["lon"] = next(iter(unique))
                precisions = [c.get("precision") for c in coords]
                if any(isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0 for p in precisions):
                    row["reason"] = "coordinate_precision_missing_or_invalid"
                elif row["lat"] == 0 or abs(row["lat"]) <= max(precisions):
                    row["reason"] = "coordinate_precision_interval_touches_equator"
                else:
                    row["hemisphere"] = "north" if row["lat"] > 0 else "south"
                    row["reason"] = "single_P19_single_direct_earth_coordinate"
                    row["status"] = "classified_supplement"
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--cache", required=True)
    parser.add_argument("--limit", type=int, default=0, help="0 means all input seeds")
    parser.add_argument("--max-requests", type=int, default=600)
    parser.add_argument("--max-runtime-seconds", type=float, default=1500)
    parser.add_argument("--person-sparql", action="store_true", help="Fetch only P19 statements for people (200 QIDs/query); places still use API")
    parser.add_argument("--person-sparql-batch-size", type=int, default=200)
    args = parser.parse_args()
    input_path = Path(args.input)
    input_bytes = input_path.read_bytes()
    seeds = [json.loads(line) for line in input_bytes.decode("utf-8-sig").splitlines() if line.strip()]
    for index, seed in enumerate(seeds):
        if not isinstance(seed, dict) or not seed.get("record_id") or not seed.get("cohort"):
            raise ValueError("Each input row needs cohort and record_id; invalid row " + str(index + 1))
    if args.limit < 0:
        raise ValueError("--limit must be nonnegative")
    if not 1 <= args.person_sparql_batch_size <= 250:
        raise ValueError("--person-sparql-batch-size must be 1..250")
    if args.limit:
        seeds = seeds[:args.limit]
    client = Client(args.cache, max_requests=args.max_requests, max_runtime_seconds=args.max_runtime_seconds,
                    person_sparql=args.person_sparql, person_sparql_batch_size=args.person_sparql_batch_size)
    rows = screen(seeds, client)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    rows_file = output / "birthplace_wikidata_rows.jsonl"
    rows_file.write_bytes(b"".join(json_bytes(row) for row in rows))
    grouped = {}
    for cohort in sorted({r["cohort"] for r in rows}):
        cohort_rows = [r for r in rows if r["cohort"] == cohort]
        grouped[cohort] = {"seed_rows": len(cohort_rows), "hemisphere_counts": dict(Counter(r["hemisphere"] for r in cohort_rows)),
                           "reason_counts": dict(Counter(r["reason"] for r in cohort_rows)),
                           "unique_record_keys": len({r["record_id"] for r in cohort_rows}),
                           "duplicate_record_key_rows": sum(r["duplicate_record_key"] for r in cohort_rows)}
    summary = {"schema": "academy_birthplace_wikidata_supplement_v1", "created_utc": utc_now(),
               "input_sha256": sha(input_bytes), "script_sha256": sha(Path(__file__).read_bytes()),
               "output_rows_sha256": sha(rows_file.read_bytes()), "input_selected_rows": len(seeds), "output_rows": len(rows),
               "request_count_this_run": client.request_count, "by_cohort": grouped,
               "source_grade": "S3 supplement, independent of DOB source grade",
               "rules": ["Only existing QIDs or exact unique one-to-one external-ID links; no name matching.",
                         "Only direct P19 birthplace -> direct Earth P625; no country centroids or nationality.",
                         "Multiple distinct P19 or valid direct coordinate values remain unknown.",
                         "All input rows retained, including duplicate record keys (explicitly flagged).",
                         "DOB and native acceptance, calendar and eligibility flags are not changed.",
                         "These are source-sensitive geographic supplements, not final cohort approvals."]}
    if len(rows) != len(seeds):
        raise AssertionError("Output row conservation failure")
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
