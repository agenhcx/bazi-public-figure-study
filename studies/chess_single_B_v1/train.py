#!/usr/bin/env python3
"""Nested 2013-only B1 searches; seal every task before any external scoring."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

STUDY = Path("studies/chess_single_B_v1")
SOURCE_LOCK = STUDY / "b1_lock.json"
REPRESENTATIONS = ("b1", "raw", "date")
TASKS = tuple(f"outer-{i}" for i in range(5)) + ("final",)
SEAL_NAME = "fitted_models_lock.json"
SEAL_STATUS = "all_B1_models_sealed_before_external_scoring"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ids_sha256(ids) -> str:
    return hashlib.sha256(("\n".join(map(str, ids)) + "\n").encode()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _a_imports(root: Path):
    source = str(root / "studies/chess_single_A_v2")
    if source not in sys.path:
        sys.path.insert(0, source)
    from model_inputs import load_model_frame, get_training_ids
    from train_models import fit_predict_checked, environment_versions
    return load_model_frame, get_training_ids, fit_predict_checked, environment_versions


def _splitter(config: dict, kind: str) -> KFold:
    spec = config["cv"][kind]
    return KFold(n_splits=int(spec["n_splits"]), shuffle=bool(spec["shuffle"]),
                 random_state=int(spec["random_state"]))


def task_frames(frame: pd.DataFrame, task: str, config: dict, ids):
    """Use the original lexicographic ordering and all 800 outer training rows."""
    if task not in TASKS:
        raise ValueError("Unknown fixed B1 task")
    selected = list(map(str, ids))
    if len(selected) != 1000 or len(set(selected)) != 1000:
        raise ValueError("random_1000 must contain 1000 distinct identities")
    if frame["canonical_id"].astype(str).duplicated().any():
        raise ValueError("Duplicate development identity")
    frame = frame.copy()
    frame["canonical_id"] = frame["canonical_id"].astype(str)
    if set(selected) - set(frame["canonical_id"]):
        raise ValueError("Missing development identity")
    primary = frame.loc[frame["canonical_id"].isin(selected)].sort_values(
        "canonical_id", kind="stable").reset_index(drop=True)
    if task == "final":
        return primary, None
    index = int(task.split("-")[1])
    training, validation = list(_splitter(config, "outer").split(primary))[index]
    return primary.iloc[training].reset_index(drop=True), primary.iloc[validation].reset_index(drop=True)


def first_best(rows, tolerance: float):
    valid = [row for row in rows if row["status"] == "complete"]
    if not valid:
        raise RuntimeError("No valid candidate in the fixed search")
    minimum = min(row["mae"] for row in valid)
    return next(row for row in valid if row["mae"] <= minimum + tolerance)


def search_candidates(frame: pd.DataFrame, y, config: dict, candidate_list,
                      estimator_factory=None, fit_predict=None, progress=None):
    """Select by pooled person-level OOF MAE; never inspect an outer target."""
    y = np.asarray(y, dtype=float)
    if y.shape != (len(frame),) or not np.isfinite(y).all():
        raise ValueError("Invalid or unaligned training targets")
    choices = list(candidate_list)
    if not choices or len({c["candidate_id"] for c in choices}) != len(choices):
        raise ValueError("Candidate identifiers must be nonempty and unique")
    if estimator_factory is None:
        from features import build_estimator
        estimator_factory = build_estimator
    if fit_predict is None:
        fit_predict = _a_imports(Path(__file__).resolve().parents[2])[2]
    folds = list(_splitter(config, "inner").split(frame))
    rows = []
    for candidate in choices:
        oof = np.full(len(y), np.nan)
        row = {"candidate_id": candidate["candidate_id"], "candidate": candidate,
               "status": "complete", "mae": None, "folds": [], "oof_predictions": None}
        for fold, (train, valid) in enumerate(folds):
            try:
                estimator = estimator_factory(candidate)
                prediction, diagnostics = fit_predict(
                    estimator, frame.iloc[train], y[train], frame.iloc[valid])
                if prediction is not None:
                    prediction = np.asarray(prediction, dtype=float)
                    if prediction.shape != (len(valid),) or not np.isfinite(prediction).all():
                        raise ValueError("Invalid held-out predictions")
            except Exception as error:
                prediction = None
                diagnostics = {"status": "invalid", "warnings": [],
                               "error_type": type(error).__name__, "error": str(error)}
            diagnostics.update({"fold": fold, "training_n": len(train), "validation_n": len(valid)})
            if prediction is None:
                row["status"] = "invalid"
                row["folds"].append(diagnostics)
                break
            oof[valid] = prediction
            diagnostics["absolute_error_sum"] = float(np.abs(y[valid] - prediction).sum())
            row["folds"].append(diagnostics)
        if row["status"] == "complete":
            if not np.isfinite(oof).all():
                raise RuntimeError("Incomplete predictions from a complete candidate")
            row["mae"] = float(np.mean(np.abs(y - oof)))
            row["oof_predictions"] = oof.tolist()
        rows.append(row)
        if progress:
            progress(rows)
    winner = first_best(rows, float(config["selection"]["tie_tolerance_mae"]))
    return {"status": "complete", "n_rows": len(y), "n_folds": len(folds),
            "metric": "pooled per-player OOF MAE in original Elo units",
            "selected_candidate": winner["candidate"], "selected_candidate_id": winner["candidate_id"],
            "selected_inner_mae": winner["mae"], "candidate_results": rows}


def search_stats(search: dict) -> dict:
    rows = search["candidate_results"]
    entries = [fold for row in rows for fold in row["folds"]]
    warnings = [warning for fold in entries for warning in fold["warnings"]]
    return {"candidates": len(rows), "valid_candidates": sum(row["status"] == "complete" for row in rows),
            "invalid_candidates": sum(row["status"] != "complete" for row in rows),
            "fit_entries": len(entries), "warning_records": len(warnings),
            "convergence_warnings": sum(w["category"] == "ConvergenceWarning" for w in warnings),
            "failed_fit_entries": sum(fold["status"] != "complete" for fold in entries)}


def executing_commit(root: Path) -> str:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else os.environ.get("GITHUB_SHA", "local_uncommitted")


def _validate_search(search, choices, y, config):
    if search.get("status") != "complete" or search.get("n_rows") != len(y):
        raise ValueError("Incomplete or misaligned candidate search")
    folds = list(_splitter(config, "inner").split(np.arange(len(y))))
    rows = search["candidate_results"]
    if [row["candidate"] for row in rows] != choices or search.get("n_folds") != len(folds):
        raise ValueError("Search candidates/folds differ from the fixed grid")
    for row in rows:
        entries = row["folds"]
        if row["candidate_id"] != row["candidate"]["candidate_id"] or not entries or len(entries) > len(folds):
            raise ValueError("Invalid candidate/fold record")
        for i, entry in enumerate(entries):
            a, b = folds[i]
            if entry.get("fold") != i or entry.get("training_n") != len(a) or entry.get("validation_n") != len(b):
                raise ValueError("Search fold sizes/index differ")
        if row["status"] == "complete":
            prediction = np.asarray(row["oof_predictions"], dtype=float)
            if (len(entries) != len(folds) or any(e["status"] != "complete" for e in entries)
                    or prediction.shape != y.shape or not np.isfinite(prediction).all()
                    or row["mae"] != float(np.mean(np.abs(y - prediction)))):
                raise ValueError("Candidate pooled OOF score is inconsistent")
            for entry, (_, valid) in zip(entries, folds):
                if entry.get("absolute_error_sum") != float(np.abs(y[valid] - prediction[valid]).sum()):
                    raise ValueError("Candidate fold error sum is inconsistent")
        elif (row["status"] != "invalid" or row["mae"] is not None or row["oof_predictions"] is not None
              or entries[-1]["status"] != "invalid"):
            raise ValueError("Invalid candidate must not retain a selection score")
    best = first_best(rows, config["selection"]["tie_tolerance_mae"])
    if (search.get("selected_candidate") != best["candidate"]
            or search.get("selected_candidate_id") != best["candidate_id"]
            or search.get("selected_inner_mae") != best["mae"]):
        raise ValueError("Search selected candidate violates its tie rule")
    return best


def run_task(root: Path, task: str, output: Path):
    root, output = root.resolve(), output.resolve()
    from lock_b1 import verify_lock
    from features import candidates, build_estimator
    verify_lock(root)
    config_path = root / STUDY / "config.json"
    config = read_json(config_path)
    if config.get("fit_allowed") is not True:
        raise ValueError("B1 research fitting is disabled")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite an existing training task")
    output.mkdir(parents=True, exist_ok=True)
    load_frame, get_ids, fit_predict, environment = _a_imports(root)
    training, validation = task_frames(load_frame(root, "development"), task, config,
                                       get_ids(root, "random_1000"))
    y = training["rating"].to_numpy(dtype=float)
    ids = training["canonical_id"].tolist()
    write_json(output / "training_ids.json", ids)
    inner = [{"fold": i, "training_ids": [ids[j] for j in a], "validation_ids": [ids[j] for j in b]}
             for i, (a, b) in enumerate(_splitter(config, "inner").split(training))]
    write_json(output / "inner_folds.json", inner)
    (output / "config.json").write_bytes(config_path.read_bytes())
    median = float(np.median(y))
    recorded_environment = environment()
    recorded_environment["packages"]["matplotlib"] = importlib.metadata.version("matplotlib")
    manifest = {"protocol_id": "chess-single-B-v1", "status": "incomplete", "task": task,
                "started_at_utc": datetime.now(timezone.utc).isoformat(), "train_n": len(training),
                "training_ids_sha256": ids_sha256(ids), "median_elo": median,
                "source_lock_sha256": sha256(root / SOURCE_LOCK), "config_sha256": sha256(config_path),
                "data_manifest_sha256": sha256(root / "studies/chess_single_A_v2/data/data_manifest.json"),
                "executing_commit": executing_commit(root), "environment": recorded_environment,
                "external_data_loaded": False, "representations": {}}
    prediction_table = None
    if validation is not None:
        validation_ids = validation["canonical_id"].tolist()
        write_json(output / "validation_ids.json", validation_ids)
        manifest["validation_ids_sha256"] = ids_sha256(validation_ids)
        manifest["validation_n"] = len(validation)
        prediction_table = pd.DataFrame({"canonical_id": validation_ids,
            "rating": validation["rating"].to_numpy(dtype=float), "outer_fold": int(task.split("-")[1]),
            "prediction_median": median})
    manifest_path = output / "task_manifest.json"
    write_json(manifest_path, manifest)
    try:
        all_candidates = candidates(config)
        for representation in REPRESENTATIONS:
            selected = [c for c in all_candidates if c["representation"] == representation]
            search_path = output / "searches" / f"{representation}.json"
            def progress(rows, path=search_path, rep=representation):
                write_json(path, {"status": "incomplete", "representation": rep, "candidate_results": rows})
                row = rows[-1]
                print(f"[{task}/{rep}] {row['candidate_id']} {row['status']} MAE={row['mae']}", flush=True)
            search = search_candidates(training, y, config, selected, build_estimator, fit_predict, progress)
            write_json(search_path, search)
            candidate = search["selected_candidate"]
            model = build_estimator(candidate)
            prediction, diagnostics = fit_predict(model, training, y, validation if validation is not None else training)
            if prediction is None:
                raise RuntimeError(f"Selected {representation} refit failed: {diagnostics}")
            rep = {"candidate": candidate, "candidate_id": candidate["candidate_id"],
                   "inner_mae": search["selected_inner_mae"], "search_stats": search_stats(search),
                   "model_file": None, "model_sha256": None, "refit_diagnostics": diagnostics}
            if task == "final":
                path = output / "models" / f"{representation}.joblib"
                path.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump(model, path, compress=3)
                rep.update(model_file=path.relative_to(output).as_posix(), model_sha256=sha256(path))
            else:
                prediction_table[f"prediction_{representation}"] = prediction
                prediction_table.to_csv(output / "outer_predictions.csv", index=False, float_format="%.17g")
            manifest["representations"][representation] = rep
            write_json(manifest_path, manifest)
        manifest["status"] = "complete"
        manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["files"] = {path.relative_to(output).as_posix(): sha256(path) for path in sorted(output.rglob("*"))
                             if path.is_file() and path != manifest_path and not path.name.endswith(".tmp")}
        write_json(manifest_path, manifest)
        return manifest
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__, error=str(error))
        write_json(manifest_path, manifest)
        raise


def _safe_file(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Unsafe recorded path")
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file() or path.is_symlink():
        raise ValueError(f"Missing or unsafe recorded file: {relative}")
    return path


def _validate_task_outputs(root: Path, inputs: Path):
    from features import candidates
    load_frame, get_ids, _, _ = _a_imports(root)
    config = read_json(root / STUDY / "config.json")
    allowed = {c["candidate_id"]: c for c in candidates(config)}
    source_sha = sha256(root / SOURCE_LOCK)
    expected_environment = read_json(root / "studies/chess_single_A_v2/analysis_lock.json")["environment"]
    data_sha = sha256(root / "studies/chess_single_A_v2/data/data_manifest.json")
    commits = set()
    frame = load_frame(root, "development")
    primary_ids = get_ids(root, "random_1000")
    manifests = list(inputs.rglob("task_manifest.json"))
    if len(manifests) != len(TASKS):
        raise ValueError("Seal requires exactly all six task manifests")
    tasks, files = {}, {}
    for path in manifests:
        manifest = read_json(path)
        task = manifest.get("task")
        if task not in TASKS or task in tasks or manifest.get("status") != "complete":
            raise ValueError("Missing, duplicated, or incomplete B1 task")
        if manifest.get("protocol_id") != "chess-single-B-v1" or manifest.get("external_data_loaded") is not False:
            raise ValueError("Wrong protocol or external data used during training")
        if manifest.get("source_lock_sha256") != source_sha or manifest.get("config_sha256") != sha256(root / STUDY / "config.json"):
            raise ValueError("Training outputs use another source/config lock")
        commit = manifest.get("executing_commit", "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Training provenance lacks an exact source commit")
        commits.add(commit)
        if os.environ.get("GITHUB_SHA") and commit != os.environ["GITHUB_SHA"]:
            raise ValueError("Training source commit differs from this locked workflow")
        environment = manifest.get("environment", {})
        if (environment.get("python") != expected_environment["python"]
                or environment.get("fit_thread_limit") != 1
                or any(environment.get("packages", {}).get(name) != version
                       for name, version in expected_environment.items() if name != "python")
                or manifest.get("data_manifest_sha256") != data_sha):
            raise ValueError("Training environment/data provenance differs from the pinned analysis")
        directory = path.parent
        if sha256(directory / "config.json") != sha256(root / STUDY / "config.json"):
            raise ValueError("Copied training configuration differs")
        training, validation = task_frames(frame, task, config, primary_ids)
        training_ids = training["canonical_id"].tolist()
        if read_json(directory / "training_ids.json") != training_ids or manifest.get("training_ids_sha256") != ids_sha256(training_ids):
            raise ValueError("Training identities disagree with the fixed CV split")
        if manifest.get("train_n") != len(training) or manifest.get("median_elo") != float(np.median(training["rating"])):
            raise ValueError("Training size/median mismatch")
        expected_inner = [{"fold": i, "training_ids": [training_ids[j] for j in a],
                           "validation_ids": [training_ids[j] for j in b]}
                          for i, (a, b) in enumerate(_splitter(config, "inner").split(training))]
        if read_json(directory / "inner_folds.json") != expected_inner:
            raise ValueError("Inner folds disagree with the fixed split")
        if set(manifest.get("representations", {})) != set(REPRESENTATIONS):
            raise ValueError("Incomplete model representations")
        for rep, record in manifest["representations"].items():
            candidate = record.get("candidate", {})
            if allowed.get(record.get("candidate_id")) != candidate or candidate.get("representation") != rep:
                raise ValueError("Selected candidate is outside its fixed representation grid")
            search = read_json(directory / "searches" / f"{rep}.json")
            expected_choices = [c for c in allowed.values() if c["representation"] == rep]
            best = _validate_search(search, expected_choices, training["rating"].to_numpy(dtype=float), config)
            if (best["candidate"] != candidate or record["inner_mae"] != best["mae"]
                    or record["search_stats"] != search_stats(search)):
                raise ValueError("Search selection does not match its fixed candidates/scores")
            if record["refit_diagnostics"]["status"] != "complete":
                raise ValueError("Selected refit did not complete")
            if task == "final":
                model = _safe_file(directory, record["model_file"])
                if model.suffix != ".joblib" or sha256(model) != record["model_sha256"]:
                    raise ValueError("Final model hash mismatch")
            elif record.get("model_file") is not None:
                raise ValueError("Unexpected outer model artifact")
        if validation is not None:
            ids = validation["canonical_id"].tolist()
            if read_json(directory / "validation_ids.json") != ids or manifest.get("validation_ids_sha256") != ids_sha256(ids):
                raise ValueError("Validation identities disagree with the fixed CV split")
            predictions = pd.read_csv(directory / "outer_predictions.csv", dtype={"canonical_id": str})
            required = {"canonical_id", "rating", "outer_fold", "prediction_median"} | {f"prediction_{r}" for r in REPRESENTATIONS}
            if set(predictions) != required or predictions["canonical_id"].tolist() != ids:
                raise ValueError("Validation prediction identity/column mismatch")
            if (not np.isfinite(predictions.drop(columns="canonical_id").to_numpy(dtype=float)).all()
                    or not np.array_equal(predictions["rating"], validation["rating"])
                    or not (predictions["outer_fold"] == int(task.split("-")[1])).all()
                    or not (predictions["prediction_median"] == manifest["median_elo"]).all()):
                raise ValueError("Invalid validation targets/predictions")
        recorded_files = manifest.get("files", {})
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() and p != path}
        if set(recorded_files) != actual:
            raise ValueError("Unrecorded or missing task files")
        for name, digest in recorded_files.items():
            if sha256(_safe_file(directory, name)) != digest:
                raise ValueError(f"Changed task artifact: {name}")
        tasks[task] = {"directory": directory.relative_to(inputs).as_posix(), "manifest_sha256": sha256(path)}
        for item in [path] + [directory / name for name in recorded_files]:
            name = item.relative_to(inputs).as_posix()
            if name in files:
                raise ValueError("Task output directories overlap")
            files[name] = sha256(item)
    if set(tasks) != set(TASKS):
        raise ValueError("Missing required task")
    if len(commits) != 1:
        raise ValueError("B1 task source commits differ")
    return {"tasks": dict(sorted(tasks.items())), "files": dict(sorted(files.items()))}


def seal_models(root: Path, inputs: Path):
    root, inputs = root.resolve(), inputs.resolve()
    from lock_b1 import verify_lock
    verify_lock(root)
    path = inputs / SEAL_NAME
    if path.exists():
        return verify_seal(root, inputs)
    result = _validate_task_outputs(root, inputs)
    seal = {"protocol_id": "chess-single-B-v1", "status": SEAL_STATUS,
            "source_lock_sha256": sha256(root / SOURCE_LOCK), "external_scoring_occurred": False,
            "created_at_utc": datetime.now(timezone.utc).isoformat(), **result}
    write_json(path, seal)
    return seal


def verify_seal(root: Path, inputs: Path):
    root, inputs = root.resolve(), inputs.resolve()
    from lock_b1 import verify_lock
    verify_lock(root)
    seal = read_json(inputs / SEAL_NAME)
    if (seal.get("status") != SEAL_STATUS or seal.get("protocol_id") != "chess-single-B-v1"
            or seal.get("external_scoring_occurred") is not False
            or seal.get("source_lock_sha256") != sha256(root / SOURCE_LOCK)):
        raise ValueError("Invalid fitted B1 model seal")
    current = _validate_task_outputs(root, inputs)
    if seal.get("tasks") != current["tasks"] or seal.get("files") != current["files"]:
        raise ValueError("Sealed B1 outputs changed")
    return seal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--task", choices=TASKS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--inputs-dir", type=Path)
    args = parser.parse_args()
    if args.seal:
        if args.task or args.inputs_dir is None:
            parser.error("--seal requires --inputs-dir and no --task")
        result = seal_models(args.repo_root, args.inputs_dir)
    else:
        if args.task is None or args.output_dir is None:
            parser.error("Training requires --task and --output-dir")
        result = run_task(args.repo_root, args.task, args.output_dir)
    print(json.dumps({"status": result["status"], "task": result.get("task"),
                      "external_data_loaded": False}))


if __name__ == "__main__":
    main()
