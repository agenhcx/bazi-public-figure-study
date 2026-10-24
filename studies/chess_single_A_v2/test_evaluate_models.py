import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("evaluate_models", HERE / "evaluate_models.py")
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture_task(root, task="final_random_500", kind="final", families=("ridge",)):
    directory = root / task
    directory.mkdir(parents=True, exist_ok=True)
    expected = {"kind": kind, "training_ids": ["1", "2"], "train_n": 2,
                "median_elo": 15.0, "heldout_ids": ["3", "4"],
                "heldout_ratings": {"3": 12., "4": 18.}, "outer_fold": 0}
    hashes = {"config_sha256": "a", "data_manifest_sha256": "b", "analysis_lock_sha256": "c"}
    representations, files = {}, []
    for representation in e.REPRESENTATIONS:
        models, search_rows = {}, []
        for index, family in enumerate(families):
            name = f"models/{representation}/{family}.joblib"
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            estimator = DummyRegressor(strategy="constant", constant=15. + index)
            estimator.fit(np.zeros((2, 1)), [10., 20.])
            joblib.dump(estimator, path)
            checksum = e.digest(path)
            files.append({"path": name, "sha256": checksum})
            models[family] = {"status": "complete", "candidate_id": family + "_0",
                              "inner_mae": 5. + index, "model_file": name,
                              "model_sha256": checksum}
            search_rows.append({"candidate_id": family + "_0", "family": family,
                                "candidate": {"candidate_id": family + "_0", "family": family, "params": {}},
                                "mae": 5. + index, "status": "complete"})
        search_name = f"search_{representation}.json"
        dump(directory / search_name, {"status": "complete", "candidate_results": search_rows})
        files.append({"path": search_name, "sha256": e.digest(directory / search_name)})
        representations[representation] = {"selected_family": families[0],
                                            "selected_candidate_id": families[0] + "_0",
                                            "selected_inner_mae": 5., "family_models": models,
                                            "selected_model": dict(models[families[0]])}
    manifest = {"status": "complete", "task": task, "kind": kind,
                "train_n": 2, "training_ids_sha256": e.ids_hash(["1", "2"]),
                "median_elo": 15., **hashes,
                "files": files, "representations": representations}
    if kind == "development":
        name = "outer_predictions.csv"
        pd.DataFrame({"canonical_id": ["3", "4"], "rating": [12., 18.],
                      "pred_raw_A": [14., 16.], "pred_date_control": [13., 17.],
                      "pred_median": [15., 15.]}).to_csv(directory / name, index=False)
        manifest["development_predictions_file"] = name
        manifest["files"].append({"path": name, "sha256": e.digest(directory / name)})
    dump(directory / "trainer_manifest.json", manifest)
    return directory, manifest, expected, hashes


class MetricsTests(unittest.TestCase):
    def test_exact_metric_units_and_undefined_constant_spearman(self):
        metrics = e.regression_metrics([10, 20], [12, 16])
        self.assertEqual(metrics["mae"], 3.)
        self.assertAlmostEqual(metrics["rmse"], np.sqrt(10.))
        self.assertAlmostEqual(metrics["spearman"], 1.)
        self.assertIsNone(e.regression_metrics([10, 20], [15, 15])["spearman"])
        self.assertIsNone(e.regression_metrics([10, 10], [9, 11])["spearman"])

    def test_metrics_reject_nonfinite_or_different_lengths(self):
        with self.assertRaises(ValueError):
            e.regression_metrics([1, 2], [1, np.nan])
        with self.assertRaises(ValueError):
            e.regression_metrics([1, 2], [1])

    def test_identical_paired_predictions_give_exact_zero_interval(self):
        predictions = pd.DataFrame({"canonical_id": ["2", "1"], "rating": [20., 10.],
                                    "prediction": [18., 12.]})
        differences = e.paired_loss_difference(predictions, predictions.iloc[::-1])
        result = e.bootstrap_mean(differences["difference"], n_resamples=10000)
        self.assertEqual((result["estimate"], result["ci_low"], result["ci_high"]), (0., 0., 0.))

    def test_paired_alignment_uses_person_ids_not_row_order(self):
        first = pd.DataFrame({"canonical_id": ["2", "1"], "rating": [20., 10.],
                              "prediction": [24., 12.]})
        second = pd.DataFrame({"canonical_id": ["1", "2"], "rating": [10., 20.],
                               "prediction": [11., 22.]})
        paired = e.paired_loss_difference(first, second)
        self.assertEqual(paired["canonical_id"].tolist(), ["1", "2"])
        np.testing.assert_array_equal(paired["difference"], [1., 2.])
        self.assertEqual(e.bootstrap_mean([1., 1., 1.])["estimate"], 1.)

    def test_pairing_rejects_missing_duplicate_people_or_changed_targets(self):
        source = pd.DataFrame({"canonical_id": ["1", "2"], "rating": [10., 20.], "prediction": [11., 19.]})
        with self.assertRaises(ValueError):
            e.paired_loss_difference(source, source.iloc[:1])
        duplicate = source.copy()
        duplicate["canonical_id"] = ["1", "1"]
        with self.assertRaises(ValueError):
            e.paired_loss_difference(source, duplicate)
        changed = source.copy()
        changed.loc[0, "rating"] = 11.
        with self.assertRaises(ValueError):
            e.paired_loss_difference(source, changed)


class SealTests(unittest.TestCase):
    def test_complete_task_ledger_and_model_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory, manifest, expected, hashes = fixture_task(root)
            records, ledger = e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge"])
            self.assertEqual(len(records), 1)
            self.assertEqual(len(ledger[0]["files"]), 4)
            model = directory / manifest["files"][0]["path"]
            model.write_bytes(model.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge"])

    def test_missing_task_blocks_before_external_data_access(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, manifest, expected, hashes = fixture_task(root)
            specs = {manifest["task"]: expected, "final_random_800": expected}
            with self.assertRaisesRegex(ValueError, "Incomplete task set"):
                e.validate_runs(root, hashes, specs, ["ridge"])

    def test_root_digest_training_people_and_unlisted_files_are_rejected(self):
        for mutation in ("digest", "people", "extra"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                directory, manifest, expected, hashes = fixture_task(root)
                if mutation == "digest":
                    manifest["config_sha256"] = "wrong"
                elif mutation == "people":
                    manifest["training_ids_sha256"] = e.ids_hash(["1", "3"])
                else:
                    (directory / "unlisted.txt").write_text("extra")
                dump(directory / "trainer_manifest.json", manifest)
                with self.assertRaises(ValueError):
                    e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge"])

    def test_final_selection_must_use_inner_score_not_external_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory, manifest, expected, hashes = fixture_task(root, families=("ridge", "small_mlp"))
            chosen = manifest["representations"]["raw_A"]
            chosen["selected_family"] = "small_mlp"
            chosen["selected_candidate_id"] = "small_mlp_0"
            chosen["selected_inner_mae"] = 6.
            chosen["selected_model"] = dict(chosen["family_models"]["small_mlp"])
            dump(directory / "trainer_manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "CV winner"):
                e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge", "small_mlp"])

    def test_chained_near_ties_keep_distinct_global_and_family_models(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory, manifest, expected, hashes = fixture_task(root, families=("ridge", "small_mlp"))
            rows = [{"candidate_id": "ridge_0", "family": "ridge", "mae": 1.4e-12, "status": "complete"},
                    {"candidate_id": "ridge_1", "family": "ridge", "mae": .5e-12, "status": "complete"},
                    {"candidate_id": "small_mlp_0", "family": "small_mlp", "mae": 0., "status": "complete"}]
            self.assertEqual(e._best_record(rows)["candidate_id"], "ridge_1")
            self.assertEqual(e._best_record(rows[:2])["candidate_id"], "ridge_0")
            for representation in e.REPRESENTATIONS:
                item = manifest["representations"][representation]
                item["family_models"]["ridge"]["inner_mae"] = 1.4e-12
                item["family_models"]["small_mlp"]["inner_mae"] = 0.
                chosen = dict(item["family_models"]["ridge"])
                selected_path = directory / f"models/{representation}/selected_global.joblib"
                selected_estimator = DummyRegressor(strategy="constant", constant=17.)
                selected_estimator.fit(np.zeros((2, 1)), [10., 20.])
                joblib.dump(selected_estimator, selected_path)
                selected_name = selected_path.relative_to(directory).as_posix()
                chosen.update({"candidate_id": "ridge_1", "inner_mae": .5e-12,
                               "model_file": selected_name, "model_sha256": e.digest(selected_path)})
                manifest["files"].append({"path": selected_name, "sha256": e.digest(selected_path)})
                item.update({"selected_family": "ridge", "selected_candidate_id": "ridge_1",
                             "selected_inner_mae": .5e-12, "selected_model": chosen})
                name = f"search_{representation}.json"
                dump(directory / name, {"status": "complete", "candidate_results": rows})
                for entry in manifest["files"]:
                    if entry["path"] == name:
                        entry["sha256"] = e.digest(directory / name)
            dump(directory / "trainer_manifest.json", manifest)
            e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge", "small_mlp"])
            chosen = manifest["representations"]["raw_A"]["selected_model"]
            wrong_alias = manifest["representations"]["raw_A"]["family_models"]["ridge"]
            chosen["model_file"], chosen["model_sha256"] = wrong_alias["model_file"], wrong_alias["model_sha256"]
            dump(directory / "trainer_manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "alias the same saved model"):
                e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge", "small_mlp"])

    def test_heldout_people_and_targets_are_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory, manifest, expected, hashes = fixture_task(root, "dev_f0_n400", "development")
            e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge"])
            path = directory / "outer_predictions.csv"
            frame = pd.read_csv(path)
            frame.loc[0, "rating"] = 13.
            frame.to_csv(path, index=False)
            for entry in manifest["files"]:
                if entry["path"] == path.name:
                    entry["sha256"] = e.digest(path)
            dump(directory / "trainer_manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "targets"):
                e.validate_runs(root, hashes, {manifest["task"]: expected}, ["ridge"])

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                e.safe_path(Path(temp), "../outside.joblib")

    def test_rehashed_artifact_after_full_seal_blocks_before_external_access(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            study = root / e.RELATIVE_STUDY
            dump(study / "config.json", {"families": [{"name": "ridge"}]})
            dump(study / "data/data_manifest.json", {})
            dump(study / "analysis_lock.json", {})
            hashes = e.reference_hashes(root)
            runs, specs = root / "runs", {}
            for task in e.EXPECTED_TASKS:
                kind = "development" if task.startswith("dev_") else "final"
                directory, manifest, spec, _ = fixture_task(runs, task, kind)
                manifest.update(hashes)
                dump(directory / "trainer_manifest.json", manifest)
                specs[task] = spec
            expected_candidates = [{"candidate_id": "ridge_0", "family": "ridge", "params": {}}]
            lock_module = types.SimpleNamespace(verify_analysis_lock=lambda root: None)
            model_module = types.SimpleNamespace(candidate_configs=lambda config: expected_candidates)
            with patch.dict(sys.modules, {"lock_utils": lock_module, "models": model_module}), \
                    patch.object(e, "expected_task_specs", return_value=specs):
                sealed = e.seal_models(root, runs, root / "sealed")
                self.assertEqual(sealed["task_count"], 20)
                self.assertFalse(sealed["external_predictions_or_scores_created"])
                e.verify_seal(root, runs, root / "sealed/fitted_models_lock.json")
                manifest_path = runs / "final_random_500/trainer_manifest.json"
                manifest = json.loads(manifest_path.read_text())
                model = manifest["representations"]["raw_A"]["family_models"]["ridge"]
                path = manifest_path.parent / model["model_file"]
                path.write_bytes(path.read_bytes() + b"changed after seal")
                new_hash = e.digest(path)
                model["model_sha256"] = new_hash
                manifest["representations"]["raw_A"]["selected_model"]["model_sha256"] = new_hash
                for entry in manifest["files"]:
                    if entry["path"] == model["model_file"]:
                        entry["sha256"] = new_hash
                dump(manifest_path, manifest)
                with patch.object(e, "external_scores") as external, \
                        patch.object(e, "development_scores") as development:
                    with self.assertRaisesRegex(ValueError, "changed after sealing"):
                        e.evaluate_models(root, runs, root / "sealed/fitted_models_lock.json", root / "results")
                    external.assert_not_called()
                    development.assert_not_called()


class EvaluationTests(unittest.TestCase):
    def test_full_fixed_menu_and_ranked1000_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = {}
            for subset in e.FINAL_SUBSETS:
                directory, manifest, expected, _ = fixture_task(root, "final_" + subset)
                records["final_" + subset] = {"directory": directory, "manifest": manifest, "expected": expected}
            # A near-tied global winner can differ from its family's own winner.
            # Selected-pipeline predictions must use that separately saved object.
            selected_path = records["final_random_1000"]["directory"] / "selected_global.joblib"
            selected_estimator = DummyRegressor(strategy="constant", constant=17.)
            selected_estimator.fit(np.zeros((2, 1)), [10., 20.])
            joblib.dump(selected_estimator, selected_path)
            for representation in e.REPRESENTATIONS:
                record = records["final_random_1000"]
                chosen = dict(record["manifest"]["representations"][representation]["selected_model"])
                chosen.update({"candidate_id": "ridge_global", "model_file": selected_path.name,
                               "model_sha256": e.digest(selected_path)})
                record["manifest"]["representations"][representation]["selected_model"] = chosen
            frame = pd.DataFrame({"canonical_id": ["4", "3", "5"], "rating": [18., 12., 20.]})
            model_inputs = types.SimpleNamespace(
                load_model_frame=lambda *_: frame.copy(),
                make_raw_matrix=lambda frame, config: np.zeros((len(frame), 1)),
                make_date_matrix=lambda frame, config: np.zeros((len(frame), 1)))
            with patch.dict(sys.modules, {"model_inputs": model_inputs}):
                metrics, predictions = e.external_scores(records, root, {"families": [{"name": "ridge"}]})
            self.assertEqual(set(metrics["subset"]), set(e.ALL_SUBSETS))
            self.assertEqual(set(metrics["cohort"]), set(e.EXTERNAL_ROLES))
            self.assertEqual(len(metrics), 6 * 3 * 5)
            self.assertEqual(len(predictions), 6 * 3 * 5 * 3)
            original = e.select_predictions(predictions, "random_1000", "raw_A")
            alias = e.select_predictions(predictions, "ranked_1000_with_ties", "raw_A")
            a, b = e.align_predictions(original, alias)
            np.testing.assert_array_equal(a["prediction"], b["prediction"])
            np.testing.assert_array_equal(a["prediction"], [17., 17., 17.])
            self.assertTrue((metrics[metrics.subset == "ranked_1000_with_ties"].source_subset == "random_1000").all())

    def test_primary_sign_and_all_prespecified_size_contrasts(self):
        blocks = []
        for size in (500, 800, 1000):
            for representation in e.REPRESENTATIONS:
                block = pd.DataFrame({"canonical_id": ["1", "2"], "rating": [10., 20.],
                                      "prediction": [10., 20.] if representation == "raw_A" else [12., 22.],
                                      "subset": f"random_{size}", "representation": representation,
                                      "cohort": "primary_new", "model": "selected_pipeline"})
                blocks.append(block)
        config = {"primary": {"interval": {"n_resamples": 10000, "random_state": 20261023, "confidence_level": .95},
                               "minimum_meaningful_gain_elo": None}}
        primary, paired, comparisons = e.inferential_summaries(pd.concat(blocks), config)
        self.assertEqual(primary["estimate"], 2.)
        self.assertEqual((primary["ci_low"], primary["ci_high"]), (2., 2.))
        self.assertEqual(len(comparisons), 6)
        self.assertTrue((comparisons["estimate"] == 0).all())
        self.assertTrue((paired["difference"] == 2).all())


if __name__ == "__main__":
    unittest.main()
