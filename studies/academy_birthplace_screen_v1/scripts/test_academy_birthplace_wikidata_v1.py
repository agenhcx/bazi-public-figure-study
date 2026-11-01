"""Offline tests: ambiguity, row conservation, exact external links, retries and provenance."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import academy_birthplace_wikidata_v1 as m


def item(prop, qid, rank="normal", claim_id=None):
    return {"id": claim_id or prop + "$" + qid, "rank": rank,
            "mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": qid}}}}


def coordinate(lat, lon=1, precision=0.001, globe="http://www.wikidata.org/entity/Q2", rank="normal"):
    return {"id": "P625$" + str(lat), "rank": rank, "mainsnak": {"snaktype": "value",
            "datavalue": {"value": {"latitude": lat, "longitude": lon, "precision": precision, "globe": globe}}}}


def entity(claims, label="Place"):
    return {"claims": claims, "labels": {"en": {"value": label}}}


class FixtureClient:
    def __init__(self, entities=None, errors=None, bindings=None, query_error=False):
        self.data = entities or {}
        self.errors = errors or {}
        self.bindings = bindings or []
        self.query_error = query_error
        self.entity_calls = []

    def entities(self, qids):
        ids = sorted(set(qids))
        self.entity_calls.append(ids)
        good = {q: self.data[q] for q in ids if q in self.data and q not in self.errors}
        return good, {q: {"response_sha256": "fixture", "url": "fixture://api", "retrieved_utc": "fixture"} for q in good}, {
            q: self.errors.get(q, "fixture_missing") for q in ids if q not in good}

    def request_json(self, url):
        if self.query_error:
            raise m.FetchFailure("fixture_query_failure")
        return {"results": {"bindings": self.bindings}}, {"response_sha256": "fixture", "url": url}


def seed(record_id="a", qid="Q1", **extra):
    return {"cohort": "test", "record_id": record_id, "name": "Original Name", "dob": "1901-02-03", "qid": qid, **extra}


def binding(external_id, qid):
    return {"externalId": {"value": external_id}, "person": {"value": "http://www.wikidata.org/entity/" + qid}}


class ScreeningTests(unittest.TestCase):
    def test_direct_birthplace_only_and_deprecated_excluded(self):
        data = {"Q1": entity({"P19": [item("P19", "Q2"), item("P19", "Q3", "deprecated")],
                               "P625": [coordinate(-50)]}),
                "Q2": entity({"P625": [coordinate(30), coordinate(-30, rank="deprecated")]})}
        result = m.screen([seed()], FixtureClient(data))[0]
        self.assertEqual((result["hemisphere"], result["lat"]), ("north", 30))
        self.assertEqual(result["dob"], "1901-02-03")
        self.assertFalse(result["dob_or_acceptance_modified"])
        self.assertEqual(result["birthplace_source_grade"], "S3")

    def test_multiple_birthplaces_and_coordinates_stay_unknown(self):
        data = {"Q1": entity({"P19": [item("P19", "Q2"), item("P19", "Q3")]}),
                "Q2": entity({"P625": [coordinate(20)]}), "Q3": entity({"P625": [coordinate(21)]})}
        self.assertEqual(m.screen([seed()], FixtureClient(data))[0]["reason"], "multiple_distinct_birthplace_P19_conflict")
        data["Q1"]["claims"]["P19"] = [item("P19", "Q2")]
        data["Q2"]["claims"]["P625"] = [coordinate(20), coordinate(-20)]
        self.assertEqual(m.screen([seed()], FixtureClient(data))[0]["reason"], "multiple_distinct_direct_coordinates_conflict")

    def test_country_non_earth_and_precision_are_not_shortcuts(self):
        data = {"Q1": entity({"P19": [item("P19", "Q2")]}),
                "Q2": entity({"P625": [coordinate(-10)], "P31": [item("P31", "Q6256")]})}
        self.assertEqual(m.screen([seed()], FixtureClient(data))[0]["reason"], "broad_birthplace_needs_extent")
        data["Q2"]["claims"] = {"P625": [coordinate(5, globe="http://www.wikidata.org/entity/Q111")]}
        self.assertEqual(m.screen([seed()], FixtureClient(data))[0]["reason"], "no_valid_direct_earth_P625")
        data["Q2"]["claims"] = {"P625": [coordinate(0.01, precision=0.1)]}
        self.assertEqual(m.screen([seed()], FixtureClient(data))[0]["reason"], "coordinate_precision_interval_touches_equator")

    def test_shared_qid_and_duplicate_seeds_conserve_rows(self):
        client = FixtureClient({"Q1": entity({"P19": [item("P19", "Q2")]}), "Q2": entity({"P625": [coordinate(-33)]})})
        rows = m.screen([seed(), seed("b"), seed()], client)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["hemisphere"] for r in rows], ["south"] * 3)
        self.assertEqual([r["duplicate_record_key"] for r in rows], [True, False, True])
        self.assertEqual(client.entity_calls[0], ["Q1"])

    def test_fetch_failures_and_no_safe_identity_retain_rows(self):
        client = FixtureClient(errors={"Q1": "fixture_timeout"})
        rows = m.screen([seed(), seed("b", ""), seed("c", "not_a_qid")], client)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["hemisphere"] == "unknown" for r in rows))
        self.assertEqual(rows[0]["reason"], "person_fetch_failed:fixture_timeout")
        self.assertEqual(rows[1]["reason"], "no_safe_qid")
        self.assertEqual(rows[2]["reason"], "invalid_qid")

    def test_exact_external_id_one_to_one_only(self):
        external = lambda rid, eid: seed(rid, "", external_id_property="P8612", external_id=eid)
        bindings = [binding("NA1", "Q10"), binding("NA2", "Q20"), binding("NA2", "Q21"),
                    binding("NA3", "Q30"), binding("NA4", "Q30"), binding("UNREQUESTED", "Q10")]
        client = FixtureClient(bindings=bindings)
        matches, provenance, errors = m.resolve_external_seeds([external("a", "NA1"), external("b", "NA2"),
            external("c", "NA3"), external("d", "NA4"), external("e", "NA5")], client)
        self.assertEqual(matches, {("P8612", "NA1"): "Q10"})
        self.assertEqual(provenance[("P8612", "NA1")]["source_grade"], "S3")
        self.assertEqual(errors[("P8612", "NA2")], "external_id_multiple_qids")
        self.assertEqual(errors[("P8612", "NA3")], "qid_multiple_input_external_ids")
        self.assertEqual(errors[("P8612", "NA5")], "external_id_no_match")

    def test_external_id_query_error_does_not_drop_seed(self):
        rows = m.screen([seed("a", "", external_id_property="P8612", external_id="NA1")], FixtureClient(query_error=True))
        self.assertEqual(len(rows), 1)
        self.assertIn("external_id_query_failed", rows[0]["reason"])


class TransportTests(unittest.TestCase):
    def test_success_cache_resume_and_corruption_requires_refetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = b'{"entities":{}}'
            with patch.object(m, "urlopen", return_value=io.BytesIO(body)) as transport:
                client = m.Client(tmp, interval=0)
                _, meta = client.request_json("https://example.test/api")
                self.assertEqual(meta["response_sha256"], m.sha(body))
                client.request_json("https://example.test/api")
                self.assertEqual(transport.call_count, 1)
                (Path(tmp) / meta["raw_response_file"]).write_bytes(b"tampered")
                with patch.object(m, "urlopen", return_value=io.BytesIO(body)) as second:
                    client.request_json("https://example.test/api")
                    self.assertEqual(second.call_count, 1)

    def test_retry_after_and_request_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            error = HTTPError("https://example.test/api", 429, "rate limited", {"Retry-After": "12"}, None)
            with patch.object(m, "urlopen", side_effect=[error, io.BytesIO(b'{"entities":{}}')]) as transport, patch.object(m.time, "sleep") as sleep:
                m.Client(tmp, interval=0).request_json("https://example.test/api")
                self.assertEqual(transport.call_count, 2)
                self.assertTrue(any(call.args[0] >= 12 for call in sleep.call_args_list))
            with self.assertRaisesRegex(m.FetchFailure, "request_budget_exhausted"):
                m.Client(tmp, max_requests=0).request_json("https://different.test/api")


if __name__ == "__main__":
    unittest.main()
