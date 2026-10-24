import csv
from datetime import date
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import types
import unittest

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("model_inputs", HERE / "model_inputs.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def symbol_row(**changes):
    row = {"canonical_id": "1", "snapshot": "2013-01", "exact_dob_frozen": "1990-11-30", "rating": 2500,
           "year_stem": "庚", "year_branch": "午", "month_stem": "丁", "month_branch": "亥",
           "day_stem": "己", "day_branch": "亥", "year_pillar": "庚午", "month_pillar": "丁亥", "day_pillar": "己亥"}
    row.update(changes)
    return row


class FakeBackend:
    @staticmethod
    def fromSolar(y, mon, d):
        class Day:
            def getYearGZ(self): return types.SimpleNamespace(tg=6, dz=6)
            def getMonthGZ(self): return types.SimpleNamespace(tg=3, dz=11)
            def getDayGZ(self): return types.SimpleNamespace(tg=5, dz=11)
        return Day()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class InputEncodingTests(unittest.TestCase):
    def test_one_hot_has_six_ones_and_keeps_repeated_symbol_positions_distinct(self):
        frame = pd.DataFrame([symbol_row()])
        x = m.make_raw_matrix(frame, CONFIG)
        self.assertEqual(x.shape, (1, 66))
        self.assertEqual(x.sum(), 6)
        self.assertEqual(np.flatnonzero(x[0]).tolist(), [6, 16, 25, 43, 49, 65])
        other = m.make_raw_matrix(pd.DataFrame([symbol_row(year_stem="甲")]), CONFIG)
        self.assertEqual(np.flatnonzero(x[0] != other[0]).tolist(), [0, 6])

    def test_absent_categories_keep_identical_width_and_offsets(self):
        a = m.make_raw_matrix(pd.DataFrame([symbol_row()]), CONFIG)
        b = m.make_raw_matrix(pd.DataFrame([symbol_row(), symbol_row(day_stem="癸")]), CONFIG)
        np.testing.assert_array_equal(a[0], b[0])
        self.assertEqual(b.shape, (2, 66))

    def test_unknown_or_missing_symbol_is_rejected(self):
        for value in ["?", "", None, np.nan, 6]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.make_raw_matrix(pd.DataFrame([symbol_row(day_stem=value)]), CONFIG)
        with self.assertRaises(ValueError):
            m.make_raw_matrix(pd.DataFrame([symbol_row()]).drop(columns="day_stem"), CONFIG)

    def test_date_leap_year_harmonics_and_snapshot_age(self):
        frame = pd.DataFrame([symbol_row(exact_dob_frozen="2000-02-29", snapshot="2023-01")])
        x = m.make_date_matrix(frame, CONFIG)[0]
        age = (date(2023, 1, 1) - date(2000, 2, 29)).days / 365.2425
        phase = 2 * math.pi * 59 / 366
        np.testing.assert_allclose(x, [age, age ** 2, age ** 3, math.sin(phase), math.cos(phase),
                                      math.sin(2 * phase), math.cos(2 * phase)], rtol=1e-14)

    def test_date_encoding_is_row_local_with_no_training_fit(self):
        row = symbol_row(exact_dob_frozen="1999-03-01", snapshot="2013-01")
        a = m.make_date_matrix(pd.DataFrame([row]), CONFIG)
        b = m.make_date_matrix(pd.DataFrame([symbol_row(exact_dob_frozen="1900-01-01"), row]), CONFIG)
        np.testing.assert_array_equal(a[0], b[1])
        phase = 2 * math.pi * 59 / 365
        self.assertAlmostEqual(a[0, 3], math.sin(phase))

    def test_invalid_date_or_future_date_is_rejected(self):
        for changes in [{"exact_dob_frozen": "2001-02-29"}, {"exact_dob_frozen": "2024-01-01"},
                        {"snapshot": "2023-13"}, {"exact_dob_frozen": "2000-2-01"}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                m.make_date_matrix(pd.DataFrame([symbol_row(**changes)]), CONFIG)

    def test_generation_preserves_legacy_default_method_calls(self):
        row = m.generate_pillars("1990-11-30", FakeBackend)
        for column in m.RAW_COLUMNS + m.PILLAR_COLUMNS:
            self.assertEqual(row[column], symbol_row()[column])
        self.assertEqual(set(row), set(m.RAW_COLUMNS + m.PILLAR_COLUMNS))

    def test_legacy_mismatch_in_dob_pillar_or_explicit_column_stops(self):
        base = symbol_row()
        for change in [{"exact_dob_frozen": "1990-12-01"}, {"day_pillar": "庚子"}, {"year_stem": "甲"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.compare_legacy({"development": [base]}, [dict(base, **change)], "legacy.csv")

    def test_legacy_cross_snapshot_rating_change_is_allowed_but_same_snapshot_is_not(self):
        ref = symbol_row(rating=2600)
        with self.assertRaises(ValueError):
            m.compare_legacy({"development": [symbol_row()]}, [ref], "same.csv")
        result = m.compare_legacy({"development": [symbol_row(snapshot="2023-01")]}, [ref], "other.csv")
        self.assertEqual(result["matching_person_comparisons"]["development"], 1)

    def test_changed_vocabulary_and_order_are_rejected(self):
        config = json.loads(json.dumps(CONFIG))
        config["representations"]["raw_A"]["inputs"][0:2] = ["year_branch", "year_stem"]
        with self.assertRaises(ValueError):
            m.make_raw_matrix(pd.DataFrame([symbol_row()]), config)


class ModelInputProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / m.DATA_REL
        self.data.mkdir(parents=True)
        write_json(self.root / m.CONFIG_REL, CONFIG)

    def put_derived(self, rows=None):
        rows = rows or [symbol_row()]
        path = self.data / "model_inputs_development.csv"
        write_csv(path, rows)
        info = {"path": path.relative_to(self.root).as_posix(), "sha256": m.sha256(path),
                "n": len(rows), "snapshot": "2013-01"}
        manifest = {"status": m.COMPLETE, "feature_spec_sha256": m._json_hash(m.feature_spec(CONFIG)),
                    "roles": {"development": info}}
        write_json(self.data / "data_manifest.json", manifest)
        return path, manifest

    def test_loader_checks_fingerprint_and_sorts_string_ids(self):
        path, _ = self.put_derived([symbol_row(canonical_id="2"), symbol_row(canonical_id="10")])
        frame = m.load_model_frame(self.root, "development")
        self.assertEqual(frame.canonical_id.tolist(), ["10", "2"])
        self.assertTrue(np.issubdtype(frame.rating.dtype, np.integer))
        path.write_text(path.read_text().replace("2500", "2501"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            m.load_model_frame(self.root, "development")

    def test_loader_rejects_duplicate_ids_extra_predictor_columns_and_illegal_parity(self):
        for rows in [[symbol_row(), symbol_row()], [dict(symbol_row(), ten_god_score=1)],
                     [symbol_row(year_stem="乙", year_pillar="乙午")]]:
            self.put_derived(rows)
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                m.load_model_frame(self.root, "development")

    def test_loader_rejects_path_escape_incomplete_preparation_and_feature_change(self):
        _, manifest = self.put_derived()
        manifest["roles"]["development"]["path"] = "../outside.csv"
        write_json(self.data / "data_manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "escapes"):
            m.load_model_frame(self.root, "development")
        self.put_derived()
        config = json.loads(json.dumps(CONFIG))
        config["representations"]["date_control"]["age"] = "another formula"
        write_json(self.root / m.CONFIG_REL, config)
        with self.assertRaisesRegex(ValueError, "specification changed"):
            m.load_model_frame(self.root, "development")
        write_json(self.data / "data_manifest.json", {"status": "incomplete"})
        with self.assertRaisesRegex(ValueError, "not complete"):
            m.load_model_frame(self.root, "development")

    def test_training_ids_validate_csv_hash_order_and_ordered_id_hash(self):
        rows = [{"label": "random_500", "canonical_id": "2", "order": 2},
                {"label": "random_500", "canonical_id": "10", "order": 1}]
        path = self.data / "training_subsets.csv"
        write_csv(path, rows)
        manifest = {"status": "subsets_fixed_no_models_fitted",
                    "output": {"path": path.relative_to(self.root).as_posix(), "sha256": m.sha256(path)},
                    "subsets": {"random_500": {"actual_n": 2,
                     "ordered_ids_sha256": hashlib.sha256(b"10\n2\n").hexdigest()}}}
        write_json(self.data / "subset_manifest.json", manifest)
        self.assertEqual(m.get_training_ids(self.root, "random_500"), ["10", "2"])
        manifest["subsets"]["random_500"]["ordered_ids_sha256"] = "bad"
        write_json(self.data / "subset_manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "ordered-ID"):
            m.get_training_ids(self.root, "random_500")
        path.write_text(path.read_text() + "random_500,3,3\n")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            m.get_training_ids(self.root, "random_500")

    def test_failed_preparation_invalidates_previous_manifest_and_derived_rows(self):
        path, _ = self.put_derived()
        with self.assertRaises(FileNotFoundError):
            m.prepare_inputs(self.root, backend=FakeBackend)
        self.assertFalse(path.exists())
        self.assertEqual(json.loads((self.data / "data_manifest.json").read_text())["status"],
                         "feature_preparation_incomplete_no_models_fitted")

    def test_complete_preparation_legacy_reconciliation_and_all_four_role_loaders(self):
        def source(fid, snapshot, elo):
            return {"fide_id": str(fid), "identity_bridge_modern_fide_id": str(fid),
                    "snapshot": snapshot, "exact_dob_frozen": "1990-11-30", "rating": elo}

        development = [source(fid, "2013-01", 2500) for fid in range(1, 1001)]
        primary = [source(fid, "2023-01", 2600) for fid in range(2001, 2501)]
        supplementary = [source(fid, "2023-01", 2600) for fid in list(range(1, 701)) + list(range(2001, 2302))]
        acquired = {"2013_M": ("cohort_2013_M.csv", development),
                    "2023_M_NEW_TARGET": ("cohort_2023_M_NEW_TARGET.csv", primary),
                    "2023_M_FULL": ("cohort_2023_M_FULL.csv", supplementary)}
        summary = {"status": "acquisition_complete_no_models_fitted", "cohorts": {}}
        acquisition = {"status": "acquisition_complete_no_models_fitted", "executing_commit": "test-collector",
                       "outputs": []}
        for role, (filename, rows) in acquired.items():
            path = self.data / filename
            write_csv(path, rows)
            digest = m.sha256(path)
            acquisition["outputs"].append({"file": filename, "sha256": digest})
            summary["cohorts"][role] = {"sha256": digest, "n": len(rows)}
        write_json(self.data / "manifest.json", acquisition)
        write_json(self.data / "summary.json", summary)
        upstream = {"manifest_sha256": m.sha256(self.data / "manifest.json"),
                    "summary_sha256": m.sha256(self.data / "summary.json")}
        write_json(self.data / "independent_audit.json", dict(upstream, status="passed"))
        training_path = self.data / "training_subsets.csv"
        write_csv(training_path, [{"label": "random_1000", "canonical_id": str(fid), "order": fid}
                                  for fid in range(1, 1001)])
        ordered = "\n".join(str(fid) for fid in range(1, 1001)) + "\n"
        subset = {"status": "subsets_fixed_no_models_fitted",
                  "source_acquisition_manifest_sha256": upstream["manifest_sha256"],
                  "source_acquisition_summary_sha256": upstream["summary_sha256"],
                  "output": {"path": training_path.relative_to(self.root).as_posix(),
                             "sha256": m.sha256(training_path)},
                  "subsets": {"random_1000": {"actual_n": 1000,
                               "ordered_ids_sha256": hashlib.sha256(ordered.encode()).hexdigest()}}}
        write_json(self.data / "subset_manifest.json", subset)

        def golden(row):
            result = dict(row)
            result.update(m.generate_pillars(row["exact_dob_frozen"], FakeBackend))
            return result

        write_csv(self.root / m.REFERENCE_PATHS[0], [golden(row) for row in development[:501]])
        write_csv(self.root / m.REFERENCE_PATHS[1], [golden(row) for row in supplementary[:501]])
        old_new = [source(fid, "2023-01", 2600) for fid in range(2001, 2502)]
        write_csv(self.root / m.REFERENCE_PATHS[2], [golden(row) for row in old_new])
        manifest = m.prepare_inputs(self.root, backend=FakeBackend)
        self.assertEqual(manifest["status"], m.COMPLETE)
        self.assertFalse(manifest["traditional_features_supplied"])
        self.assertEqual({role: data["n"] for role, data in manifest["roles"].items()},
                         {"development": 1000, "primary_new": 500,
                          "supplementary_full": 1001, "legacy_full": 501})
        for role, expected in [("development", 1000), ("primary_new", 500),
                               ("supplementary_full", 1001), ("legacy_full", 501)]:
            frame = m.load_model_frame(self.root, role)
            self.assertEqual(len(frame), expected)
            self.assertEqual(set(frame.columns), set(m.OUTPUT_COLUMNS))
            self.assertEqual(m.make_raw_matrix(frame, CONFIG).shape, (expected, 66))
            self.assertEqual(m.make_date_matrix(frame, CONFIG).shape, (expected, 7))
        self.assertEqual(len(m.get_training_ids(self.root, "random_1000")), 1000)
        audit = json.loads((self.data / "feature_audit.json").read_text())
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["legacy_comparisons"][0]["matching_person_comparisons"]["development"], 501)
        self.assertFalse(audit["model_fits_or_scores_calculated"])


if __name__ == "__main__":
    unittest.main()
