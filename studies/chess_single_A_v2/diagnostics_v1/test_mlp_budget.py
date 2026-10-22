"""Synthetic-only tests for the paired MLP budget diagnostic."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import mlp_budget as diagnostic


def source_config():
    return json.loads((HERE.parent / "config.json").read_text(encoding="utf-8"))


def first_mlp(config):
    return next(row for row in diagnostic.models.candidate_configs(config)
                if row["family"] == "small_mlp")


class MLPBudgetTests(unittest.TestCase):
    def test_budget_copy_changes_only_two_fixed_values(self):
        original = source_config()
        original_copy = deepcopy(original)
        extended = diagnostic.config_for_budget(original, "extended")
        expected = deepcopy(original)
        fixed = next(row["fixed"] for row in expected["families"] if row["name"] == "small_mlp")
        fixed.update(max_iter=5000, max_fun=100000)
        self.assertEqual(extended, expected)
        self.assertEqual(original, original_copy)
        self.assertEqual(diagnostic.config_for_budget(original, "original"), original)

    def test_reject_changed_original_budget_or_seed_policy(self):
        for field, value in (("max_iter", 50), ("max_fun", 100),
                             ("random_states", [1, 2, 3])):
            config = source_config()
            next(row for row in config["families"] if row["name"] == "small_mlp")["fixed"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                diagnostic.config_for_budget(config, "extended")
        with self.assertRaises(ValueError):
            diagnostic.config_for_budget(source_config(), "choose_best_budget")

    def test_three_separate_seed_pipelines_match_original_seed_ensemble(self):
        rng = np.random.default_rng(109)
        X = rng.normal(size=(24, 3))
        y = 2500 + 20 * X[:, 0] - 7 * X[:, 1] + 2 * X[:, 2] ** 2
        config = source_config()
        candidate = first_mlp(config)
        snapshot = deepcopy(config)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with diagnostic.threadpool_limits(limits=1):
                original = diagnostic.models.build_estimator(candidate, config).fit(X, y)
        payload, train, heldout, records = diagnostic.fit_seed_mean(
            candidate, config, "original", X, y, X[:5], y[:5])
        np.testing.assert_allclose(train, original.predict(X), rtol=0, atol=2e-10)
        np.testing.assert_allclose(heldout, original.predict(X[:5]), rtol=0, atol=2e-10)
        np.testing.assert_allclose(heldout, np.mean(
            [model.predict(X[:5]) for model in payload["estimators"]], axis=0))
        self.assertEqual([row["seed"] for row in records], list(diagnostic.SEEDS))
        self.assertEqual(len(payload["estimators"]), 3)
        self.assertTrue(all(np.isfinite(row["loss"]) and row["n_iter"] >= 1 for row in records))
        self.assertEqual(config, snapshot)

    def test_metrics_reject_nonfinite_and_misaligned_predictions(self):
        for prediction in ([1.0], [1.0, np.nan]):
            with self.assertRaises(ValueError):
                diagnostic.prediction_metrics([1.0, 2.0], prediction)
        score = diagnostic.prediction_metrics([1.0, 4.0], [2.0, 2.0])
        self.assertEqual(score["mae"], 1.5)
        self.assertAlmostEqual(score["rmse"], np.sqrt(2.5))

    def fixture(self, root, fold=0):
        study = root / "studies/chess_single_A_v2"
        study.mkdir(parents=True)
        config = source_config()
        diagnostic.write_json(study / "config.json", config)
        diagnostic.write_json(study / "analysis_lock.json", {"synthetic": True})
        frame = pd.DataFrame({"canonical_id": [str(i) for i in range(1, 1001)],
            "rating": 2450 + np.arange(1000) % 80,
            "synthetic_feature": np.arange(1000) % 7}).sample(frac=1, random_state=8).reset_index(drop=True)
        ids = frame["canonical_id"].tolist()
        task = f"dev_f{fold}_n800"
        training, heldout, _ = diagnostic.train_models.task_frames(frame, task, config, lambda _: ids)
        runs = root / "sealed/runs"
        task_dir = runs / f"fit-{task}"
        task_dir.mkdir(parents=True)
        train_ids, heldout_ids = (part["canonical_id"].tolist() for part in (training, heldout))
        diagnostic.write_json(task_dir / "training_ids.json", train_ids)
        diagnostic.write_json(task_dir / "validation_ids.json", heldout_ids)
        candidate = first_mlp(config)
        for representation in diagnostic.REPRESENTATIONS:
            diagnostic.write_json(task_dir / f"search_{representation}.json", {
                "family_best": {"small_mlp": {"candidate": candidate,
                    "candidate_id": candidate["candidate_id"], "mae": 99.0}}})
        manifest = {"status": "complete", "task": task, "kind": "development", "train_n": 800,
            "config_sha256": diagnostic.sha256(study / "config.json"),
            "training_ids_sha256": diagnostic.train_models.ids_sha256(train_ids),
            "validation_ids_sha256": diagnostic.train_models.ids_sha256(heldout_ids),
            "files": [{"path": path.name, "sha256": diagnostic.sha256(path)}
                      for path in sorted(task_dir.glob("*.json"))]}
        diagnostic.write_json(task_dir / "trainer_manifest.json", manifest)
        return frame, ids, runs, training, heldout, task_dir

    def test_fold_uses_only_development_and_original_order_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame, ids, runs, training, heldout, _ = self.fixture(root)
            config_path = root / "studies/chess_single_A_v2/config.json"
            before = config_path.read_bytes()
            seen = []

            def fake_fit(candidate, config, budget, X_train, y_train, X_heldout, y_heldout):
                seen.append((budget, X_train.copy(), y_train.copy(), X_heldout.copy(), y_heldout.copy()))
                prediction = float(np.mean(y_train)) + (0.1 if budget == "extended" else 0)
                records = [{"seed": seed, "budget": budget, **diagnostic.BUDGETS[budget],
                    "n_iter": 7, "loss": 1.0, "iteration_limit_reached": False,
                    "seconds": 0.0, "warning_count": 0, "convergence_warning_count": 0,
                    "warnings": []} for seed in diagnostic.SEEDS]
                return {"estimators": [], "seeds": list(diagnostic.SEEDS)}, np.full(
                    len(y_train), prediction), np.full(len(y_heldout), prediction), records

            matrix = lambda part, _: part[["synthetic_feature"]].to_numpy(dtype=float)
            with (patch.object(diagnostic.lock_utils, "verify_analysis_lock") as lock,
                    patch.object(diagnostic.model_inputs, "load_model_frame", return_value=frame) as load,
                    patch.object(diagnostic.model_inputs, "get_training_ids", return_value=ids),
                    patch.object(diagnostic.model_inputs, "make_raw_matrix", side_effect=matrix),
                    patch.object(diagnostic.model_inputs, "make_date_matrix", side_effect=matrix),
                    patch.object(diagnostic, "fit_seed_mean", side_effect=fake_fit)):
                summary = diagnostic.run_fold(root, runs, 0, root / "out")
            lock.assert_called_once_with(root.resolve())
            load.assert_called_once_with(root.resolve(), "development")
            self.assertEqual(summary["status"], "complete")
            self.assertFalse(summary["external_data_loaded"])
            self.assertFalse(summary["candidate_reselection"])
            self.assertEqual(summary["metric_rows"], 4)
            self.assertEqual(summary["heldout_prediction_rows"], 400)
            self.assertEqual(summary["seed_fit_rows"], 12)
            self.assertEqual(config_path.read_bytes(), before)
            for _, X_train, y_train, X_heldout, y_heldout in seen:
                np.testing.assert_array_equal(X_train[:, 0], training["synthetic_feature"])
                np.testing.assert_array_equal(y_train, training["rating"])
                np.testing.assert_array_equal(X_heldout[:, 0], heldout["synthetic_feature"])
                np.testing.assert_array_equal(y_heldout, heldout["rating"])
            predictions = pd.read_csv(root / "out/mlp_budget_predictions.csv", dtype={"canonical_id": str})
            self.assertEqual(predictions.columns.tolist(), ["canonical_id", "fold", "representation",
                "rating", "pred_original", "pred_extended", "pred_median"])
            self.assertEqual(predictions.iloc[:200]["canonical_id"].tolist(), heldout["canonical_id"].tolist())
            self.assertTrue((root / "out/mlp_seed_diagnostics.json").exists())
            for item in summary["files"]:
                self.assertEqual(diagnostic.sha256(root / "out" / item["path"]), item["sha256"])

    def test_tampered_original_file_stops_before_loading_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, runs, _, _, task_dir = self.fixture(root)
            (task_dir / "training_ids.json").write_text("[]")
            with patch.object(diagnostic.lock_utils, "verify_analysis_lock"), \
                    patch.object(diagnostic.model_inputs, "load_model_frame") as load:
                with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                    diagnostic.run_fold(root, runs, 0, root / "out")
            load.assert_not_called()

    def test_rehashed_but_reordered_fold_ids_stop_before_fitting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame, ids, runs, _, _, task_dir = self.fixture(root)
            changed = list(reversed(diagnostic.read_json(task_dir / "validation_ids.json")))
            diagnostic.write_json(task_dir / "validation_ids.json", changed)
            manifest_path = task_dir / "trainer_manifest.json"
            manifest = diagnostic.read_json(manifest_path)
            manifest["validation_ids_sha256"] = diagnostic.train_models.ids_sha256(changed)
            for item in manifest["files"]:
                if item["path"] == "validation_ids.json":
                    item["sha256"] = diagnostic.sha256(task_dir / item["path"])
            diagnostic.write_json(manifest_path, manifest)
            with (patch.object(diagnostic.lock_utils, "verify_analysis_lock"),
                    patch.object(diagnostic.model_inputs, "load_model_frame", return_value=frame),
                    patch.object(diagnostic.model_inputs, "get_training_ids", return_value=ids),
                    patch.object(diagnostic, "fit_seed_mean") as fit):
                with self.assertRaisesRegex(ValueError, "IDs/order"):
                    diagnostic.run_fold(root, runs, 0, root / "out")
            fit.assert_not_called()

    def test_invalid_fold_is_rejected_before_loading_or_fitting(self):
        with self.assertRaises(ValueError):
            diagnostic.run_fold(Path("."), Path("."), 5, Path("unused"))


if __name__ == "__main__":
    unittest.main()
