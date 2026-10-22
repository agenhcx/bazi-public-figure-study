import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("independent_audit", HERE / "audit_completed_cohorts.py")
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def row(fid, elo, snapshot="2013-01", qid=None):
    return {"fide_id": str(fid), "identity_bridge_modern_fide_id": str(fid),
            "name": f"Player{fid}", "rating": str(elo), "snapshot": snapshot,
            "sex": "M", "active": "True", "eligible": "True", "birth_year": "1990",
            "exact_dob_frozen": "1990-02-03", "birthplace_hemisphere": "north",
            "birthplace_latitudes": "40.0", "wikidata_person_qids": qid or f"Q{1000 + fid}",
            "evidence_source": "new_wikidata_best_rank_query",
            "dob_calendar_status": "explicit_gregorian_required"}


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class IndependentAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.new_target = 2
        self.rows = {
            "candidate_audit_2013_M.csv": [row(1, 2700), row(2, 2600), row(3, 2600)],
            "cohort_2013_M.csv": [row(1, 2700), row(2, 2600), row(3, 2600)],
            "candidate_audit_2023_M.csv": [row(1, 2800, "2023-01"), row(4, 2700, "2023-01"), row(5, 2600, "2023-01")],
            "cohort_2023_M_FULL.csv": [row(1, 2800, "2023-01"), row(4, 2700, "2023-01")],
            "cohort_2023_M_NEW_TARGET.csv": [row(4, 2700, "2023-01"), row(5, 2600, "2023-01")],
            "excluded_legacy_ids.csv": [{"canonical_id": str(fid)} for fid in (1, 2, 3, 10, 11, 12)],
        }
        for path, fid in zip(a.LEGACY_PATHS, (10, 11, 1, 12)):
            write_csv(self.root / path, [row(fid, 2700)])
        self.save()

    def save(self):
        for name, rows in self.rows.items():
            write_csv(self.data / name, rows)
        outputs = [{"file": name, "sha256": a.digest(self.data / name)} for name in self.rows]
        manifest = {"status": a.COMPLETE, "executing_commit": "a" * 40,
                    "rules": {"target": 2, "new_target": self.new_target}, "outputs": outputs,
                    "collector_sha256": a.digest(HERE / "collect_cohorts.py"),
                    "protocol_sha256": a.digest(HERE / "acquisition_protocol.md")}
        summary = {"status": a.COMPLETE, "target": 2, "new_target": self.new_target, "cohorts": {}}
        for group, paths in a.COHORTS.items():
            rows = self.rows[paths[0]]
            summary["cohorts"][group] = {"n": len(rows), "cutoff_elo": min(int(r["rating"]) for r in rows),
                                         "sha256": a.digest(self.data / paths[0])}
        (self.data / "manifest.json").write_text(json.dumps(manifest))
        (self.data / "summary.json").write_text(json.dumps(summary))

    def run_audit(self):
        return a.audit(self.root, self.data, expected_target=2, expected_new_target=self.new_target)

    def test_valid_complete_ties_and_independent_people(self):
        result = self.run_audit()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["cohorts"]["2013_M"]["n"], 3)
        self.assertEqual(result["overlaps"]["development_new_person_qids"], 0)

    def test_new_target_is_independent_of_development_and_full_targets(self):
        self.new_target = 1
        self.rows["cohort_2023_M_NEW_TARGET.csv"] = [row(4, 2700, "2023-01")]
        self.save()
        result = self.run_audit()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["cohorts"]["2013_M"]["target_n"], 2)
        self.assertEqual(result["cohorts"]["2023_M_FULL"]["target_n"], 2)
        self.assertEqual(result["cohorts"]["2023_M_NEW_TARGET"]["target_n"], 1)

    def test_wrong_new_target_does_not_silently_pass(self):
        result = a.audit(self.root, self.data, expected_target=2, expected_new_target=1)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("NEW target changed" in message for message in result["errors"]))

    def test_dropped_boundary_tie_fails_even_with_updated_hashes(self):
        self.rows["cohort_2013_M.csv"].pop()
        self.rows["excluded_legacy_ids.csv"] = [{"canonical_id": str(fid)} for fid in (1, 2, 10, 11, 12)]
        self.save()
        result = self.run_audit()
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("all eligible cutoff ties" in message for message in result["errors"]))

    def test_qid_alias_catches_leakage_with_different_fide_ids(self):
        for name, rows in self.rows.items():
            if "2023" in name:
                for record in rows:
                    if record["fide_id"] == "4":
                        record["wikidata_person_qids"] = "Q1002"
        self.save()
        result = self.run_audit()
        self.assertEqual(result["overlaps"]["development_new_canonical_ids"], 0)
        self.assertEqual(result["overlaps"]["development_new_person_qids"], 1)
        self.assertTrue(any("alias leakage" in message for message in result["errors"]))

    def test_legacy_qid_alias_is_also_excluded(self):
        for name, rows in self.rows.items():
            if "2023" in name:
                for record in rows:
                    if record["fide_id"] == "4":
                        record["wikidata_person_qids"] = "Q1010"
        self.save()
        result = self.run_audit()
        self.assertEqual(result["overlaps"]["legacy_new_person_qids"], 1)
        self.assertTrue(any("Legacy/NEW" in message for message in result["errors"]))

    def test_unrecorded_output_change_fails_hash_check(self):
        path = self.data / "cohort_2013_M.csv"
        path.write_text(path.read_text() + "\n")
        result = self.run_audit()
        self.assertTrue(any("Output hash mismatch" in message for message in result["errors"]))

    def test_unverified_new_calendar_is_rejected(self):
        for name, rows in self.rows.items():
            if "2023" in name:
                for record in rows:
                    record["dob_calendar_status"] = "unknown"
        self.save()
        result = self.run_audit()
        self.assertTrue(any("not explicitly Gregorian" in message for message in result["errors"]))


if __name__ == "__main__":
    unittest.main()
