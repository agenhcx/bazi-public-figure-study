"""Offline checks for peak-history acquisition and source provenance."""
import gzip
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

import collect_fide as collection


def payload(fid="123", records=None):
    return json.dumps(records if records is not None else [
        {"id": fid, "date": "2003-04-01", "rating": 2400},
        {"id": fid, "date": "2013-01-01", "rating": 2500},
        {"id": fid, "date": "2023-10-01", "rating": 2679},
        {"id": fid, "date": "2023-11-01", "rating": 2679},
        {"id": fid, "date": "2024-01-01", "rating": 2800},
    ]).encode()


def lichess_payload(points=None):
    return json.dumps({"standard": points if points is not None else
        [2003042400, 2012122500, 2013022500, 2023102679, 2023112679, 2024012800],
        "rapid": [2023123300], "blitz": [2023123400]}).encode()


def person(fid="123"):
    return {"canonical_id": fid, "fide_id": fid, "name": "Fixture Player",
            "role": "development", "cohort": "development", "snapshot": "2013-01",
            "snapshot_elo": 2500, "exact_dob_frozen": "1980-01-01"}


def metadata(fid, raw, provider="fide_official_chart"):
    return {"source_url": collection.lichess_url(fid) if provider == "lichess_fide_history"
            else collection.chart_url(fid), "source_provider": provider,
            "fetched_at_utc": "2026-10-23T00:00:00Z", "http_status": 200,
            "raw_sha256": collection.sha256_bytes(raw), "raw_bytes": len(raw),
            "request_method": "GET" if provider == "lichess_fide_history" else "POST"}


class NoWait:
    def __init__(self): self.calls = 0
    def wait(self): self.calls += 1


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, body, url): self.body, self.url = body, url
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, *args): return self.body
    def geturl(self): return self.url


class HistoryTests(unittest.TestCase):
    def test_live_official_chart_fields_and_nullable_early_identity(self):
        raw = json.dumps([
            {"date_2": "2003-Apr", "rating": "2400", "id_number": None,
             "rapid_rtng": "3000", "blitz_rtng": "3100"},
            {"date_2": "2023-Dec", "rating": "2679", "id_number": "123",
             "rapid_rtng": "3200", "blitz_rtng": "3300"},
        ]).encode()
        result = collection.parse_history(raw, "123")
        self.assertEqual(result["observed_fide_history_peak_elo_through_2023"], 2679)
        self.assertEqual(result["history_start"], "2003-04")
        wrong = raw.replace(b'"id_number": "123"', b'"id_number": "456"')
        with self.assertRaises(collection.SourceIntegrityError):
            collection.parse_history(wrong, "123")

    def test_official_standard_peak_uses_fixed_cutoff_and_keeps_future_source(self):
        result = collection.parse_history(payload(), "123")
        self.assertEqual(result["observed_fide_history_peak_elo_through_2023"], 2679)
        self.assertEqual(result["peak_months"], ["2023-10", "2023-11"])
        self.assertEqual(result["all_standard_history"][-1]["month"], "2024-01")

    def test_empty_or_invalid_official_json_is_unavailable(self):
        for raw in (b"", b"\xef\xbb\xbf", b"[]", b"not JSON"):
            with self.subTest(raw=raw), self.assertRaises(collection.HistoryUnavailable):
                collection.parse_history(raw, "123")

    def test_official_identity_conflict_is_integrity_error(self):
        with self.assertRaises(collection.SourceIntegrityError):
            collection.parse_history(payload("456"), "123")

    def test_lichess_uses_standard_only_and_derives_only_snapshot_state(self):
        result = collection.parse_lichess_history(lichess_payload(), "123", snapshot="2013-01")
        self.assertEqual(result["observed_fide_history_peak_elo_through_2023"], 2679)
        self.assertFalse(result["peak_months_complete"])
        inferred = [row for row in result["all_standard_history"] if row.get("derived_state")]
        self.assertEqual(len(inferred), 1)
        self.assertEqual(inferred[0]["month"], "2013-01")
        self.assertEqual(inferred[0]["standard_elo"], 2500)
        self.assertEqual(inferred[0]["derived_from_month"], "2012-12")
        self.assertFalse(inferred[0]["source_point"])

    def test_lichess_snapshot_never_extrapolates_or_crosses_unrated_gap(self):
        for month in ("2000-01", "2025-01"):
            result = collection.parse_lichess_history(lichess_payload(), "123", snapshot=month)
            self.assertFalse(result["snapshot_derived_from_compressed_history"])
        result = collection.parse_lichess_history(lichess_payload(
            [2010012500, 2012010000, 2015012600]), "123", snapshot="2013-01")
        self.assertFalse(result["snapshot_derived_from_compressed_history"])

    def test_lichess_invalid_or_conflicting_points_are_integrity_errors(self):
        for points in ([2023132500], [2023012500, 2023012501],
                       [2023010000, 2023012500], [True], ["2023012500"]):
            with self.subTest(points=points), self.assertRaises(collection.SourceIntegrityError):
                collection.parse_lichess_history(lichess_payload(points), "123")


class CacheTests(unittest.TestCase):
    def test_round_trip_cache_checks_raw_and_gzip_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = payload()
            saved = collection.save_cache(Path(tmp), "123", raw, metadata("123", raw))
            cached_raw, cached_meta = collection.read_cache(Path(tmp), "123")
            self.assertEqual(cached_raw, raw)
            self.assertEqual(cached_meta["raw_sha256"], collection.sha256_bytes(raw))
            self.assertEqual(cached_meta, saved)
            raw_path, _ = collection.cache_paths(Path(tmp), "123")
            raw_path.write_bytes(gzip.compress(raw + b" ", mtime=0))
            with self.assertRaises(collection.CacheIntegrityError):
                collection.read_cache(Path(tmp), "123")

    def test_lichess_cache_url_must_match_queried_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = lichess_payload()
            meta = metadata("456", raw, "lichess_fide_history")
            collection.save_cache(Path(tmp), "123", raw, meta)
            with self.assertRaises(collection.CacheIntegrityError):
                collection.read_cache(Path(tmp), "123")

    def test_existing_verified_official_cache_ignores_new_provider_preference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, raw = Path(tmp), payload()
            collection.save_cache(root, "123", raw, metadata("123", raw))
            with patch.object(collection, "fetch_lichess") as lichess, \
                 patch.object(collection, "fetch_chart") as fide:
                entry = collection.process_person(person(), root, None, prefer_provider="lichess")
            self.assertEqual(entry["status"], "history_acquired")
            self.assertEqual(entry["source_provider"], "fide_official_chart")
            lichess.assert_not_called(); fide.assert_not_called()

    def test_unusable_legacy_cache_is_archived_before_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, bad = Path(tmp), b"\xef\xbb\xbf"
            collection.save_cache(root, "123", bad, metadata("123", bad))
            good = payload()
            def fetch(*args, **kwargs): return good, metadata("123", good)
            entry = collection.process_person(person(), root, None, fetcher=fetch)
            self.assertEqual(entry["status"], "history_acquired")
            rejected = list((root / "failures").glob("*.json.gz"))
            self.assertEqual(len(rejected), 1)
            self.assertEqual(gzip.decompress(rejected[0].read_bytes()), bad)
            self.assertEqual(collection.read_cache(root, "123")[0], good)


class FetchTests(unittest.TestCase):
    def test_semantically_empty_http200_retries_before_cache(self):
        bodies, sleeps, limiter = iter([b"\xef\xbb\xbf", b"[]", payload()]), [], NoWait()
        raw, meta = collection.fetch_chart("123", limiter,
            opener=lambda request, timeout: Response(next(bodies), request.full_url),
            sleeper=sleeps.append)
        self.assertEqual(raw, payload())
        self.assertEqual(limiter.calls, 3)
        self.assertEqual(sleeps, [1, 3])
        self.assertEqual(len(meta["attempt_records"]), 3)

    def test_lichess_first_success_skips_official(self):
        raw = lichess_payload()
        meta = metadata("123", raw, "lichess_fide_history")
        with patch.object(collection, "fetch_lichess", return_value=(raw, meta)) as lichess, \
             patch.object(collection, "fetch_chart") as fide:
            result = collection.fetch_history("123", None, prefer_provider="lichess")
        self.assertEqual(result, (raw, meta))
        lichess.assert_called_once(); fide.assert_not_called()

    def test_unavailable_lichess_falls_back_to_official_and_preserves_rejection(self):
        raw, bad = payload(), b"{}"
        failure = collection.FetchFailure("unavailable", [{"attempt": 3, "http_status": 200}], bad)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(collection, "fetch_lichess", side_effect=failure), \
                 patch.object(collection, "fetch_chart", return_value=(raw, metadata("123", raw))):
                entry = collection.process_person(person(), root, None, prefer_provider="lichess")
            self.assertEqual(entry["status"], "history_acquired")
            self.assertEqual(entry["source_provider"], "fide_official_chart")
            _, cached = collection.read_cache(root, "123")
            rejection = root / cached["lichess_provider_unavailable"]["last_response_file"]
            self.assertEqual(gzip.decompress(rejection.read_bytes()), bad)

    def test_unavailable_official_falls_back_to_lichess_with_provenance(self):
        raw = lichess_payload()
        failure = collection.FetchFailure("unavailable", [{"attempt": 3}], b"[]")
        with patch.object(collection, "fetch_chart", side_effect=failure), \
             patch.object(collection, "fetch_lichess", return_value=(raw, metadata("123", raw, "lichess_fide_history"))):
            result, meta = collection.fetch_history("123", None)
        self.assertEqual(result, raw)
        self.assertIn("official_provider_unavailable", meta)

    def test_integrity_conflicts_or_stop_never_change_provider(self):
        for preferred, first, second in (("fide", "fetch_chart", "fetch_lichess"),
                                          ("lichess", "fetch_lichess", "fetch_chart")):
            for error in (collection.SourceIntegrityError("conflicting identity/data"),
                          collection.AcquisitionStopped("rate limited")):
                with self.subTest(preferred=preferred, error=type(error).__name__), \
                     patch.object(collection, first, side_effect=error), \
                     patch.object(collection, second) as fallback:
                    with self.assertRaises(type(error)):
                        collection.fetch_history("123", None, prefer_provider=preferred)
                    fallback.assert_not_called()

    def test_http429_stops_without_retry(self):
        for fetch in (collection.fetch_chart, collection.fetch_lichess):
            limiter, calls = collection.RateLimiter(4), []
            def opener(request, timeout):
                calls.append(request.full_url)
                raise urllib.error.HTTPError(request.full_url, 429, "Slow down", {}, io.BytesIO(b"limited"))
            with self.subTest(fetch=fetch.__name__), self.assertRaises(collection.AcquisitionStopped):
                fetch("123", limiter, opener=opener, sleeper=lambda _: None)
            self.assertEqual(len(calls), 1)
            self.assertTrue(limiter.stopped.is_set())

    def test_lichess_network_requests_are_serialized(self):
        state, guard, raw = {"active": 0, "maximum": 0}, threading.Lock(), lichess_payload()
        class ConcurrentResponse(Response):
            def __enter__(self):
                with guard:
                    state["active"] += 1
                    state["maximum"] = max(state["maximum"], state["active"])
                return self
            def __exit__(self, *args):
                with guard: state["active"] -= 1
            def read(self, *args):
                time.sleep(.015)
                return raw
        def fetch(fid):
            return collection.fetch_lichess(fid, NoWait(),
                opener=lambda request, timeout: ConcurrentResponse(raw, request.full_url))
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(len(list(pool.map(fetch, ["123", "456", "789", "101"]))), 4)
        self.assertEqual(state, {"active": 0, "maximum": 1})

    def test_stop_file_blocks_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = Path(tmp) / "STOP"
            stop.write_text("pause")
            limiter = collection.RateLimiter(4, stop_file=stop)
            with patch.object(collection.urllib.request, "urlopen") as opener:
                with self.assertRaises(collection.AcquisitionStopped):
                    collection.fetch_lichess("123", limiter)
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
