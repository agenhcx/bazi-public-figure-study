"""Synthetic checks for B1; these tests never load or fit the chess cohorts."""
import importlib.util
from datetime import date
import math
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.preprocessing import StandardScaler


SPEC = importlib.util.spec_from_file_location("b1_features", Path(__file__).with_name("features.py"))
features = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(features)
GRID_CONFIG = {"grid": {"middle": [.25, .5, .75], "residual_ratio": [.25, .5, .75],
                        "month": [1, 1.5, 2, 3], "alpha": [.1, 1, 10, 100, 1000]}}


def row(**changes):
    result = dict(year_stem="甲", year_branch="卯", month_stem="丙", month_branch="子",
                  day_stem="戊", day_branch="酉", exact_dob_frozen="1990-11-30",
                  snapshot="2013-01", rating=2400, canonical_id="synthetic")
    result.update(changes)
    return result


def diverse_frame():
    """Deterministic synthetic symbols with independently varying positions."""
    return pd.DataFrame([
        row(year_stem=features.STEMS[(i * 7) % 10], year_branch=features.BRANCHES[i % 12],
            month_stem=features.STEMS[(i // 3) % 10], month_branch=features.BRANCHES[(i * 5 + i // 12) % 12],
            day_stem=features.STEMS[(i // 7) % 10], day_branch=features.BRANCHES[(i * 7 + i // 5) % 12],
            exact_dob_frozen=f"{1970 + i % 30}-03-{1 + i % 28:02d}")
        for i in range(84)
    ])


class B1FeatureTests(unittest.TestCase):
    def test_hidden_role_table_and_exact_normalized_mixtures(self):
        self.assertEqual(features.HIDDEN_STEMS["巳"], ("丙", "戊", "庚"))
        self.assertEqual(features.HIDDEN_STEMS["午"], ("丁", "己"))
        self.assertEqual(features.HIDDEN_STEMS["亥"], ("壬", "甲"))
        mixtures = features.branch_phase_mixtures(.5, .5)
        np.testing.assert_allclose(mixtures.sum(axis=1), 1)
        np.testing.assert_allclose(mixtures[features.BRANCHES.index("巳")], np.array([0, 1, .5, .25, 0]) / 1.75)
        np.testing.assert_allclose(mixtures[features.BRANCHES.index("午")], np.array([0, 1, .5, 0, 0]) / 1.5)
        np.testing.assert_allclose(mixtures[features.BRANCHES.index("亥")], np.array([.5, 0, 0, 0, 1]) / 1.5)
        np.testing.assert_array_equal(mixtures[features.BRANCHES.index("子")], [0, 0, 0, 0, 1])
        # Residual ratio has no effect when the branch has only two stems.
        np.testing.assert_array_equal(mixtures[features.BRANCHES.index("午")],
                                      features.branch_phase_mixtures(.5, .8)[features.BRANCHES.index("午")])

    def test_month_multiplier_applies_to_branch_only(self):
        frame = pd.DataFrame([row()])
        ordinary = features.B1FeatureTransformer(month=1).transform(frame)[0, 66:71]
        month = features.B1FeatureTransformer(month=3).transform(frame)[0, 66:71]
        np.testing.assert_allclose(ordinary, np.array([2, 1, 1, 1, 1]) / 6)
        np.testing.assert_allclose(month, np.array([2, 1, 1, 1, 3]) / 8)
        changed = features.B1FeatureTransformer(month=3).transform(pd.DataFrame([row(month_stem="甲")]))[0, 66:71]
        # A changed month stem moves one unit, despite month-branch weight 3.
        np.testing.assert_allclose(changed - month, np.array([1, -1, 0, 0, 0]) / 8)

    def test_86_columns_raw_prefix_day_rotation_and_directed_products(self):
        frame = pd.DataFrame([row(day_stem="庚")])
        matrix = features.B1FeatureTransformer().fit_transform(frame)
        self.assertEqual(matrix.shape, (1, 86))
        np.testing.assert_array_equal(matrix[:, :66], features.B1FeatureTransformer(representation="raw").transform(frame))
        np.testing.assert_allclose(matrix[0, 66:71], np.array([2, 1, 0, 2, 1]) / 6)
        np.testing.assert_allclose(matrix[0, 71:76], np.array([2, 1, 2, 1, 0]) / 6)
        np.testing.assert_allclose(matrix[0, 76:81], np.array([2, 0, 0, 2, 2]) / 36)
        np.testing.assert_allclose(matrix[0, 81:86], np.array([0, 2, 0, 4, 1]) / 36)
        self.assertEqual(matrix[0, :66].sum(), 6)
        self.assertEqual(len(set(features.B1FeatureTransformer().get_feature_names_out())), 86)

    def test_structural_weights_survive_standardization_after_pooling(self):
        frame = diverse_frame()
        base = features.B1FeatureTransformer(middle=.25, residual_ratio=.25, month=1).transform(frame)
        for parameters in (dict(middle=.75, residual_ratio=.25, month=1),
                           dict(middle=.25, residual_ratio=.75, month=1),
                           dict(middle=.25, residual_ratio=.25, month=3)):
            changed = features.B1FeatureTransformer(**parameters).transform(frame)
            # Raw66 stay fixed; heterogeneous pooled mixtures change shape even
            # after each output feature is centered and scaled independently.
            np.testing.assert_array_equal(base[:, :66], changed[:, :66])
            standardized_base = StandardScaler().fit_transform(base[:, 66:71])
            standardized_changed = StandardScaler().fit_transform(changed[:, 66:71])
            self.assertGreater(np.max(np.abs(standardized_base - standardized_changed)), .05)

    def test_constraints_and_bad_symbols_rejected(self):
        frame = pd.DataFrame([row()])
        for parameter in ("middle", "residual_ratio"):
            for value in (0, 1, -.1, np.nan, np.inf, True, "0.5"):
                with self.subTest(parameter=parameter, value=value), self.assertRaises(ValueError):
                    features.B1FeatureTransformer(**{parameter: value}).fit(frame)
        for value in (.99, -1, np.nan, np.inf, True):
            with self.subTest(month=value), self.assertRaises(ValueError):
                features.B1FeatureTransformer(month=value).transform(frame)
        with self.assertRaises(ValueError):
            # Positive scalar inputs must not silently underflow the residual
            # strength to zero and violate the actual ordered-weight bound.
            features.B1FeatureTransformer(middle=5e-324, residual_ratio=.5).transform(frame)
        with self.assertRaises(ValueError):
            features.B1FeatureTransformer(representation="unknown").transform(frame)
        with self.assertRaises(ValueError):
            features.B1FeatureTransformer().transform(frame.drop(columns="day_stem"))
        for value in (None, "A", 1):
            with self.subTest(symbol=value), self.assertRaises(ValueError):
                features.B1FeatureTransformer().transform(pd.DataFrame([row(day_branch=value)]))

    def test_clone_and_fit_do_not_use_labels_or_irrelevant_columns(self):
        frame = diverse_frame()
        transformer = features.B1FeatureTransformer(middle=.75, residual_ratio=.25, month=1.5)
        expected = transformer.transform(frame)

        class ForbiddenLabels:
            def __array__(self, *args, **kwargs):
                raise AssertionError("Encoder inspected y")

        fitted = clone(transformer).fit(frame, ForbiddenLabels())
        np.testing.assert_array_equal(expected, fitted.transform(frame.drop(columns=["rating", "canonical_id"])))
        changed = frame.copy()
        changed["rating"] = object()
        changed["canonical_id"] = object()
        np.testing.assert_array_equal(expected, clone(transformer).fit_transform(changed, ForbiddenLabels()))
        self.assertEqual(fitted.get_params(), transformer.get_params())

    def test_date_control_exact_formula_and_validation(self):
        frame = pd.DataFrame([row(exact_dob_frozen="2000-02-29")])
        transformer = features.B1FeatureTransformer(representation="date")
        age = (date(2013, 1, 1) - date(2000, 2, 29)).days / 365.2425
        phase = 2 * math.pi * 59 / 366
        expected = [[age, age * age, age * age * age, math.sin(phase), math.cos(phase),
                     math.sin(2 * phase), math.cos(2 * phase)]]
        np.testing.assert_array_equal(transformer.fit_transform(frame), expected)
        self.assertEqual(len(transformer.get_feature_names_out()), 7)
        for changes in (dict(exact_dob_frozen="2013-01-02"), dict(snapshot="2013-1"),
                        dict(exact_dob_frozen="20000229"), dict(exact_dob_frozen="2001-02-29")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                transformer.transform(pd.DataFrame([row(**changes)]))
        minimal = frame.loc[:, ["exact_dob_frozen", "snapshot"]]
        np.testing.assert_array_equal(transformer.transform(minimal), expected)

    def test_candidates_have_stable_order_and_strict_constraints(self):
        all_candidates = features.candidates(GRID_CONFIG)
        self.assertEqual(len(all_candidates), 190)
        self.assertEqual(len({candidate["candidate_id"] for candidate in all_candidates}), 190)
        self.assertEqual(all_candidates[0], dict(candidate_id="b1_000", representation="b1",
                         middle=.25, residual_ratio=.25, month=1., alpha=.1))
        self.assertEqual(all_candidates[1]["alpha"], 1)
        self.assertEqual(all_candidates[5]["month"], 1.5)
        self.assertEqual(all_candidates[20]["residual_ratio"], .5)
        self.assertEqual(all_candidates[60]["middle"], .5)
        self.assertEqual(all_candidates[179]["candidate_id"], "b1_179")
        self.assertEqual(all_candidates[180], dict(candidate_id="raw_000", representation="raw", alpha=.1))
        self.assertEqual(all_candidates[185], dict(candidate_id="date_000", representation="date", alpha=.1))
        self.assertEqual(all_candidates, features.candidates(GRID_CONFIG))
        for candidate in all_candidates[:180]:
            self.assertTrue(1 > candidate["middle"] > candidate["middle"] * candidate["residual_ratio"] > 0)
            self.assertGreaterEqual(candidate["month"], 1)

    def test_estimator_fits_synthetic_data_and_uses_training_only_scalers(self):
        frame = diverse_frame()
        y = 2000 + np.arange(len(frame)) * 3 + (np.arange(len(frame)) % 5) ** 2
        for representation in ("b1", "raw", "date"):
            candidate = next(c for c in features.candidates(GRID_CONFIG) if c["representation"] == representation)
            estimator = clone(features.build_estimator(candidate)).fit(frame.iloc[:60], y[:60])
            prediction = estimator.predict(frame.iloc[60:].drop(columns="rating"))
            self.assertEqual(prediction.shape, (24,))
            self.assertTrue(np.isfinite(prediction).all())
            pipeline = estimator.regressor_
            encoded_training = pipeline.named_steps["features"].transform(frame.iloc[:60])
            np.testing.assert_allclose(pipeline.named_steps["scale"].mean_, encoded_training.mean(axis=0))
            np.testing.assert_allclose(estimator.transformer_.mean_, [y[:60].mean()])
            ridge = pipeline.named_steps["regressor"]
            self.assertEqual((ridge.solver, ridge.tol, ridge.max_iter), ("lsqr", 1e-6, 10000))


if __name__ == "__main__":
    unittest.main()
