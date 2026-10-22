"""Exercise the complete artifact barrier using synthetic data and dummy fits.

This test never loads participant data or enables the repository's research
configuration. Only a temporary root is allowed through the patched I/O/lock
interfaces. All fixed tasks and candidate records still use production code.
"""
from contextlib import redirect_stdout
from datetime import date, timedelta
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def synthetic_frame(ids, *, development=False):
    from model_inputs import STEMS, BRANCHES

    rows = []
    for index, fid in enumerate(ids):
        birthday = date(1960, 1, 1) + timedelta(days=(int(fid) * 17) % 14000)
        if development:
            rating = 3000 - int(fid)
            # Preserve explicit 500/501 and 800/801 cutoff ties.
            if int(fid) in (501, 801):
                rating += 1
        else:
            rating = 2100 + (int(fid) * 7) % 401
        row = {"canonical_id": str(fid), "snapshot": "2013-01" if development else "2023-01",
               "exact_dob_frozen": birthday.isoformat(), "rating": rating}
        for position, prefix in enumerate(("year", "month", "day")):
            number = int(fid) + position * 5
            stem, branch = STEMS[number % 10], BRANCHES[number % 12]
            row[prefix + "_stem"] = stem
            row[prefix + "_branch"] = branch
            row[prefix + "_pillar"] = stem + branch
        rows.append(row)
    return pd.DataFrame(rows).sort_values("canonical_id").reset_index(drop=True)


class PipelineIntegrationTests(unittest.TestCase):
    def test_all_twenty_tasks_seal_evaluate_and_tamper_barrier_with_synthetic_inputs(self):
        inputs = importlib.import_module("model_inputs")
        models = importlib.import_module("models")
        trainer = importlib.import_module("train_models")
        evaluator = importlib.import_module("evaluate_models")
        locks = importlib.import_module("lock_utils")

        research_config_path = HERE / "config.json"
        original_config_bytes = research_config_path.read_bytes()
        config = json.loads(original_config_bytes)
        config["fit_allowed"] = True  # This copy is written only below temp_root.
        expected_families = {item["name"] for item in config["families"]}
        self.assertEqual(len(models.candidate_configs(config)), 33)

        with tempfile.TemporaryDirectory(prefix="chess-synthetic-integration-") as temporary:
            root = Path(temporary).resolve()
            study = root / "studies/chess_single_A_v2"
            runs, seal_dir, result_dir = root / "runs", root / "sealed", root / "results"
            write_json(study / "config.json", config)
            write_json(study / "analysis_lock.json", {"status": "synthetic_test_only", "root": str(root)})
            ids = [str(fid) for fid in range(1, 1001)]
            primary_ids = [str(fid) for fid in range(2001, 2501)]
            full_ids = ids[:600] + primary_ids[:300] + [str(fid) for fid in range(10001, 10102)]
            frames = {
                "development": synthetic_frame(ids, development=True),
                "primary_new": synthetic_frame(primary_ids),
                "supplementary_full": synthetic_frame(full_ids),
                "legacy_full": synthetic_frame(full_ids[:501]),
            }
            self.assertEqual({role: len(frame) for role, frame in frames.items()},
                             {"development": 1000, "primary_new": 500,
                              "supplementary_full": 1001, "legacy_full": 501})
            self.assertFalse(set(ids) & set(primary_ids))
            # Bind actual temporary files to data_manifest bytes, although the
            # strict synthetic loader deliberately never accesses real CSVs.
            role_info = {}
            for role, frame in frames.items():
                path = study / "data" / f"synthetic_{role}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                frame.to_csv(path, index=False)
                role_info[role] = {"n": len(frame), "path": path.relative_to(root).as_posix(),
                                   "sha256": evaluator.digest(path)}
            write_json(study / "data/data_manifest.json", {"status": inputs.COMPLETE, "roles": role_info,
                                                           "synthetic_test_only": True})

            random_ids = sorted(ids, key=lambda fid: (hashlib.sha256(f"20261024\n{fid}".encode()).hexdigest(), fid))
            subsets = {f"random_{n}": random_ids[:n] for n in (500, 800, 1000)}
            by_rating = frames["development"].sort_values(["rating", "canonical_id"], ascending=[False, True])
            for n in (500, 800, 1000):
                cutoff = by_rating.iloc[n - 1]["rating"]
                subsets[f"ranked_{n}_with_ties"] = by_rating.loc[
                    by_rating.rating >= cutoff, "canonical_id"].tolist()
            self.assertEqual([len(subsets[f"ranked_{n}_with_ties"]) for n in (500, 800, 1000)],
                             [501, 801, 1000])
            calls = []
            forbid_external = [True]

            def strict_root(candidate):
                self.assertEqual(Path(candidate).resolve(), root, "Synthetic test attempted real-root access")

            def load_frame(candidate_root, role):
                strict_root(candidate_root)
                self.assertIn(role, frames)
                if forbid_external[0] and role != "development":
                    raise AssertionError("An external frame was read before the artifact barrier passed")
                calls.append(role)
                return frames[role].copy()

            def training_ids(candidate_root, label):
                strict_root(candidate_root)
                self.assertIn(label, subsets)
                return list(subsets[label])

            def synthetic_lock(candidate_root, **unused):
                strict_root(candidate_root)
                self.assertTrue(json.loads((study / "config.json").read_text())["fit_allowed"])
                return {"status": "synthetic_test_only"}

            def dummy_factory(candidate, supplied_config):
                self.assertIn(candidate["family"], expected_families)
                self.assertEqual(supplied_config["families"], config["families"])
                return DummyRegressor(strategy="mean")

            with patch.object(inputs, "load_model_frame", side_effect=load_frame), \
                 patch.object(inputs, "get_training_ids", side_effect=training_ids), \
                 patch.object(locks, "verify_analysis_lock", side_effect=synthetic_lock), \
                 patch.object(models, "build_estimator", side_effect=dummy_factory), \
                 redirect_stdout(io.StringIO()):
                manifests = {}
                for task in evaluator.EXPECTED_TASKS:
                    manifests[task] = trainer.run_task(root, task, runs / task)
                self.assertEqual(len(manifests), 20)
                self.assertTrue(all(item["status"] == "complete" for item in manifests.values()))
                self.assertTrue(all(item["external_data_loaded"] is False for item in manifests.values()))
                self.assertEqual(set(calls), {"development"})
                for task, manifest in manifests.items():
                    self.assertEqual(set(manifest["representations"]), {"raw_A", "date_control"})
                    for representation in ("raw_A", "date_control"):
                        rep = manifest["representations"][representation]
                        self.assertEqual(rep["selected_family"], "ridge")
                        self.assertEqual(rep["selected_model"]["status"], "complete")
                        if task.startswith("final_"):
                            self.assertEqual(set(rep["family_models"]), expected_families)
                        search = json.loads((runs / task / f"search_{representation}.json").read_text())
                        self.assertEqual(len(search["candidate_results"]), 33)
                seal = evaluator.seal_models(root, runs, seal_dir)
                seal_file = seal_dir / "fitted_models_lock.json"
                self.assertEqual(seal["status"], evaluator.SEALED_STATUS)
                self.assertEqual(seal["task_count"], 20)
                self.assertFalse(seal["external_predictions_or_scores_created"])
                self.assertEqual(seal["aliases"], {"ranked_1000_with_ties": "random_1000"})
                self.assertEqual(set(calls), {"development"})

                forbid_external[0] = False
                result = evaluator.evaluate_models(root, runs, seal_file, result_dir)
                self.assertEqual(result["status"], "complete_fixed_external_evaluation")
                self.assertTrue(result["all_prespecified_tasks_complete"])
                self.assertFalse(result["model_or_grid_changes_after_scoring"])
                self.assertEqual(result["metrics_rows"], 234)
                self.assertEqual(result["prediction_rows"], 156156)
                primary = json.loads((result_dir / "primary_result.json").read_text())
                self.assertEqual(primary["n"], 500)
                self.assertEqual(primary["estimate"], 0.0)
                self.assertEqual((primary["ci_low"], primary["ci_high"]), (0.0, 0.0))
                self.assertEqual(primary["raw_metrics"]["mae"], primary["date_control_metrics"]["mae"])
                development = pd.read_csv(result_dir / "development_predictions.csv", dtype={"canonical_id": str})
                self.assertEqual(len(development), 3000)
                for size, group in development.groupby("train_n"):
                    self.assertIn(size, (400, 600, 800))
                    self.assertEqual(len(group), 1000)
                    self.assertEqual(set(group.canonical_id), set(ids))
                    self.assertEqual(group.groupby("outer_fold").size().tolist(), [200] * 5)
                metrics = pd.read_csv(result_dir / "external_metrics.csv")
                self.assertEqual(set(metrics.subset), set(subsets))
                self.assertEqual(set(metrics.cohort), {"primary_new", "supplementary_full", "legacy_full"})
                first = metrics[metrics.subset == "random_1000"].drop(columns=["subset"]).reset_index(drop=True)
                alias = metrics[metrics.subset == "ranked_1000_with_ties"].drop(columns=["subset"]).reset_index(drop=True)
                pd.testing.assert_frame_equal(first, alias)
                self.assertTrue((result_dir / "REPORT.md").is_file())
                # Actual plotting is part of the integration contract, so schema
                # disagreements cannot be hidden by a hand-built plot fixture.
                self.assertEqual(len(list(result_dir.glob("*.png"))), 3)
                self.assertEqual(len(list(result_dir.glob("*.svg"))), 3)

                # A changed saved model must stop evaluation before loading an
                # external frame, even if the changed pickle might still load.
                victim_manifest = manifests["final_random_1000"]
                model_name = victim_manifest["representations"]["raw_A"]["selected_model"]["model_file"]
                victim = runs / "final_random_1000" / model_name
                victim.write_bytes(victim.read_bytes() + b"\nsynthetic-tamper")
                calls.clear()
                forbid_external[0] = True
                with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                    evaluator.evaluate_models(root, runs, seal_file, root / "tampered_results")
                self.assertFalse(set(calls) - {"development"})
            self.assertEqual(research_config_path.read_bytes(), original_config_bytes)


if __name__ == "__main__":
    unittest.main()
