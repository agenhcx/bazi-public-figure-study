"""Offline SPARQL fixtures; originals also run against the compatible optimized module."""
import unittest
import academy_birthplace_wikidata_v1_sparql_people as m
import test_academy_birthplace_wikidata_v1 as original_tests


def row(person, statement=None, rank="NormalRank", birthplace=None, novalue=False):
    out = {"person": {"type": "uri", "value": "http://www.wikidata.org/entity/" + person}}
    if statement:
        out["statement"] = {"type": "uri", "value": "http://www.wikidata.org/entity/statement/" + statement}
        out["rank"] = {"type": "uri", "value": "http://wikiba.se/ontology#" + rank}
        out["isNoValue"] = {"type": "literal", "value": str(novalue).lower()}
    if birthplace is not None:
        out["birthplace"] = birthplace
    return out


class OptimizedPeopleTests(unittest.TestCase):
    def test_all_requested_people_and_snak_rank_distinctions_preserved(self):
        payload = {"results": {"bindings": [
            row("Q1", "Q1-abc", birthplace={"type": "uri", "value": "http://www.wikidata.org/entity/Q10"}),
            row("Q1", "Q1-def", rank="DeprecatedRank", birthplace={"type": "uri", "value": "http://www.wikidata.org/entity/Q11"}),
            row("Q2", "Q2-abc", birthplace={"type": "bnode", "value": "b123"}),
            row("Q3", "Q3-abc", novalue=True),
            row("Q4"),
            row("Q5", "Q5-abc", birthplace={"type": "uri", "value": "http://www.wikidata.org/.well-known/genid/xyz"}),
        ]}}
        entities = m.parse_person_p19_response(["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"], payload)
        self.assertEqual(set(entities), {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"})
        self.assertEqual(entities["Q1"]["claims"]["P19"][0]["id"], "Q1$abc")
        self.assertEqual(entities["Q1"]["claims"]["P19"][1]["rank"], "deprecated")
        self.assertEqual(m.item_values(entities["Q1"], "P19")[0]["qid"], "Q10")
        self.assertEqual(entities["Q2"]["claims"]["P19"][0]["mainsnak"]["snaktype"], "somevalue")
        self.assertEqual(entities["Q3"]["claims"]["P19"][0]["mainsnak"]["snaktype"], "novalue")
        self.assertEqual(entities["Q4"]["claims"]["P19"], [])
        self.assertEqual(entities["Q5"]["claims"]["P19"][0]["mainsnak"]["snaktype"], "somevalue")

    def test_people_transport_batches_and_error_row_conservation(self):
        import tempfile
        from unittest.mock import patch
        qids = ["Q" + str(i) for i in range(1, 202)]
        with tempfile.TemporaryDirectory() as tmp:
            client = m.Client(tmp, person_sparql=True, person_sparql_batch_size=200)
            with patch.object(client, "request_json", side_effect=[({"results": {"bindings": []}}, {"url": "fixture"}), m.FetchFailure("fixture_timeout")]):
                good, evidence, errors = client.people(qids)
            self.assertEqual(len(good), 200)
            self.assertEqual(errors, {"Q201": "fixture_timeout"})
            self.assertEqual(len(evidence), 200)
            self.assertTrue(all(entity["claims"]["P19"] == [] for entity in good.values()))

    def test_output_records_deprecated_and_nonvalue_statements(self):
        people = m.parse_person_p19_response(["Q1"], {"results": {"bindings": [
            row("Q1", "Q1-abc", birthplace={"type": "uri", "value": "http://www.wikidata.org/entity/Q10"}),
            row("Q1", "Q1-def", rank="DeprecatedRank", birthplace={"type": "bnode", "value": "some"}),
        ]}})
        client = original_tests.FixtureClient({**people, "Q10": original_tests.entity({"P625": [original_tests.coordinate(25)]})})
        out = m.screen([original_tests.seed()], client)[0]
        self.assertEqual(out["hemisphere"], "north")
        self.assertEqual(len(out["person_birthplace_statement_inventory"]), 2)
        self.assertEqual(out["person_birthplace_statement_inventory"][1]["snaktype"], "somevalue")
        self.assertEqual(out["person_birthplace_statement_inventory"][1]["rank"], "deprecated")

    def test_unexpected_person_and_invalid_seed_rejected(self):
        with self.assertRaises(m.FetchFailure):
            m.parse_person_p19_response(["Q1"], {"results": {"bindings": [row("Q2")]}})
        with self.assertRaises(ValueError):
            m.person_p19_query(["Q1", "Q2 } UNION {}"])


if __name__ == "__main__":
    # Reuse the nine meaningful original cases against the compatible module too.
    original_tests.m = m
    suite = unittest.defaultTestLoader.loadTestsFromModule(original_tests)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(OptimizedPeopleTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
