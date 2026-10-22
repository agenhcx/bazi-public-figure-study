"""Synthetic-only tests: never fit the chess research outcomes."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("train_models", HERE / "train_models.py")
t = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t)


def config():
    return {
        "fit_allowed": True,
        "cv": {
            "inner": {"n_splits": 4, "shuffle": True, "random_state": 20261022},
            "outer": {"n_splits": 5, "shuffle": True, "random_state": 20261021},
        },
        "learning_curve": {"subset_permutation_seed": 20261024},
        "selection": {"tie_tolerance_mae": 1e-12},
    }


def candidate(name="constant_000", family="constant", value=0.0):
    return {"candidate_id": name, "family": family, "params": {"value": value}}


class ConstantEstimator:
    def __init__(self, value=0.0, warn=False, nonfinite=False, fail=False):
        self.value, self.warn, self.nonfinite, self.fail = value, warn, nonfinite, fail

    def fit(self, X, y):
        if self.warn:
            warnings.warn("synthetic iteration limit", ConvergenceWarning)
        if self.fail:
            raise FloatingPointError("synthetic numeric failure")
        self.training_mean = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), np.nan if self.nonfinite else self.value, dtype=float)


def factory(c, unused):
    return ConstantEstimator(c["params"]["value"])


class SearchTests(unittest.TestCase):
    def test_pooled_per_person_mae_not_equal_fold_average(self):
        c = config()
        c["cv"]["inner"]["n_splits"] = 3
        X, y = np.arange(7).reshape(-1, 1), np.array([0, 1, 2, 3, 4, 5, 100.0])
        found = t.search_candidates(X, y, c, [candidate()], factory)
        row = found["candidate_results"][0]
        self.assertEqual(row["mae"], float(np.mean(np.abs(y))))
        fold_average = np.mean([
            fold["absolute_error_sum"] / fold["validation_n"] for fold in row["folds"]])
        self.assertNotAlmostEqual(row["mae"], fold_average)
        self.assertEqual(row["oof_predictions"], [0.0] * 7)

    def test_global_tie_policy_selects_first_within_minimum_tolerance(self):
        rows = [
            {"candidate_id": "a", "status": "complete", "mae": 1.0},
            {"candidate_id": "b", "status": "complete", "mae": 1.0 - 0.75e-12},
            {"candidate_id": "c", "status": "complete", "mae": 1.0 - 1.5e-12},
        ]
        self.assertEqual(t._first_best(rows, 1e-12)["candidate_id"], "b")

    def test_first_exact_tie_and_family_specific_selection(self):
        candidates = [candidate("a", "family_one", 1), candidate("b", "family_two", 1),
                      candidate("c", "family_one", 10)]
        found = t.search_candidates(np.zeros((8, 1)), np.zeros(8), config(), candidates, factory)
        self.assertEqual(found["selected_candidate_id"], "a")
        self.assertEqual(found["family_best"]["family_one"]["candidate_id"], "a")
        self.assertEqual(found["family_best"]["family_two"]["candidate_id"], "b")

    def test_one_failed_fold_invalidates_whole_candidate(self):
        calls = []
        def failing_factory(c, unused):
            calls.append(c["candidate_id"])
            return ConstantEstimator(0, fail=c["candidate_id"] == "broken" and calls.count("broken") == 2)
        found = t.search_candidates(
            np.zeros((8, 1)), np.zeros(8), config(),
            [candidate("broken"), candidate("valid", value=2)], failing_factory)
        broken = found["candidate_results"][0]
        self.assertEqual(broken["status"], "invalid")
        self.assertIsNone(broken["mae"])
        self.assertIsNone(broken["oof_predictions"])
        self.assertEqual(len(broken["folds"]), 2)
        self.assertEqual(found["selected_candidate_id"], "valid")

    def test_nonfinite_candidate_not_promoted_and_invalid_family_explicit(self):
        def nonfinite_factory(c, unused):
            return ConstantEstimator(1, nonfinite=c["family"] == "bad")
        found = t.search_candidates(
            np.zeros((8, 1)), np.zeros(8), config(),
            [candidate("bad", "bad"), candidate("good", "good")], nonfinite_factory)
        self.assertIsNone(found["family_best"]["bad"])
        self.assertEqual(found["selected_family"], "good")
        self.assertEqual(found["candidate_results"][0]["folds"][0]["error_type"], "FloatingPointError")

    def test_all_invalid_stops_instead_of_expanding_search(self):
        with self.assertRaisesRegex(RuntimeError, "All candidate"):
            t.search_candidates(np.zeros((8, 1)), np.zeros(8), config(), [candidate()],
                                lambda c, cfg: ConstantEstimator(nonfinite=True))

    def test_finite_convergence_warning_is_retained(self):
        found = t.search_candidates(
            np.zeros((8, 1)), np.zeros(8), config(), [candidate()],
            lambda c, cfg: ConstantEstimator(warn=True))
        self.assertEqual(found["candidate_results"][0]["status"], "complete")
        captured = [warning for fold in found["candidate_results"][0]["folds"]
                    for warning in fold["warnings"]]
        self.assertEqual(len(captured), 4)
        self.assertEqual(captured[0]["category"], "ConvergenceWarning")

    def test_training_folds_never_include_their_validation_rows(self):
        recorded = []
        class Memorizer(ConstantEstimator):
            def fit(self, X, y):
                self.seen = set(X[:, 0])
                return super().fit(X, y)
            def predict(self, X):
                recorded.append((self.seen, set(X[:, 0])))
                return super().predict(X)
        t.search_candidates(np.arange(12).reshape(-1, 1), np.arange(12), config(),
                            [candidate()], lambda c, cfg: Memorizer())
        self.assertEqual(len(recorded), 4)
        self.assertTrue(all(not train & validation for train, validation in recorded))

    def test_bad_inputs_and_duplicate_candidate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            t.search_candidates(np.array([[np.nan]] * 8), np.zeros(8), config(), [candidate()], factory)
        with self.assertRaisesRegex(ValueError, "unique"):
            t.search_candidates(np.zeros((8, 1)), np.zeros(8), config(), [candidate(), candidate()], factory)


class TaskTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({"canonical_id": [str(i) for i in range(1, 1001)],
                             "rating": np.arange(1000, dtype=float) + 2000,
                             "x": np.arange(1000, dtype=float)})

    def test_all_outer_holdouts_partition_primary_and_curve_subsets_are_nested(self):
        frame, c = self.frame(), config()
        get_ids = lambda label: frame["canonical_id"].tolist()
        all_holdouts = []
        for fold in range(5):
            subsets, validation_sets = [], []
            for n in (400, 600, 800):
                training, validation, spec = t.task_frames(frame, f"dev_f{fold}_n{n}", c, get_ids)
                subsets.append(set(training["canonical_id"]))
                validation_sets.append(set(validation["canonical_id"]))
                self.assertEqual(len(training), n)
                self.assertEqual(len(validation), 200)
                self.assertEqual(spec["outer_training_pool_n"], 800)
                self.assertFalse(set(training["canonical_id"]) & set(validation["canonical_id"]))
                self.assertEqual(training["canonical_id"].tolist(), sorted(training["canonical_id"]))
            self.assertTrue(subsets[0] <= subsets[1] <= subsets[2])
            self.assertEqual(validation_sets[0], validation_sets[1])
            self.assertEqual(validation_sets[1], validation_sets[2])
            all_holdouts.extend(validation_sets[0])
        self.assertEqual(len(all_holdouts), 1000)
        self.assertEqual(len(set(all_holdouts)), 1000)

    def test_task_split_is_independent_of_source_row_order(self):
        frame, c = self.frame(), config()
        get_ids = lambda label: frame["canonical_id"].tolist()[::-1]
        a, va, _ = t.task_frames(frame, "dev_f2_n400", c, get_ids)
        b, vb, _ = t.task_frames(frame.iloc[::-1], "dev_f2_n400", c, get_ids)
        self.assertEqual(a["canonical_id"].tolist(), b["canonical_id"].tolist())
        self.assertEqual(va["canonical_id"].tolist(), vb["canonical_id"].tolist())

    def test_unplanned_task_and_wrong_random_size_are_rejected(self):
        for name in ("dev_f5_n800", "dev_f0_n1000", "final_ranked_1000_with_ties", "anything"):
            with self.assertRaises(ValueError):
                t.parse_task(name)
        frame = self.frame()
        with self.assertRaisesRegex(ValueError, "wrong prespecified"):
            t.task_frames(frame, "final_random_500", config(), lambda label: ["1", "2", "3", "4"])

    def test_config_fit_guard_fails_before_any_data_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            study = root / "studies/chess_single_A_v2"
            study.mkdir(parents=True)
            (study / "config.json").write_text(json.dumps({"fit_allowed": False}))
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                t.run_task(root, "final_random_500")
            manifest = json.loads((study / "training_runs/final_random_500/trainer_manifest.json").read_text())
            self.assertEqual(manifest["status"], "incomplete")

    def test_final_artifacts_load_development_only_and_hash_saved_models(self):
        frame = self.frame().iloc[:500].copy()
        loads = []
        input_module = types.SimpleNamespace(
            load_model_frame=lambda root, role: (loads.append(role) or frame.copy()),
            get_training_ids=lambda root, label: frame["canonical_id"].tolist(),
            make_raw_matrix=lambda f, cfg: f[["x"]].to_numpy(),
            make_date_matrix=lambda f, cfg: f[["x"]].to_numpy())
        lock_calls = []
        lock_module = types.SimpleNamespace(verify_analysis_lock=lambda root: lock_calls.append(root))
        model_module = types.SimpleNamespace(
            candidate_configs=lambda cfg: [candidate("mean_000", "mean", 2450)],
            build_estimator=factory)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            study = root / "studies/chess_single_A_v2"
            (study / "data").mkdir(parents=True)
            (study / "config.json").write_text(json.dumps(config()))
            (study / "analysis_lock.json").write_text("{}")
            (study / "data/data_manifest.json").write_text("{}")
            with patch.dict(sys.modules, {
                "model_inputs": input_module, "lock_utils": lock_module, "models": model_module}):
                manifest = t.run_task(root, "final_random_500")
            self.assertEqual(loads, ["development"])
            self.assertEqual(len(lock_calls), 1)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["kind"], "final")
            self.assertEqual(manifest["train_n"], 500)
            self.assertFalse(manifest["external_data_loaded"])
            self.assertEqual(set(manifest["representations"]), {"raw_A", "date_control"})
            output = study / "training_runs/final_random_500"
            for entry in manifest["files"]:
                self.assertEqual(t.sha256(output / entry["path"]), entry["sha256"])
            for rep in manifest["representations"].values():
                item = rep["family_models"]["mean"]
                self.assertEqual(rep["selected_model"], item)
                fitted = joblib.load(output / item["model_file"])
                self.assertEqual(float(fitted.predict(np.zeros((1, 1)))[0]), 2450)
                self.assertEqual(item["model_sha256"], t.sha256(output / item["model_file"]))
            self.assertEqual(manifest["training_ids_sha256"],
                             t.ids_sha256(sorted(frame["canonical_id"])))

    def test_global_near_tie_winner_is_saved_separately_from_family_winner(self):
        frame = self.frame()
        frame["rating"] = 0.0
        candidates = [candidate("A_early", "A", 1.4e-12),
                      candidate("A_late", "A", .5e-12),
                      candidate("B_zero", "B", 0)]
        input_module = types.SimpleNamespace(
            load_model_frame=lambda root, role: frame.copy(),
            get_training_ids=lambda root, label: frame["canonical_id"].tolist()[
                :int(label.split("_")[1])],
            make_raw_matrix=lambda f, cfg: f[["x"]].to_numpy(),
            make_date_matrix=lambda f, cfg: f[["x"]].to_numpy())
        model_module = types.SimpleNamespace(
            candidate_configs=lambda cfg: candidates, build_estimator=factory)
        lock_module = types.SimpleNamespace(verify_analysis_lock=lambda root: None)
        for task in ("final_random_500", "dev_f0_n400"):
            with self.subTest(task=task), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                study = root / "studies/chess_single_A_v2"
                (study / "data").mkdir(parents=True)
                (study / "config.json").write_text(json.dumps(config()))
                (study / "analysis_lock.json").write_text("{}")
                (study / "data/data_manifest.json").write_text("{}")
                with patch.dict(sys.modules, {
                    "model_inputs": input_module, "lock_utils": lock_module, "models": model_module}):
                    manifest = t.run_task(root, task)
                output = study / "training_runs" / task
                for representation, rep in manifest["representations"].items():
                    self.assertEqual(rep["selected_candidate_id"], "A_late")
                    self.assertEqual(rep["selected_model"]["candidate_id"], "A_late")
                    selected = rep["selected_model"]
                    fitted = joblib.load(output / selected["model_file"])
                    self.assertEqual(float(fitted.predict(np.zeros((1, 1)))[0]), .5e-12)
                    self.assertEqual(selected["model_sha256"],
                                     t.sha256(output / selected["model_file"]))
                    if manifest["kind"] == "final":
                        family = rep["family_models"]["A"]
                        self.assertEqual(family["candidate_id"], "A_early")
                        self.assertNotEqual(family["model_file"], selected["model_file"])
                        family_fitted = joblib.load(output / family["model_file"])
                        self.assertEqual(float(family_fitted.predict(np.zeros((1, 1)))[0]), 1.4e-12)
                    else:
                        self.assertEqual(rep["family_models"], {})
                        predictions = pd.read_csv(output / "outer_predictions.csv")
                        np.testing.assert_allclose(
                            predictions[f"pred_{representation}"], .5e-12, rtol=0, atol=1e-25)


if __name__ == "__main__":
    unittest.main()
