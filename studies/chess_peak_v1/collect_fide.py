#!/usr/bin/env python3
"""Resumable acquisition of frozen-cohort published standard-rating histories.

The target window ends in December 2023. Raw provider bytes, request provenance,
and rejected responses are retained; no models are fitted by this module.
"""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request

PROTOCOL = "chess-peak-history-acquisition-v1"
CUTOFF = "2023-12"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
HEADERS = {"User-Agent": "chess-peak-research/1.0 (bounded public rating-history acquisition)",
           "Accept": "application/json, text/plain, */*"}
FIDE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; chess-peak-research/1.0)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://ratings.fide.com", "X-Requested-With": "XMLHttpRequest"}
LICHESS_NETWORK_LOCK = threading.Lock()
SOURCE_SPECS = {
    "development": {"path": "studies/chess_single_A_v2/data/cohort_2013_M.csv", "n": 1000,
        "sha256": "eaf7528e72a9768609e2d973d7695df1e4d73f53a0c9647e032e5821bb12f5d2",
        "snapshot": "2013-01", "role": "development"},
    "primary_new": {"path": "studies/chess_single_A_v2/data/cohort_2023_M_NEW_TARGET.csv", "n": 500,
        "sha256": "2d6215734b4673785d4834b5e89745ea29ef727c0bec0bf7553918d6bc6fb8eb",
        "snapshot": "2023-01", "role": "primary_new"},
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def canonical_id(value):
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]+", text) or int(text) <= 0:
        raise ValueError("FIDE ID must be a positive integer")
    return str(int(text))


def safe_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError("Output path must remain beneath acquisition root")
    return path


def write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def write_json(path, value):
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


class HistoryUnavailable(ValueError):
    """No interpretable standard-history data at an available provider."""


class SourceIntegrityError(ValueError):
    def __init__(self, message, response_body=None, attempts=None):
        super().__init__(message)
        self.response_body = response_body
        self.attempts = [] if attempts is None else attempts


class AcquisitionStopped(RuntimeError):
    pass


class FetchFailure(RuntimeError):
    def __init__(self, message, attempts, response_body=None):
        super().__init__(message)
        self.attempts, self.response_body = attempts, response_body


class CacheIntegrityError(ValueError):
    pass


def _decode(raw):
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HistoryUnavailable("History response is not usable JSON") from error


def _month(value):
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-[A-Za-z]{3}", text):
        try:
            text = datetime.strptime(text, "%Y-%b").strftime("%Y-%m")
        except ValueError as error:
            raise SourceIntegrityError("Invalid named published rating month") from error
    if re.fullmatch(r"\d{6}", text):
        text = text[:4] + "-" + text[4:]
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?(?:[ T].*)?", text)
    if not match:
        raise SourceIntegrityError(f"Invalid published rating month: {text!r}")
    year, month = map(int, match.groups())
    if not 1971 <= year <= datetime.now(timezone.utc).year + 1 or not 1 <= month <= 12:
        raise SourceIntegrityError("Published rating month outside allowed bounds")
    return f"{year:04d}-{month:02d}"


def _rating(value):
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value).strip()):
        raise SourceIntegrityError("Invalid standard rating")
    rating = int(value)
    if not 0 <= rating <= 3500:
        raise SourceIntegrityError("Standard rating outside allowed bounds")
    return rating


def _summarize(points, *, compressed=False, snapshot_derived=False):
    points = sorted(points, key=lambda row: row["month"])
    eligible = [row for row in points if row["month"] <= CUTOFF and not row.get("derived_state")]
    if not eligible:
        raise HistoryUnavailable("No positive standard ratings through cutoff")
    peak = max(row["standard_elo"] for row in eligible)
    return {"all_standard_history": points, "standard_history_n": len(eligible),
        "history_start": points[0]["month"], "history_end": points[-1]["month"],
        "observed_fide_history_peak_elo_through_2023": peak,
        "peak_months": [row["month"] for row in eligible if row["standard_elo"] == peak],
        "peak_months_complete": not compressed,
        "history_compression": "first_and_last_month_of_equal_rating_streak" if compressed else None,
        "snapshot_derived_from_compressed_history": snapshot_derived,
        "future_months_in_raw": sum(row["month"] > CUTOFF for row in points),
        "rating_type": "standard", "lifetime_peak_claimed": False}


def parse_history(raw, fide_id):
    """Validate direct FIDE chart records; never mix rapid/blitz ratings."""
    value = _decode(raw)
    if not isinstance(value, list) or not value:
        raise HistoryUnavailable("Official chart contains no records")
    fid, by_month = canonical_id(fide_id), {}
    for record in value:
        if not isinstance(record, dict):
            raise SourceIntegrityError("Official chart record is not an object", raw)
        for field in ("id_number", "id", "event", "fide_id"):
            if record.get(field) not in (None, ""):
                try:
                    response_id = canonical_id(record[field])
                except ValueError as error:
                    raise SourceIntegrityError("Official chart record has an invalid FIDE ID", raw) from error
                if response_id != fid:
                    raise SourceIntegrityError("Official chart response has a different FIDE ID", raw)
        date = next((record[key] for key in ("date_2", "date", "period", "month", "rating_date") if key in record), None)
        rating = next((record[key] for key in ("rating", "rtng", "standard", "standard_rating") if key in record), None)
        if date is None:
            raise SourceIntegrityError("Official chart record lacks a published month", raw)
        month = _month(date)
        # FIDE includes blitz/rapid-only months before a player's first standard
        # rating (e.g. Murzin November/December2014). Missing standard is unrated,
        # exactly like zero; the month/identity still must pass validation.
        rating = 0 if rating is None or (isinstance(rating, str) and not rating.strip()) else _rating(rating)
        if month in by_month and by_month[month] != rating:
            raise SourceIntegrityError("Conflicting standard ratings for one month", raw)
        by_month[month] = rating
    result = _summarize([{"month": month, "standard_elo": rating, "source_point": True}
                         for month, rating in by_month.items() if rating])
    unrated = sorted(month for month, rating in by_month.items() if rating == 0)
    result.update(unrated_standard_months=unrated, unrated_standard_months_n=len(unrated))
    return result


def lichess_url(fide_id):
    return f"https://lichess.org/api/fide/player/{canonical_id(fide_id)}/ratings"


def parse_lichess_history(raw, fide_id, *, snapshot=None):
    """Read FIDE-derived packed standard points; preserve compressed provenance."""
    canonical_id(fide_id)
    value = _decode(raw)
    if not isinstance(value, dict) or not isinstance(value.get("standard"), list) or not value["standard"]:
        raise HistoryUnavailable("Lichess endpoint contains no standard history")
    by_month = {}
    for packed in value["standard"]:
        if isinstance(packed, bool) or not isinstance(packed, int) or packed <= 0:
            raise SourceIntegrityError("Invalid packed standard history value", raw)
        stamp, rating = divmod(packed, 10000)
        month, rating = _month(stamp), _rating(rating)
        if month in by_month and by_month[month] != rating:
            raise SourceIntegrityError("Conflicting compressed standard ratings", raw)
        by_month[month] = rating
    rows = [{"month": month, "standard_elo": rating, "source_point": True}
            for month, rating in sorted(by_month.items()) if rating]
    derived = False
    if snapshot is not None:
        snapshot = _month(snapshot)
        keys = sorted(by_month)
        if keys and keys[0] <= snapshot <= keys[-1] and snapshot not in by_month:
            previous = max((month for month in keys if month < snapshot), default=None)
            if previous is not None and by_month[previous] > 0:
                rows.append({"month": snapshot, "standard_elo": by_month[previous], "source_point": False,
                    "derived_state": True, "derived_from_month": previous,
                    "derivation": "piecewise_constant_state_from_compressed_FIDE_rating_history"})
                derived = True
    return _summarize(rows, compressed=True, snapshot_derived=derived)


def load_rosters(repo_root, source_specs=None):
    """Verify both fixed input files and person disjointness before requests."""
    specs = SOURCE_SPECS if source_specs is None else source_specs
    people, audit, seen_ids, seen_qids = [], {}, set(), set()
    for key, spec in specs.items():
        path = Path(repo_root) / spec["path"]
        digest = sha256_file(path)
        if digest != spec["sha256"]:
            raise ValueError(f"Frozen roster fingerprint differs: {key}")
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        if len(rows) != spec["n"]:
            raise ValueError(f"Frozen roster count differs: {key}")
        for row in rows:
            fid = canonical_id(row.get("identity_bridge_modern_fide_id") or row["fide_id"])
            qids = set(re.findall(r"Q\d+", row.get("wikidata_person_qids", "")))
            if not qids:
                raise ValueError("Frozen person has no Wikidata identity")
            if fid in seen_ids or qids & seen_qids:
                raise ValueError("Frozen cohorts contain duplicate/overlapping persons")
            snapshot = row.get("snapshot") or spec["snapshot"]
            if snapshot != spec["snapshot"]:
                raise ValueError("Frozen roster snapshot differs")
            dob = row.get("exact_dob_frozen", "")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob):
                raise ValueError("Frozen exact date of birth missing")
            datetime.strptime(dob, "%Y-%m-%d")
            seen_ids.add(fid); seen_qids.update(qids)
            people.append({**row, "canonical_id": fid, "wikidata_person_qids": sorted(qids),
                "role": spec.get("role", key),
                "snapshot": snapshot, "snapshot_elo": _rating(row["rating"]),
                "source_roster": spec["path"], "source_roster_sha256": digest})
        audit[key] = {"path": spec["path"], "sha256": digest, "n": len(rows)}
    return people, {"sources": audit, "unique_people_n": len(people),
                    "canonical_id_overlap_n": 0, "wikidata_person_overlap_n": 0}


class RateLimiter:
    def __init__(self, requests_per_second=1.0, stop_file=None):
        if not 0 < requests_per_second <= 4:
            raise ValueError("Request starts must be >0 and <=4 per second")
        self.interval = 1.0 / requests_per_second
        self.lock, self.stopped = threading.Lock(), threading.Event()
        self.next_start = 0.0
        self.stop_file = Path(stop_file) if stop_file is not None else None

    def stop(self):
        self.stopped.set()

    def check_stop(self):
        if self.stopped.is_set() or (self.stop_file is not None and self.stop_file.exists()):
            self.stopped.set()
            raise AcquisitionStopped("Acquisition stopped by marker or provider rate limit")

    def wait(self):
        self.check_stop()
        with self.lock:
            delay = max(0.0, self.next_start - time.monotonic())
            if self.stopped.wait(delay):
                self.check_stop()
            self.check_stop()
            self.next_start = time.monotonic() + self.interval


def chart_url(fide_id):
    return f"https://ratings.fide.com/a_chart_data.phtml?event={canonical_id(fide_id)}&period=0"


def _fetch(fide_id, limiter, *, provider, timeout=25, attempts=3, opener=None, sleeper=time.sleep):
    if attempts != 3 or not 0 < timeout <= 60:
        raise ValueError("Acquisition requires three bounded attempts and a timeout <=60 seconds")
    opener = urllib.request.urlopen if opener is None else opener
    official = provider == "fide_official_chart"
    url = chart_url(fide_id) if official else lichess_url(fide_id)
    records, last_body = [], None
    for attempt in range(1, attempts + 1):
        limiter.wait()
        record = {"attempt": attempt, "started_at_utc": utc_now()}
        try:
            headers = dict(FIDE_HEADERS if official else HEADERS)
            if official:
                headers["Referer"] = f"https://ratings.fide.com/profile/{canonical_id(fide_id)}"
            request = urllib.request.Request(url, data=b"" if official else None,
                                             method="POST" if official else "GET", headers=headers)
            record.update(source_url=url, request_method=request.get_method(), request_headers=headers)
            lock = threading.Lock() if official else LICHESS_NETWORK_LOCK
            with lock, opener(request, timeout=timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES or response.status != 200:
                    raise SourceIntegrityError("History response exceeds size/status bounds", body)
                if response.geturl() != url:
                    raise SourceIntegrityError("History response redirected to another endpoint", body)
                last_body = body
                record.update(http_status=200, bytes=len(body), raw_sha256=sha256_bytes(body))
                try:
                    (parse_history if official else parse_lichess_history)(body, fide_id)
                except SourceIntegrityError as error:
                    error.response_body, error.attempts = body, records + [record]
                    raise
                records.append(record)
                return body, {"source_url": url, "request_method": request.get_method(),
                    "request_headers": headers, "request_body": "" if official else None,
                    "final_url": url, "fetched_at_utc": utc_now(), "http_status": 200,
                    "content_type": response.headers.get("Content-Type"), "attempt_records": records,
                    "raw_sha256": sha256_bytes(body), "raw_bytes": len(body), "source_provider": provider,
                    "identity_anchor": "queried_FIDE_ID_endpoint"}
        except (SourceIntegrityError, AcquisitionStopped):
            raise
        except Exception as error:
            record.update(error_type=type(error).__name__, error=str(error))
            if isinstance(error, urllib.error.HTTPError):
                last_body = error.read(MAX_RESPONSE_BYTES)
                record.update(http_status=error.code, bytes=len(last_body), raw_sha256=sha256_bytes(last_body))
                if error.code == 429:
                    if hasattr(limiter, "stop"):
                        limiter.stop()
                    raise AcquisitionStopped(f"{provider} requested rate limiting; acquisition stopped") from error
            records.append(record)
            if attempt < attempts:
                sleeper((1, 3)[attempt - 1])
    raise FetchFailure(f"All three {provider} history attempts failed", records, last_body)


def fetch_chart(fide_id, limiter, *, timeout=25, attempts=3, opener=None, sleeper=time.sleep):
    return _fetch(fide_id, limiter, provider="fide_official_chart", timeout=timeout,
                  attempts=attempts, opener=opener, sleeper=sleeper)


def fetch_lichess(fide_id, limiter, *, timeout=25, attempts=3, opener=None, sleeper=time.sleep):
    return _fetch(fide_id, limiter, provider="lichess_fide_history", timeout=timeout,
                  attempts=attempts, opener=opener, sleeper=sleeper)


def fetch_history(fide_id, limiter, *, timeout=25, attempts=3, prefer_provider="fide"):
    """Use fixed provider order/availability; never choose based on peak values."""
    if prefer_provider not in ("fide", "lichess"):
        raise ValueError("Preferred provider must be fide or lichess")
    first, second, failed_provider = ((fetch_chart, fetch_lichess, "official")
        if prefer_provider == "fide" else (fetch_lichess, fetch_chart, "lichess"))
    try:
        return first(fide_id, limiter, timeout=timeout, attempts=attempts)
    except FetchFailure as error:
        raw, metadata = second(fide_id, limiter, timeout=timeout, attempts=attempts)
        metadata[f"{failed_provider}_provider_unavailable"] = {"attempt_records": error.attempts,
            "last_response_raw_sha256": sha256_bytes(error.response_body) if error.response_body is not None else None,
            "last_response_bytes": len(error.response_body) if error.response_body is not None else None}
        metadata[f"_{failed_provider}_failure_body"] = error.response_body
        return raw, metadata


def cache_paths(output, fide_id):
    fid = canonical_id(fide_id)
    return safe_path(output, f"raw/{fid}.json.gz"), safe_path(output, f"raw/{fid}.metadata.json")


def read_cache(output, fide_id):
    raw_path, meta_path = cache_paths(output, fide_id)
    if not raw_path.exists() and not meta_path.exists():
        return None
    if not raw_path.is_file() or not meta_path.is_file():
        raise CacheIntegrityError("Response cache is incomplete")
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise CacheIntegrityError("Response metadata must be an object")
        compressed = raw_path.read_bytes()
        raw = gzip.decompress(compressed)
        provider = metadata.get("source_provider", "fide_official_chart")
        expected_url = {"fide_official_chart": chart_url(fide_id), "lichess_fide_history": lichess_url(fide_id)}.get(provider)
        if (metadata.get("canonical_id") != canonical_id(fide_id)
                or expected_url is None or metadata.get("source_url") != expected_url
                or metadata.get("http_status") != 200
                or metadata.get("raw_sha256") != sha256_bytes(raw)
                or metadata.get("raw_bytes") != len(raw)
                or metadata.get("gzip_sha256") != sha256_bytes(compressed)):
            raise CacheIntegrityError("Response cache fingerprints differ")
    except (OSError, EOFError, json.JSONDecodeError) as error:
        raise CacheIntegrityError("Response cache is unreadable") from error
    return raw, metadata


def save_cache(output, fide_id, raw, metadata):
    raw_path, meta_path = cache_paths(output, fide_id)
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    metadata = dict(metadata)
    for failed_provider in ("official", "lichess"):
        failure_body = metadata.pop(f"_{failed_provider}_failure_body", None)
        if failure_body is not None:
            digest = sha256_bytes(failure_body)
            failed = safe_path(output, f"failures/{canonical_id(fide_id)}.{failed_provider}-unavailable.{digest[:16]}.gz")
            write_bytes(failed, gzip.compress(failure_body, mtime=0))
            metadata[f"{failed_provider}_provider_unavailable"]["last_response_file"] = failed.relative_to(Path(output).resolve()).as_posix()
    metadata.setdefault("source_provider", "fide_official_chart")
    metadata = {**metadata, "canonical_id": canonical_id(fide_id), "raw_sha256": sha256_bytes(raw),
                "raw_bytes": len(raw), "gzip_sha256": sha256_bytes(compressed)}
    write_bytes(raw_path, compressed)
    write_json(meta_path, metadata)
    return metadata


def parse_provider(raw, fide_id, provider, *, snapshot=None):
    if provider == "fide_official_chart":
        return parse_history(raw, fide_id)
    if provider == "lichess_fide_history":
        return parse_lichess_history(raw, fide_id, snapshot=snapshot)
    raise SourceIntegrityError("Unknown rating-history provider")


def archive_unusable_cache(output, fide_id, raw, metadata, reason):
    prefix = f"failures/{canonical_id(fide_id)}.unusable-cache.{sha256_bytes(raw)[:16]}"
    write_bytes(safe_path(output, prefix + ".json.gz"), gzip.compress(raw, compresslevel=6, mtime=0))
    write_json(safe_path(output, prefix + ".metadata.json"), {**metadata,
        "cache_replacement_reason": reason, "replacement_audited_at_utc": utc_now()})


def _snapshot_rating(parsed, person):
    return {row["month"]: row["standard_elo"] for row in parsed["all_standard_history"]}.get(person["snapshot"])


def _validate_snapshot(parsed, person, raw, metadata):
    birth_month = person["exact_dob_frozen"][:7]
    if any(row["standard_elo"] > 0 and row["month"] < birth_month
           for row in parsed["all_standard_history"]):
        raise SourceIntegrityError("Positive standard-rating history predates the frozen birth month; provider change forbidden",
                                   raw, metadata.get("attempt_records", []))
    return _snapshot_rating(parsed, person)


def normalize_source_name(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value)).casefold() if c.isalnum())


def _official_snapshot_identity(person, raw, metadata):
    """Require same-chart name/month and a nonnull current-ID identity witness."""
    fid = canonical_id(person["canonical_id"])
    if metadata.get("source_url") != chart_url(fid) or metadata.get("http_status") != 200:
        raise SourceIntegrityError("Snapshot review lacks the exact official chart request", raw)
    expected_name = normalize_source_name(person["name"])
    snapshot_rows, witnesses = [], []
    for row in _decode(raw):
        date = next((row[key] for key in ("date_2", "date", "period", "month", "rating_date") if key in row), None)
        month = _month(date)
        matches_name = normalize_source_name(row.get("name", "")) == expected_name
        if row.get("id_number") not in (None, "") and canonical_id(row["id_number"]) == fid and matches_name:
            witnesses.append(month)
        value = next((row[key] for key in ("rating", "rtng", "standard", "standard_rating") if key in row), None)
        rated = value is not None and not (isinstance(value, str) and not value.strip()) and _rating(value) > 0
        if month == person["snapshot"] and rated:
            if not matches_name:
                raise SourceIntegrityError("Official snapshot name differs from the frozen person", raw)
            snapshot_rows.append(row)
    if not snapshot_rows or not witnesses or not expected_name:
        raise SourceIntegrityError("Official snapshot review lacks name/month/current-ID proof", raw)
    return snapshot_rows[0]["name"], min(witnesses)


def _coverage_evidence(output, fide_id, raw, metadata):
    """Persist both bytes and original request provenance before cache replacement."""
    provider = metadata.get("source_provider", "fide_official_chart")
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    provenance = {key: value for key, value in metadata.items()
                  if key not in ("source_coverage_audit", "source_raw_sha256s", "source_selection_reason",
                                 "snapshot_disagreement", "source_evidence")}
    provenance.update(canonical_id=canonical_id(fide_id), source_provider=provider,
                      raw_sha256=sha256_bytes(raw), raw_bytes=len(raw), gzip_sha256=sha256_bytes(compressed))
    meta_bytes = (json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    prefix = (f"coverage-evidence/{canonical_id(fide_id)}.{provider}."
              f"{sha256_bytes(raw)[:16]}.{sha256_bytes(meta_bytes)[:16]}")
    raw_name, meta_name = prefix + ".json.gz", prefix + ".metadata.json"
    for name, content in ((raw_name, compressed), (meta_name, meta_bytes)):
        path = safe_path(output, name)
        if path.exists() and path.read_bytes() != content:
            raise CacheIntegrityError("Existing coverage evidence differs; refusing to overwrite")
        if not path.exists():
            write_bytes(path, content)
    return {"source_provider": provider, "raw_sha256": sha256_bytes(raw), "raw_bytes": len(raw),
            "raw_file": raw_name, "gzip_sha256": sha256_bytes(compressed),
            "metadata_file": meta_name, "metadata_sha256": sha256_bytes(meta_bytes)}


def _stage_snapshot_disagreement(person, output, raw, metadata, parsed, prior_evidence=()):
    official_name, witness_month = _official_snapshot_identity(person, raw, metadata)
    observed = _snapshot_rating(parsed, person)
    if observed is None or observed == person["snapshot_elo"]:
        raise SourceIntegrityError("Snapshot disagreement proof requires differing observed and frozen values", raw)
    frozen_sha = person.get("source_roster_sha256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", frozen_sha) or not person.get("source_roster"):
        raise SourceIntegrityError("Snapshot disagreement lacks frozen roster provenance", raw)
    evidence = _coverage_evidence(output, person["canonical_id"], raw, metadata)
    proof = {"rule_id": "direct-official-frozen-snapshot-disagreement-v1",
        "status": "officially_verified_pending_peak_identifiability",
        "canonical_id": canonical_id(person["canonical_id"]), "snapshot_month": person["snapshot"],
        "frozen_snapshot_elo": person["snapshot_elo"], "official_snapshot_elo": observed,
        "frozen_name": person["name"], "official_name": official_name,
        "frozen_source_roster": person["source_roster"], "frozen_source_roster_sha256": frozen_sha,
        "official_evidence": evidence, "prior_evidence": list(prior_evidence),
        "identity_witness_month": witness_month}
    metadata = {**metadata, "snapshot_disagreement": proof,
        "source_selection_reason": "direct_official_authority_snapshot_disagreement_pending_peak_identifiability",
        "source_raw_sha256s": {s["source_provider"]: s["raw_sha256"] for s in [*prior_evidence, evidence]}}
    return metadata


def ensure_source_coverage(person, output, limiter, raw, metadata, *, timeout=25):
    """Use frozen-date coverage checks only; never inspect peaks to choose sources."""
    fid = canonical_id(person["canonical_id"])
    provider = metadata.get("source_provider", "fide_official_chart")
    parsed = parse_provider(raw, fid, provider, snapshot=person["snapshot"])
    snapshot_rating = _validate_snapshot(parsed, person, raw, metadata)
    disagrees = snapshot_rating is not None and snapshot_rating != person["snapshot_elo"]
    if provider != "lichess_fide_history":
        if disagrees:
            prior = metadata.get("snapshot_disagreement", {}).get("prior_evidence", [])
            metadata = _stage_snapshot_disagreement(person, output, raw, metadata, parsed, prior)
            metadata = save_cache(output, fid, raw, metadata)
        return raw, metadata, parsed
    reasons = []
    if snapshot_rating is None:
        reasons.append("lichess_missing_frozen_snapshot")
    if parsed["history_start"] > "2003-04" and person["exact_dob_frozen"] < "1985-01-01":
        reasons.append("lichess_late_history_for_older_person")
    if not reasons and not disagrees:
        return raw, metadata, parsed

    mirror_evidence = _coverage_evidence(output, fid, raw, metadata)
    audit = {"rule_id": "lichess-frozen-snapshot-and-older-window-v1", "reasons": reasons,
        "unresolved": True, "selected_provider": provider, "direct_source_coverage_checked": False,
        "sources": [mirror_evidence], "official_outcome": "unavailable"} if reasons else None
    metadata = dict(metadata)
    try:
        official_raw, official_meta = fetch_chart(fid, limiter, timeout=timeout, attempts=3)
    except FetchFailure as error:
        metadata["official_provider_unavailable"] = {"attempt_records": error.attempts,
            "last_response_raw_sha256": sha256_bytes(error.response_body) if error.response_body is not None else None,
            "last_response_bytes": len(error.response_body) if error.response_body is not None else None}
        metadata["_official_failure_body"] = error.response_body
        if disagrees:
            # Save failed official request provenance, but never waive a dispute.
            save_cache(output, fid, raw, metadata)
            raise SourceIntegrityError("Frozen snapshot disagreement could not be verified by the official source",
                                       raw, error.attempts) from error
    else:
        official_meta = {**official_meta, "source_provider": "fide_official_chart"}
        # The official bytes remain reviewable even when their snapshot conflicts.
        official_evidence = _coverage_evidence(output, fid, official_raw, official_meta)
        if audit is not None:
            audit["sources"].append(official_evidence)
        official_parsed = parse_history(official_raw, fid)
        official_snapshot = _validate_snapshot(official_parsed, person, official_raw, official_meta)
        if audit is not None:
            audit["direct_source_coverage_checked"] = True
        if official_snapshot is not None:
            if disagrees:
                _official_snapshot_identity(person, official_raw, official_meta)
            # A direct chart can legitimately start late for an older unrated entrant.
            # Checking that source is evidence, not an assertion of an earlier start.
            official_disagrees = official_snapshot != person["snapshot_elo"]
            if official_disagrees:
                official_meta = _stage_snapshot_disagreement(person, output, official_raw,
                    official_meta, official_parsed, [mirror_evidence])
            if audit is not None:
                audit.update(unresolved=False, selected_provider="fide_official_chart",
                    official_outcome="selected_snapshot_disagreement_verified" if official_disagrees
                                     else "selected_snapshot_verified")
            raw, metadata, parsed = official_raw, official_meta, official_parsed
        else:
            if disagrees:
                raise SourceIntegrityError("Official source lacks the disputed snapshot month", official_raw)
            audit["official_outcome"] = "missing_frozen_snapshot"
    sources = audit["sources"] if audit is not None else [mirror_evidence, official_evidence]
    if audit is not None:
        metadata["source_coverage_audit"] = audit
    metadata.setdefault("source_selection_reason", "fixed_frozen_snapshot_and_older_window_coverage_check"
                        if reasons else "direct_official_authority_for_snapshot_source_review")
    metadata.update(source_evidence=sources,
        source_raw_sha256s={source["source_provider"]: source["raw_sha256"] for source in sources})
    metadata = save_cache(output, fid, raw, metadata)
    return raw, metadata, parsed


def process_person(person, output, limiter, *, timeout=25, fetcher=fetch_history, prefer_provider="fide"):
    fid = canonical_id(person["canonical_id"])
    entry = {**person, "protocol_id": PROTOCOL, "cutoff_month": CUTOFF,
             "status": "failed", "source_url": chart_url(fid), "lifetime_peak_claimed": False}
    try:
        if prefer_provider not in ("fide", "lichess"):
            raise ValueError("Preferred provider must be fide or lichess")
        if limiter is not None and hasattr(limiter, "check_stop"):
            limiter.check_stop()
        cached = read_cache(output, fid)
        if cached is not None:
            try:
                parse_provider(cached[0], fid, cached[1].get("source_provider", "fide_official_chart"), snapshot=person["snapshot"])
            except HistoryUnavailable as error:
                archive_unusable_cache(output, fid, *cached, str(error))
                cached = None
        if cached is None:
            options = {"timeout": timeout, "attempts": 3}
            if fetcher is fetch_history:
                options["prefer_provider"] = prefer_provider
            raw, metadata = fetcher(fid, limiter, **options)
            # Validate semantics before committing newly fetched bytes to a reusable cache.
            parse_provider(raw, fid, metadata.get("source_provider", "fide_official_chart"), snapshot=person["snapshot"])
            metadata = save_cache(output, fid, raw, metadata)
        else:
            raw, metadata = cached
        entry.update({key: metadata[key] for key in ("source_url", "fetched_at_utc", "raw_sha256", "raw_bytes")})
        entry["source_provider"] = metadata.get("source_provider", "fide_official_chart")
        # Apply the same fixed coverage checks to resumed and newly fetched mirrors.
        raw, metadata, parsed = ensure_source_coverage(person, output, limiter, raw, metadata, timeout=timeout)
        entry.update({key: metadata[key] for key in ("source_url", "fetched_at_utc", "raw_sha256", "raw_bytes")})
        provider = metadata.get("source_provider", "fide_official_chart")
        entry["source_provider"] = provider
        for key in ("source_coverage_audit", "source_selection_reason", "source_raw_sha256s",
                    "snapshot_disagreement", "source_evidence"):
            if key in metadata:
                entry[key] = metadata[key]
        history = parsed.pop("all_standard_history")
        snapshot_rating = {row["month"]: row["standard_elo"] for row in history}.get(person["snapshot"])
        reasons = []
        staged_disagreement = "snapshot_disagreement" in metadata
        if snapshot_rating is not None and snapshot_rating != person["snapshot_elo"] and not staged_disagreement:
            reasons.append("official_chart_snapshot_rating_differs_from_frozen_snapshot")
        if parsed["observed_fide_history_peak_elo_through_2023"] < person["snapshot_elo"] and not staged_disagreement:
            reasons.append("observed_history_peak_is_below_frozen_snapshot_rating")
        if snapshot_rating is None:
            reasons.append("frozen_snapshot_month_absent_from_official_chart_history")
        if metadata.get("source_coverage_audit", {}).get("unresolved"):
            reasons.append("rating_history_coverage_unresolved")
        boundary, older = parsed["history_start"] <= "2003-04", person["exact_dob_frozen"] < "1985-01-01"
        normalized_path = safe_path(output, f"normalized/{fid}.json")
        write_json(normalized_path, {"canonical_id": fid, "source_raw_sha256": metadata["raw_sha256"],
            "standard_history": history, "future_months_retained_in_source_only": True,
            "label_cutoff_month": CUTOFF, "source_provider": provider,
            "history_compression": parsed.get("history_compression"), "peak_months_complete": parsed["peak_months_complete"]})
        entry.update(parsed)
        entry.update({"status": "history_acquired_requires_snapshot_audit" if reasons else "history_acquired",
            "snapshot_in_history": snapshot_rating is not None, "snapshot_history_elo": snapshot_rating,
            "snapshot_audit_required": bool(reasons), "snapshot_audit_reasons": reasons,
            "history_hits_2003_database_boundary": boundary, "birth_before_1985": older,
            "coverage_needs_pre2003": boundary or older,
            "coverage_flag_rule": "history starts <=2003-04 OR birth before1985; conservative historical-merge flag, not proof of prior rating",
            "peak_status": "available_chart_window_only_pending_historical_merge",
            "normalized_history_file": normalized_path.relative_to(Path(output).resolve()).as_posix(),
            "normalized_history_sha256": sha256_file(normalized_path)})
    except AcquisitionStopped:
        raise
    except Exception as error:
        entry.update(error_type=type(error).__name__, error=str(error))
        if isinstance(error, (FetchFailure, SourceIntegrityError)):
            entry["attempt_records"] = error.attempts
            if error.response_body is not None:
                failed_path = safe_path(output, f"failures/{fid}.last-response.gz")
                write_bytes(failed_path, gzip.compress(error.response_body, mtime=0))
                entry.update(failed_response_file=failed_path.relative_to(Path(output).resolve()).as_posix(),
                    failed_response_raw_sha256=sha256_bytes(error.response_body))
    write_json(safe_path(output, f"entries/{fid}.json"), entry)
    return entry


def load_roster(repo_root, source_specs=None):
    """Stable singular API used by the peak preparation pipeline."""
    return load_rosters(repo_root, source_specs)


def shard_people(people, shard_index, shard_count):
    if shard_count < 1 or shard_index < 0 or shard_index >= shard_count:
        raise ValueError("Invalid acquisition shard")
    return [person for person in people if int(hashlib.sha256(person["canonical_id"].encode()).hexdigest(), 16) % shard_count == shard_index]


def run_acquisition(repo_root, output_dir, *, shard_index=0, shard_count=1, max_players=None,
                    workers=2, requests_per_second=1.0, timeout=25, fetcher=fetch_history, source_specs=None,
                    stop_file=None, prefer_provider="fide"):
    if not 1 <= workers <= 4 or not 0 < timeout <= 60:
        raise ValueError("Workers must be 1..4 and timeout <=60 seconds")
    if max_players is not None and max_players < 1:
        raise ValueError("Pilot limit must be positive")
    if prefer_provider not in ("fide", "lichess"):
        raise ValueError("Preferred provider must be fide or lichess")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    people, roster_audit = load_rosters(repo_root, source_specs)
    shard = shard_people(people, shard_index, shard_count)
    selected = shard if max_players is None else shard[:max_players]
    limiter = RateLimiter(requests_per_second, stop_file=output / "STOP" if stop_file is None else stop_file)
    entries, stop_reason = [], None
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_person, person, output, limiter, timeout=timeout,
                    fetcher=fetcher, prefer_provider=prefer_provider): person for person in selected}
        for future in as_completed(futures):
            try:
                entry = future.result()
                entries.append(entry)
                print(json.dumps({"canonical_id": entry["canonical_id"], "status": entry["status"],
                                  "completed_n": len(entries), "selected_n": len(selected)}), flush=True)
            except AcquisitionStopped as error:
                limiter.stop(); stop_reason = str(error)
                for queued in futures:
                    queued.cancel()
            except Exception as error:
                if not future.cancelled():
                    raise
    entries.sort(key=lambda row: row["canonical_id"])
    failed = sum(row["status"] == "failed" for row in entries)
    counts = {"fide_official_chart": 0, "lichess_fide_history": 0}
    for row in entries:
        if row["status"] != "failed":
            provider = row["source_provider"]
            counts[provider] = counts.get(provider, 0) + 1
    status = ("history_acquisition_stopped" if stop_reason else "history_acquisition_failed" if failed
        else "partial_pilot_history_acquisition" if len(selected) != len(shard)
        else "rating_histories_acquired_pending_historical_merge" if counts["lichess_fide_history"]
        else "official_chart_histories_acquired_pending_historical_merge")
    files = {path.relative_to(output).as_posix(): sha256_file(path) for path in sorted(output.rglob("*"))
             if path.is_file() and path.name != "acquisition_manifest.json" and path.name != "STOP"}
    manifest = {"protocol_id": PROTOCOL, "status": status, "cutoff_month": CUTOFF,
        "created_at_utc": utc_now(), "shard_index": shard_index, "shard_count": shard_count,
        "full_shard_expected_n": len(shard), "selected_n": len(selected), "completed_n": len(entries),
        "failed_n": failed, "snapshot_audit_n": sum(bool(row.get("snapshot_audit_required")) for row in entries),
        "snapshot_disagreement_n": sum("snapshot_disagreement" in row for row in entries),
        "source_provider_counts": counts, "preferred_provider": prefer_provider,
        "workers": workers, "requests_per_second": requests_per_second, "stop_reason": stop_reason,
        "roster_audit": roster_audit, "model_fitting_performed": False, "lifetime_peak_claimed": False,
        "files": files}
    write_json(output / "acquisition_manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--max-players", type=int)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--requests-per-second", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=25)
    parser.add_argument("--stop-file")
    parser.add_argument("--prefer-provider", choices=("fide", "lichess"), default="fide")
    args = parser.parse_args()
    result = run_acquisition(args.repo_root, args.output_dir, shard_index=args.shard_index,
        shard_count=args.shard_count, max_players=args.max_players, workers=args.workers,
        requests_per_second=args.requests_per_second, timeout=args.timeout, stop_file=args.stop_file,
        prefer_provider=args.prefer_provider)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("official_chart_histories_acquired_pending_historical_merge",
        "rating_histories_acquired_pending_historical_merge", "partial_pilot_history_acquisition") else 1


if __name__ == "__main__":
    raise SystemExit(main())
