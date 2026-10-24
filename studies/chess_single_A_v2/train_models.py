#!/usr/bin/env python3
"""Fit locked 2013-only searches and save models before external evaluation.

The production CLI requires the immutable analysis lock. Synthetic unit tests may
exercise the selection helpers without enabling research-data fitting.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import re
import subprocess
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from threadpoolctl import threadpool_limits

REPRESENTATIONS = ("raw_A", "date_control")
FINAL_SUBSETS = ("random_500", "random_800", "random_1000",
                 "ranked_500_with_ties", "ranked_800_with_ties")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ids_sha256(ids) -> str:
    return hashlib.sha256(("\n".join(map(str, ids)) + "\n").encode("utf-8")).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def environment_versions() -> dict:
    packages = {}
    for name in ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl", "sxtwl"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": packages, "fit_thread_limit": 1}


def executing_commit(root: Path) -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except OSError:
        pass
    return os.environ.get("GITHUB_SHA", "local_uncommitted")


def parse_task(task: str) -> dict:
    match = re.fullmatch(r"dev_f([0-4])_n(400|600|800)", task)
    if match:
        return {"kind": "development", "outer_fold": int(match.group(1)),
                "train_size": int(match.group(2)), "training_subset": "random_1000"}
    if task.startswith("final_") and task[6:] in FINAL_SUBSETS:
        return {"kind": "final", "training_subset": task[6:]}
    raise ValueError(f"Task is not in the prespecified task set: {task}")


def ordered_subset(frame: pd.DataFrame, ids) -> pd.DataFrame:
    selected = [str(value) for value in ids]
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate training-subset canonical ID")
    if "canonical_id" not in frame or frame["canonical_id"].astype(str).duplicated().any():
        raise ValueError("Development data must have unique canonical IDs")
    available = set(frame["canonical_id"].astype(str))
    if set(selected) - available:
        raise ValueError("Training-subset IDs absent from development data")
    chosen = frame.loc[frame["canonical_id"].astype(str).isin(selected)].copy()
    chosen["canonical_id"] = chosen["canonical_id"].astype(str)
    return chosen.sort_values("canonical_id", kind="stable").reset_index(drop=True)


def inner_folds(n_rows: int, config: dict):
    specification = config["cv"]["inner"]
    return list(KFold(n_splits=int(specification["n_splits"]),
                      shuffle=bool(specification["shuffle"]),
                      random_state=int(specification["random_state"])).split(np.arange(n_rows)))


def task_frames(frame: pd.DataFrame, task: str, config: dict, get_ids):
    """Return sorted training/outer-validation frames without loading 2023 data."""
    spec = parse_task(task)
    if spec["kind"] == "final":
        chosen = ordered_subset(frame, get_ids(spec["training_subset"]))
        required = int(spec["training_subset"].split("_")[1])
        if (spec["training_subset"].startswith("random_") and len(chosen) != required
                or spec["training_subset"].startswith("ranked_") and len(chosen) < required):
            raise ValueError("Final training subset has the wrong prespecified size")
        return chosen, None, spec
    primary = ordered_subset(frame, get_ids("random_1000"))
    if len(primary) != 1000:
        raise ValueError("Primary development subset must contain exactly 1000 people")
    outer = config["cv"]["outer"]
    splitter = KFold(n_splits=int(outer["n_splits"]),
                    shuffle=bool(outer["shuffle"]),
                    random_state=int(outer["random_state"]))
    train_indices, test_indices = list(splitter.split(np.arange(len(primary))))[spec["outer_fold"]]
    outer_train = primary.iloc[train_indices].copy()
    validation = primary.iloc[test_indices].copy().reset_index(drop=True)
    n = spec["train_size"]
    if len(outer_train) < n:
        raise ValueError("Outer training fold is smaller than the stated curve size")
    seed = int(config["learning_curve"]["subset_permutation_seed"]) + spec["outer_fold"]
    ids = outer_train["canonical_id"].tolist()
    ids.sort(key=lambda fid: (hashlib.sha256(f"{seed}\n{fid}".encode()).hexdigest(), fid))
    chosen = ordered_subset(outer_train, ids[:n])
    if set(chosen["canonical_id"]) & set(validation["canonical_id"]):
        raise ValueError("Outer training/validation identity overlap")
    spec["outer_training_pool_n"] = len(outer_train)
    spec["outer_validation_n"] = len(validation)
    spec["curve_subset_seed"] = seed
    return chosen, validation, spec


def _warning_records(caught):
    return [{"category": item.category.__name__, "message": str(item.message)} for item in caught]


def fit_predict_checked(estimator, X_train, y_train, X_predict):
    """Keep finite warning fits; expose every warning and every fit exception."""
    started = time.perf_counter()
    caught = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with threadpool_limits(limits=1):
                estimator.fit(X_train, y_train)
                prediction = np.asarray(estimator.predict(X_predict), dtype=float)
        if prediction.shape != (len(X_predict),):
            raise ValueError(f"Unexpected prediction shape {prediction.shape}")
        if not np.isfinite(prediction).all():
            raise FloatingPointError("Nonfinite prediction")
    except Exception as error:
        return None, {"status": "invalid", "seconds": time.perf_counter() - started,
                      "warnings": _warning_records(caught),
                      "error_type": type(error).__name__, "error": str(error)}
    return prediction, {"status": "complete", "seconds": time.perf_counter() - started,
                        "warnings": _warning_records(caught), "error_type": None, "error": None}


def _validate_arrays(X, y):
    X, y = np.asarray(X, dtype=float), np.asarray(y, dtype=float)
    if X.ndim != 2 or y.ndim != 1 or len(X) != len(y):
        raise ValueError("Expected an aligned feature matrix and one-dimensional target")
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        raise ValueError("Nonfinite model input or target")
    return X, y


def _first_best(rows, tolerance):
    valid = [row for row in rows if row["status"] == "complete"]
    if not valid:
        return None
    minimum = min(row["mae"] for row in valid)
    return next(row for row in valid if row["mae"] <= minimum + tolerance)


def search_candidates(X, y, config: dict, candidates=None, estimator_factory=None,
                      progress_callback=None) -> dict:
    """Run the finite inner search; any failed fold invalidates its candidate."""
    if candidates is None or estimator_factory is None:
        from models import candidate_configs, build_estimator
        candidates = candidate_configs(config) if candidates is None else candidates
        estimator_factory = build_estimator if estimator_factory is None else estimator_factory
    candidates = list(candidates)
    if not candidates or len({c["candidate_id"] for c in candidates}) != len(candidates):
        raise ValueError("Candidate IDs must be nonempty and unique")
    X, y = _validate_arrays(X, y)
    folds = inner_folds(len(y), config)
    result_rows = []
    for candidate in candidates:
        oof = np.full(len(y), np.nan)
        row = {"candidate_id": candidate["candidate_id"], "family": candidate["family"],
               "candidate": candidate, "status": "complete", "folds": [],
               "mae": None, "oof_predictions": None}
        for fold_index, (training, validation) in enumerate(folds):
            try:
                estimator = estimator_factory(candidate, config)
                prediction, diagnostics = fit_predict_checked(estimator, X[training], y[training], X[validation])
            except Exception as error:
                prediction, diagnostics = None, {"status": "invalid", "seconds": 0.0,
                    "warnings": [], "error_type": type(error).__name__, "error": str(error)}
            diagnostics.update({"fold": fold_index, "training_n": len(training), "validation_n": len(validation)})
            if prediction is not None:
                oof[validation] = prediction
                diagnostics["absolute_error_sum"] = float(np.abs(y[validation] - prediction).sum())
            row["folds"].append(diagnostics)
            if prediction is None:
                row["status"] = "invalid"
                break
        if row["status"] == "complete":
            if not np.isfinite(oof).all():
                raise RuntimeError("A supposedly valid candidate lacks complete OOF predictions")
            row["mae"] = float(np.mean(np.abs(y - oof)))
            row["oof_predictions"] = oof.tolist()
        result_rows.append(row)
        if progress_callback is not None:
            progress_callback(result_rows)
    tolerance = float(config["selection"]["tie_tolerance_mae"])
    winner = _first_best(result_rows, tolerance)
    if winner is None:
        raise RuntimeError("All candidate configurations are invalid for this representation")
    family_best = {}
    for family in dict.fromkeys(c["family"] for c in candidates):
        best = _first_best([row for row in result_rows if row["family"] == family], tolerance)
        family_best[family] = None if best is None else {
            "candidate": best["candidate"], "candidate_id": best["candidate_id"], "mae": best["mae"]}
    return {"status": "complete", "n_rows": len(y), "n_folds": len(folds),
            "metric": "pooled per-player OOF MAE in original Elo units",
            "selected_candidate": winner["candidate"], "selected_candidate_id": winner["candidate_id"],
            "selected_family": winner["family"], "selected_inner_mae": winner["mae"],
            "family_best": family_best, "candidate_results": result_rows}


def _fit_and_save(candidate, representation, X, y, prediction_X, config, output,
                  artifact_name=None):
    from models import build_estimator
    estimator = build_estimator(candidate, config)
    prediction, diagnostics = fit_predict_checked(estimator, X, y, prediction_X)
    if prediction is None:
        raise RuntimeError(f"Selected {representation}/{candidate['candidate_id']} refit failed: {diagnostics}")
    name = candidate["family"] if artifact_name is None else artifact_name
    path = output / "models" / representation / f"{name}.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(estimator, path, compress=3)
    return prediction, path, diagnostics


def run_task(repo_root: Path, task: str, output_dir: Path | None = None) -> dict:
    root = repo_root.resolve()
    study = root / "studies/chess_single_A_v2"
    output = output_dir or study / "training_runs" / task
    output = output if output.is_absolute() else root / output
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "trainer_manifest.json"
    write_json(manifest_path, {"status": "incomplete", "task": task,
                              "started_at_utc": datetime.now(timezone.utc).isoformat()})
    config_path = study / "config.json"
    data_path, lock_path = study / "data/data_manifest.json", study / "analysis_lock.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("fit_allowed") is not True:
        raise RuntimeError("Research-data fitting is disabled by the analysis configuration")
    from lock_utils import verify_analysis_lock
    verify_analysis_lock(root)
    from model_inputs import load_model_frame, make_raw_matrix, make_date_matrix, get_training_ids
    frame = load_model_frame(root, "development")
    training, validation, spec = task_frames(
        frame, task, config, lambda label: get_training_ids(root, label))
    y = training["rating"].to_numpy(dtype=float)
    ids = training["canonical_id"].astype(str).tolist()
    write_json(output / "training_ids.json", ids)
    (output / "config.json").write_bytes(config_path.read_bytes())
    inner = inner_folds(len(training), config)
    write_json(output / "inner_folds.json", [{"fold": i,
        "training_ids": [ids[j] for j in train], "validation_ids": [ids[j] for j in valid]}
        for i, (train, valid) in enumerate(inner)])
    median = float(np.median(y))
    manifest = {"status": "incomplete", "task": task, **spec,
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "train_n": len(training),
        "actual_train_size": len(training), "training_ids_sha256": ids_sha256(ids),
        "median_elo": median, "config_sha256": sha256(config_path),
        "data_manifest_sha256": sha256(data_path), "analysis_lock_sha256": sha256(lock_path),
        "executing_commit": executing_commit(root),
        "trainer_code_sha256": sha256(Path(__file__).resolve()),
        "environment": environment_versions(), "representations": {},
        "external_data_loaded": False, "warning_count": 0, "invalid_candidate_count": 0}
    if validation is not None:
        validation_ids = validation["canonical_id"].astype(str).tolist()
        write_json(output / "validation_ids.json", validation_ids)
        manifest["validation_ids_sha256"] = ids_sha256(validation_ids)
        manifest["holdout_ids_sha256"] = ids_sha256(validation_ids)
        manifest["development_predictions_file"] = "outer_predictions.csv"
        prediction_table = pd.DataFrame({
            "canonical_id": validation_ids, "rating": validation["rating"].to_numpy(dtype=float),
            "pred_median": median})
    else:
        prediction_table = None
    write_json(manifest_path, manifest)
    functions = {"raw_A": make_raw_matrix, "date_control": make_date_matrix}
    try:
        for representation in REPRESENTATIONS:
            X = functions[representation](training, config)
            pred_X = functions[representation](validation, config) if validation is not None else X
            search_path = output / f"search_{representation}.json"
            def progress(rows, path=search_path, rep=representation):
                write_json(path, {"status": "incomplete", "representation": rep, "candidate_results": rows})
                last = rows[-1]
                print(f"[{task}/{rep}] {last['candidate_id']} {last['status']} MAE={last['mae']}", flush=True)
            search = search_candidates(X, y, config, progress_callback=progress)
            write_json(search_path, search)
            manifest["warning_count"] += sum(
                len(fold["warnings"]) for row in search["candidate_results"] for fold in row["folds"])
            manifest["invalid_candidate_count"] += sum(
                row["status"] != "complete" for row in search["candidate_results"])
            rep = {"selected_candidate_id": search["selected_candidate_id"],
                   "selected_family": search["selected_family"],
                   "selected_inner_mae": search["selected_inner_mae"],
                   "selected_model": None, "family_models": {}}
            selected_prediction = None
            family_items = search["family_best"].items() if spec["kind"] == "final" else []
            for family, best in family_items:
                if best is None:
                    rep["family_models"][family] = {
                        "status": "invalid_no_valid_candidate", "candidate_id": None,
                        "model_file": None, "model_sha256": None, "inner_mae": None}
                    continue
                prediction, path, diagnostics = _fit_and_save(
                    best["candidate"], representation, X, y, pred_X, config, output)
                manifest["warning_count"] += len(diagnostics["warnings"])
                rep["family_models"][family] = {
                    "status": "complete", "candidate_id": best["candidate_id"],
                    "candidate": best["candidate"], "model_file": path.relative_to(output).as_posix(),
                    "model_sha256": sha256(path), "inner_mae": best["mae"],
                    "refit_diagnostics": diagnostics}
                if best["candidate_id"] == search["selected_candidate_id"]:
                    rep["selected_model"] = rep["family_models"][family]
                    selected_prediction = prediction
            # Global and within-family tolerance ties need not choose the same
            # configuration. Keep both independently defined selections intact.
            if rep["selected_model"] is None:
                prediction, path, diagnostics = _fit_and_save(
                    search["selected_candidate"], representation, X, y, pred_X,
                    config, output, artifact_name="selected_pipeline")
                manifest["warning_count"] += len(diagnostics["warnings"])
                rep["selected_model"] = {
                    "status": "complete", "candidate_id": search["selected_candidate_id"],
                    "candidate": search["selected_candidate"],
                    "model_file": path.relative_to(output).as_posix(),
                    "model_sha256": sha256(path), "inner_mae": search["selected_inner_mae"],
                    "refit_diagnostics": diagnostics}
                selected_prediction = prediction
            if selected_prediction is None:
                raise RuntimeError("Selected family has no refitted predictions")
            manifest["representations"][representation] = rep
            if prediction_table is not None:
                prediction_table[f"pred_{representation}"] = selected_prediction
                prediction_table.to_csv(output / "outer_predictions.csv", index=False, float_format="%.17g")
            write_json(manifest_path, manifest)
        if prediction_table is not None:
            prediction_table = prediction_table[[
                "canonical_id", "rating", "pred_raw_A", "pred_date_control", "pred_median"]]
            prediction_table.to_csv(output / "outer_predictions.csv", index=False, float_format="%.17g")
        manifest["status"] = "complete"
        manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["files"] = [
            {"path": path.relative_to(output).as_posix(), "sha256": sha256(path)}
            for path in sorted(output.rglob("*"))
            if path.is_file() and path != manifest_path and not path.name.endswith(".tmp")]
        write_json(manifest_path, manifest)
        return manifest
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error_type"] = type(error).__name__
        manifest["error"] = str(error)
        manifest["failed_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    manifest = run_task(args.repo_root, args.task, args.output_dir)
    print(json.dumps({"status": manifest["status"], "task": manifest["task"],
                      "train_n": manifest["train_n"], "external_data_loaded": False}, indent=2))


if __name__ == "__main__":
    main()
