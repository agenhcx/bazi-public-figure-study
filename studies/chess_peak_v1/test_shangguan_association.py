import json
import unittest

import numpy as np
import pandas as pd

from shangguan_association import (FEATURES, analyze_cohort, correlation, derive_values,
                                   is_shangguan, ols_hc3)


def fixture(n=80):
    rows = []
    for i in range(n):
        rows.append({"canonical_id": str(100000 + i), "exact_dob_frozen": f"{1970+i%35}-06-15",
                     "rating": 2400 + 20 * (i % 2) + (i % 7) * 2,
                     "year_stem": "甲" if i % 3 else "乙", "year_branch": "辰",
                     "month_stem": "丙", "month_branch": "巳" if i % 2 else "午",
                     "day_stem": "乙", "day_branch": "酉"})
    return pd.DataFrame(rows)


class ShangguanTest(unittest.TestCase):
    def test_rule_all_ten_day_stems_have_exactly_one_shangguan(self):
        stems = "甲乙丙丁戊己庚辛壬癸"
        expected = "丁丙己戊辛庚癸壬乙甲"
        for day, other in zip(stems, expected):
            self.assertEqual([s for s in stems if is_shangguan(day, s)], [other])
        self.assertEqual(is_shangguan("乙", "丙"), 1)
        self.assertEqual(is_shangguan("乙", "丁"), 0)
        self.assertEqual(is_shangguan("癸", "甲"), 1)

    def test_five_positions_exclude_reference_day_stem(self):
        data = derive_values(fixture(2))
        self.assertEqual(data[FEATURES[0]].tolist(), [0, 1])
        self.assertEqual(data[FEATURES[1]].tolist(), [1, 2])
        self.assertEqual(len(data), 2)
        self.assertTrue((data.age_at_2024_01_01 > 0).all())

    def test_missing_identity_and_invalid_symbols_stop(self):
        for mutate in (lambda d: d.drop(columns="day_stem"),
                       lambda d: d.assign(day_branch="?"),
                       lambda d: d.assign(canonical_id="same"),
                       lambda d: d.assign(rating=np.nan),
                       lambda d: d.assign(exact_dob_frozen="2025-01-01")):
            with self.assertRaises((ValueError, TypeError)):
                derive_values(mutate(fixture()))

    def test_raw_binary_slope_equals_group_mean_difference(self):
        data = derive_values(fixture())
        x, y = data[FEATURES[0]], data.rating
        fit = ols_hc3(x, y)
        difference = y[x == 1].mean() - y[x == 0].mean()
        self.assertAlmostEqual(fit["elo_per_unit"], difference, places=9)
        self.assertLess(fit["ci95_low"], fit["elo_per_unit"])
        self.assertGreater(fit["ci95_high"], fit["elo_per_unit"])

    def test_age_adjustment_recovers_known_additive_difference(self):
        rng = np.random.default_rng(77)
        age = np.linspace(18, 70, 200)
        x = (rng.random(len(age)) < .5).astype(float)
        y = 2400 + 35 * x + 3 * age - .03 * age ** 2
        raw, adjusted = ols_hc3(x, y), ols_hc3(x, y, age)
        self.assertEqual(adjusted["status"], "available")
        self.assertAlmostEqual(adjusted["elo_per_unit"], 35, places=8)
        self.assertAlmostEqual(adjusted["partial_r"], 1, places=10)
        self.assertNotAlmostEqual(raw["elo_per_unit"], 35, places=3)

    def test_constant_feature_is_explicitly_unavailable(self):
        self.assertIsNone(correlation(np.ones(20), np.arange(20))["r"])
        fit = ols_hc3(np.ones(20), np.arange(20))
        self.assertEqual(fit["status"], "unavailable_rank_or_sample_size")
        self.assertIsNone(fit["elo_per_unit"])

    def test_cohort_output_retains_every_person_and_no_p_values(self):
        results, data = analyze_cohort(fixture(), "development")
        self.assertEqual(len(results), 2)
        self.assertEqual(len(data), 80)
        self.assertEqual(sum(g["n"] for g in results[0]["groups"]), 80)
        self.assertIsNotNone(results[1]["spearman_r"])
        encoded = json.dumps(results, allow_nan=False)
        self.assertNotIn("pvalue", encoded)
        self.assertNotIn("p_value", encoded)


if __name__ == "__main__":
    unittest.main()
