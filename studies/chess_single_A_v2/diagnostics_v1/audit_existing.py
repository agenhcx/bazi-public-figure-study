"""Read-only diagnostics of the sealed A1 fits using development people only.

This module never calls fit, opens a 2023 input frame, or reads external scores.
The selected-candidate inner OOF errors are descriptive selection statistics,
not unbiased estimates from a fresh validation experiment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits


STUDY = Path("studies/chess_single_A_v2")
REPRESENTATIONS = ("raw_A", "date_control")
EXPECTED_TASKS = {
    *(f"dev_f{fold}_n{size}" for fold in range(5) for size in (400, 600, 800)),
    "final_random_500", "final_random_800", "final_random_1000",
    "final_ranked_500_with_ties", "final_ranked_800_with_ties",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_file(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Expected a relative checkpoint file")
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError(f"Missing or escaping checkpoint file: {relative}")
    return path


def metrics(y, prediction) -> dict:
    y = np.asarray(y, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    if y.ndim != 1 or prediction.shape != y.shape or not len(y):
        raise ValueError("Prediction/target shape mismatch")
    if not np.isfinite(y).all() or not np.isfinite(prediction).all():
        raise ValueError("Nonfinite diagnostic values")
    errors = prediction - y
    return {"n": len(y), "mae": float(np.abs(errors).mean()),
            "rmse": float(np.sqrt(np.square(errors).mean()))}


def verify_checkpoint(root: Path, runs_dir: Path) -> tuple[dict, list[tuple[Path, dict]]]:
    """Check the immutable model seal before unpickling any fitted estimator."""
    seal_path = runs_dir.parent / "fitted_models_lock.json"
    seal = read_json(seal_path)
    if seal.get("status") != "all_prespecified_models_sealed_before_external_evaluation":
        raise ValueError("Missing completed A1 seal")
    if seal.get("external_predictions_or_scores_created") is not False:
        raise ValueError("The model seal does not precede external scoring")
    references = {
        "config_sha256": root / STUDY / "config.json",
        "analysis_lock_sha256": root / STUDY / "analysis_lock.json",
        "data_manifest_sha256": root / STUDY / "data/data_manifest.json",
    }
    for name, path in references.items():
        if sha256(path) != seal["reference_hashes"].get(name):
            raise ValueError(f"A1 reference differs from seal: {name}")
    records, seen = [], set()
    actual = {p.resolve() for p in runs_dir.rglob("trainer_manifest.json")}
    for entry in seal["tasks"]:
        task = entry["task"]
        if task in seen:
            raise ValueError("Duplicate sealed task")
        seen.add(task)
        manifest_path = safe_file(runs_dir, entry["manifest_path"])
        if sha256(manifest_path) != entry["manifest_sha256"]:
            raise ValueError(f"Changed task manifest: {task}")
        manifest = read_json(manifest_path)
        if manifest.get("status") != "complete" or manifest.get("task") != task:
            raise ValueError(f"Incomplete or misidentified task: {task}")
        if manifest.get("external_data_loaded") is not False:
            raise ValueError(f"External inputs were loaded by trainer: {task}")
        if manifest.get("executing_commit") != seal["execution_commit"]:
            raise ValueError(f"Task execution commit differs: {task}")
        for key in references:
            if manifest.get(key) != seal["reference_hashes"][key]:
                raise ValueError(f"Task reference differs: {task}/{key}")
        recorded = {item["path"]: item["sha256"] for item in manifest["files"]}
        sealed_files = {item["path"]: item["sha256"] for item in entry["files"]}
        if len(recorded) != len(manifest["files"]) or recorded != sealed_files:
            raise ValueError(f"Task file ledger differs from seal: {task}")
        for name, digest in sealed_files.items():
            if sha256(safe_file(manifest_path.parent, name)) != digest:
                raise ValueError(f"Changed sealed file: {task}/{name}")
        records.append((manifest_path.parent, manifest))
    if seen != EXPECTED_TASKS or seal.get("task_count") != len(EXPECTED_TASKS):
        raise ValueError("The completed twenty-task ledger is required")
    if actual != {folder / "trainer_manifest.json" for folder, _ in records}:
        raise ValueError("Unsealed or missing task manifest")
    return seal, sorted(records, key=lambda item: item[1]["task"])


def inner_median_predictions(ids: list[str], y, folds: list[dict]) -> np.ndarray:
    """Recreate the benchmark using each inner training fold's median only."""
    ids = list(map(str, ids))
    if len(set(ids)) != len(ids):
        raise ValueError("Repeated training identity")
    lookup = {identifier: i for i, identifier in enumerate(ids)}
    output = np.full(len(ids), np.nan)
    assigned = np.zeros(len(ids), dtype=int)
    y = np.asarray(y, dtype=float)
    for fold in folds:
        training = list(map(str, fold["training_ids"]))
        validation = list(map(str, fold["validation_ids"]))
        if (set(training) & set(validation) or set(training) | set(validation) != set(ids)
                or len(set(training)) != len(training) or len(set(validation)) != len(validation)):
            raise ValueError("Invalid inner fold identities")
        train_index = [lookup[item] for item in training]
        valid_index = [lookup[item] for item in validation]
        output[valid_index] = float(np.median(y[train_index]))
        assigned[valid_index] += 1
    if not np.all(assigned == 1):
        raise ValueError("Inner validation does not predict each person once")
    return output


def warning_fit_row(task, representation, family, stage, diagnostics,
                    candidate_id, fold=None) -> dict:
    captured = diagnostics.get("warnings", [])
    convergence = sum(item.get("category") == "ConvergenceWarning" for item in captured)
    return {"task": task, "representation": representation, "family": family,
            "stage": stage, "candidate_id": candidate_id, "fold": fold,
            "status": diagnostics.get("status", "complete"), "fit_entries": 1,
            "fit_entries_with_warning": int(bool(captured)),
            "fit_entries_with_convergence_warning": int(convergence > 0),
            "warning_records": len(captured), "convergence_warning_records": convergence}


def warning_summary(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    counts = ["fit_entries", "fit_entries_with_warning", "fit_entries_with_convergence_warning",
              "warning_records", "convergence_warning_records"]
    summary = frame.groupby(["stage", "representation", "family"], as_index=False)[counts].sum()
    summary["fraction_fit_entries_with_convergence_warning"] = (
        summary["fit_entries_with_convergence_warning"] / summary["fit_entries"])
    return summary


def _prefix(values: dict, prefix: str) -> dict:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def run_audit(root: Path, runs_dir: Path, out: Path) -> dict:
    root, runs_dir, out = root.resolve(), runs_dir.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    study = root / STUDY
    if str(study) not in sys.path:
        sys.path.insert(0, str(study))
    seal, tasks = verify_checkpoint(root, runs_dir)
    analysis_lock = read_json(study / "analysis_lock.json")
    source_hashes = {}
    for name in ("models.py", "model_inputs.py"):
        relative = (STUDY / name).as_posix()
        source_hashes[relative] = sha256(study / name)
        if source_hashes[relative] != analysis_lock["files"].get(relative):
            raise ValueError(f"Original A1 source file differs: {relative}")
    # Import original classes before loading trusted, hash-verified joblib data.
    import models  # noqa: F401
    from model_inputs import load_model_frame, make_raw_matrix, make_date_matrix
    config = read_json(study / "config.json")
    development = load_model_frame(root, "development").set_index("canonical_id", drop=False)
    development.index = development.index.astype(str)
    if len(development) != 1000 or development.index.duplicated().any():
        raise ValueError("The locked 1000-person development frame is required")
    matrices = {"raw_A": make_raw_matrix, "date_control": make_date_matrix}
    model_rows, candidate_rows, warning_rows, outer_frames = [], [], [], []
    unique_models, selected_final_warnings = 0, []
    for folder, manifest in tasks:
        task, kind = manifest["task"], manifest["kind"]
        ids = list(map(str, read_json(folder / "training_ids.json")))
        if (len(ids) != manifest["train_n"] or len(set(ids)) != len(ids)
                or not set(ids) <= set(development.index)):
            raise ValueError(f"Training identities differ: {task}")
        train = development.loc[ids].reset_index(drop=True)
        y = train["rating"].to_numpy(dtype=float)
        if float(np.median(y)) != manifest["median_elo"]:
            raise ValueError(f"Training-median Elo differs: {task}")
        folds = read_json(folder / "inner_folds.json")
        benchmark = np.repeat(float(np.median(y)), len(y))
        inner_benchmark = inner_median_predictions(ids, y, folds)
        baseline_row = {"task": task, "kind": kind, "train_n": len(y),
                        "representation": "benchmark", "family": "training_median",
                        "candidate_id": None, "roles": "benchmark", "selected_pipeline": False,
                        "model_file": None, "model_sha256": None,
                        **_prefix(metrics(y, benchmark), "train"),
                        **_prefix(metrics(y, inner_benchmark), "inner_oof")}
        baseline_row["inner_minus_train_mae"] = baseline_row["inner_oof_mae"] - baseline_row["train_mae"]
        outer = None
        if kind == "development":
            outer = pd.read_csv(folder / manifest["development_predictions_file"],
                                dtype={"canonical_id": str}, float_precision="round_trip")
            validation_ids = list(map(str, read_json(folder / "validation_ids.json")))
            if (outer["canonical_id"].tolist() != validation_ids or set(ids) & set(validation_ids)
                    or not set(validation_ids) <= set(development.index)):
                raise ValueError(f"Invalid outer identities: {task}")
            valid = development.loc[validation_ids].reset_index(drop=True)
            if not np.array_equal(valid["rating"].to_numpy(dtype=float), outer["rating"].to_numpy(dtype=float)):
                raise ValueError(f"Outer Elo differs: {task}")
            baseline_row.update(_prefix(metrics(outer["rating"], outer["pred_median"]), "outer"))
            outer_frames.append(outer.assign(task=task, train_n=len(y), outer_fold=manifest["outer_fold"]))
        model_rows.append(baseline_row)
        for representation in REPRESENTATIONS:
            rep = manifest["representations"][representation]
            search = read_json(folder / f"search_{representation}.json")
            if search.get("status") != "complete" or search.get("n_rows") != len(y):
                raise ValueError(f"Incomplete inner search: {task}/{representation}")
            result_by_id = {}
            for result in search["candidate_results"]:
                candidate_id = result["candidate_id"]
                if candidate_id in result_by_id:
                    raise ValueError("Repeated candidate identity")
                result_by_id[candidate_id] = result
                if result["status"] == "complete":
                    calculated = metrics(y, result["oof_predictions"])
                    if abs(calculated["mae"] - result["mae"]) > 1e-9:
                        raise ValueError(f"Inner OOF metric differs: {task}/{representation}/{candidate_id}")
                    candidate_rows.append({"task": task, "kind": kind, "representation": representation,
                                           "train_n": len(y), "family": result["family"],
                                           "candidate_id": candidate_id, "status": result["status"],
                                           **_prefix(calculated, "inner_oof")})
                else:
                    candidate_rows.append({"task": task, "kind": kind, "representation": representation,
                                           "train_n": len(y), "family": result["family"],
                                           "candidate_id": candidate_id, "status": result["status"]})
                for fold in result["folds"]:
                    warning_rows.append(warning_fit_row(task, representation, result["family"],
                        "inner_search", fold, candidate_id, fold.get("fold")))
            # A selected pipeline can alias a family object. Score/unpickle it once.
            objects = {}
            for role, record in [("selected_pipeline", rep["selected_model"]),
                                 *[(f"family:{family}", record)
                                   for family, record in rep["family_models"].items()]]:
                if record.get("status") != "complete":
                    continue
                name = record["model_file"]
                if name in objects:
                    prior, roles = objects[name]
                    if prior["candidate_id"] != record["candidate_id"] or prior["model_sha256"] != record["model_sha256"]:
                        raise ValueError("Aliased model has contradictory metadata")
                    roles.append(role)
                else:
                    objects[name] = (record, [role])
            X = matrices[representation](train, config)
            for name, (record, roles) in objects.items():
                path = safe_file(folder, name)
                if sha256(path) != record["model_sha256"]:
                    raise ValueError(f"Model fingerprint differs: {task}/{name}")
                model = joblib.load(path)
                with threadpool_limits(limits=1):
                    train_prediction = model.predict(X)
                candidate_id = record["candidate_id"]
                result = result_by_id[candidate_id]
                if result["status"] != "complete":
                    raise ValueError("Saved model has an invalid inner search candidate")
                row = {"task": task, "kind": kind, "train_n": len(y),
                       "representation": representation, "family": record["candidate"]["family"],
                       "candidate_id": candidate_id, "roles": ";".join(roles),
                       "selected_pipeline": "selected_pipeline" in roles,
                       "model_file": name, "model_sha256": record["model_sha256"],
                       **_prefix(metrics(y, train_prediction), "train"),
                       **_prefix(metrics(y, result["oof_predictions"]), "inner_oof")}
                row["inner_minus_train_mae"] = row["inner_oof_mae"] - row["train_mae"]
                diagnostics = record["refit_diagnostics"]
                row["refit_warning_records"] = len(diagnostics.get("warnings", []))
                warning_rows.append(warning_fit_row(task, representation, row["family"],
                    "refit", diagnostics, candidate_id))
                if kind == "final" and row["selected_pipeline"]:
                    selected_final_warnings.append({"task": task, "representation": representation,
                        "family": row["family"], "warning_records": row["refit_warning_records"]})
                if outer is not None and row["selected_pipeline"]:
                    with threadpool_limits(limits=1):
                        replay = np.asarray(model.predict(matrices[representation](valid, config)), dtype=float)
                    cached = outer[f"pred_{representation}"].to_numpy(dtype=float)
                    if not np.allclose(replay, cached, rtol=0, atol=1e-8):
                        raise ValueError(f"Sealed outer prediction replay differs: {task}/{representation}")
                    row.update(_prefix(metrics(outer["rating"], cached), "outer"))
                    row["outer_replay_max_abs_difference"] = float(np.max(np.abs(replay - cached)))
                model_rows.append(row)
                unique_models += 1
    model_frame = pd.DataFrame(model_rows)
    pd.DataFrame(candidate_rows).to_csv(out / "existing_candidate_metrics.csv", index=False, float_format="%.17g")
    model_frame.to_csv(out / "existing_model_metrics.csv", index=False, float_format="%.17g")
    pd.DataFrame(warning_rows).to_csv(out / "existing_warning_fits.csv", index=False)
    warning_summary(warning_rows).to_csv(out / "existing_warning_summary.csv", index=False, float_format="%.17g")
    outer_frame = pd.concat(outer_frames, ignore_index=True)
    outer_frame.to_csv(out / "existing_development_predictions.csv", index=False, float_format="%.17g")
    outer_rows = []
    for train_n, block in outer_frame.groupby("train_n"):
        if len(block) != 1000 or block["canonical_id"].nunique() != 1000:
            raise ValueError("Pooled outer predictions must cover all 1000 people once per size")
        for representation, column in [("raw_A", "pred_raw_A"), ("date_control", "pred_date_control"),
                                       ("benchmark", "pred_median")]:
            outer_rows.append({"train_n": int(train_n), "representation": representation,
                               **metrics(block["rating"], block[column])})
    pd.DataFrame(outer_rows).to_csv(out / "existing_development_metrics.csv", index=False, float_format="%.17g")
    all_warning_records = sum(row["warning_records"] for row in warning_rows)
    if all_warning_records != sum(manifest["warning_count"] for _, manifest in tasks):
        raise ValueError("Warning ledger does not reproduce the sealed manifest totals")
    summary = {
        "status": "complete_read_only_A1_development_audit",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_models_fitted": 0, "external_data_or_scores_loaded": False,
        "loaded_model_frame_roles": ["development"], "tasks": len(tasks),
        "script_sha256": sha256(Path(__file__).resolve()),
        "config_sha256": seal["reference_hashes"]["config_sha256"],
        "development_input_sha256": read_json(study / "data/data_manifest.json")["roles"]["development"]["sha256"],
        "original_source_files_sha256": source_hashes,
        "environment": {"python": platform.python_version(),
            **{package: importlib.metadata.version(package) for package in
               ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl")}},
        "sealed_models_lock_sha256": sha256(runs_dir.parent / "fitted_models_lock.json"),
        "analysis_lock_sha256": seal["reference_hashes"]["analysis_lock_sha256"],
        "execution_commit_A1": seal["execution_commit"], "unique_model_objects_scored": unique_models,
        "model_metric_rows_including_median": len(model_rows),
        "candidate_metric_rows": len(candidate_rows), "warning_fit_entries": len(warning_rows),
        "warning_records": all_warning_records,
        "fit_entries_with_convergence_warning": sum(row["fit_entries_with_convergence_warning"] for row in warning_rows),
        "selected_final_refits": selected_final_warnings,
        "selected_final_refit_warning_records": sum(row["warning_records"] for row in selected_final_warnings),
        "primary_nested_cv_train_n": 800,
        "primary_nested_cv_metrics": [row for row in outer_rows if row["train_n"] == 800],
        "interpretation": [
            "Inner OOF errors of chosen candidates have selection bias; these are descriptive diagnostics, not fresh confirmation.",
            "Train/OOF gaps compare a full-size refit against smaller inner-fold fits and are not a pure same-training-size generalization gap.",
            "Warning rows count estimator fit entries; one MLP ensemble entry may generate warnings from multiple seeds.",
            "The original estimators optimize squared-error-based objectives, with regularization where specified; evaluation MAE need not improve when that objective improves.",
            "Original development outer predictions are replayed without fitting; their prior use means this audit is not a new blind experiment.",
        ],
    }
    summary["outputs"] = [{"path": name, "sha256": sha256(out / name)} for name in (
        "existing_candidate_metrics.csv", "existing_model_metrics.csv",
        "existing_warning_fits.csv", "existing_warning_summary.csv",
        "existing_development_predictions.csv", "existing_development_metrics.csv")]
    (out / "existing_audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_audit(args.repo_root, args.runs_dir, args.output_dir)
    print(json.dumps({key: result[key] for key in ("status", "tasks", "unique_model_objects_scored", "warning_records", "selected_final_refit_warning_records")}, indent=2))


if __name__ == "__main__":
    main()
