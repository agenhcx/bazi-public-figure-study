#!/usr/bin/env python3
"""Bounded recovery checks using the frozen 2013 covariates and synthetic targets.

No real Elo is used to define a target, select a candidate, or score a model.
The control functions are specified here before fitting. Their recovery says
only what these fixed procedures recover for these injected functions/noises.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from threadpoolctl import threadpool_limits

STUDY_DIR = Path(__file__).resolve().parents[1]
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

from lock_utils import verify_analysis_lock
from model_inputs import load_model_frame, make_raw_matrix
from models import build_estimator, candidate_configs


SIGNALS = ("null", "additive", "pairwise", "third_order")
POSITION_COLUMNS = ("year_stem", "year_branch", "month_stem", "month_branch",
                    "day_stem", "day_branch")
POSITION_SLICES = ((0, 10), (10, 22), (22, 32), (32, 44), (44, 54), (54, 66))
DESIGN_SEED = 20261025
NOISE_BASE_SEED = 20261026
N_REPLICATES = 2
NONZERO_STRENGTHS = (0.5, 2.0)
OUTER_SEED = 20261021
N_FOLDS = 5
TARGET_CENTER = 2500.0
NOISE_SCALE = 50.0
REPRESENTATIVE_PARAMETERS = (
    ("ridge", {"alpha": 10}),
    ("pairwise_ridge", {"alpha": 100}),
    ("rbf_kernel_ridge", {"alpha": 1, "gamma": 0.01}),
    ("shallow_gradient_boosting", {"max_depth": 2, "n_estimators": 100,
                                    "min_samples_leaf": 10}),
    ("small_mlp", {"hidden_layer_sizes": [16], "alpha": 1}),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    """Replace progress/manifest files atomically; reject nonfinite JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def fixed_candidates(config: dict) -> list[dict]:
    """Use five exact A1 candidates; there is no control-dependent tuning."""
    all_candidates = candidate_configs(config)
    result = []
    for family, parameters in REPRESENTATIVE_PARAMETERS:
        matches = [candidate for candidate in all_candidates
                   if candidate["family"] == family and candidate["params"] == parameters]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous fixed control candidate: {family}")
        result.append(matches[0])
    return result


def signal_design(X: np.ndarray, signal_name: str) -> tuple[np.ndarray, dict]:
    """Define a deterministic signal conditional on the available raw inputs.

    Full-X centering/scaling is part of defining the synthetic data-generating
    function. It uses no real or synthetic target labels. Estimator preprocessing
    is nevertheless fitted separately inside each training fold.
    """
    if signal_name not in SIGNALS:
        raise ValueError(f"Unknown synthetic signal: {signal_name}")
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] != 66 or len(X) < 2 or not np.isfinite(X).all():
        raise ValueError("Control signals require a finite n-by-66 raw matrix")
    if not np.isin(X, (0.0, 1.0)).all():
        raise ValueError("Raw controls require one-hot indicators")
    for begin, end in POSITION_SLICES:
        if not np.all(X[:, begin:end].sum(axis=1) == 1.0):
            raise ValueError("Every raw position must contain exactly one indicator")
    coefficients = np.random.default_rng(DESIGN_SEED).normal(size=66)
    scores = np.column_stack([X[:, begin:end] @ coefficients[begin:end]
                              for begin, end in POSITION_SLICES])
    if signal_name == "null":
        raw_signal = np.zeros(len(X))
        equation = "0"
    elif signal_name == "additive":
        raw_signal = scores.sum(axis=1)
        equation = "sum of the six position-specific random category scores"
    elif signal_name == "pairwise":
        raw_signal = scores[:, 0] * scores[:, 4]
        equation = "year_stem_score * day_stem_score"
    else:
        raw_signal = scores[:, 0] * scores[:, 2] * scores[:, 4]
        equation = "year_stem_score * month_stem_score * day_stem_score"
    center = float(raw_signal.mean())
    scale = float(raw_signal.std(ddof=0))
    if signal_name == "null":
        standardized = np.zeros(len(X))
        # The null is an exact zero function, never a divide-by-zero result.
        scale = 0.0
    else:
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("The specified control function has no variation in these inputs")
        standardized = (raw_signal - center) / scale
    return standardized, {
        "signal": signal_name, "design_seed": DESIGN_SEED,
        "position_columns": list(POSITION_COLUMNS),
        "position_slices": [list(item) for item in POSITION_SLICES],
        "coefficients": coefficients.tolist(), "raw_signal_equation": equation,
        "raw_signal_center": center, "raw_signal_population_sd": scale,
        "signal_standardization": "center and population SD over the fixed 1000 raw input rows; null is identically zero",
        "signal_isolation_limit": "Interactions need not be orthogonal to lower-order functions under the actual calendar covariate distribution",
        "target_equation": "2500 + 50 * (strength * standardized_signal + independent_normal_noise)",
        "real_outcome_used": False,
    }


def synthetic_target(signal: np.ndarray, strength: float, replicate: int) -> tuple[np.ndarray, np.ndarray]:
    if replicate not in range(N_REPLICATES):
        raise ValueError("Unexpected noise replicate")
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1 or not np.isfinite(signal).all():
        raise ValueError("Synthetic signal must be finite and one-dimensional")
    if strength not in (0.0, *NONZERO_STRENGTHS):
        raise ValueError("Unexpected synthetic signal strength")
    noise = np.random.default_rng(NOISE_BASE_SEED + replicate).normal(size=len(signal))
    return TARGET_CENTER + NOISE_SCALE * (strength * signal + noise), noise


def _metrics(y, prediction) -> dict:
    difference = np.asarray(prediction, dtype=float) - np.asarray(y, dtype=float)
    if difference.ndim != 1 or not np.isfinite(difference).all():
        raise ValueError("Synthetic scoring requires finite paired vectors")
    return {"n": len(difference), "mae": float(np.abs(difference).mean()),
            "rmse": float(np.sqrt(np.mean(difference ** 2)))}


def _fit_predictions(candidate, config, X_train, y_train, X_valid):
    """Preserve every finite fit and report failures without rescue/tuning."""
    started = time.perf_counter()
    captured = []
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            with threadpool_limits(limits=1):
                estimator = build_estimator(candidate, config)
                estimator.fit(X_train, y_train)
                train_prediction = np.asarray(estimator.predict(X_train), dtype=float)
                valid_prediction = np.asarray(estimator.predict(X_valid), dtype=float)
        if (train_prediction.shape != np.asarray(y_train).shape
                or valid_prediction.shape != (len(X_valid),)
                or not np.isfinite(train_prediction).all()
                or not np.isfinite(valid_prediction).all()):
            raise ValueError("Nonfinite or misaligned synthetic predictions")
        status, error_type, error = "complete", None, None
    except Exception as exception:
        train_prediction, valid_prediction = None, None
        status, error_type, error = "failed", type(exception).__name__, str(exception)
    recorded = [{"category": item.category.__name__, "message": str(item.message)}
                for item in captured]
    diagnostics = {"status": status, "error_type": error_type, "error": error,
                   "warnings": recorded, "warning_count": len(recorded),
                   "fit_with_convergence_warning": any(item["category"] == "ConvergenceWarning"
                                                        for item in recorded),
                   "seconds": float(time.perf_counter() - started)}
    return train_prediction, valid_prediction, diagnostics


def run_signal(root: Path, signal_name: str, out: Path) -> dict:
    """Run one prespecified signal job; no external data or model selection."""
    if signal_name not in SIGNALS:
        raise ValueError(f"Unknown synthetic signal: {signal_name}")
    root, out = Path(root).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = {"status": "incomplete", "diagnostic": "A1_synthetic_recovery_v1",
                "signal": signal_name, "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "external_data_loaded": False, "actual_ratings_used_for_targets": False,
                "hyperparameter_search": False, "new_blind_confirmation": False,
                "fit_attempt_unit": "one candidate ensemble fit; the MLP includes all three fixed seeds",
                "interpretation": "Recovery applies only to these injected functions, noise levels and fixed procedures; it is not evidence of a real BaZi-Elo relation"}
    write_json(manifest_path, manifest)
    try:
        verify_analysis_lock(root)
        config_path = root / "studies/chess_single_A_v2/config.json"
        config_bytes = config_path.read_bytes()
        config = json.loads(config_bytes)
        outer = config["cv"]["outer"]
        if outer != {"method": "KFold", "n_splits": N_FOLDS, "shuffle": True,
                     "random_state": OUTER_SEED}:
            raise ValueError("Original five-fold development design changed")
        frame = load_model_frame(root, "development")
        # Deliberately discard Elo and all other unused columns before building X.
        inputs = frame[["canonical_id", *POSITION_COLUMNS]].copy()
        inputs["canonical_id"] = inputs["canonical_id"].astype(str)
        inputs = inputs.sort_values("canonical_id").reset_index(drop=True)
        if len(inputs) != 1000 or inputs["canonical_id"].nunique() != 1000:
            raise ValueError("Synthetic recovery requires the 1000 distinct development people")
        ids = inputs["canonical_id"].tolist()
        X = make_raw_matrix(inputs, config)
        signal, design = signal_design(X, signal_name)
        candidates = fixed_candidates(config)
        folds = list(KFold(n_splits=N_FOLDS, shuffle=True, random_state=OUTER_SEED).split(ids))
        if any(len(train) != 800 or len(valid) != 200 for train, valid in folds):
            raise ValueError("Synthetic recovery fold sizes changed")
        write_json(out / "signal_design.json", design)
        write_json(out / "fold_ids.json", [{"fold": index,
            "training_ids": [ids[i] for i in train],
            "validation_ids": [ids[i] for i in valid]}
            for index, (train, valid) in enumerate(folds)])
        strengths = (0.0,) if signal_name == "null" else NONZERO_STRENGTHS
        scenario_count = len(strengths) * N_REPLICATES
        manifest.update({
            "n_people": len(ids), "train_n_per_fold": 800, "validation_n_per_fold": 200,
            "n_folds": N_FOLDS, "outer_seed": OUTER_SEED,
            "strengths": list(strengths), "noise_base_seed": NOISE_BASE_SEED,
            "n_noise_replicates": N_REPLICATES, "scenario_count": scenario_count,
            "expected_fits": scenario_count * N_FOLDS * len(candidates),
            "fixed_candidates": candidates,
            "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "analysis_lock_sha256": sha256(root / "studies/chess_single_A_v2/analysis_lock.json"),
            "development_input_sha256": sha256(root / "studies/chess_single_A_v2/data/model_inputs_development.csv"),
            "script_sha256": sha256(Path(__file__).resolve()),
            "ordered_ids_sha256": hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest(),
            "raw_matrix_sha256": hashlib.sha256(np.asarray(X, dtype="<f8").tobytes()).hexdigest(),
        })
        write_json(manifest_path, manifest)
        predictions, fold_metrics, records, targets = [], [], [], []
        for strength in strengths:
            for replicate in range(N_REPLICATES):
                scenario_id = f"{signal_name}_s{strength:g}_r{replicate}"
                y, noise = synthetic_target(signal, strength, replicate)
                common = {"signal": signal_name, "strength": strength,
                          "replicate": replicate, "scenario_id": scenario_id}
                targets.extend({**common, "canonical_id": person,
                                "standardized_signal": float(signal[i]),
                                "noise": float(noise[i]), "synthetic_target": float(y[i])}
                               for i, person in enumerate(ids))
                for fold, (train, valid) in enumerate(folds):
                    median = float(np.median(y[train]))
                    benchmark_prediction = np.full(len(valid), median)
                    fold_metrics.append({**common, "fold": fold, "model": "training_median",
                                         "candidate_id": None, "status": "complete",
                                         "train_mae": _metrics(y[train], np.full(len(train), median))["mae"],
                                         "train_rmse": _metrics(y[train], np.full(len(train), median))["rmse"],
                                         **_metrics(y[valid], benchmark_prediction)})
                    predictions.extend({**common, "fold": fold, "model": "training_median",
                                        "canonical_id": ids[i], "synthetic_target": float(y[i]),
                                        "prediction": median} for i in valid)
                    for candidate in candidates:
                        train_prediction, heldout_prediction, diagnostics = _fit_predictions(
                            candidate, config, X[train], y[train], X[valid])
                        record = {**common, "fold": fold, "model": candidate["family"],
                                  "candidate_id": candidate["candidate_id"],
                                  "training_n": len(train), "validation_n": len(valid), **diagnostics}
                        records.append(record)
                        row = {**common, "fold": fold, "model": candidate["family"],
                               "candidate_id": candidate["candidate_id"],
                               "status": diagnostics["status"], "n": 0,
                               "mae": None, "rmse": None, "train_mae": None, "train_rmse": None}
                        if diagnostics["status"] == "complete":
                            row.update(_metrics(y[valid], heldout_prediction))
                            train_metrics = _metrics(y[train], train_prediction)
                            row.update({"train_mae": train_metrics["mae"], "train_rmse": train_metrics["rmse"]})
                            predictions.extend({**common, "fold": fold, "model": candidate["family"],
                                                "canonical_id": ids[i], "synthetic_target": float(y[i]),
                                                "prediction": float(value)}
                                               for i, value in zip(valid, heldout_prediction))
                        fold_metrics.append(row)
                        write_json(out / "fit_records.json", records)
                        write_json(out / "progress.json", {"completed_fit_attempts": len(records),
                            "expected_fit_attempts": manifest["expected_fits"],
                            "latest": {key: record[key] for key in
                                       ("scenario_id", "fold", "model", "status")}})
                        print(f"[control/{scenario_id}/fold{fold}] {candidate['candidate_id']} {diagnostics['status']}",
                              flush=True)
        prediction_table = pd.DataFrame(predictions)
        metrics_table = pd.DataFrame(fold_metrics)
        target_table = pd.DataFrame(targets)
        pooled = []
        model_names = ["training_median", *[candidate["family"] for candidate in candidates]]
        for strength in strengths:
            for replicate in range(N_REPLICATES):
                scenario_id = f"{signal_name}_s{strength:g}_r{replicate}"
                subset = prediction_table[prediction_table["scenario_id"] == scenario_id]
                reference = subset[subset["model"] == "training_median"]
                median_metrics = _metrics(reference["synthetic_target"], reference["prediction"])
                for model in model_names:
                    rows = subset[subset["model"] == model]
                    complete = len(rows) == 1000 and rows["canonical_id"].nunique() == 1000
                    values = _metrics(rows["synthetic_target"], rows["prediction"]) if complete else {
                        "n": len(rows), "mae": None, "rmse": None}
                    pooled.append({"signal": signal_name, "strength": strength, "replicate": replicate,
                                   "scenario_id": scenario_id, "model": model,
                                   "status": "complete" if complete else "invalid_incomplete_folds",
                                   **values, "median_mae": median_metrics["mae"],
                                   "mae_gain": median_metrics["mae"] - values["mae"] if complete else None})
        prediction_table.to_csv(out / "synthetic_predictions.csv.gz", index=False, float_format="%.17g",
                                compression={"method": "gzip", "mtime": 0})
        metrics_table.to_csv(out / "fold_metrics.csv", index=False, float_format="%.17g")
        target_table.to_csv(out / "synthetic_targets.csv", index=False, float_format="%.17g")
        pd.DataFrame(pooled).to_csv(out / "pooled_metrics.csv", index=False, float_format="%.17g")
        if config_path.read_bytes() != config_bytes:
            raise RuntimeError("Original A1 configuration changed during the diagnostic")
        manifest.update({"status": "complete", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                         "fit_attempts": len(records),
                         "failed_fit_attempts": sum(item["status"] != "complete" for item in records),
                         "fit_attempts_with_convergence_warning": sum(item["fit_with_convergence_warning"] for item in records),
                         "warning_records": sum(item["warning_count"] for item in records),
                         "prediction_rows": len(predictions), "pooled_metric_rows": len(pooled),
                         "outputs": [{"path": path.relative_to(out).as_posix(), "sha256": sha256(path)}
                                     for path in sorted(out.rglob("*"))
                                     if path.is_file() and path != manifest_path and not path.name.endswith(".tmp")]})
        write_json(manifest_path, manifest)
        return manifest
    except Exception as exception:
        manifest.update({"status": "failed", "error_type": type(exception).__name__,
                         "error": str(exception), "failed_at_utc": datetime.now(timezone.utc).isoformat()})
        write_json(manifest_path, manifest)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--signal", required=True, choices=SIGNALS)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = run_signal(args.repo_root, args.signal, args.output_dir)
    print(json.dumps({key: manifest[key] for key in
                      ("status", "signal", "fit_attempts", "failed_fit_attempts", "prediction_rows")}, indent=2))


if __name__ == "__main__":
    main()
