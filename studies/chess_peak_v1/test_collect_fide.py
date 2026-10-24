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

    def test_fide_request_has_exact_provider_specific_headers(self):
        expected = {"User-Agent": "Mozilla/5.0 (compatible; chess-peak-research/1.0)",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": "https://ratings.fide.com", "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://ratings.fide.com/profile/123"}
        requests = []
        def opener(request, timeout):
            requests.append(request)
            return Response(payload() if request.get_method() == "POST" else lichess_payload(),
                            request.full_url)
        _, official_meta = collection.fetch_chart("123", NoWait(), opener=opener)
        _, mirror_meta = collection.fetch_lichess("123", NoWait(), opener=opener)
        self.assertEqual(official_meta["request_headers"], expected)
        self.assertEqual({key.lower(): value for key, value in requests[0].header_items()},
                         {key.lower(): value for key, value in expected.items()})
        self.assertEqual(requests[0].get_method(), "POST")
        self.assertEqual(requests[0].data, b"")
        self.assertEqual(mirror_meta["request_headers"], collection.HEADERS)
        mirror_headers = {key.lower(): value for key, value in requests[1].header_items()}
        self.assertNotIn("origin", mirror_headers)
        self.assertNotIn("x-requested-with", mirror_headers)
        self.assertNotEqual(mirror_headers["user-agent"], expected["User-Agent"])


class CoverageTests(unittest.TestCase):
    def test_positive_rating_before_frozen_birth_month_fails_without_provider_change(self):
        for provider, raw in (("fide_official_chart", payload()),
                              ("lichess_fide_history", lichess_payload())):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                frozen = {**person(), "exact_dob_frozen": "2004-05-10"}
                def fetch(*args, **kwargs):
                    return raw, metadata("123", raw, provider)
                with patch.object(collection, "fetch_chart") as official, \
                     patch.object(collection, "fetch_lichess") as mirror:
                    entry = collection.process_person(frozen, Path(tmp), None, fetcher=fetch)
                self.assertEqual(entry["status"], "failed")
                self.assertEqual(entry["error_type"], "SourceIntegrityError")
                self.assertIn("birth month", entry["error"])
                official.assert_not_called(); mirror.assert_not_called()

    @staticmethod
    def acquire(root, chart_raw, *, mirror_raw=None, subject=None, chart_error=None):
        mirror_raw = mirror_raw if mirror_raw is not None else lichess_payload(
            [2013012500, 2023102679])
        chart_options = ({"side_effect": chart_error} if chart_error is not None else
                         {"return_value": (chart_raw, metadata("123", chart_raw))})
        with patch.object(collection, "fetch_lichess", return_value=(mirror_raw,
                          metadata("123", mirror_raw, "lichess_fide_history"))) as mirror, \
             patch.object(collection, "fetch_chart", **chart_options) as official:
            entry = collection.process_person(subject or person(), root, None,
                                              prefer_provider="lichess")
        return entry, mirror, official

    def assert_evidence(self, root, audit, expected_raw):
        self.assertEqual(audit["selected_provider"], "fide_official_chart")
        sources = {row["source_provider"]: row for row in audit["sources"]}
        self.assertEqual(set(sources), set(expected_raw))
        for provider, raw in expected_raw.items():
            evidence = sources[provider]
            self.assertEqual(evidence["raw_sha256"], collection.sha256_bytes(raw))
            raw_path, meta_path = root / evidence["raw_file"], root / evidence["metadata_file"]
            self.assertTrue(raw_path.is_file()); self.assertTrue(meta_path.is_file())
            stored = raw_path.read_bytes()
            self.assertEqual(gzip.decompress(stored) if raw_path.suffix == ".gz" else stored, raw)
            self.assertEqual(json.loads(meta_path.read_text())["raw_sha256"], collection.sha256_bytes(raw))

    def test_missing_snapshot_in_lichess_triggers_official_coverage_check(self):
        raw, mirror_raw = payload(), lichess_payload([2014022500, 2023102679])
        subject = {**person(), "exact_dob_frozen": "1990-01-01"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry, mirror, official = self.acquire(root, raw, mirror_raw=mirror_raw, subject=subject)
            official.assert_called_once(); mirror.assert_called_once()
            self.assertEqual(entry["status"], "history_acquired")
            self.assertEqual(entry["source_provider"], "fide_official_chart")
            audit = entry["source_coverage_audit"]
            self.assertEqual(audit["reasons"], ["lichess_missing_frozen_snapshot"])
            self.assertFalse(audit["unresolved"])
            self.assert_evidence(root, audit, {"fide_official_chart": raw, "lichess_fide_history": mirror_raw})

    def test_older_person_late_lichess_history_checked_even_with_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry, _, official = self.acquire(Path(tmp), payload())
            official.assert_called_once()
            self.assertEqual(entry["snapshot_history_elo"], 2500)
            self.assertIn("lichess_late_history_for_older_person", entry["source_coverage_audit"]["reasons"])
            self.assertNotIn("lichess_missing_frozen_snapshot", entry["source_coverage_audit"]["reasons"])

    def test_independently_checked_official_is_selected_even_if_also_late_or_lower(self):
        raw = payload(records=[{"id": "123", "date": "2013-01-01", "rating": 2500},
                               {"id": "123", "date": "2023-10-01", "rating": 2600}])
        with tempfile.TemporaryDirectory() as tmp:
            entry, _, official = self.acquire(Path(tmp), raw)
            official.assert_called_once()
            self.assertEqual(entry["source_provider"], "fide_official_chart")
            self.assertEqual(entry["observed_fide_history_peak_elo_through_2023"], 2600)
            self.assertTrue(entry["source_coverage_audit"]["direct_source_coverage_checked"])
            self.assertFalse(entry["source_coverage_audit"]["unresolved"])

    def test_present_lichess_snapshot_disagreement_fails_without_official_fetch(self):
        mirror_raw = lichess_payload([2003042400, 2013012499, 2023102679])
        with tempfile.TemporaryDirectory() as tmp:
            entry, _, official = self.acquire(Path(tmp), payload(), mirror_raw=mirror_raw)
            official.assert_not_called()
            self.assertEqual(entry["status"], "failed")
            self.assertEqual(entry["error_type"], "SourceIntegrityError")

    def test_cached_lichess_coverage_repair_preserves_original_evidence(self):
        raw, mirror_raw = payload(), lichess_payload([2013012500, 2023102679])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collection.save_cache(root, "123", mirror_raw, metadata("123", mirror_raw, "lichess_fide_history"))
            entry, mirror, official = self.acquire(root, raw, mirror_raw=mirror_raw)
            mirror.assert_not_called(); official.assert_called_once()
            self.assertEqual(entry["source_provider"], "fide_official_chart")
            _, cached_meta = collection.read_cache(root, "123")
            self.assertEqual(cached_meta["source_coverage_audit"], entry["source_coverage_audit"])
            self.assert_evidence(root, entry["source_coverage_audit"],
                                 {"fide_official_chart": raw, "lichess_fide_history": mirror_raw})
            self.assertTrue(all(row["raw_file"].startswith("coverage-evidence/")
                                for row in entry["source_coverage_audit"]["sources"]))

    def test_unavailable_official_coverage_keeps_mirror_and_marks_unresolved(self):
        failure = collection.FetchFailure("unavailable", [{"attempt": 3}], b"[]")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry, _, official = self.acquire(root, payload(), chart_error=failure)
            official.assert_called_once()
            self.assertEqual(entry["source_provider"], "lichess_fide_history")
            audit = entry["source_coverage_audit"]
            self.assertTrue(audit["unresolved"])
            self.assertEqual(audit["selected_provider"], "lichess_fide_history")
            self.assertEqual(entry["status"], "history_acquired_requires_snapshot_audit")
            self.assertIn("rating_history_coverage_unresolved", entry["snapshot_audit_reasons"])
            self.assertEqual(collection.read_cache(root, "123")[1]["source_coverage_audit"], audit)

    def test_official_coverage_missing_snapshot_keeps_mirror_and_marks_unresolved(self):
        raw = payload(records=[{"id": "123", "date": "2014-01-01", "rating": 2600},
                               {"id": "123", "date": "2023-10-01", "rating": 2700}])
        with tempfile.TemporaryDirectory() as tmp:
            entry, _, official = self.acquire(Path(tmp), raw)
            official.assert_called_once()
            self.assertEqual(entry["source_provider"], "lichess_fide_history")
            self.assertTrue(entry["source_coverage_audit"]["unresolved"])
            self.assertEqual(entry["snapshot_history_elo"], 2500)
            self.assertIn("rating_history_coverage_unresolved", entry["snapshot_audit_reasons"])

    def test_official_snapshot_disagreement_fails_without_mirror_fallback(self):
        raw = payload(records=[{"id": "123", "date": "2013-01-01", "rating": 2499},
                               {"id": "123", "date": "2023-10-01", "rating": 2679}])
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(collection, "fetch_chart", return_value=(raw, metadata("123", raw))), \
             patch.object(collection, "fetch_lichess") as mirror:
            entry = collection.process_person(person(), Path(tmp), None, prefer_provider="fide")
        mirror.assert_not_called()
        self.assertEqual(entry["status"], "failed")
        self.assertEqual(entry["error_type"], "SourceIntegrityError")

    def test_coverage_http429_propagates_stop(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(collection.AcquisitionStopped):
            self.acquire(Path(tmp), payload(), chart_error=collection.AcquisitionStopped("rate limited"))


if __name__ == "__main__":
    unittest.main()
