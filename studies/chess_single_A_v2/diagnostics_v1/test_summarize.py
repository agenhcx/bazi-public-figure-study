import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

import summarize as report


def save_json(path, value):
    path.write_text(json.dumps(value) + "\n")


def seal(folder, filename, value, field="outputs"):
    value[field] = [{"path": p.name, "sha256": report.digest(p)}
                    for p in sorted(folder.iterdir()) if p.is_file() and p.name != filename]
    save_json(folder / filename, value)


def fixture(root):
    inputs = root / "inputs"; inputs.mkdir()
    audit = inputs / "diag-audit"; audit.mkdir()
    ids = np.array([str(10000 + i) for i in range(1000)])
    y = 2500 + np.arange(1000) % 3
    folds = np.arange(1000) % 5
    outer = pd.DataFrame({"canonical_id": ids, "rating": y, "pred_raw_A": 2501.,
                          "pred_date_control": 2501., "pred_median": 2501., "outer_fold": folds})
    pd.concat([outer.assign(train_n=n) for n in (400, 600, 800)]).to_csv(audit / "existing_development_predictions.csv", index=False)
    models = [{"task": "final_random_1000", "representation": "benchmark", "family": "training_median", "train_mae": 1., "inner_oof_mae": 2.}]
    models += [{"task": "final_random_1000", "representation": rep, "family": family,
                "train_mae": 1., "inner_oof_mae": 2.}
               for rep in report.REPS for family in report.MODELS[1:]]
    pd.DataFrame(models).to_csv(audit / "existing_model_metrics.csv", index=False)
    pd.DataFrame([{"stage": "inner_search", "representation": rep, "family": family,
                   "fit_entries_with_convergence_warning": 0, "fit_entries": 10,
                   "fraction_fit_entries_with_convergence_warning": 0.}
                  for rep in report.REPS for family in report.MODELS[1:]]).to_csv(audit / "existing_warning_summary.csv", index=False)
    seal(audit, "existing_audit_summary.json", {"status": "complete_read_only_A1_development_audit",
         "external_data_or_scores_loaded": False, "tasks": 20, "unique_model_objects_scored": 80,
         "warning_records": 0, "fit_entries_with_convergence_warning": 0, "warning_fit_entries": 100,
         "selected_final_refit_warning_records": 0})
    for fold in range(5):
        folder = inputs / f"diag-mlp-{fold}"; folder.mkdir()
        held, train, metrics, seeds = [], [], [], []
        for rep in report.REPS:
            for selected, dest in ((folds == fold, held), (folds != fold, train)):
                for identity, target in zip(ids[selected], y[selected]):
                    dest.append({"canonical_id": identity, "fold": fold, "representation": rep,
                        "rating": target, "pred_original": 2501., "pred_extended": 2501., "pred_median": 2501.})
            for budget in ("original", "extended"):
                train_score = report.score(y[folds != fold], np.full(800, 2501.))
                held_score = report.score(y[folds == fold], np.full(200, 2501.))
                metrics.append({"representation": rep, "budget": budget,
                    **{f"train_{name}": train_score[name] for name in ("mae", "rmse")},
                    **{f"heldout_{name}": held_score[name] for name in ("mae", "rmse")}})
                for seed in (20261021, 20261022, 20261023):
                    seeds.append({"representation": rep, "budget": budget, "fold": fold,
                                  "seed": seed, "convergence_warning_count": 0, "loss": 1., "n_iter": 10})
        pd.DataFrame(held).to_csv(folder / "mlp_budget_predictions.csv", index=False)
        pd.DataFrame(train).to_csv(folder / "mlp_budget_training_predictions.csv", index=False)
        pd.DataFrame(metrics).to_csv(folder / "mlp_budget_metrics.csv", index=False)
        save_json(folder / "mlp_seed_diagnostics.json", seeds)
        seal(folder, "mlp_budget_summary.json", {"status": "complete", "fold": fold, "external_data_loaded": False}, "files")
    for signal in report.SIGNALS:
        folder = inputs / f"diag-control-{signal}"; folder.mkdir()
        rows, metric_rows = [], []
        for strength in ((0.,) if signal == "null" else (.5, 2.)):
            for replicate in range(2):
                scenario = f"{signal}_s{strength:g}_r{replicate}"
                target = y + strength + replicate
                prediction = np.full(1000, 2501. + strength + replicate)
                values = report.score(target, prediction)
                for model in report.MODELS:
                    metric_rows.append({"signal": signal, "strength": strength, "replicate": replicate,
                        "scenario_id": scenario, "model": model, "status": "complete", **values,
                        "median_mae": values["mae"], "mae_gain": 0.})
                    rows.extend({"signal": signal, "strength": strength, "replicate": replicate,
                        "scenario_id": scenario, "model": model, "canonical_id": identity,
                        "synthetic_target": actual, "prediction": pred, "fold": int(fold)}
                        for identity, actual, pred, fold in zip(ids, target, prediction, folds))
        pd.DataFrame(rows).to_csv(folder / "synthetic_predictions.csv.gz", index=False, compression="gzip")
        pd.DataFrame(metric_rows).to_csv(folder / "pooled_metrics.csv", index=False)
        seal(folder, "manifest.json", {"status": "complete", "diagnostic": "A1_synthetic_recovery_v1",
            "signal": signal, "external_data_loaded": False, "fit_attempts": 50 if signal == "null" else 100,
            "failed_fit_attempts": 0, "fit_attempts_with_convergence_warning": 0, "warning_records": 0})
    for filename in ("PLAN.md", "diagnostic_lock.json", "summarize.py"):
        path = root / report.REL / filename; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(filename)
    return inputs


class SummaryTests(unittest.TestCase):
    def test_complete_joint_synthetic_workers_recompute_all_metrics(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); inputs = fixture(root)
            summary = report.run_summary(root, inputs, root / "out", verify_lock=False, make_plots=False)
            self.assertEqual(summary["worker_count"], 10)
            self.assertFalse(summary["external_predictive_scoring_performed"])
            self.assertEqual(len(summary["mlp_pooled_metrics"]), 6)
            for row in summary["mlp_pooled_improvements"]:
                self.assertEqual(row["original_minus_extended_mae"], 0)
            for entry in summary["outputs"]:
                self.assertEqual(report.digest(root / "out" / entry["path"]), entry["sha256"])
            text = (root / "out/REPORT.md").read_text()
            self.assertIn("Checking only the", text)
            self.assertIn("squared error plus L2", text)
            self.assertEqual(len(pd.read_csv(root / "out/synthetic_pooled_metrics.csv")), 84)

    def test_missing_worker_is_blocked(self):
        with tempfile.TemporaryDirectory() as name:
            inputs = Path(name)
            with self.assertRaisesRegex(ValueError, "exactly ten workers"):
                report.locate_workers(inputs)

    def test_duplicate_ids_block_even_with_updated_worker_checksum(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); inputs = fixture(root)
            folder = inputs / "diag-mlp-0"
            path = folder / "mlp_budget_predictions.csv"
            table = report.read_csv(path)
            table.loc[1, "canonical_id"] = table.loc[0, "canonical_id"]
            table.to_csv(path, index=False)
            value = report.read_json(folder / "mlp_budget_summary.json")
            seal(folder, "mlp_budget_summary.json", value, "files")
            with self.assertRaisesRegex(ValueError, "Duplicate, missing"):
                report.run_summary(root, inputs, root / "out", verify_lock=False, make_plots=False)

    def test_changed_worker_file_is_blocked(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder / "data.csv").write_text("a\n1\n")
            seal(folder, "manifest.json", {"status": "complete"})
            value = report.read_json(folder / "manifest.json")
            (folder / "data.csv").write_text("a\n2\n")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                report.verify_outputs(folder / "manifest.json", value)


if __name__ == "__main__": unittest.main()
