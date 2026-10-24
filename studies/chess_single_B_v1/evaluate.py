"""Jointly score the sealed B1 models; the 2023 cohort is previously seen.

No model or hyperparameter is selected here. The complete development outputs
and final model bytes must pass the seal before any external frame is loaded
or any model is deserialized.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import KFold
from threadpoolctl import threadpool_limits

STUDY = Path("studies/chess_single_B_v1")
REPS = ("b1", "raw", "date")
MODELS = REPS + ("median",)
LABELS = {"b1": "B1 structured Ridge", "raw": "Raw Ridge", "date": "Date Ridge", "median": "Training median"}
EXPECTED_TASKS = {*(f"outer-{i}" for i in range(5)), "final"}
OUTER_SEED = 20261021


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_csv(path):
    return pd.read_csv(path, dtype={"canonical_id": str}, float_precision="round_trip")


def score(actual, prediction):
    actual, prediction = np.asarray(actual, float), np.asarray(prediction, float)
    if actual.ndim != 1 or actual.shape != prediction.shape or len(actual) == 0:
        raise ValueError("Predictions and targets must be aligned nonempty vectors")
    if not np.isfinite(actual).all() or not np.isfinite(prediction).all():
        raise ValueError("Nonfinite target or prediction")
    error = actual - prediction
    rho = None
    if len(actual) > 1 and np.ptp(actual) > 0 and np.ptp(prediction) > 0:
        rho = float(spearmanr(actual, prediction).statistic)
        if not np.isfinite(rho):
            raise ValueError("Nonfinite rank correlation for varying inputs")
    return {"n": len(actual), "mae": float(np.mean(np.abs(error))),
            "rmse": float(np.sqrt(np.mean(error ** 2))), "spearman": rho}


def metrics_table(predictions, cohort):
    rows = [{"cohort": cohort, "model": name,
             **score(predictions.rating, predictions[f"prediction_{name}"])} for name in MODELS]
    return pd.DataFrame(rows)


def paired_differences(predictions, cohort):
    y = predictions.rating.to_numpy(float)
    b = np.abs(y - predictions.prediction_b1.to_numpy(float))
    return [{"cohort": cohort, "n": len(y), "comparison": f"b1_minus_{other}",
             "mean_absolute_error_difference": float(np.mean(b - np.abs(y - predictions[f"prediction_{other}"].to_numpy(float)))),
             "negative_favors": "b1", "formal_inference_claim": False}
            for other in ("raw", "date", "median")]


def load_tasks(inputs, seal):
    if set(seal.get("tasks", {})) != EXPECTED_TASKS:
        raise ValueError("Sealed inputs must contain exactly five outer tasks and final")
    result = {}
    for task, entry in seal["tasks"].items():
        folder = (inputs / entry["directory"]).resolve()
        if not folder.is_relative_to(inputs.resolve()):
            raise ValueError("Unsafe task directory")
        path = folder / "task_manifest.json"
        if digest(path) != entry["manifest_sha256"]:
            raise ValueError("Task manifest differs from sealed bytes")
        manifest = read_json(path)
        if manifest.get("status") != "complete" or manifest.get("task") != task:
            raise ValueError("Task status or identity differs from seal")
        result[task] = (folder, manifest)
    return result


def aggregate_outer(development, tasks):
    development = development.sort_values("canonical_id", kind="stable").reset_index(drop=True)
    if len(development) != 1000 or development.canonical_id.nunique() != 1000:
        raise ValueError("Development must contain exactly 1000 unique people")
    parts = []
    split = KFold(n_splits=5, shuffle=True, random_state=OUTER_SEED)
    for fold, (train, held) in enumerate(split.split(development)):
        folder, manifest = tasks[f"outer-{fold}"]
        table = read_csv(folder / "outer_predictions.csv")
        required = {"canonical_id", "rating", "outer_fold", *(f"prediction_{m}" for m in MODELS)}
        if not required <= set(table) or len(table) != 200 or table.canonical_id.nunique() != 200:
            raise ValueError("Outer predictions have duplicate, missing or malformed rows")
        expected = development.iloc[held].set_index("canonical_id")
        if set(table.canonical_id) != set(expected.index) or set(table.outer_fold) != {fold}:
            raise ValueError("Outer predictions do not match the fixed held-out IDs")
        aligned = table.set_index("canonical_id").loc[expected.index].reset_index()
        if not np.array_equal(aligned.rating.to_numpy(), expected.rating.to_numpy()):
            raise ValueError("Outer ratings differ from frozen development targets")
        median = float(np.median(development.iloc[train].rating.to_numpy(float)))
        if manifest.get("train_n") != 800 or manifest.get("median_elo") != median:
            raise ValueError("Outer training size or median differs from its training fold")
        if not np.allclose(aligned.prediction_median.to_numpy(float), median, rtol=0, atol=1e-10):
            raise ValueError("Outer benchmark was not fitted on the training fold")
        for model in MODELS:
            score(aligned.rating, aligned[f"prediction_{model}"])
        parts.append(aligned)
    pooled = pd.concat(parts, ignore_index=True).sort_values("canonical_id", kind="stable").reset_index(drop=True)
    if len(pooled) != 1000 or pooled.canonical_id.nunique() != 1000:
        raise ValueError("Pooled outer predictions must cover every person exactly once")
    return pooled


def selection_tables(tasks):
    selections, stats = [], []
    for task in [*(f"outer-{i}" for i in range(5)), "final"]:
        _, manifest = tasks[task]
        for rep in REPS:
            entry = manifest["representations"][rep]
            candidate = entry["candidate"]
            row = {"task": task, "representation": rep, "candidate_id": entry["candidate_id"],
                   "alpha": candidate["alpha"], "inner_mae": entry["inner_mae"]}
            if rep == "b1":
                middle, ratio, month = (float(candidate[k]) for k in ("middle", "residual_ratio", "month"))
                residual = middle * ratio
                if not (1 > middle > residual > 0 and month >= 1):
                    raise ValueError("Selected hidden-qi/month parameters violate constraints")
                row.update(main=1., middle=middle, residual_ratio=ratio, residual=residual, month=month,
                    middle_at_grid_boundary=middle in (.25, .75),
                    residual_ratio_at_grid_boundary=ratio in (.25, .75), month_at_grid_boundary=month in (1., 3.))
            selections.append(row)
            values = dict(entry["search_stats"])
            expected = 180 if rep == "b1" else 5
            if values.get("candidates") != expected:
                raise ValueError("Candidate coverage differs from the fixed search")
            if values.get("valid_candidates", 0) + values.get("invalid_candidates", 0) != expected:
                raise ValueError("Candidate status counts do not cover the fixed search")
            stats.append({"task": task, "representation": rep, **values,
                          "refit_warning_records": len(entry["refit_diagnostics"].get("warnings", [])),
                          "refit_convergence_warnings": entry["refit_diagnostics"].get("convergence_warnings", 0)})
    return pd.DataFrame(selections), pd.DataFrame(stats)


def external_predictions(root, tasks, development, load_frame):
    # Called only after verify_seal, load_tasks, and development validation.
    external = load_frame(root, "primary_new").sort_values("canonical_id", kind="stable").reset_index(drop=True)
    if len(external) != 500 or external.canonical_id.nunique() != 500:
        raise ValueError("Previously seen 2023 NEW must contain exactly 500 unique people")
    if set(external.canonical_id) & set(development.canonical_id):
        raise ValueError("Development and 2023 NEW identities overlap")
    folder, manifest = tasks["final"]
    median = float(np.median(development.rating.to_numpy(float)))
    if manifest.get("train_n") != 1000 or manifest.get("median_elo") != median:
        raise ValueError("Final training size or median differs from full development")
    result = external[["canonical_id", "rating"]].copy()
    for rep in REPS:
        entry = manifest["representations"][rep]
        path = (folder / entry["model_file"]).resolve()
        if not path.is_relative_to(folder.resolve()) or digest(path) != entry["model_sha256"]:
            raise ValueError("Final model bytes differ from the sealed manifest")
        model = joblib.load(path)
        with threadpool_limits(limits=1):
            prediction = np.asarray(model.predict(external), float)
        score(external.rating, prediction)
        result[f"prediction_{rep}"] = prediction
    result["prediction_median"] = median
    return result


def make_plot(metrics, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = ("#377eb8", "#777777", "#e69f00", "#009e73")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), constrained_layout=True)
    for axis, cohort, title in zip(axes, ("development_nested_cv", "previously_seen_2023_new"),
            ("2013 development: nested CV", "2023 NEW: previously seen cohort")):
        block = metrics[metrics.cohort == cohort].set_index("model").loc[list(MODELS)]
        bars = axis.bar(np.arange(4), block.mae, color=colors, width=.68)
        axis.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
        axis.set_xticks(np.arange(4), ("B1", "Raw", "Date", "Median"))
        axis.set_ylabel("Mean absolute error (Elo)")
        axis.set_title(title, fontsize=11)
        axis.set_ylim(0, float(block.mae.max()) * 1.18)
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)
    fig.suptitle("B1 constrained feature comparison — exploratory", fontsize=13)
    fig.savefig(output / "mae_comparison.png", dpi=180)
    fig.savefig(output / "mae_comparison.svg")
    plt.close(fig)


def markdown_table(headers, rows):
    def text(value):
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "—"
        if isinstance(value, (float, np.floating)):
            return f"{value:.3f}"
        return str(value)
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                       *("| " + " | ".join(text(v) for v in row) + " |" for row in rows)])


def report_text(summary, metrics, selections, stats, differences, has_plots):
    metric_rows = []
    for row in metrics.itertuples():
        cohort = "2013 nested CV" if row.cohort == "development_nested_cv" else "2023 NEW (seen)"
        metric_rows.append((cohort, LABELS[row.model], row.n, row.mae, row.rmse, row.spearman))
    b = selections[selections.representation == "b1"]
    weight_rows = [(r.task, r.alpha, r.main, r.middle, r.residual, r.month, r.inner_mae) for r in b.itertuples()]
    diff_rows = [(r["cohort"], r["comparison"], r["mean_absolute_error_difference"]) for r in differences]
    final = b[b.task == "final"].iloc[0]
    invalid = int(stats.invalid_candidates.sum())
    warnings = int(stats.warning_records.sum())
    boundary_count = int((b.middle_at_grid_boundary.astype(bool) | b.residual_ratio_at_grid_boundary.astype(bool) | b.month_at_grid_boundary.astype(bool)).sum())
    return f"""# B1 constrained five-phase features: joint exploratory report

This is a post-A exploratory comparison. Both the 2013 development outcomes
and the 2023 NEW outcomes had already been examined. The 2023 table is not a
new blind test. Every B1 structural parameter and Ridge alpha was selected
using only 2013 inner folds; every final model was sealed before 2023 loading
and scoring. No model or parameter was selected from the tables below.

## Prediction errors

{markdown_table(("Cohort", "Model", "People", "MAE", "RMSE", "Spearman"), metric_rows)}

2013 numbers pool one outer held-out prediction for each of 1,000 people;
each outer training set contains 800. The final models are refitted on all
1,000 development people and scored on the same previously seen 500-person
2023 NEW cohort. Training medians are fitted separately within each outer
training fold, or on all development data for 2023. A constant prediction has
undefined Spearman correlation, shown as a dash. The pooled outer medians can
vary between folds, so their pooled correlation need not be undefined.

{markdown_table(("Cohort", "Comparison", "Paired mean absolute-error difference"), diff_rows)}

Differences are B1 minus comparator on the same people: **negative favors B1**.
They are descriptive, with no new p-value or formal confidence claim. These
raw/date comparators use Ridge only; the raw comparator is not the earlier
A1 procedure that selected among five model families.

## Selected constrained weights

{markdown_table(("Fit", "Ridge alpha", "Main", "Middle", "Residual", "Month branch", "Selected inner MAE"), weight_rows)}

Main qi is fixed at 1 to set a ratio scale. Middle is selected from
{{0.25, 0.5, 0.75}}, residual is middle times a ratio in {{0.25, 0.5, 0.75}},
and the month-branch multiplier is selected from {{1, 1.5, 2, 3}}. Thus every
candidate satisfies main > middle > residual > 0 and month >= 1. The final
selection is middle {final.middle:g}, residual {final.residual:g}, month
{final.month:g}. Across the five outer fits plus final, {boundary_count}/6
selections touch at least one structural grid boundary. Boundary choices and
variation across these dependent fits do not identify an optimum beyond the
grid or establish a reliable physical strength estimate. The grid is not
expanded in response to these results.

## What was tested

All models use the fixed Random1000 sample, the original shuffled five outer
folds and four inner folds, fold-local input and target standardization, and
the same five Ridge alpha values. B1 searches 36 structural settings times
five alphas (180 candidates); raw and date Ridge each search five candidates.
Search budgets are unequal. There are {invalid} invalid candidate searches
and {warnings} recorded warnings across inner fitting entries; complete
candidate, fold, failure and refit records are preserved. Each representation
has its own inner selection; selection is repeated inside every outer fold.

B1 retains the 66 position-specific raw one-hot columns and adds 20 columns:
five pooled phase fractions, five fractions relative to the day-master phase,
five generating-pair products and five controlling-pair products. Visible
stems each contribute one unit. A branch mixes only its present hidden stems,
normalizing their role weights to one unit; only the month branch is then
multiplied by the month parameter. Pooled masses are divided by 5 + month.
These operations occur before the training-fold StandardScaler, so the
weights affect the mixture rather than being canceled as independent-column
scales. The paired products are defined features, not measured causal flows,
and no auspicious/adverse Elo sign is imposed.

The project’s versioned hidden-stem priority table is used, including 巳 =
丙、戊、庚. List slots are assigned main, middle, residual; absent slots are
zero. For 午 = 丁、己 and 亥 = 壬、甲, the second slot receives middle weight.
This is an explicit operational definition, not a claim that all traditional
schools agree on qi labels or on the ordering in another calendar library.

For fixed structural weights, these added features are expressible within
A1’s full pairwise raw-feature space. B1 therefore tests parameter sharing
and regularization, not new birth information or additional expressivity.
Keeping raw columns also lets the readout compensate through raw coefficients:
the ordering constraints apply to constructed input forces, not to final Elo
marginal effects. Learned weights cannot be read as true traditional forces.
No birth-hour information, branch clashes, combinations or additional rules
were added. Better performance here would require confirmation on a sample
not used for model development; worse performance does not rule out all BaZi
functions or establish that a missing hour must matter.

{('![MAE comparison](mae_comparison.png)' if has_plots else '')}

## Reproducibility

Source-lock SHA256: `{summary['source_lock_sha256']}`.
Fitted-model seal SHA256: `{summary['fitted_models_lock_sha256']}`.
The machine-readable summary and checkpoint bundle record all six complete
training tasks, selected candidates, final model hashes and prediction hashes.
The original A1 source, data and results are unchanged.
"""


def make_bundle(inputs, output, seal):
    paths = {"fitted_models_lock.json", *seal["files"]}
    target = output / "training_checkpoint_bundle.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative in sorted(paths):
            path = (inputs / relative).resolve()
            if not path.is_relative_to(inputs.resolve()) or not path.is_file():
                raise ValueError("Unsafe checkpoint file")
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    if target.stat().st_size >= 50 * 1024 * 1024:
        raise ValueError("Checkpoint bundle exceeds 50 MiB repository budget")
    value = {"file": target.name, "files": len(paths), "bytes": target.stat().st_size, "sha256": digest(target)}
    (output / "training_checkpoint_bundle.json").write_text(json.dumps(value, indent=2) + "\n")
    return value


def run_evaluation(root, inputs, output, *, make_plots=True):
    root, inputs, output = map(lambda p: Path(p).resolve(), (root, inputs, output))
    if output.is_relative_to(inputs) or inputs.is_relative_to(output):
        raise ValueError("Evaluation output and sealed inputs must be separate directories")
    # Do not move this check after external frame loading or model deserialization.
    import train as training
    seal = training.verify_seal(root, inputs)
    tasks = load_tasks(inputs, seal)
    from model_inputs import load_model_frame
    development = load_model_frame(root, "development")
    pooled = aggregate_outer(development, tasks)
    selections, stats = selection_tables(tasks)
    external = external_predictions(root, tasks, development, load_model_frame)
    metrics = pd.concat([metrics_table(pooled, "development_nested_cv"),
                         metrics_table(external, "previously_seen_2023_new")], ignore_index=True)
    differences = [*paired_differences(pooled, "development_nested_cv"),
                   *paired_differences(external, "previously_seen_2023_new")]
    output.mkdir(parents=True, exist_ok=True)
    tables = {"nested_cv_predictions.csv": pooled, "exploratory_2023_new_predictions.csv": external,
              "metrics.csv": metrics, "selected_parameters.csv": selections, "search_statistics.csv": stats,
              "paired_mae_differences.csv": pd.DataFrame(differences)}
    for name, frame in tables.items():
        frame.to_csv(output / name, index=False)
    bundle = make_bundle(inputs, output, seal)
    if make_plots:
        make_plot(metrics, output)
    summary = {"protocol_id": "chess-single-B-v1", "status": "complete_exploratory_joint_evaluation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "source_commit": os.environ.get("GITHUB_SHA"),
        "source_lock_sha256": seal["source_lock_sha256"], "fitted_models_lock_sha256": digest(inputs / "fitted_models_lock.json"),
        "external_previously_seen": True, "new_blind_test_claim": False, "formal_inference_claim": False,
        "all_final_models_sealed_before_external_loading": True, "task_count": len(tasks),
        "metrics": json.loads(metrics.to_json(orient="records")), "paired_mae_differences": differences,
        "checkpoint_bundle": bundle}
    (output / "REPORT.md").write_text(report_text(summary, metrics, selections, stats, differences, make_plots), encoding="utf-8")
    summary["outputs"] = [{"path": p.name, "sha256": digest(p)} for p in sorted(output.iterdir())
                          if p.is_file() and p.name != "evaluation_summary.json"]
    (output / "evaluation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--inputs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo_root / "studies/chess_single_A_v2"))
    result = run_evaluation(args.repo_root, args.inputs_dir, args.output_dir)
    print(json.dumps({"status": result["status"], "task_count": result["task_count"], "metrics": result["metrics"]}, allow_nan=False))


if __name__ == "__main__":
    main()
