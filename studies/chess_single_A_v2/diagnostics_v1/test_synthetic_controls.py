"""Synthetic-only checks for the bounded A1 recovery diagnostic."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

import synthetic_controls as controls


CONFIG = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())


def fake_frame(n=1000):
    rng = np.random.default_rng(1513)
    raw = CONFIG["representations"]["raw_A"]
    values = {"canonical_id": [str(10000 + i) for i in range(n)]}
    for index, column in enumerate(controls.POSITION_COLUMNS):
        vocab = raw["stem_vocabulary"] if index % 2 == 0 else raw["branch_vocabulary"]
        values[column] = rng.choice(vocab, size=n)
    # Deliberately no rating, DOB, name or external-cohort fields.
    return pd.DataFrame(values).sample(frac=1, random_state=55).reset_index(drop=True)


def fixture(root):
    study = root / "studies/chess_single_A_v2"
    (study / "data").mkdir(parents=True)
    (study / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False))
    (study / "analysis_lock.json").write_text("{}\n")
    (study / "data/model_inputs_development.csv").write_text("synthetic fixture only\n")
    return study


class SyntheticControlTests(unittest.TestCase):
    def test_functions_are_fixed_standardized_and_not_rare_indicator_events(self):
        frame = fake_frame()
        X = controls.make_raw_matrix(frame, CONFIG)
        values = {}
        for name in controls.SIGNALS:
            signal, design = controls.signal_design(X, name)
            again, again_design = controls.signal_design(X, name)
            np.testing.assert_array_equal(signal, again)
            self.assertEqual(design, again_design)
            self.assertFalse(design["real_outcome_used"])
            scores = np.column_stack([X[:, begin:end] @ np.array(design["coefficients"])[begin:end]
                                      for begin, end in controls.POSITION_SLICES])
            raw = {"null": np.zeros(len(X)), "additive": scores.sum(axis=1),
                   "pairwise": scores[:, 0] * scores[:, 4],
                   "third_order": scores[:, 0] * scores[:, 2] * scores[:, 4]}[name]
            if name == "null":
                np.testing.assert_array_equal(signal, np.zeros(1000))
                self.assertEqual(design["raw_signal_population_sd"], 0.0)
            else:
                np.testing.assert_allclose(signal, (raw - raw.mean()) / raw.std(ddof=0))
                self.assertAlmostEqual(float(signal.mean()), 0.0)
                self.assertAlmostEqual(float(signal.std(ddof=0)), 1.0)
                self.assertGreater(np.count_nonzero(signal), 900)
            values[name] = signal
        self.assertFalse(np.array_equal(values["additive"], values["pairwise"]))
        self.assertFalse(np.array_equal(values["pairwise"], values["third_order"]))
        with self.assertRaises(ValueError):
            controls.signal_design(X[:, :-1], "additive")
        broken = X.copy()
        broken[0, :10] = 0
        with self.assertRaises(ValueError):
            controls.signal_design(broken, "additive")

    def test_targets_use_fixed_independent_noise_and_known_strength(self):
        X = controls.make_raw_matrix(fake_frame(), CONFIG)
        signal, _ = controls.signal_design(X, "additive")
        weak, weak_noise = controls.synthetic_target(signal, 0.5, 0)
        strong, strong_noise = controls.synthetic_target(signal, 2.0, 0)
        other, other_noise = controls.synthetic_target(signal, 0.5, 1)
        np.testing.assert_array_equal(weak_noise, strong_noise)
        self.assertFalse(np.array_equal(weak_noise, other_noise))
        np.testing.assert_allclose(strong - weak, 75.0 * signal)
        np.testing.assert_allclose(weak, 2500 + 50 * (0.5 * signal + weak_noise))
        null, noise = controls.synthetic_target(np.zeros(1000), 0.0, 0)
        np.testing.assert_allclose(null, 2500 + 50 * noise)
        self.assertTrue(np.isfinite(null).all())
        with self.assertRaises(ValueError):
            controls.synthetic_target(signal, 1.0, 0)

    def test_five_representatives_match_original_candidates_and_mlp_budget(self):
        before = deepcopy(CONFIG)
        candidates = controls.fixed_candidates(CONFIG)
        self.assertEqual([row["candidate_id"] for row in candidates], [
            "ridge_002", "pairwise_ridge_003", "rbf_kernel_ridge_003",
            "shallow_gradient_boosting_006", "small_mlp_004"])
        self.assertEqual(CONFIG, before)
        mlp = controls.build_estimator(candidates[-1], CONFIG).regressor.named_steps["regressor"]
        self.assertEqual(mlp.mlp_params["max_iter"], 1000)
        self.assertEqual(mlp.mlp_params["max_fun"], 20000)
        self.assertEqual(mlp.random_states, (20261021, 20261022, 20261023))
        changed = deepcopy(CONFIG)
        changed["families"][0]["grid"]["alpha"] = [0.1]
        with self.assertRaises(ValueError):
            controls.fixed_candidates(changed)

    def test_complete_null_job_uses_no_rating_and_preserves_source_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            study = fixture(root)
            original = (study / "config.json").read_bytes()
            frame = fake_frame()
            seen_y = []

            class RecordingDummy:
                def fit(self, X, y):
                    seen_y.append(np.asarray(y).copy())
                    self.fitted = DummyRegressor(strategy="mean").fit(X, y)
                    return self

                def predict(self, X):
                    return self.fitted.predict(X)

            with patch.object(controls, "verify_analysis_lock") as verify, \
                    patch.object(controls, "load_model_frame", return_value=frame) as loader, \
                    patch.object(controls, "build_estimator", side_effect=lambda *args: RecordingDummy()) as builder, \
                    redirect_stdout(io.StringIO()):
                manifest = controls.run_signal(root, "null", root / "output")
            loader.assert_called_once_with(root.resolve(), "development")
            verify.assert_called_once_with(root.resolve())
            self.assertEqual(builder.call_count, 50)
            self.assertEqual(manifest["fit_attempts"], 50)
            self.assertEqual(manifest["failed_fit_attempts"], 0)
            self.assertEqual(manifest["prediction_rows"], 12000)
            self.assertEqual(manifest["pooled_metric_rows"], 12)
            self.assertFalse(manifest["actual_ratings_used_for_targets"])
            self.assertFalse(manifest["external_data_loaded"])
            self.assertEqual((study / "config.json").read_bytes(), original)
            target = pd.read_csv(root / "output/synthetic_targets.csv", float_precision="round_trip")
            self.assertEqual(len(target), 2000)
            self.assertEqual(set(target.strength), {0.0})
            self.assertEqual(set(target.standardized_signal), {0.0})
            allowed = set(target.synthetic_target)
            for y in seen_y:
                self.assertEqual(len(y), 800)
                self.assertTrue(set(y) <= allowed)
            predicted = pd.read_csv(root / "output/synthetic_predictions.csv.gz")
            counts = predicted.groupby(["scenario_id", "model"]).canonical_id.nunique()
            self.assertTrue((counts == 1000).all())
            folds = json.loads((root / "output/fold_ids.json").read_text())
            heldout = []
            for fold in folds:
                self.assertEqual(len(fold["training_ids"]), 800)
                self.assertEqual(len(fold["validation_ids"]), 200)
                self.assertFalse(set(fold["training_ids"]) & set(fold["validation_ids"]))
                heldout.extend(fold["validation_ids"])
            self.assertEqual(len(set(heldout)), 1000)
            for entry in manifest["outputs"]:
                self.assertEqual(hashlib.sha256((root / "output" / entry["path"]).read_bytes()).hexdigest(),
                                 entry["sha256"])
            self.assertFalse(list((root / "output").glob("*.tmp")))

    def test_failed_fit_is_reported_without_rescue_or_partial_pooled_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            attempts = []

            def fixed_fit(candidate, config, X_train, y_train, X_valid):
                attempts.append(candidate["candidate_id"])
                if len(attempts) == 1:
                    return None, None, {"status": "failed", "error_type": "SyntheticFailure",
                        "error": "intentional synthetic test", "warnings": [], "warning_count": 0,
                        "fit_with_convergence_warning": False, "seconds": 0.0}
                mean = float(np.mean(y_train))
                return np.full(len(X_train), mean), np.full(len(X_valid), mean), {
                    "status": "complete", "error_type": None, "error": None,
                    "warnings": [], "warning_count": 0, "fit_with_convergence_warning": False,
                    "seconds": 0.0}

            with patch.object(controls, "verify_analysis_lock"), \
                    patch.object(controls, "load_model_frame", return_value=fake_frame()), \
                    patch.object(controls, "_fit_predictions", side_effect=fixed_fit), \
                    redirect_stdout(io.StringIO()):
                manifest = controls.run_signal(root, "null", root / "output")
            self.assertEqual(len(attempts), 50)
            self.assertEqual(manifest["failed_fit_attempts"], 1)
            pooled = pd.read_csv(root / "output/pooled_metrics.csv")
            failed = pooled[(pooled.model == "ridge") & (pooled.replicate == 0)].iloc[0]
            self.assertEqual(failed["status"], "invalid_incomplete_folds")
            self.assertEqual(failed["n"], 800)
            self.assertTrue(pd.isna(failed["mae"]))
            self.assertTrue(pd.isna(failed["mae_gain"]))

    def test_bad_input_records_atomic_failure_manifest_before_any_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            with patch.object(controls, "verify_analysis_lock"), \
                    patch.object(controls, "load_model_frame", return_value=fake_frame(999)), \
                    patch.object(controls, "build_estimator") as builder:
                with self.assertRaises(ValueError):
                    controls.run_signal(root, "additive", root / "output")
            builder.assert_not_called()
            manifest = json.loads((root / "output/manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["error_type"], "ValueError")
            self.assertFalse(list((root / "output").glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
