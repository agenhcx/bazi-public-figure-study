"""Synthetic behavior checks; no study participants or research scores are read."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import unittest
import warnings

import joblib
import numpy as np
from numpy.testing import assert_allclose
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from models import (MeanSeedMLPRegressor, build_estimator, candidate_configs,
                    fit_with_diagnostics)


class WarnRegressor(RegressorMixin, BaseEstimator):
    def fit(self, X, y):
        self.value_ = float(np.mean(y))
        warnings.warn("synthetic iteration limit", ConvergenceWarning)
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


class BadRegressor(RegressorMixin, BaseEstimator):
    def fit(self, X, y):
        return self

    def predict(self, X):
        return np.full(len(X), np.nan)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
        cls.candidates = candidate_configs(cls.config)

    def candidate(self, family):
        return next(item for item in self.candidates if item["family"] == family)

    def test_all_33_candidates_have_stable_order_and_independent_parameters(self):
        candidates = candidate_configs(self.config)
        self.assertEqual(len(candidates), 33)
        self.assertEqual(len({item["candidate_id"] for item in candidates}), 33)
        self.assertEqual([item["family"] for item in candidates],
                         ["ridge"] * 5 + ["pairwise_ridge"] * 5
                         + ["rbf_kernel_ridge"] * 9
                         + ["shallow_gradient_boosting"] * 8 + ["small_mlp"] * 6)
        self.assertEqual([item["params"]["alpha"] for item in candidates[:5]],
                         [0.1, 1, 10, 100, 1000])
        self.assertEqual(candidates[10]["params"], {"alpha": .1, "gamma": .01})
        self.assertEqual(candidates[11]["params"], {"alpha": .1, "gamma": .1})
        candidates[-1]["params"]["hidden_layer_sizes"].append(999)
        self.assertEqual(self.config["families"][-1]["grid"]["hidden_layer_sizes"],
                         [[8], [16]])

    def test_input_and_target_scaling_are_training_local_and_inverse_elo(self):
        X = np.array([[0., 0.], [1., 2.], [2., 1.], [3., 5.]])
        y = np.array([2000., 2100., 2200., 2300.])
        model, _ = fit_with_diagnostics(
            build_estimator(self.candidate("ridge"), self.config), X, y)
        learned = model.regressor_.named_steps["scale"]
        assert_allclose(learned.mean_, X.mean(axis=0))
        assert_allclose(model.transformer_.mean_, [y.mean()])
        before = deepcopy((learned.mean_, learned.scale_, model.transformer_.mean_))
        model.predict(np.array([[1e6, -1e6]]))
        for old, current in zip(before, (learned.mean_, learned.scale_, model.transformer_.mean_)):
            assert_allclose(old, current)
        standardized = model.regressor_.predict(X)
        expected = model.transformer_.inverse_transform(standardized[:, None]).ravel()
        assert_allclose(model.predict(X), expected)
        shifted, _ = fit_with_diagnostics(
            build_estimator(self.candidate("ridge"), self.config), X, y + 1000)
        assert_allclose(shifted.predict(X), model.predict(X) + 1000, atol=1e-9)

    def test_pairwise_model_learns_nonadditive_signal_and_retains_main_terms(self):
        X = np.tile(np.array([[-1., -1.], [-1., 1.], [1., -1.], [1., 1.]]), (10, 1))
        y = 2000 + 100 * X[:, 0] * X[:, 1]
        additive, _ = fit_with_diagnostics(
            build_estimator(self.candidate("ridge"), self.config), X, y)
        interaction, _ = fit_with_diagnostics(
            build_estimator(self.candidate("pairwise_ridge"), self.config), X, y)
        self.assertGreater(np.mean(np.abs(additive.predict(X) - y)), 99)
        self.assertLess(np.mean(np.abs(interaction.predict(X) - y)), 1)
        pipeline = interaction.regressor_
        expansion = pipeline.named_steps["interactions"]
        assert_allclose(expansion.transform(X)[:, :2], X)
        self.assertEqual(pipeline.named_steps["scale"].n_features_in_, 3)
        self.assertEqual([name for name, _ in pipeline.steps],
                         ["interactions", "scale", "regressor"])

    def test_every_family_can_clone_fit_and_predict_finite_original_units(self):
        rng = np.random.default_rng(35)
        X = rng.normal(size=(50, 3))
        y = 2200 + 50 * X[:, 0]
        for family in [item["name"] for item in self.config["families"]]:
            with self.subTest(family=family):
                model = clone(build_estimator(self.candidate(family), self.config))
                model, _ = fit_with_diagnostics(model, X, y)
                predictions = model.predict(X[:7])
                self.assertEqual(predictions.shape, (7,))
                self.assertTrue(np.isfinite(predictions).all())
                self.assertGreater(float(np.mean(predictions)), 1000)
                names = [name for name, _ in model.regressor_.steps]
                self.assertEqual("scale" in names, family != "shallow_gradient_boosting")

    def test_mlp_averages_all_fixed_seeds_and_serializes_the_complete_ensemble(self):
        candidate = self.candidate("small_mlp")
        config = deepcopy(self.config)
        # Deliberately short synthetic fits exercise warning retention, never a
        # change to the study configuration or the research search budget.
        config["families"][-1]["fixed"]["max_iter"] = 3
        X = np.arange(60, dtype=float).reshape(30, 2) / 20
        y = 1800 + 100 * np.sin(X[:, 0])
        model, diagnostics = fit_with_diagnostics(build_estimator(candidate, config), X, y)
        ensemble = model.regressor_.named_steps["regressor"]
        self.assertIsInstance(ensemble, MeanSeedMLPRegressor)
        self.assertEqual([member.random_state for member in ensemble.estimators_],
                         self.config["families"][-1]["fixed"]["random_states"])
        transformed = model.regressor_.named_steps["scale"].transform(X)
        mean = np.mean([member.predict(transformed) for member in ensemble.estimators_], axis=0)
        assert_allclose(ensemble.predict(transformed), mean)
        self.assertGreater(diagnostics["convergence_warnings"], 0)
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        buffer.seek(0)
        restored = joblib.load(buffer)
        assert_allclose(restored.predict(X), model.predict(X))
        self.assertEqual(len(restored.regressor_.named_steps["regressor"].estimators_), 3)
        cloned = clone(model)
        self.assertFalse(hasattr(cloned, "regressor_"))

    def test_finite_iteration_warning_is_retained_and_nonfinite_fit_is_rejected(self):
        X, y = np.array([[0.], [1.]]), np.array([1800., 2000.])
        fitted, report = fit_with_diagnostics(WarnRegressor(), X, y)
        assert_allclose(fitted.predict(X), [1900, 1900])
        self.assertEqual(report["convergence_warnings"], 1)
        self.assertEqual(report["warnings"][0]["category"], "ConvergenceWarning")
        with self.assertRaisesRegex(ValueError, "invalid training predictions"):
            fit_with_diagnostics(BadRegressor(), X, y)

    def test_outside_grid_and_fixed_parameter_overrides_are_rejected(self):
        candidate = deepcopy(self.candidate("ridge"))
        candidate["params"]["alpha"] = 9999
        with self.assertRaisesRegex(ValueError, "outside configured grid"):
            build_estimator(candidate, self.config)
        candidate = deepcopy(self.candidate("ridge"))
        candidate["params"]["solver"] = "svd"
        with self.assertRaisesRegex(ValueError, "do not match configured grid"):
            build_estimator(candidate, self.config)


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        unittest.main()
