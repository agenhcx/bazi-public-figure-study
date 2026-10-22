#!/usr/bin/env python3
"""Paired, post hoc MLP optimization-budget diagnostics using 2013 only.

The candidate in each representation/fold is the already recorded A1 MLP
family winner. No candidate, seed, budget or stopping condition is selected
using these diagnostic held-out outcomes. The old outer folds have already
been viewed: these are development diagnostics, not a new confirmatory test.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from threadpoolctl import threadpool_limits

STUDY_DIR = Path(__file__).resolve().parents[1]
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))
import lock_utils
import model_inputs
import models
import train_models

BUDGETS = {
    "original": {"max_iter": 1000, "max_fun": 20000},
    "extended": {"max_iter": 5000, "max_fun": 100000},
}
REPRESENTATIONS = ("raw_A", "date_control")
SEEDS = (20261021, 20261022, 20261023)
SCOPE = (
    "Post hoc development diagnostic on already viewed 2013 outer folds; "
    "not a new confirmatory evaluation. The fixed original MLP candidate and "
    "all three seeds are retained, and no budget is selected from these scores."
)
OBJECTIVE = (
    "Each seed optimizes squared error plus L2 regularization on the "
    "training-fold-standardized target. A lower optimizer loss need not lower "
    "MAE or held-out error. loss_ is in the estimator's standardized objective "
    "units, while reported prediction errors are original Elo units."
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def config_for_budget(config: dict, budget: str) -> dict:
    """Copy A1 settings, allowing precisely the two fixed budget changes."""
    if budget not in BUDGETS:
        raise ValueError(f"Unknown optimization budget: {budget}")
    result = deepcopy(config)
    matches = [row for row in result["families"] if row["name"] == "small_mlp"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one original MLP family")
    fixed = matches[0]["fixed"]
    if ({key: fixed[key] for key in BUDGETS["original"]} != BUDGETS["original"]
            or tuple(fixed["random_states"]) != SEEDS):
        raise ValueError("Original MLP budget/seeds differ from A1")
    fixed.update(BUDGETS[budget])
    return result


def prediction_metrics(actual, prediction) -> dict:
    actual = np.asarray(actual, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    if (actual.shape != prediction.shape or actual.ndim != 1
            or not np.isfinite(actual).all() or not np.isfinite(prediction).all()):
        raise ValueError("Invalid diagnostic target/prediction")
    residual = prediction - actual
    return {"mae": float(np.mean(np.abs(residual))),
            "rmse": float(np.sqrt(np.mean(residual ** 2)))}


def fit_seed_mean(candidate: dict, config: dict, budget: str,
                  X_train: np.ndarray, y_train: np.ndarray,
                  X_heldout: np.ndarray, y_heldout: np.ndarray):
    """Fit the same three initializations separately to attribute warnings.

    Every seed retains the original target/input scaling pipeline. Since the
    inverse target scaling is affine, averaging the three Elo predictions is
    equivalent, up to floating-point arithmetic, to A1's average followed by
    one inverse target transform. No seed is chosen or discarded.
    """
    adjusted = config_for_budget(config, budget)
    seed_models, train_predictions, heldout_predictions, records = [], [], [], []
    for seed in SEEDS:
        estimator = models.build_estimator(candidate, adjusted)
        ensemble = estimator.regressor.named_steps["regressor"]
        if tuple(ensemble.random_states) != SEEDS:
            raise ValueError("Candidate did not construct the fixed three-seed MLP")
        single = MLPRegressor(random_state=seed, **deepcopy(ensemble.mlp_params))
        estimator.set_params(regressor__regressor=single)
        started = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with threadpool_limits(limits=1):
                estimator.fit(X_train, y_train)
                train_prediction = np.asarray(estimator.predict(X_train), dtype=float)
                heldout_prediction = np.asarray(estimator.predict(X_heldout), dtype=float)
        train_score = prediction_metrics(y_train, train_prediction)
        heldout_score = prediction_metrics(y_heldout, heldout_prediction)
        fitted_mlp = estimator.regressor_.named_steps["regressor"]
        loss = float(fitted_mlp.loss_)
        if not np.isfinite(loss):
            raise ValueError("Nonfinite final MLP optimizer loss")
        records.append({
            "seed": seed, "budget": budget, **BUDGETS[budget],
            "n_iter": int(fitted_mlp.n_iter_), "loss": loss,
            "iteration_limit_reached": int(fitted_mlp.n_iter_) >= BUDGETS[budget]["max_iter"],
            "seconds": time.perf_counter() - started,
            "warning_count": len(caught),
            "convergence_warning_count": sum(
                issubclass(item.category, ConvergenceWarning) for item in caught),
            "warnings": [{"category": item.category.__name__, "message": str(item.message)}
                         for item in caught],
            "train_mae": train_score["mae"], "train_rmse": train_score["rmse"],
            "heldout_mae": heldout_score["mae"], "heldout_rmse": heldout_score["rmse"],
        })
        seed_models.append(estimator)
        train_predictions.append(train_prediction)
        heldout_predictions.append(heldout_prediction)
    return {
        "estimators": seed_models, "seeds": list(SEEDS),
        "prediction_aggregation": "arithmetic mean of all three original-Elo predictions",
    }, np.mean(train_predictions, axis=0), np.mean(heldout_predictions, axis=0), records


def find_task(runs_dir: Path, task: str):
    matches = []
    for path in sorted(runs_dir.rglob("trainer_manifest.json")):
        manifest = read_json(path)
        if manifest.get("task") == task:
            matches.append((path, manifest))
    if len(matches) != 1:
        raise ValueError(f"Expected one sealed task {task}, found {len(matches)}")
    path, manifest = matches[0]
    if (manifest.get("status") != "complete" or manifest.get("kind") != "development"
            or manifest.get("train_n") != 800):
        raise ValueError("Original task is not a complete 800-person development fit")
    for item in manifest["files"]:
        member = (path.parent / item["path"]).resolve()
        if not member.is_relative_to(path.parent.resolve()):
            raise ValueError("Original task member escapes its directory")
        if sha256(member) != item["sha256"]:
            raise ValueError(f"Original task file fingerprint mismatch: {item['path']}")
    return path, manifest


def _execution_commit(root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                            capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def run_fold(root: Path, runs_dir: Path, fold: int, out: Path) -> dict:
    """Run one fixed 800/200 fold, with 2 representations × 2 budgets."""
    if fold not in range(5):
        raise ValueError("Diagnostic fold must be 0 through 4")
    root, runs_dir, out = root.resolve(), runs_dir.resolve(), out.resolve()
    lock_utils.verify_analysis_lock(root)
    study = root / "studies/chess_single_A_v2"
    config_path = study / "config.json"
    config_digest = sha256(config_path)
    config = read_json(config_path)
    task = f"dev_f{fold}_n800"
    manifest_path, original = find_task(runs_dir, task)
    if original["config_sha256"] != config_digest:
        raise ValueError("Sealed fit and original configuration disagree")
    # The only interpreted person/target dataset opened by this module.
    frame = model_inputs.load_model_frame(root, "development")
    training, heldout, _ = train_models.task_frames(
        frame, task, config, lambda label: model_inputs.get_training_ids(root, label))
    training_ids = training["canonical_id"].astype(str).tolist()
    heldout_ids = heldout["canonical_id"].astype(str).tolist()
    if (training_ids != read_json(manifest_path.parent / "training_ids.json")
            or heldout_ids != read_json(manifest_path.parent / "validation_ids.json")
            or train_models.ids_sha256(training_ids) != original["training_ids_sha256"]
            or train_models.ids_sha256(heldout_ids) != original["validation_ids_sha256"]):
        raise ValueError("Reconstructed development fold differs from original sealed IDs/order")
    if len(training_ids) != 800 or len(heldout_ids) != 200:
        raise ValueError("Expected original 800/200 development fold")
    y_train, y_heldout = (part["rating"].to_numpy(dtype=float) for part in (training, heldout))
    median = float(np.median(y_train))
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "mlp_budget_summary.json"
    summary = {
        "status": "incomplete", "fold": fold, "original_task": task,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": SCOPE, "optimization_objective": OBJECTIVE,
        "external_data_loaded": False, "candidate_reselection": False,
        "budget_selection_from_diagnostic_scores": False, "seeds": list(SEEDS),
        "budgets": BUDGETS, "train_n": 800, "heldout_n": 200,
        "config_sha256": config_digest,
        "analysis_lock_sha256": sha256(study / "analysis_lock.json"),
        "source_trainer_manifest_sha256": sha256(manifest_path),
        "training_ids_sha256": train_models.ids_sha256(training_ids),
        "heldout_ids_sha256": train_models.ids_sha256(heldout_ids),
        "execution_commit": _execution_commit(root),
        "diagnostic_script_sha256": sha256(Path(__file__).resolve()),
        "environment": {"python": sys.version.split()[0], **{
            name: importlib.metadata.version(name) for name in
            ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl")}},
        "representations": {},
    }
    write_json(summary_path, summary)
    write_json(out / "training_ids.json", training_ids)
    write_json(out / "heldout_ids.json", heldout_ids)
    metric_rows, seed_rows, train_tables, heldout_tables, comparisons = [], [], [], [], []
    matrix_functions = {"raw_A": model_inputs.make_raw_matrix,
                        "date_control": model_inputs.make_date_matrix}
    try:
        for representation in REPRESENTATIONS:
            search_path = manifest_path.parent / f"search_{representation}.json"
            search = read_json(search_path)
            best = search["family_best"]["small_mlp"]
            if best is None or best["candidate"]["family"] != "small_mlp":
                raise ValueError("Original MLP family has no valid fixed winner")
            candidate = best["candidate"]
            known = {row["candidate_id"]: row for row in models.candidate_configs(config)}
            if candidate != known.get(best["candidate_id"]):
                raise ValueError("Original MLP winner is outside original candidate list")
            X_train = matrix_functions[representation](training, config)
            X_heldout = matrix_functions[representation](heldout, config)
            train_table = pd.DataFrame({"canonical_id": training_ids, "fold": fold,
                "representation": representation, "rating": y_train, "pred_median": median})
            heldout_table = pd.DataFrame({"canonical_id": heldout_ids, "fold": fold,
                "representation": representation, "rating": y_heldout, "pred_median": median})
            rows_by_budget = {}
            summary["representations"][representation] = {
                "fixed_candidate": candidate, "original_inner_mae": best["mae"],
                "source_search_sha256": sha256(search_path), "models": {},
            }
            for budget in BUDGETS:
                print(f"[{task}/{representation}/{budget}] fixed {candidate['candidate_id']}", flush=True)
                payload, train_prediction, heldout_prediction, records = fit_seed_mean(
                    candidate, config, budget, X_train, y_train, X_heldout, y_heldout)
                train_score = prediction_metrics(y_train, train_prediction)
                heldout_score = prediction_metrics(y_heldout, heldout_prediction)
                path = out / "models" / f"{representation}_{budget}_seeds.joblib"
                path.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(payload, path, compress=3)
                summary["representations"][representation]["models"][budget] = {
                    "path": path.relative_to(out).as_posix(), "sha256": sha256(path)}
                row = {"fold": fold, "original_task": task,
                    "representation": representation, "budget": budget,
                    "candidate_id": candidate["candidate_id"], **BUDGETS[budget],
                    "train_n": 800, "heldout_n": 200,
                    "train_mae": train_score["mae"], "train_rmse": train_score["rmse"],
                    "heldout_mae": heldout_score["mae"], "heldout_rmse": heldout_score["rmse"],
                    "mean_seed_loss": float(np.mean([r["loss"] for r in records])),
                    "max_seed_n_iter": max(r["n_iter"] for r in records),
                    "seed_fits": len(records),
                    "seed_fits_with_convergence_warning": sum(
                        r["convergence_warning_count"] > 0 for r in records),
                    "warning_records": sum(r["warning_count"] for r in records),
                }
                metric_rows.append(row)
                rows_by_budget[budget] = row
                seed_rows.extend({"fold": fold, "original_task": task,
                    "representation": representation, "candidate_id": candidate["candidate_id"],
                    **record} for record in records)
                train_table[f"pred_{budget}"] = train_prediction
                heldout_table[f"pred_{budget}"] = heldout_prediction
                print(f"[{task}/{representation}/{budget}] train MAE={train_score['mae']:.6f}; "
                      f"heldout MAE={heldout_score['mae']:.6f}", flush=True)
                write_json(summary_path, summary)
            comparison = {"fold": fold, "representation": representation,
                "candidate_id": candidate["candidate_id"],
                "positive_improvement_favors": "extended", "train_n": 800, "heldout_n": 200}
            for metric in ("train_mae", "train_rmse", "heldout_mae", "heldout_rmse", "mean_seed_loss"):
                comparison[f"original_minus_extended_{metric}"] = (
                    rows_by_budget["original"][metric] - rows_by_budget["extended"][metric])
            comparisons.append(comparison)
            train_tables.append(train_table)
            heldout_tables.append(heldout_table)
        if sha256(config_path) != config_digest:
            raise RuntimeError("Original configuration changed during diagnostics")
        pd.DataFrame(metric_rows).to_csv(out / "mlp_budget_metrics.csv", index=False, float_format="%.17g")
        pd.DataFrame(comparisons).to_csv(out / "mlp_budget_comparisons.csv", index=False, float_format="%.17g")
        order = ["canonical_id", "fold", "representation", "rating",
                 "pred_original", "pred_extended", "pred_median"]
        pd.concat(heldout_tables, ignore_index=True)[order].to_csv(
            out / "mlp_budget_predictions.csv", index=False, float_format="%.17g")
        pd.concat(train_tables, ignore_index=True)[order].to_csv(
            out / "mlp_budget_training_predictions.csv", index=False, float_format="%.17g")
        write_json(out / "mlp_seed_diagnostics.json", seed_rows)
        summary.update(status="complete", completed_at_utc=datetime.now(timezone.utc).isoformat(),
            metric_rows=len(metric_rows), heldout_prediction_rows=sum(map(len, heldout_tables)),
            seed_fit_rows=len(seed_rows),
            files=[{"path": path.relative_to(out).as_posix(), "sha256": sha256(path)}
                   for path in sorted(out.rglob("*"))
                   if path.is_file() and path != summary_path and not path.name.endswith(".tmp")])
        write_json(summary_path, summary)
        return summary
    except Exception as error:
        summary.update(status="failed", error_type=type(error).__name__, error=str(error))
        write_json(summary_path, summary)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--fold", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_fold(args.repo_root, args.runs_dir, args.fold, args.output_dir)
    print(json.dumps({"status": result["status"], "fold": result["fold"],
                      "external_data_loaded": result["external_data_loaded"]}))


if __name__ == "__main__":
    main()
