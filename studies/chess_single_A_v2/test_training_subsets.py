"""Synthetic input tests for the fixed subset selection and provenance boundary."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("build_training_subsets", HERE / "build_training_subsets.py")
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


class SubsetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.config_path = self.root / "config.json"
        self.config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.rows = {
            "2013_M": [{"fide_id": str(500000 + i), "identity_bridge_modern_fide_id": f"000{i}",
                        "rating": str(3000 - (i - 1) // 3)} for i in range(1, 1003)],
            "2023_M_NEW_TARGET": [{"fide_id": str(20000 + i), "identity_bridge_modern_fide_id": "",
                                    "rating": str(2800 - (i - 1) // 3)} for i in range(1, 1003)],
        }
        self.acquisition = {"status": b.COMPLETE, "executing_commit": "a" * 40, "outputs": []}
        self.summary = {"status": b.COMPLETE, "development_new_overlap": 0,
                        "cross_snapshot_conflicts": 0, "cohorts": {}}
        self.write_sources()

    def write_sources(self):
        self.acquisition["outputs"] = []
        for role, filename in b.SOURCE_FILES.items():
            path = self.data / filename
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["fide_id", "identity_bridge_modern_fide_id", "rating"])
                writer.writeheader()
                writer.writerows(self.rows[role])
            digest = b.sha256(path)
            self.summary["cohorts"][role] = {"n": len(self.rows[role]), "sha256": digest,
                                            "cutoff_elo": min(int(row["rating"]) for row in self.rows[role])}
            self.acquisition["outputs"].append({"file": filename, "sha256": digest})
        self.write_metadata()

    def write_metadata(self):
        for name, value in [("manifest.json", self.acquisition), ("summary.json", self.summary)]:
            (self.data / name).write_text(json.dumps(value), encoding="utf-8")

    def build(self):
        with patch.dict("os.environ", {"GITHUB_SHA": "b" * 40}):
            return b.build_subsets(self.root, self.data, self.config_path)

    def read_subsets(self):
        groups = {}
        with (self.data / "training_subsets.csv").open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, ["label", "canonical_id", "order"])
            for row in reader:
                group = groups.setdefault(row["label"], [])
                self.assertEqual(int(row["order"]), len(group) + 1)
                group.append(row["canonical_id"])
        return groups

    def test_exact_counts_nested_random_and_known_sha_order(self):
        result = self.build()
        groups = self.read_subsets()
        expected = sorted((str(i) for i in range(1, 1003)),
                          key=lambda fid: (hashlib.sha256(("20261024\n" + fid).encode()).hexdigest(), fid))
        for size in (500, 800, 1000):
            self.assertEqual(groups[f"random_{size}"], expected[:size])
            self.assertEqual(result["subsets"][f"random_{size}"]["actual_n"], size)
        self.assertEqual(groups["random_500"], groups["random_800"][:500])
        self.assertEqual(groups["random_800"], groups["random_1000"][:800])
        self.assertFalse(self.config["fit_allowed"])
        self.assertEqual(result["status"], "subsets_fixed_no_models_fitted")

    def test_complete_rating_ties_at_all_ranked_thresholds(self):
        result = self.build()
        groups = self.read_subsets()
        for threshold, actual_n in [(500, 501), (800, 801), (1000, 1002)]:
            label = f"ranked_{threshold}_with_ties"
            self.assertEqual(set(groups[label]), {str(i) for i in range(1, actual_n + 1)})
            self.assertEqual(result["subsets"][label]["actual_n"], actual_n)
            self.assertEqual(result["subsets"][label]["cutoff_elo"], 3000 - (threshold - 1) // 3)

    def test_order_independent_and_repeatable_output(self):
        first = self.build()
        original = (self.data / "training_subsets.csv").read_bytes()
        self.rows["2013_M"].reverse()
        self.rows["2023_M_NEW_TARGET"].reverse()
        self.write_sources()
        second = self.build()
        self.assertEqual((self.data / "training_subsets.csv").read_bytes(), original)
        self.assertEqual(first["output"]["sha256"], second["output"]["sha256"])

    def test_provenance_records_inputs_config_code_and_execution_commits(self):
        result = self.build()
        self.assertEqual(result["source_executing_collector_commit"], "a" * 40)
        self.assertEqual(result["builder_executing_commit"], "b" * 40)
        self.assertEqual(result["builder_commit_source"], "GITHUB_SHA")
        self.assertEqual(result["builder_sha256"], b.sha256(HERE / "build_training_subsets.py"))
        self.assertEqual(result["config"]["sha256"], b.sha256(self.config_path))
        self.assertEqual(result["sources"]["2013_M"]["n"], 1002)
        self.assertEqual(result["development_new_overlap"], 0)

    def test_duplicate_normalized_modern_id_rejected(self):
        self.rows["2013_M"][1]["identity_bridge_modern_fide_id"] = "01"
        self.write_sources()
        with self.assertRaisesRegex(ValueError, "Duplicate canonical ID"):
            self.build()

    def test_actual_overlap_rejected_even_if_summary_says_zero(self):
        self.rows["2023_M_NEW_TARGET"][0]["identity_bridge_modern_fide_id"] = "0001"
        self.write_sources()
        with self.assertRaisesRegex(ValueError, "identity overlap"):
            self.build()

    def test_wrong_summary_fingerprint_rejected(self):
        self.summary["cohorts"]["2013_M"]["sha256"] = "0" * 64
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            self.build()

    def test_wrong_acquisition_manifest_fingerprint_rejected(self):
        self.acquisition["outputs"][0]["sha256"] = "0" * 64
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            self.build()

    def test_incomplete_acquisition_and_summary_each_rejected(self):
        for metadata in (self.acquisition, self.summary):
            metadata["status"] = "acquisition_incomplete"
            self.write_metadata()
            with self.assertRaisesRegex(ValueError, "must both be complete"):
                self.build()
            metadata["status"] = b.COMPLETE

    def test_partial_cohort_cannot_be_labeled_complete(self):
        self.rows["2013_M"] = self.rows["2013_M"][:999]
        self.write_sources()
        with self.assertRaisesRegex(ValueError, "fewer than 1000"):
            self.build()

    def test_config_seed_change_requires_amendment(self):
        self.config["training_subsets"]["random_seed"] += 1
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fixed v2 subset design"):
            self.build()

    def test_failed_rerun_invalidates_stale_complete_subset_output(self):
        self.build()
        self.acquisition["status"] = "acquisition_incomplete"
        self.write_metadata()
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse((self.data / "training_subsets.csv").exists())
        manifest = json.loads((self.data / "subset_manifest.json").read_text())
        self.assertEqual(manifest["status"], "subset_build_incomplete_no_models_fitted")


if __name__ == "__main__":
    unittest.main()
