"""Synthetic checks for nested selection and sealing; no research-data fitting."""
from __future__ import annotations

import json
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train


CONFIG = {"cv": {"outer": {"n_splits": 5, "shuffle": True, "random_state": 20261021},
                   "inner": {"n_splits": 4, "shuffle": True, "random_state": 20261022}},
          "selection": {"tie_tolerance_mae": 1e-12}}


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({"row": np.arange(11)})
        self.y = np.arange(11, dtype=float)

    def test_pooling_uses_people_not_mean_of_fold_maes(self):
        def fitting(candidate, X, y, validation):
            error = 4 if len(validation) == 2 else 1
            prediction = validation["row"].to_numpy(dtype=float) + error
            return prediction, {"status": "complete", "warnings": []}
        choice = {"candidate_id": "c"}
        result = train.search_candidates(self.frame, self.y, CONFIG, [choice], lambda c: c, fitting)
        self.assertAlmostEqual(result["selected_inner_mae"], 17 / 11)
        self.assertNotAlmostEqual(result["selected_inner_mae"], (1 + 1 + 1 + 4) / 4)

    def test_each_fit_receives_only_inner_training_rows(self):
        def fitting(candidate, X, y, validation):
            self.assertFalse(set(X["row"]) & set(validation["row"]))
            np.testing.assert_array_equal(X["row"], y)
            return validation["row"].to_numpy(dtype=float), {"status": "complete", "warnings": []}
        result = train.search_candidates(self.frame, self.y, CONFIG, [{"candidate_id": "c"}], lambda c: c, fitting)
        self.assertEqual(result["selected_inner_mae"], 0)
        self.assertEqual(len(result["candidate_results"][0]["folds"]), 4)

    def test_any_bad_fold_invalidates_entire_candidate(self):
        calls = {"bad": 0, "good": 0}
        def fitting(candidate, X, y, validation):
            name = candidate["candidate_id"]
            calls[name] += 1
            if name == "bad" and calls[name] == 2:
                return np.full(len(validation), np.nan), {"status": "complete", "warnings": []}
            return validation["row"].to_numpy(dtype=float) + (0 if name == "bad" else 1), {
                "status": "complete", "warnings": []}
        result = train.search_candidates(self.frame, self.y, CONFIG,
            [{"candidate_id": "bad"}, {"candidate_id": "good"}], lambda c: c, fitting)
        self.assertEqual(result["selected_candidate_id"], "good")
        self.assertEqual(result["candidate_results"][0]["status"], "invalid")
        self.assertIsNone(result["candidate_results"][0]["mae"])
        self.assertEqual(calls, {"bad": 2, "good": 4})

    def test_tie_rule_uses_minimum_plus_tolerance_in_original_order(self):
        rows = [{"status": "complete", "mae": 2 + 0.8e-12, "id": "first"},
                {"status": "complete", "mae": 2, "id": "minimum"},
                {"status": "complete", "mae": 2 + 0.2e-12, "id": "third"}]
        self.assertEqual(train.first_best(rows, 1e-12)["id"], "first")
        with self.assertRaises(RuntimeError):
            train.first_best([{"status": "invalid", "mae": None}], 1e-12)

    def test_nonfinite_targets_and_duplicate_candidates_fail(self):
        with self.assertRaises(ValueError):
            train.search_candidates(self.frame, np.full(11, np.nan), CONFIG, [{"candidate_id": "c"}], lambda c: c)
        with self.assertRaises(ValueError):
            train.search_candidates(self.frame, self.y, CONFIG,
                [{"candidate_id": "c"}, {"candidate_id": "c"}], lambda c: c)

    def test_warning_fits_retained_and_counted(self):
        def fitting(candidate, X, y, validation):
            return np.zeros(len(validation)), {"status": "complete", "warnings": [
                {"category": "ConvergenceWarning", "message": "synthetic"}]}
        result = train.search_candidates(self.frame, self.y, CONFIG, [{"candidate_id": "c"}], lambda c: c, fitting)
        self.assertEqual(train.search_stats(result), {"candidates": 1, "valid_candidates": 1,
            "invalid_candidates": 0, "fit_entries": 4, "warning_records": 4,
            "convergence_warnings": 4, "failed_fit_entries": 0})

    def test_seal_search_validation_recomputes_pooled_score(self):
        choice = {"candidate_id": "c"}
        def fitting(candidate, X, y, validation):
            return validation["row"].to_numpy(dtype=float) + 1, {"status": "complete", "warnings": []}
        result = train.search_candidates(self.frame, self.y, CONFIG, [choice], lambda c: c, fitting)
        self.assertEqual(train._validate_search(result, [choice], self.y, CONFIG)["mae"], 1)
        altered = copy.deepcopy(result)
        altered["candidate_results"][0]["mae"] = 0
        with self.assertRaisesRegex(ValueError, "pooled OOF"):
            train._validate_search(altered, [choice], self.y, CONFIG)
        altered = copy.deepcopy(result)
        altered["candidate_results"][0]["folds"][0]["training_n"] = 999
        with self.assertRaisesRegex(ValueError, "fold sizes"):
            train._validate_search(altered, [choice], self.y, CONFIG)


class TaskSplitTests(unittest.TestCase):
    def setUp(self):
        self.ids = list(map(str, range(1, 1001)))
        self.frame = pd.DataFrame({"canonical_id": self.ids, "rating": np.arange(1000)})

    def test_outer_folds_are_disjoint_cover_pool_and_use_full_800(self):
        heldout = []
        for fold in range(5):
            training, validation = train.task_frames(self.frame, f"outer-{fold}", CONFIG, self.ids)
            self.assertEqual(len(training), 800)
            self.assertEqual(len(validation), 200)
            self.assertEqual(training["canonical_id"].tolist(), sorted(training["canonical_id"]))
            self.assertFalse(set(training["canonical_id"]) & set(validation["canonical_id"]))
            heldout.extend(validation["canonical_id"])
        self.assertEqual(sorted(heldout), sorted(self.ids))

    def test_final_order_and_bad_tasks(self):
        training, validation = train.task_frames(self.frame, "final", CONFIG, self.ids)
        self.assertIsNone(validation)
        self.assertEqual(training["canonical_id"].tolist(), sorted(self.ids))
        with self.assertRaises(ValueError):
            train.task_frames(self.frame, "outer-5", CONFIG, self.ids)
        with self.assertRaises(ValueError):
            train.task_frames(self.frame, "final", CONFIG, self.ids[:-1] + [self.ids[0]])


class SealTests(unittest.TestCase):
    def test_seal_is_immutable_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / train.STUDY).mkdir(parents=True)
            train.write_json(root / train.SOURCE_LOCK, {"fixed": "source"})
            inputs = root / "outputs"
            inputs.mkdir()
            inventory = {"tasks": {"final": {"directory": "final", "manifest_sha256": "a"}},
                         "files": {"final/model.joblib": "b"}}
            # Synthetic inventory is injected here; production invokes full CV/input/file validation.
            with patch.dict(sys.modules, {"lock_b1": type("Lock", (), {"verify_lock": staticmethod(lambda root: {})})}), \
                 patch.object(train, "_validate_task_outputs", return_value=inventory):
                seal = train.seal_models(root, inputs)
                original = (inputs / train.SEAL_NAME).read_bytes()
                self.assertEqual(train.seal_models(root, inputs), seal)
                self.assertEqual((inputs / train.SEAL_NAME).read_bytes(), original)
                inventory["files"]["final/model.joblib"] = "changed"
                with self.assertRaises(ValueError):
                    train.verify_seal(root, inputs)

    def test_safe_file_rejects_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "inside"
            base.mkdir()
            (base.parent / "outside").write_text("x")
            with self.assertRaises(ValueError):
                train._safe_file(base, "../outside")


if __name__ == "__main__":
    unittest.main()
