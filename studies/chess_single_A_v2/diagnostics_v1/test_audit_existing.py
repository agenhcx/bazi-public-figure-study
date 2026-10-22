"""Synthetic checks for read-only A1 diagnostics; no research-data fitting."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import audit_existing as audit


class ExistingAuditTests(unittest.TestCase):
    def test_metrics_and_nonfinite_rejection(self):
        actual = audit.metrics([1, 5], [3, 4])
        self.assertEqual(actual["n"], 2)
        self.assertEqual(actual["mae"], 1.5)
        self.assertAlmostEqual(actual["rmse"], np.sqrt(2.5))
        with self.assertRaises(ValueError):
            audit.metrics([1, 2], [1, np.nan])
        with self.assertRaises(ValueError):
            audit.metrics([1, 2], [[1, 2]])

    def test_inner_median_comes_only_from_fold_training_people(self):
        ids = ["a", "b", "c", "d"]
        folds = [
            {"training_ids": ["a", "b"], "validation_ids": ["c", "d"]},
            {"training_ids": ["c", "d"], "validation_ids": ["a", "b"]},
        ]
        predictions = audit.inner_median_predictions(ids, [0, 100, 200, 300], folds)
        np.testing.assert_array_equal(predictions, [250, 250, 50, 50])

    def test_inner_fold_leakage_or_missing_person_is_rejected(self):
        bad = [{"training_ids": ["a", "b"], "validation_ids": ["b", "c"]}]
        with self.assertRaises(ValueError):
            audit.inner_median_predictions(["a", "b", "c"], [1, 2, 3], bad)
        incomplete = [{"training_ids": ["a"], "validation_ids": ["b"]}]
        with self.assertRaises(ValueError):
            audit.inner_median_predictions(["a", "b"], [1, 2], incomplete)

    def test_three_seed_warnings_are_one_fit_entry(self):
        diagnostics = {"status": "complete", "warnings": [
            {"category": "ConvergenceWarning", "message": "limit"} for _ in range(3)]}
        row = audit.warning_fit_row("fake", "raw_A", "small_mlp", "inner_search", diagnostics, "mlp", 0)
        self.assertEqual(row["fit_entries"], 1)
        self.assertEqual(row["fit_entries_with_convergence_warning"], 1)
        self.assertEqual(row["convergence_warning_records"], 3)
        quiet = audit.warning_fit_row("fake", "raw_A", "small_mlp", "inner_search", {"warnings": []}, "mlp", 1)
        summary = audit.warning_summary([row, quiet]).iloc[0]
        self.assertEqual(summary["fit_entries"], 2)
        self.assertEqual(summary["fraction_fit_entries_with_convergence_warning"], 0.5)

    def _checkpoint(self, base: Path):
        root = base / "repo"
        runs = base / "checkpoint/runs"
        study = root / audit.STUDY
        (study / "data").mkdir(parents=True)
        refs = {}
        for key, name in [("config_sha256", "config.json"),
                          ("analysis_lock_sha256", "analysis_lock.json"),
                          ("data_manifest_sha256", "data/data_manifest.json")]:
            path = study / name
            path.write_text("{}\n")
            refs[key] = audit.sha256(path)
        sealed = []
        for task in sorted(audit.EXPECTED_TASKS):
            folder = runs / f"fit-{task}"
            folder.mkdir(parents=True)
            payload = folder / "test.txt"
            payload.write_text("unchanged")
            files = [{"path": payload.name, "sha256": audit.sha256(payload)}]
            manifest = {"task": task, "status": "complete", "external_data_loaded": False,
                        "executing_commit": "frozen", "files": files, **refs}
            path = folder / "trainer_manifest.json"
            path.write_text(json.dumps(manifest))
            sealed.append({"task": task, "manifest_path": path.relative_to(runs).as_posix(),
                           "manifest_sha256": audit.sha256(path), "files": files})
        seal = {"status": "all_prespecified_models_sealed_before_external_evaluation",
                "external_predictions_or_scores_created": False, "execution_commit": "frozen",
                "reference_hashes": refs, "task_count": 20, "tasks": sealed}
        (runs.parent / "fitted_models_lock.json").write_text(json.dumps(seal))
        return root, runs

    def test_complete_twenty_task_seal_is_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, runs = self._checkpoint(Path(temporary))
            seal, tasks = audit.verify_checkpoint(root, runs)
            self.assertEqual(seal["task_count"], 20)
            self.assertEqual(len(tasks), 20)

    def test_sealed_file_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, runs = self._checkpoint(Path(temporary))
            next(runs.rglob("test.txt")).write_text("changed")
            with self.assertRaisesRegex(ValueError, "Changed sealed file"):
                audit.verify_checkpoint(root, runs)

    def test_manifest_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, runs = self._checkpoint(Path(temporary))
            next(runs.rglob("trainer_manifest.json")).write_text("{}")
            with self.assertRaisesRegex(ValueError, "Changed task manifest"):
                audit.verify_checkpoint(root, runs)

    def test_unsealed_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, runs = self._checkpoint(Path(temporary))
            extra = runs / "extra"
            extra.mkdir()
            (extra / "trainer_manifest.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Unsealed or missing"):
                audit.verify_checkpoint(root, runs)


if __name__ == "__main__":
    unittest.main()
