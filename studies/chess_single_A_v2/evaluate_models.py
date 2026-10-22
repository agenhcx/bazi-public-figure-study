#!/usr/bin/env python3
"""Seal all pre-specified fitted models, then evaluate fixed external cohorts.

The seal command never reads an external frame. The evaluate command verifies
the complete seal again before loading any 2023 frame or producing a score.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import KFold

HERE = Path(__file__).resolve().parent
RELATIVE_STUDY = Path("studies/chess_single_A_v2")
REPRESENTATIONS = ("raw_A", "date_control")
FINAL_SUBSETS = ("random_500", "random_800", "random_1000",
                 "ranked_500_with_ties", "ranked_800_with_ties")
ALL_SUBSETS = FINAL_SUBSETS + ("ranked_1000_with_ties",)
EXTERNAL_ROLES = ("primary_new", "supplementary_full", "legacy_full")
EXPECTED_TASKS = tuple(f"dev_f{fold}_n{size}" for fold in range(5)
                       for size in (400, 600, 800)) + tuple(
                           "final_" + name for name in FINAL_SUBSETS)
SEALED_STATUS = "all_prespecified_models_sealed_before_external_evaluation"


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                     sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_path(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("Artifact path must be a nonempty relative string")
    candidate = (base / relative).resolve()
    if Path(relative).is_absolute() or not candidate.is_relative_to(base.resolve()):
        raise ValueError(f"Artifact path escapes its directory: {relative}")
    return candidate


def ids_hash(ids) -> str:
    values = sorted(str(value) for value in ids)
    if len(set(values)) != len(values):
        raise ValueError("Duplicate person IDs in training subset")
    if any(not re.fullmatch(r"[1-9][0-9]*", value) for value in values):
        raise ValueError("Non-canonical person ID in training subset")
    return hashlib.sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def reference_hashes(root: Path) -> dict:
    study = root / RELATIVE_STUDY
    return {"config_sha256": digest(study / "config.json"),
            "data_manifest_sha256": digest(study / "data/data_manifest.json"),
            "analysis_lock_sha256": digest(study / "analysis_lock.json")}


def expected_task_specs(root: Path, config: dict) -> dict:
    """Derive IDs from locked 2013 inputs; never read an external frame here."""
    from model_inputs import get_training_ids, load_model_frame

    frame = load_model_frame(root, "development").copy()
    frame["canonical_id"] = frame["canonical_id"].astype(str)
    if frame["canonical_id"].duplicated().any():
        raise ValueError("Duplicate development person IDs")
    all_rows = frame.set_index("canonical_id", drop=False)
    primary_ids = sorted(get_training_ids(root, "random_1000"))
    if len(primary_ids) != 1000 or len(set(primary_ids)) != 1000:
        raise ValueError("Primary development subset is not exactly 1000 people")
    if not set(primary_ids) <= set(all_rows.index):
        raise ValueError("Training subset contains a non-development person")
    outer = config["cv"]["outer"]
    folds = KFold(n_splits=outer["n_splits"], shuffle=outer["shuffle"],
                  random_state=outer["random_state"])
    specs = {}
    for fold, (training, held_out) in enumerate(folds.split(primary_ids)):
        training_ids = [primary_ids[index] for index in training]
        heldout_ids = sorted(primary_ids[index] for index in held_out)
        seed = config["learning_curve"]["subset_permutation_seed"] + fold
        ordered = sorted(training_ids, key=lambda fid: (
            hashlib.sha256(f"{seed}\n{fid}".encode("utf-8")).hexdigest(), fid))
        for size in config["learning_curve"]["train_sizes"]:
            if len(ordered) < size:
                raise ValueError("Outer training fold is smaller than requested size")
            ids = sorted(ordered[:size])
            specs[f"dev_f{fold}_n{size}"] = {
                "kind": "development", "training_ids": ids,
                "heldout_ids": heldout_ids, "outer_fold": fold,
                "heldout_ratings": {fid: float(all_rows.loc[fid, "rating"]) for fid in heldout_ids},
                "train_n": size,
                "median_elo": float(np.median(all_rows.loc[ids, "rating"].to_numpy(float))),
            }
    for subset in FINAL_SUBSETS:
        ids = sorted(get_training_ids(root, subset))
        if not set(ids) <= set(all_rows.index):
            raise ValueError("Final subset contains a non-development person")
        specs["final_" + subset] = {
            "kind": "final", "training_subset": subset, "training_ids": ids,
            "train_n": len(ids),
            "median_elo": float(np.median(all_rows.loc[ids, "rating"].to_numpy(float))),
        }
    alias_ids = sorted(get_training_ids(root, "ranked_1000_with_ties"))
    if alias_ids != primary_ids:
        raise ValueError("Ranked1000 cannot alias Random1000: different locked IDs")
    if set(specs) != set(EXPECTED_TASKS):
        raise ValueError("Task specification differs from the fixed 20-task design")
    return specs


def _best_record(rows):
    valid = [row for row in rows if row.get("status") == "complete"]
    if not valid:
        return None
    minimum = min(float(row["mae"]) for row in valid)
    return next(row for row in valid if float(row["mae"]) <= minimum + 1e-12)


def _check_model_entry(task, model, listed):
    if model.get("status") != "complete":
        raise ValueError(f"{task}: selected/fitted model is not complete")
    if (model.get("model_file") not in listed
            or listed[model["model_file"]] != model.get("model_sha256")):
        raise ValueError(f"{task}: model is not covered by its artifact ledger")
    if not np.isfinite(float(model.get("inner_mae", np.nan))) or float(model["inner_mae"]) < 0:
        raise ValueError(f"{task}: missing finite inner-CV MAE")


def validate_runs(runs_dir: Path, hashes: dict, expected_specs: dict,
                  family_names, expected_candidates=None) -> tuple[dict, list]:
    """Validate all artifacts and identities before any external prediction."""
    runs_dir = runs_dir.resolve()
    manifests = {}
    for path in runs_dir.rglob("trainer_manifest.json"):
        data = read_json(path)
        task = data.get("task")
        if task in manifests:
            raise ValueError(f"Duplicate training task manifest: {task}")
        manifests[task] = (path, data)
    if set(manifests) != set(expected_specs):
        missing = sorted(set(expected_specs) - set(manifests))
        extra = sorted(set(manifests) - set(expected_specs), key=str)
        raise ValueError(f"Incomplete task set; missing={missing}, unexpected={extra}")
    records, ledger = {}, []
    for task in sorted(expected_specs):
        manifest_path, data = manifests[task]
        directory = manifest_path.parent
        expected = expected_specs[task]
        if data.get("status") != "complete" or data.get("kind") != expected["kind"]:
            raise ValueError(f"Training task is not complete with the expected kind: {task}")
        for key, checksum in hashes.items():
            if data.get(key) != checksum:
                raise ValueError(f"{task}: {key} does not match the locked root inputs")
        if data.get("train_n") != expected["train_n"]:
            raise ValueError(f"{task}: unexpected training count")
        if data.get("training_ids_sha256") != ids_hash(expected["training_ids"]):
            raise ValueError(f"{task}: unexpected training people")
        if not np.isfinite(float(data.get("median_elo", np.nan))) or not np.isclose(
                float(data["median_elo"]), expected["median_elo"], rtol=0, atol=1e-12):
            raise ValueError(f"{task}: training median does not match locked training people")
        listed = {}
        for entry in data.get("files", []):
            name = entry.get("path")
            if name in listed:
                raise ValueError(f"{task}: duplicate artifact in manifest")
            path = safe_path(directory, name)
            if not path.is_file() or digest(path) != entry.get("sha256"):
                raise ValueError(f"{task}: artifact hash mismatch: {name}")
            listed[name] = entry["sha256"]
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*")
                  if p.is_file() and p != manifest_path}
        if actual != set(listed):
            raise ValueError(f"{task}: unlisted or missing task artifacts")
        if set(data.get("representations", {})) != set(REPRESENTATIONS):
            raise ValueError(f"{task}: representations are incomplete")
        for representation in REPRESENTATIONS:
            item = data["representations"][representation]
            models = item.get("family_models", {})
            if expected["kind"] == "final" and set(models) != set(family_names):
                raise ValueError(f"{task}/{representation}: final family menu is incomplete")
            selected = item.get("selected_model", {})
            if (selected.get("status") != "complete"
                    or selected.get("candidate_id") != item.get("selected_candidate_id")):
                raise ValueError(f"{task}/{representation}: invalid selected model reference")
            _check_model_entry(task, selected, listed)
            if not np.isclose(float(item.get("selected_inner_mae", np.nan)),
                              float(selected.get("inner_mae", np.nan)), rtol=0, atol=1e-12):
                raise ValueError(f"{task}/{representation}: selected CV score is inconsistent")
            search_name = f"search_{representation}.json"
            if search_name not in listed:
                raise ValueError(f"{task}: complete inner-search log is not in the artifact ledger")
            search = read_json(safe_path(directory, search_name))
            rows = search.get("candidate_results", [])
            if search.get("status") != "complete" or not rows:
                raise ValueError(f"{task}: inner-search log is incomplete")
            if len({row.get("candidate_id") for row in rows}) != len(rows):
                raise ValueError(f"{task}: duplicate inner-search candidate IDs")
            for row in rows:
                if row.get("family") not in family_names or row.get("status") not in {"complete", "invalid"}:
                    raise ValueError(f"{task}: unrecognized search family or status")
                if row["status"] == "complete" and (not np.isfinite(float(row.get("mae", np.nan)))
                                                       or float(row["mae"]) < 0):
                    raise ValueError(f"{task}: valid search candidate has no finite CV MAE")
            if expected_candidates is not None:
                if [row.get("candidate") for row in rows] != expected_candidates:
                    raise ValueError(f"{task}: search log differs from the fixed candidate grid/order")
            winner = _best_record(rows)
            if (winner is None or winner["candidate_id"] != item.get("selected_candidate_id")
                    or winner["family"] != item.get("selected_family")
                    or not np.isclose(float(winner["mae"]), float(item["selected_inner_mae"]), rtol=0, atol=1e-12)):
                raise ValueError(f"{task}/{representation}: selected model is not the global fixed-order CV winner")
            family_selected = models.get(item["selected_family"])
            if (family_selected and selected["candidate_id"] != family_selected.get("candidate_id")
                    and selected["model_file"] == family_selected.get("model_file")):
                raise ValueError(f"{task}: distinct global and family candidates alias the same saved model")
            for family, model in models.items():
                if family not in family_names:
                    raise ValueError(f"{task}: unknown family {family}")
                if model.get("status") == "invalid_no_valid_candidate":
                    if family == item.get("selected_family"):
                        raise ValueError("An invalid family cannot be selected")
                    continue
                _check_model_entry(task, model, listed)
            if expected["kind"] == "final":
                for family in family_names:
                    model = models[family]
                    family_best = _best_record([row for row in rows if row["family"] == family])
                    if family_best is None:
                        if model.get("status") != "invalid_no_valid_candidate":
                            raise ValueError(f"{task}: all-invalid family incorrectly has a fitted model")
                    elif (model.get("status") != "complete" or model.get("candidate_id") != family_best["candidate_id"]
                          or not np.isclose(float(model["inner_mae"]), float(family_best["mae"]), rtol=0, atol=1e-12)):
                        raise ValueError(f"{task}/{representation}: family model is not its independently tuned CV winner")
        if expected["kind"] == "development":
            name = data.get("development_predictions_file")
            if name not in listed:
                raise ValueError(f"{task}: held-out predictions are not in the artifact ledger")
            predictions = pd.read_csv(safe_path(directory, name), dtype={"canonical_id": str})
            required = {"canonical_id", "rating", "pred_raw_A", "pred_date_control", "pred_median"}
            if not required <= set(predictions) or predictions["canonical_id"].duplicated().any():
                raise ValueError(f"{task}: malformed held-out predictions")
            if set(predictions["canonical_id"]) != set(expected["heldout_ids"]):
                raise ValueError(f"{task}: held-out prediction people do not match the outer fold")
            if "heldout_ratings" in expected and any(
                    float(row.rating) != expected["heldout_ratings"][row.canonical_id]
                    for row in predictions.itertuples()):
                raise ValueError(f"{task}: held-out targets do not match locked development data")
            if not np.isfinite(predictions[list(required - {"canonical_id"})].to_numpy(float)).all():
                raise ValueError(f"{task}: nonfinite held-out predictions")
            if not np.allclose(predictions["pred_median"], expected["median_elo"], rtol=0, atol=1e-12):
                raise ValueError(f"{task}: held-out median benchmark is not training-only")
        record = {"task": task,
                  "manifest_path": manifest_path.relative_to(runs_dir).as_posix(),
                  "manifest_sha256": digest(manifest_path),
                  "kind": expected["kind"], "train_n": expected["train_n"],
                  "training_ids_sha256": data["training_ids_sha256"],
                  "files": [{"path": name, "sha256": checksum}
                            for name, checksum in sorted(listed.items())]}
        ledger.append(record)
        records[task] = {"directory": directory, "manifest": data, "expected": expected}
    return records, ledger


def seal_models(root: Path, runs_dir: Path, output_dir: Path) -> dict:
    from lock_utils import verify_analysis_lock
    from models import candidate_configs

    verify_analysis_lock(root)
    config = read_json(root / RELATIVE_STUDY / "config.json")
    hashes = reference_hashes(root)
    specs = expected_task_specs(root, config)
    _, ledger = validate_runs(runs_dir, hashes, specs,
                              [item["name"] for item in config["families"]], candidate_configs(config))
    result = {"status": SEALED_STATUS,
              "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
              "execution_commit": os.environ.get("GITHUB_SHA"),
              "task_count": len(ledger), "reference_hashes": hashes,
              "tasks": ledger,
              "aliases": {"ranked_1000_with_ties": "random_1000"},
              "external_predictions_or_scores_created": False,
              "scope": "All fixed final models and 2013 outer-fold models saved before external evaluation"}
    write_json(output_dir / "fitted_models_lock.json", result)
    return result


def verify_seal(root: Path, runs_dir: Path, seal_file: Path) -> tuple[dict, dict]:
    from lock_utils import verify_analysis_lock
    from models import candidate_configs

    verify_analysis_lock(root)
    config = read_json(root / RELATIVE_STUDY / "config.json")
    seal = read_json(seal_file)
    hashes = reference_hashes(root)
    if (seal.get("status") != SEALED_STATUS or seal.get("reference_hashes") != hashes
            or seal.get("external_predictions_or_scores_created") is not False
            or seal.get("task_count") != len(EXPECTED_TASKS)):
        raise ValueError("Fitted-model seal is incomplete or does not match the analysis lock")
    specs = expected_task_specs(root, config)
    records, ledger = validate_runs(runs_dir, hashes, specs,
                                    [item["name"] for item in config["families"]], candidate_configs(config))
    if seal.get("tasks") != ledger or seal.get("aliases") != {"ranked_1000_with_ties": "random_1000"}:
        raise ValueError("Fitted-model artifacts changed after sealing")
    return config, records


def finite_values(values, label: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if not len(array) or not np.isfinite(array).all():
        raise ValueError(f"Empty or nonfinite values: {label}")
    return array


def regression_metrics(y, prediction) -> dict:
    truth, fitted = finite_values(y, "rating"), finite_values(prediction, "prediction")
    if truth.shape != fitted.shape:
        raise ValueError("Prediction and target lengths differ")
    rho = None
    if len(truth) > 1 and np.ptp(truth) > 0 and np.ptp(fitted) > 0:
        rho = float(spearmanr(truth, fitted).statistic)
        if not np.isfinite(rho):
            rho = None
    difference = truth - fitted
    return {"n": len(truth), "mae": float(np.mean(np.abs(difference))),
            "rmse": float(np.sqrt(np.mean(difference ** 2))), "spearman": rho}


def bootstrap_mean(difference, n_resamples=10000, random_state=20261023,
                    confidence_level=.95) -> dict:
    values = finite_values(difference, "paired difference")
    if n_resamples < 1 or not 0 < confidence_level < 1:
        raise ValueError("Invalid bootstrap settings")
    random = np.random.default_rng(random_state)
    means = np.empty(n_resamples, dtype=float)
    for start in range(0, n_resamples, 1000):
        end = min(start + 1000, n_resamples)
        indices = random.integers(0, len(values), size=(end - start, len(values)))
        means[start:end] = values[indices].mean(axis=1)
    alpha = (1 - confidence_level) / 2
    low, high = np.quantile(means, [alpha, 1 - alpha])
    return {"estimate": float(values.mean()), "ci_low": float(low), "ci_high": float(high),
            "confidence_level": confidence_level, "n_resamples": n_resamples,
            "random_state": random_state, "n": len(values),
            "method": "paired person-level percentile bootstrap; fixed fitted models"}


def align_predictions(first: pd.DataFrame, second: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {"canonical_id", "rating", "prediction"}
    if not required <= set(first) or not required <= set(second):
        raise ValueError("Paired predictions lack required columns")
    left, right = first.copy(), second.copy()
    for frame in (left, right):
        frame["canonical_id"] = frame["canonical_id"].astype(str)
        if frame["canonical_id"].duplicated().any():
            raise ValueError("Duplicate people in paired predictions")
    if set(left["canonical_id"]) != set(right["canonical_id"]):
        raise ValueError("Paired predictions refer to different people")
    left = left.sort_values("canonical_id").reset_index(drop=True)
    right = right.sort_values("canonical_id").reset_index(drop=True)
    if not np.array_equal(left["rating"].to_numpy(float), right["rating"].to_numpy(float)):
        raise ValueError("Paired predictions have inconsistent targets")
    return left, right


def paired_loss_difference(first: pd.DataFrame, second: pd.DataFrame) -> pd.DataFrame:
    left, right = align_predictions(first, second)
    y = finite_values(left["rating"], "paired target")
    loss_first = np.abs(y - finite_values(left["prediction"], "first paired prediction"))
    loss_second = np.abs(y - finite_values(right["prediction"], "second paired prediction"))
    return pd.DataFrame({"canonical_id": left["canonical_id"], "rating": y,
                         "first_absolute_error": loss_first,
                         "second_absolute_error": loss_second,
                         "difference": loss_first - loss_second})


def development_scores(records: dict, root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    from model_inputs import load_model_frame

    development = load_model_frame(root, "development").set_index("canonical_id")
    blocks = []
    for task, record in records.items():
        if record["manifest"]["kind"] != "development":
            continue
        path = safe_path(record["directory"], record["manifest"]["development_predictions_file"])
        frame = pd.read_csv(path, dtype={"canonical_id": str})
        actual = development.loc[frame["canonical_id"], "rating"].to_numpy(float)
        if not np.array_equal(actual, frame["rating"].to_numpy(float)):
            raise ValueError(f"{task}: held-out target differs from locked development target")
        frame["outer_fold"] = record["expected"]["outer_fold"]
        frame["train_n"] = record["expected"]["train_n"]
        blocks.append(frame)
    all_predictions = pd.concat(blocks, ignore_index=True)
    result = []
    columns = {"raw_A": "pred_raw_A", "date_control": "pred_date_control", "benchmark": "pred_median"}
    for size, frame in all_predictions.groupby("train_n", sort=True):
        if len(frame) != 1000 or frame["canonical_id"].nunique() != 1000:
            raise ValueError("Development learning curve does not have one held-out row per person")
        for representation, column in columns.items():
            result.append({"train_n": int(size), "representation": representation,
                           "model": "training_median" if representation == "benchmark" else "selected_pipeline",
                           **regression_metrics(frame["rating"], frame[column])})
    return pd.DataFrame(result), all_predictions


def external_scores(records: dict, root: Path, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    from model_inputs import load_model_frame, make_raw_matrix, make_date_matrix

    frames, matrices = {}, {}
    for role in EXTERNAL_ROLES:
        frame = load_model_frame(root, role).copy()
        frame["canonical_id"] = frame["canonical_id"].astype(str)
        if frame["canonical_id"].duplicated().any():
            raise ValueError(f"Duplicate evaluation people: {role}")
        frames[role] = frame.sort_values("canonical_id").reset_index(drop=True)
        matrices[role] = {"raw_A": make_raw_matrix(frames[role], config),
                          "date_control": make_date_matrix(frames[role], config)}
    family_names = [family["name"] for family in config["families"]]
    metric_rows, prediction_blocks = [], []
    # Same fitted Random1000 object serves both fixed result labels.
    for subset in ALL_SUBSETS:
        source_subset = "random_1000" if subset == "ranked_1000_with_ties" else subset
        record = records["final_" + source_subset]
        manifest = record["manifest"]
        for role in EXTERNAL_ROLES:
            frame = frames[role]
            median_prediction = np.repeat(float(manifest["median_elo"]), len(frame))
            metric_rows.append({"cohort": role, "subset": subset, "source_subset": source_subset,
                                "train_n": manifest["train_n"], "representation": "benchmark",
                                "model": "training_median", "status": "complete", "selected_family": None,
                                **regression_metrics(frame["rating"], median_prediction)})
            prediction_blocks.append(prediction_frame(frame, median_prediction, role, subset,
                                                       "benchmark", "training_median"))
        for representation in REPRESENTATIONS:
            item = manifest["representations"][representation]
            family_predictions = {}
            for family in family_names:
                model = item["family_models"][family]
                if model["status"] != "complete":
                    for role in EXTERNAL_ROLES:
                        metric_rows.append({"cohort": role, "subset": subset, "source_subset": source_subset,
                                            "train_n": manifest["train_n"], "representation": representation,
                                            "model": family, "status": model["status"], "selected_family": None,
                                            "n": len(frames[role]), "mae": None, "rmse": None, "spearman": None})
                    continue
                estimator = joblib.load(safe_path(record["directory"], model["model_file"]))
                family_predictions[family] = {}
                for role in EXTERNAL_ROLES:
                    prediction = finite_values(estimator.predict(matrices[role][representation]), "external prediction")
                    frame = frames[role]
                    family_predictions[family][role] = prediction
                    metric_rows.append({"cohort": role, "subset": subset, "source_subset": source_subset,
                                        "train_n": manifest["train_n"], "representation": representation,
                                        "model": family, "status": "complete", "selected_family": None,
                                        **regression_metrics(frame["rating"], prediction)})
                    prediction_blocks.append(prediction_frame(frame, prediction, role, subset,
                                                               representation, family))
            selected_family = item["selected_family"]
            selected_model = item["selected_model"]
            if selected_model["candidate_id"] == item["family_models"][selected_family]["candidate_id"]:
                selected_predictions = family_predictions[selected_family]
            else:
                selected_estimator = joblib.load(safe_path(record["directory"], selected_model["model_file"]))
                selected_predictions = {role: finite_values(
                    selected_estimator.predict(matrices[role][representation]), "selected external prediction")
                    for role in EXTERNAL_ROLES}
            for role in EXTERNAL_ROLES:
                prediction = selected_predictions[role]
                metric_rows.append({"cohort": role, "subset": subset, "source_subset": source_subset,
                                    "train_n": manifest["train_n"], "representation": representation,
                                    "model": "selected_pipeline", "status": "complete",
                                    "selected_family": selected_family,
                                    **regression_metrics(frames[role]["rating"], prediction)})
                prediction_blocks.append(prediction_frame(frames[role], prediction, role, subset,
                                                           representation, "selected_pipeline"))
    metrics = pd.DataFrame(metric_rows)
    contrasts = {}
    for (cohort, subset, model), block in metrics[metrics.representation != "benchmark"].groupby(
            ["cohort", "subset", "model"], sort=False):
        rows = block.set_index("representation")
        value = None
        if (set(rows.index) == set(REPRESENTATIONS)
                and (rows["status"] == "complete").all()):
            value = float(rows.loc["date_control", "mae"] - rows.loc["raw_A", "mae"])
        contrasts[(cohort, subset, model)] = value
    metrics["date_minus_raw_mae"] = [contrasts.get((row.cohort, row.subset, row.model))
                                      for row in metrics.itertuples()]
    return metrics, pd.concat(prediction_blocks, ignore_index=True)


def prediction_frame(frame, prediction, role, subset, representation, model):
    if len(prediction) != len(frame):
        raise ValueError("External prediction count differs from evaluation people")
    result = pd.DataFrame({"canonical_id": frame["canonical_id"].to_numpy(),
                           "rating": frame["rating"].to_numpy(float), "prediction": prediction})
    result["cohort"], result["subset"] = role, subset
    result["representation"], result["model"] = representation, model
    result["absolute_error"] = np.abs(result["rating"] - result["prediction"])
    return result


def select_predictions(predictions, subset, representation):
    return predictions[(predictions["cohort"] == "primary_new")
                       & (predictions["subset"] == subset)
                       & (predictions["representation"] == representation)
                       & (predictions["model"] == "selected_pipeline")].copy()


def inferential_summaries(predictions: pd.DataFrame, config: dict):
    settings = config["primary"]["interval"]
    kwargs = {key: settings[key] for key in ("n_resamples", "random_state", "confidence_level")}
    date = select_predictions(predictions, "random_1000", "date_control")
    raw = select_predictions(predictions, "random_1000", "raw_A")
    paired = paired_loss_difference(date, raw)
    primary = {"cohort": "primary_new", "training_subset": "random_1000",
               "contrast": "MAE(date_control) - MAE(raw_A)", "positive_favors": "raw_A",
               **bootstrap_mean(paired["difference"], **kwargs),
               "raw_metrics": regression_metrics(raw["rating"], raw["prediction"]),
               "date_control_metrics": regression_metrics(date["rating"], date["prediction"]),
               "minimum_meaningful_gain_elo": config["primary"]["minimum_meaningful_gain_elo"],
               "p_value": None, "equivalence_claim_allowed": False,
               "interval_scope": "conditions on fixed fitted models; not all development/training-subset uncertainty"}
    changes = []
    for representation in REPRESENTATIONS:
        for small, large in ((500, 800), (800, 1000), (500, 1000)):
            difference = paired_loss_difference(
                select_predictions(predictions, f"random_{small}", representation),
                select_predictions(predictions, f"random_{large}", representation))
            changes.append({"cohort": "primary_new", "representation": representation,
                            "smaller_n": small, "larger_n": large,
                            "positive_favors": "larger training subset",
                            "formal_significance_claim": False,
                            **bootstrap_mean(difference["difference"], **kwargs)})
    return primary, paired, pd.DataFrame(changes)


def number(value, decimals=3):
    return "undefined" if value is None or pd.isna(value) else f"{float(value):.{decimals}f}"


def markdown_table(columns, rows):
    return "\n".join(["| " + " | ".join(columns) + " |",
                       "| " + " | ".join(["---"] * len(columns)) + " |"]
                      + ["| " + " | ".join(str(value) for value in row) + " |" for row in rows])


def cohort_metadata(root: Path) -> dict:
    from model_inputs import load_model_frame

    roles = ("development",) + EXTERNAL_ROLES
    frames = {role: load_model_frame(root, role) for role in roles}
    ids = {role: set(frame["canonical_id"].astype(str)) for role, frame in frames.items()}
    summary = {"cohorts": {role: {"n": len(frame), "minimum_elo": float(frame["rating"].min()),
                                     "maximum_elo": float(frame["rating"].max())}
                            for role, frame in frames.items()},
               "overlaps": []}
    for index, first in enumerate(roles):
        for second in roles[index + 1:]:
            summary["overlaps"].append({"first": first, "second": second,
                                        "shared_people": len(ids[first] & ids[second])})
    if ids["development"] & ids["primary_new"]:
        raise ValueError("Development and primary NEW overlap at evaluation")
    return summary


def create_report(metrics, development, primary, comparisons, records, provenance, cohorts) -> str:
    selected = metrics[(metrics["cohort"] == "primary_new") & (metrics["model"] == "selected_pipeline")]
    medians = metrics[(metrics["cohort"] == "primary_new") & (metrics["model"] == "training_median")]
    selected_rows = []
    for subset in ALL_SUBSETS:
        raw = selected[(selected.subset == subset) & (selected.representation == "raw_A")].iloc[0]
        date = selected[(selected.subset == subset) & (selected.representation == "date_control")].iloc[0]
        median = medians[medians.subset == subset].iloc[0]
        selected_rows.append([subset, int(raw.train_n), raw.selected_family, date.selected_family,
                              number(raw.mae), number(date.mae), number(median.mae), number(date.mae - raw.mae)])
    family_rows = []
    for subset in ALL_SUBSETS:
        block = metrics[(metrics.cohort == "primary_new") & (metrics.subset == subset)]
        for family in records["final_random_1000"]["manifest"]["representations"]["raw_A"]["family_models"]:
            raw = block[(block.representation == "raw_A") & (block.model == family)].iloc[0]
            date = block[(block.representation == "date_control") & (block.model == family)].iloc[0]
            family_rows.append([subset, family, number(raw.mae), number(date.mae),
                                number(date.mae - raw.mae), number(raw.rmse), number(date.rmse), raw.status, date.status])
    supplementary_rows = []
    for role in ("supplementary_full", "legacy_full"):
        for subset in ALL_SUBSETS:
            block = metrics[(metrics.cohort == role) & (metrics.subset == subset)]
            raw = block[(block.representation == "raw_A") & (block.model == "selected_pipeline")].iloc[0]
            date = block[(block.representation == "date_control") & (block.model == "selected_pipeline")].iloc[0]
            median = block[(block.representation == "benchmark") & (block.model == "training_median")].iloc[0]
            supplementary_rows.append([role, subset, int(raw.n), number(raw.mae), number(date.mae),
                                        number(date.mae - raw.mae), number(median.mae)])
    dev_rows = [[int(row.train_n), row.representation, number(row.mae), number(row.rmse), number(row.spearman)]
                for row in development.itertuples()]
    warning_total = sum(int(item["manifest"].get("warning_count", 0)) for item in records.values())
    invalid_total = sum(int(item["manifest"].get("invalid_candidate_count", 0)) for item in records.values())
    return f"""# Chess single-player A v2: complete fixed-model evaluation

Primary comparison: Random1000 trained on January-2013, evaluated on the rebuilt
{primary['n']}-person January-2023 NEW cohort. Lower MAE is better.

**Primary delta MAE (date control minus raw six symbols): {primary['estimate']:.3f} Elo,
95% paired bootstrap interval [{primary['ci_low']:.3f}, {primary['ci_high']:.3f}].**
Positive delta favors raw A. The interval conditions on these fixed fitted models.
No minimum meaningful gain was specified, and no equivalence or no-association
claim follows from a zero-crossing interval. No primary p-value is reported.

## Selected procedures and training-size comparison

Selection uses only 2013 inner cross-validation. External scores do not choose a
family, size, seed, or ranked threshold. All fixed sizes are shown together.

{markdown_table(['Training subset', 'Actual train n', 'Raw selected family', 'Date selected family', 'Raw MAE', 'Date MAE', 'Median MAE', 'Date minus raw MAE'], selected_rows)}

Random500/800/1000 are one fixed nested draw from the same population. Ranked
subsets include boundary ties and jointly change training size and Elo range.
Ranked1000 reuses the identical fitted Random1000 models, retaining both labels.

{markdown_table(['Representation', 'Training n contrast', 'MAE improvement from more people', '95% descriptive interval'], [[row.representation, f'{row.smaller_n} to {row.larger_n}', number(row.estimate), f'[{number(row.ci_low)}, {number(row.ci_high)}]'] for row in comparisons.itertuples()])}

These secondary intervals have no simultaneous-coverage or separate formal
significance claim and do not cover all variation over possible training draws.

## All five families on the common NEW cohort

Every family was independently tuned using the corresponding 2013 training
subset. Invalid families, if any, remain explicitly identified.

{markdown_table(['Training subset', 'Family', 'Raw MAE', 'Date MAE', 'Date minus raw MAE', 'Raw RMSE', 'Date RMSE', 'Raw status', 'Date status'], family_rows)}

Complete RMSE and Spearman correlations for every model/cohort are in
`external_metrics.csv`; constant-prediction correlations are undefined.

## Internal development

{markdown_table(['People used to train each outer model', 'Representation', 'Pooled held-out MAE', 'RMSE', 'Spearman'], dev_rows)}

Each row aggregates five fixed outer held-out folds with one prediction per
2013 person. The 800-training-size row is the primary nested-CV development
estimate. There is no internal-CV estimate for a model trained on 1,000 people.

## Supplementary, overlapping evaluation cohorts

{markdown_table(['Cohort', 'Training subset', 'Evaluation n', 'Raw selected MAE', 'Date selected MAE', 'Date minus raw MAE', 'Median MAE'], supplementary_rows)}

Expanded FULL and legacy FULL include repeated development people and overlap
NEW. They are supplementary diagnostics, not independent replications. Their
individual-family results are also included in `external_metrics.csv`.

{markdown_table(['Cohort', 'People', 'Minimum snapshot Elo', 'Maximum snapshot Elo'], [[name, value['n'], number(value['minimum_elo'], 0), number(value['maximum_elo'], 0)] for name, value in cohorts['cohorts'].items()])}

{markdown_table(['First cohort', 'Second cohort', 'Shared people'], [[item['first'], item['second'], item['shared_people']] for item in cohorts['overlaps']])}

## Audit and interpretation limits

- All 20 training tasks and every model/checkpoint hash were sealed before
  external evaluation, then reverified before any new external predictions or
  scores were calculated.
- Finite convergence-limit fits are retained as specified. Warning records:
  {warning_total}; invalid inner-search candidates: {invalid_total}. Detailed logs
  and selected configurations are in the sealed training artifacts.
- Raw A versus the age/season date control compares two representations. It
  does not establish incremental information conditional on an unrestricted
  date predictor, nor a causal astrological mechanism.
- Only active, exact-DOB, confirmed-northern male players meeting the fixed
  ranking and exclusion rules are represented. NEW has a different rating
  range after excluding the enlarged development pool. General-population
  talent, professional selection, and other populations are not evaluated.
- Historical 2013/2023 BaZi and Elo outcomes were previously explored. The
  acquisition amendment corrected the extra NEW1000 target to NEW500 before
  predictive fitting. This is not a newly blind preregistration.
- A finite model menu cannot prove the absence of every possible relationship.
  Test-person bootstrap uncertainty excludes all training/process uncertainty.

## Provenance

{markdown_table(['Item', 'SHA256'], [[key, value] for key, value in provenance.items() if key.endswith('sha256')])}

Predictions are saved in `external_predictions.csv.gz`; primary paired losses
are separately available in `primary_paired_losses.csv`. No model or parameter
was changed in response to these external results.
"""


def evaluate_models(root: Path, runs_dir: Path, seal_file: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "evaluation_manifest.json", {"status": "evaluation_incomplete"})
    # Every model and all task identities are checked before the first external load.
    config, records = verify_seal(root, runs_dir, seal_file)
    development, development_predictions = development_scores(records, root)
    metrics, predictions = external_scores(records, root, config)
    primary, paired, comparisons = inferential_summaries(predictions, config)
    cohorts = cohort_metadata(root)
    metrics.to_csv(output_dir / "external_metrics.csv", index=False)
    predictions.to_csv(output_dir / "external_predictions.csv.gz", index=False,
                       compression={"method": "gzip", "mtime": 0})
    paired.to_csv(output_dir / "primary_paired_losses.csv", index=False)
    comparisons.to_csv(output_dir / "size_comparisons.csv", index=False)
    development.to_csv(output_dir / "development_metrics.csv", index=False)
    development_predictions.to_csv(output_dir / "development_predictions.csv", index=False)
    write_json(output_dir / "primary_result.json", primary)
    write_json(output_dir / "cohort_summary.json", cohorts)
    provenance = {**reference_hashes(root), "fitted_models_seal_sha256": digest(seal_file),
                  "evaluation_script_sha256": digest(Path(__file__)),
                  "execution_commit": os.environ.get("GITHUB_SHA")}
    report = create_report(metrics, development, primary, comparisons, records, provenance, cohorts)
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    from plot_model_results import plot_results
    plot_results(metrics, development, output_dir)
    result = {"status": "complete_fixed_external_evaluation", **provenance,
              "completed_at_utc": datetime.now(timezone.utc).isoformat(),
              "primary": primary, "metrics_rows": len(metrics),
              "prediction_rows": len(predictions),
              "all_prespecified_tasks_complete": True, "model_or_grid_changes_after_scoring": False,
              "outputs": [{"path": path.relative_to(output_dir).as_posix(), "sha256": digest(path)}
                          for path in sorted(output_dir.rglob("*"))
                          if path.is_file() and path.name != "evaluation_manifest.json"]}
    write_json(output_dir / "evaluation_manifest.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal", "evaluate"))
    parser.add_argument("--repo-root", type=Path, default=HERE.parents[1])
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seal-file", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    runs = args.runs_dir.resolve()
    output = args.output_dir.resolve()
    if args.command == "seal":
        result = seal_models(root, runs, output)
        print(json.dumps({"status": result["status"], "task_count": result["task_count"]}))
    else:
        if args.seal_file is None:
            parser.error("evaluate requires --seal-file")
        result = evaluate_models(root, runs, args.seal_file.resolve(), output)
        print(json.dumps({"status": result["status"], "primary": result["primary"]}, indent=2))


if __name__ == "__main__":
    main()
