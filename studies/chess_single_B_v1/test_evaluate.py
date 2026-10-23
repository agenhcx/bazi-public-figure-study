import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

import evaluate as report


class ConstantPredictor:
    def __init__(self, constant):
        self.constant = constant

    def predict(self, frame):
        return np.full(len(frame), self.constant)


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fixture(root):
    inputs = root / "inputs"
    inputs.mkdir()
    development = pd.DataFrame({"canonical_id": [str(i) for i in range(10000, 11000)],
                                "rating": 2500 + np.arange(1000) % 7})
    external = pd.DataFrame({"canonical_id": [str(i) for i in range(20000, 20500)],
                            "rating": 2520 + np.arange(500) % 9})
    tasks = {}
    splits = list(KFold(5, shuffle=True, random_state=report.OUTER_SEED).split(development))
    seal = {"protocol_id": "chess-single-B-v1", "status": "all_B1_models_sealed_before_external_scoring",
            "source_lock_sha256": "a" * 64, "tasks": {}, "files": {}}
    for task in [*(f"outer-{i}" for i in range(5)), "final"]:
        folder = inputs / task
        folder.mkdir()
        train, held = (np.arange(1000), None) if task == "final" else splits[int(task[-1])]
        median = float(np.median(development.iloc[train].rating))
        manifest = {"task": task, "status": "complete", "train_n": len(train),
                    "median_elo": median, "representations": {}}
        for rep in report.REPS:
            candidate = {"candidate_id": rep + "_000", "representation": rep, "alpha": 1.}
            if rep == "b1":
                candidate.update(middle=.5, residual_ratio=.5, month=1.5)
            n = 180 if rep == "b1" else 5
            entry = {"candidate": candidate, "candidate_id": candidate["candidate_id"], "inner_mae": 1.,
                     "refit_diagnostics": {"warnings": [], "convergence_warnings": 0},
                     "search_stats": {"candidates": n, "valid_candidates": n, "invalid_candidates": 0,
                                      "fit_entries": 4 * n, "failed_fit_entries": 0,
                                      "warning_records": 0, "convergence_warnings": 0}}
            if task == "final":
                (folder / "models").mkdir(exist_ok=True)
                path = folder / "models" / f"{rep}.joblib"
                joblib.dump(ConstantPredictor(median + {"b1": .2, "raw": 1., "date": -.5}[rep]), path)
                entry.update(model_file=f"models/{rep}.joblib", model_sha256=report.digest(path))
            manifest["representations"][rep] = entry
        if held is not None:
            frame = development.iloc[held].copy()
            frame["outer_fold"] = int(task[-1])
            for rep in report.MODELS:
                frame[f"prediction_{rep}"] = median + {"b1": .2, "raw": 1., "date": -.5, "median": 0.}[rep]
            frame.to_csv(folder / "outer_predictions.csv", index=False)
        save(folder / "task_manifest.json", manifest)
        tasks[task] = (folder, manifest)
        seal["tasks"][task] = {"directory": task, "manifest_sha256": report.digest(folder / "task_manifest.json")}
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                seal["files"][path.relative_to(inputs).as_posix()] = report.digest(path)
    save(inputs / "fitted_models_lock.json", seal)
    return inputs, development, external, seal, tasks


def fake_verify(root, inputs):
    seal = report.read_json(inputs / "fitted_models_lock.json")
    for path, expected in seal["files"].items():
        if report.digest(inputs / path) != expected:
            raise ValueError("Sealed file changed")
    return seal


class EvaluationTests(unittest.TestCase):
    def test_metrics_and_paired_sign_are_exact_and_constant_rank_is_undefined(self):
        score = report.score([1., 3.], [2., 2.])
        self.assertEqual(score, {"n": 2, "mae": 1., "rmse": 1., "spearman": None})
        frame = pd.DataFrame({"rating": [1., 3.], "prediction_b1": [1., 3.],
                              "prediction_raw": [2., 2.], "prediction_date": [0., 4.],
                              "prediction_median": [2., 2.]})
        differences = report.paired_differences(frame, "synthetic")
        self.assertTrue(all(row["mean_absolute_error_difference"] == -1 for row in differences))
        self.assertTrue(all(row["negative_favors"] == "b1" for row in differences))
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            report.score([1., 2.], [1., np.nan])

    def test_complete_synthetic_joint_evaluation_preserves_all_models_and_predictions(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            inputs, development, external, seal, tasks = fixture(root)
            calls = []
            def verify(root, inputs):
                calls.append("seal")
                return fake_verify(root, inputs)
            def load(root, role):
                calls.append(role)
                return development.copy() if role == "development" else external.copy()
            with patch.dict("sys.modules", {"train": types.SimpleNamespace(verify_seal=verify),
                    "model_inputs": types.SimpleNamespace(load_model_frame=load)}):
                summary = report.run_evaluation(root, inputs, root / "out", make_plots=False)
            self.assertEqual(calls, ["seal", "development", "primary_new"])
            self.assertEqual(summary["task_count"], 6)
            self.assertTrue(summary["external_previously_seen"])
            self.assertFalse(summary["new_blind_test_claim"])
            self.assertEqual(len(summary["metrics"]), 8)
            self.assertEqual(len(report.read_csv(root / "out/nested_cv_predictions.csv")), 1000)
            self.assertEqual(len(report.read_csv(root / "out/exploratory_2023_new_predictions.csv")), 500)
            for entry in summary["outputs"]:
                self.assertEqual(report.digest(root / "out" / entry["path"]), entry["sha256"])
            with zipfile.ZipFile(root / "out/training_checkpoint_bundle.zip") as archive:
                self.assertEqual(set(archive.namelist()), {"fitted_models_lock.json", *seal["files"]})
                for relative, expected in seal["files"].items():
                    self.assertEqual(hashlib.sha256(archive.read(relative)).hexdigest(), expected)
            text = (root / "out/REPORT.md").read_text()
            self.assertIn("Search budgets are unequal", text)
            self.assertIn("negative favors B1", text)
            self.assertIn("not a\nnew blind test", text)

    def test_failed_seal_blocks_external_loading_and_model_deserialization(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            def reject(root, inputs):
                raise ValueError("invalid seal")
            loader = unittest.mock.Mock()
            with patch.dict("sys.modules", {"train": types.SimpleNamespace(verify_seal=reject),
                    "model_inputs": types.SimpleNamespace(load_model_frame=loader)}), patch.object(report.joblib, "load") as deserialize:
                with self.assertRaisesRegex(ValueError, "invalid seal"):
                    report.run_evaluation(root, root / "inputs", root / "out", make_plots=False)
            loader.assert_not_called()
            deserialize.assert_not_called()

    def test_outer_duplicate_ids_and_wrong_training_median_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            inputs, development, external, seal, tasks = fixture(Path(name))
            table = report.read_csv(inputs / "outer-0/outer_predictions.csv")
            table.loc[1, "canonical_id"] = table.loc[0, "canonical_id"]
            table.to_csv(inputs / "outer-0/outer_predictions.csv", index=False)
            with self.assertRaisesRegex(ValueError, "duplicate, missing"):
                report.aggregate_outer(development, tasks)
        with tempfile.TemporaryDirectory() as name:
            inputs, development, external, seal, tasks = fixture(Path(name))
            tasks["outer-0"][1]["median_elo"] += 1
            with self.assertRaisesRegex(ValueError, "median differs"):
                report.aggregate_outer(development, tasks)

    def test_constraints_and_missing_tasks_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            inputs, development, external, seal, tasks = fixture(Path(name))
            tasks["final"][1]["representations"]["b1"]["candidate"]["month"] = .9
            with self.assertRaisesRegex(ValueError, "violate constraints"):
                report.selection_tables(tasks)
            del seal["tasks"]["outer-0"]
            with self.assertRaisesRegex(ValueError, "exactly five outer"):
                report.load_tasks(inputs, seal)


if __name__ == "__main__":
    unittest.main()
