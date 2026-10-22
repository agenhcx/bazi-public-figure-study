"""Validate and jointly report all fixed post-result A1 diagnostics."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

REL = Path("studies/chess_single_A_v2/diagnostics_v1")
REPS = ("raw_A", "date_control")
SIGNALS = ("null", "additive", "pairwise", "third_order")
MODELS = ("training_median", "ridge", "pairwise_ridge", "rbf_kernel_ridge",
          "shallow_gradient_boosting", "small_mlp")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def read_csv(path):
    # The literal signal name "null" is a real category, not a missing value.
    return pd.read_csv(path, dtype={"canonical_id": str}, float_precision="round_trip",
                       keep_default_na=False, na_values=[""])


def score(y, prediction):
    y, prediction = np.asarray(y, float), np.asarray(prediction, float)
    if len(y) == 0 or y.shape != prediction.shape or not np.isfinite([y, prediction]).all():
        raise ValueError("Nonfinite or misaligned diagnostic predictions")
    return {"n": len(y), "mae": float(np.mean(np.abs(y - prediction))),
            "rmse": float(np.sqrt(np.mean((y - prediction) ** 2)))}


def verify_outputs(path, manifest):
    entries = manifest.get("outputs", manifest.get("files"))
    if not entries:
        raise ValueError(f"Worker has no output checksum ledger: {path}")
    seen = set()
    for entry in entries:
        relative = entry["path"]
        target = (path.parent / relative).resolve()
        if target in seen or not target.is_relative_to(path.parent.resolve()):
            raise ValueError("Unsafe or repeated worker output path")
        seen.add(target)
        if digest(target) != entry["sha256"]:
            raise ValueError(f"Worker output checksum mismatch: {target}")


def locate_workers(inputs):
    audits = list(inputs.rglob("existing_audit_summary.json"))
    mlps = list(inputs.rglob("mlp_budget_summary.json"))
    controls = []
    for path in inputs.rglob("manifest.json"):
        value = read_json(path)
        if value.get("diagnostic") == "A1_synthetic_recovery_v1":
            controls.append(path)
    if len(audits) != 1 or len(mlps) != 5 or len(controls) != 4:
        raise ValueError("Need exactly ten workers: one audit, five MLP folds, four controls")
    workers = [(p, read_json(p)) for p in [*audits, *mlps, *controls]]
    for path, value in workers:
        expected = "complete_read_only_A1_development_audit" if path in audits else "complete"
        if value.get("status") != expected:
            raise ValueError(f"Incomplete worker: {path}")
        if value.get("external_data_loaded", value.get("external_data_or_scores_loaded")) is not False:
            raise ValueError("Worker external-data scope is missing or inconsistent")
        verify_outputs(path, value)
    if {read_json(p).get("fold") for p in mlps} != set(range(5)):
        raise ValueError("MLP workers do not cover each original fold exactly once")
    if {read_json(p).get("signal") for p in controls} != set(SIGNALS):
        raise ValueError("Synthetic workers do not cover each fixed signal exactly once")
    return audits[0], sorted(mlps), sorted(controls), workers


def close(actual, expected, label):
    if not np.isfinite([actual, expected]).all() or not np.isclose(actual, expected, rtol=1e-11, atol=1e-9):
        raise ValueError(f"Recomputed diagnostic metric differs: {label}")


def aggregate_mlp(paths, audited_outer):
    reference = audited_outer[audited_outer.train_n == 800].copy()
    if len(reference) != 1000 or reference.canonical_id.nunique() != 1000:
        raise ValueError("Audited development reference must contain 1000 unique IDs")
    predictions, training, metrics, seeds = [], [], [], []
    for path in paths:
        manifest = read_json(path)
        fold = manifest["fold"]
        held = read_csv(path.parent / "mlp_budget_predictions.csv")
        train = read_csv(path.parent / "mlp_budget_training_predictions.csv")
        table = read_csv(path.parent / "mlp_budget_metrics.csv")
        seed_rows = read_json(path.parent / "mlp_seed_diagnostics.json")
        if len(table) != 4 or set(zip(table.representation, table.budget)) != {
                (rep, budget) for rep in REPS for budget in ("original", "extended")}:
            raise ValueError("Each MLP fold needs all four fixed representation/budget rows")
        if len(seed_rows) != 12:
            raise ValueError("Each MLP fold needs all twelve seed fits")
        expected = reference[reference.outer_fold == fold].set_index("canonical_id")
        if len(expected) != 200:
            raise ValueError("Audited held-out fold is not 200 people")
        for rep in REPS:
            block = held[held.representation == rep]
            train_block = train[train.representation == rep]
            if len(block) != 200 or block.canonical_id.nunique() != 200 or set(block.canonical_id) != set(expected.index):
                raise ValueError("Duplicate, missing or unexpected MLP held-out IDs")
            if set(block.fold) != {fold} or set(train_block.fold) != {fold}:
                raise ValueError("MLP prediction fold labels differ")
            if len(train_block) != 800 or train_block.canonical_id.nunique() != 800:
                raise ValueError("MLP training predictions need 800 distinct IDs")
            if set(train_block.canonical_id) & set(block.canonical_id) or set(train_block.canonical_id) | set(block.canonical_id) != set(reference.canonical_id):
                raise ValueError("MLP training/held-out identities do not partition development")
            aligned = block.set_index("canonical_id").loc[expected.index]
            if not np.array_equal(aligned.rating.to_numpy(), expected.rating.to_numpy()):
                raise ValueError("MLP held-out targets differ from audited development")
            train_reference = reference.set_index("canonical_id").loc[train_block.canonical_id]
            if not np.array_equal(train_block.rating.to_numpy(), train_reference.rating.to_numpy()):
                raise ValueError("MLP training targets differ from audited development")
            if not np.allclose(aligned.pred_median, expected.pred_median, rtol=0, atol=1e-10):
                raise ValueError("MLP fold median differs from original fold median")
            for budget in ("original", "extended"):
                row = table[(table.representation == rep) & (table.budget == budget)].iloc[0]
                for name, values in (("heldout", block), ("train", train_block)):
                    computed = score(values.rating, values[f"pred_{budget}"])
                    for metric in ("mae", "rmse"):
                        close(computed[metric], float(row[f"{name}_{metric}"]), f"fold{fold}/{rep}/{budget}/{name}/{metric}")
        if held.duplicated(["canonical_id", "representation"]).any():
            raise ValueError("Duplicate MLP held-out prediction")
        predictions.append(held); training.append(train); metrics.append(table); seeds.extend(seed_rows)
    predictions, training, metrics = map(lambda parts: pd.concat(parts, ignore_index=True), (predictions, training, metrics))
    seeds = pd.DataFrame(seeds)
    pooled, differences = [], []
    for rep in REPS:
        held, train = predictions[predictions.representation == rep], training[training.representation == rep]
        if len(held) != 1000 or held.canonical_id.nunique() != 1000:
            raise ValueError("Pooled MLP predictions must cover 1000 distinct people per representation")
        values = {}
        for budget in ("original", "extended", "median"):
            row = {"representation": rep, "budget": budget,
                   **score(held.rating, held[f"pred_{budget}"])}
            train_score = score(train.rating, train[f"pred_{budget}"])
            row.update(training_prediction_rows=len(train), train_mae=train_score["mae"], train_rmse=train_score["rmse"])
            if budget != "median":
                block = seeds[(seeds.representation == rep) & (seeds.budget == budget)]
                if len(block) != 15 or block.duplicated(["fold", "seed"]).any():
                    raise ValueError("MLP pooled seed records incomplete or duplicated")
                row.update(seed_fits=15, seed_fits_with_convergence_warning=int((block.convergence_warning_count > 0).sum()),
                           mean_seed_loss=float(block.loss.mean()), mean_seed_iterations=float(block.n_iter.mean()))
            pooled.append(row); values[budget] = row
        differences.append({"representation": rep,
            **{f"original_minus_extended_{key}": values["original"][key] - values["extended"][key]
               for key in ("mae", "rmse", "train_mae", "train_rmse", "mean_seed_loss")},
            "positive_favors": "extended", "formal_inference_claim": False})
    return pd.DataFrame(pooled), pd.DataFrame(differences), predictions, metrics


def aggregate_controls(paths):
    tables, diagnostic_counts = [], []
    expected_people = None
    for path in paths:
        manifest = read_json(path)
        signal = manifest["signal"]
        table = read_csv(path.parent / "pooled_metrics.csv")
        predictions = read_csv(path.parent / "synthetic_predictions.csv.gz")
        strengths = (0.0,) if signal == "null" else (0.5, 2.0)
        expected_keys = {(strength, replicate, model) for strength in strengths for replicate in range(2) for model in MODELS}
        if len(table) != len(expected_keys) or set(zip(table.strength, table.replicate, table.model)) != expected_keys or set(table.signal) != {signal}:
            raise ValueError("Synthetic pooled metric coverage differs from fixed design")
        if predictions.duplicated(["scenario_id", "model", "canonical_id"]).any():
            raise ValueError("Duplicate synthetic held-out prediction IDs")
        for row in table.itertuples():
            block = predictions[(predictions.scenario_id == row.scenario_id) & (predictions.model == row.model)]
            reference = predictions[(predictions.scenario_id == row.scenario_id) & (predictions.model == "training_median")]
            if len(reference) != 1000 or reference.canonical_id.nunique() != 1000:
                raise ValueError("Synthetic median reference needs 1000 distinct IDs")
            if expected_people is None:
                expected_people = set(reference.canonical_id)
            if set(reference.canonical_id) != expected_people:
                raise ValueError("Synthetic conditions do not use the same development people")
            median = score(reference.synthetic_target, reference.prediction)
            close(row.median_mae, median["mae"], "synthetic median")
            if row.status == "complete":
                if len(block) != 1000 or set(block.canonical_id) != expected_people:
                    raise ValueError("Complete synthetic model has incomplete ID coverage")
                target = reference.set_index("canonical_id").synthetic_target
                aligned = block.set_index("canonical_id").loc[target.index]
                if not np.array_equal(aligned.synthetic_target.to_numpy(), target.to_numpy()):
                    raise ValueError("Synthetic targets differ by model")
                computed = score(block.synthetic_target, block.prediction)
                for metric in ("mae", "rmse"):
                    close(getattr(row, metric), computed[metric], "synthetic metric")
                close(row.mae_gain, median["mae"] - computed["mae"], "synthetic improvement")
            elif row.status != "invalid_incomplete_folds" or len(block) == 1000:
                raise ValueError("Unrecognized synthetic fit status")
        tables.append(table)
        diagnostic_counts.append({key: manifest[key] for key in ("signal", "fit_attempts", "failed_fit_attempts", "fit_attempts_with_convergence_warning", "warning_records")})
    return pd.concat(tables, ignore_index=True), diagnostic_counts


def markdown(headers, rows):
    def fmt(value):
        if value is None or isinstance(value, float) and not np.isfinite(value): return "—"
        if isinstance(value, (float, np.floating)): return f"{value:.3f}"
        return str(value).replace("|", "/")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |", *["| " + " | ".join(map(fmt, row)) + " |" for row in rows]])


def create_report(audit, models, warnings, pooled, differences, controls, control_counts):
    main = models[models.task == "final_random_1000"]
    audit_rows = []
    for family in MODELS:
        if family == "training_median":
            row = main[main.family == family].iloc[0]
            audit_rows.append([family, row.train_mae, row.inner_oof_mae, row.train_mae, row.inner_oof_mae])
        else:
            a = main[(main.family == family) & (main.representation == "raw_A")].iloc[0]
            d = main[(main.family == family) & (main.representation == "date_control")].iloc[0]
            audit_rows.append([family, a.train_mae, a.inner_oof_mae, d.train_mae, d.inner_oof_mae])
    warning_rows = [[r.representation, r.family, int(r.fit_entries_with_convergence_warning), int(r.fit_entries), r.fraction_fit_entries_with_convergence_warning]
                    for r in warnings[warnings.stage == "inner_search"].itertuples()]
    budget_rows = [[r.representation, r.budget, r.train_mae, r.mae, r.rmse,
                    getattr(r, "seed_fits_with_convergence_warning", None)] for r in pooled.itertuples()]
    changes = [[r.representation, r.original_minus_extended_train_mae, r.original_minus_extended_mae,
                r.original_minus_extended_rmse, r.original_minus_extended_mean_seed_loss] for r in differences.itertuples()]
    control_rows = []
    for signal in SIGNALS:
        for strength in ((0.0,) if signal == "null" else (0.5, 2.0)):
            block = controls[(controls.signal == signal) & (controls.strength == strength)]
            vals = [signal, strength]
            for family in MODELS[1:]:
                pair = block[block.model == family]
                vals.append(float(pair.mae_gain.mean()) if len(pair) == 2 and (pair.status == "complete").all() else None)
            control_rows.append(vals)
    mlp_row = main[(main.representation == "raw_A") & (main.family == "small_mlp")].iloc[0]
    median_row = main[main.family == "training_median"].iloc[0]
    return f"""# A1 training-sufficiency diagnostics: complete joint report

This is a fixed, post-result diagnostic, not a new blind predictive test. It uses
only 2013 development data for interpreted outcomes, fits and predictions. The
2013 and 2023 A1 results were already seen; no 2023 model predictions or scores
were calculated here. The original A1 files and results are unchanged.

The full-1000 raw MLP has training MAE **{mlp_row.train_mae:.3f} Elo** versus its
saved inner-OOF MAE **{mlp_row.inner_oof_mae:.3f}**, while the corresponding
fold-training-median OOF MAE is **{median_row.inner_oof_mae:.3f}**. This is
consistent with fitting training patterns that do not improve held-out
prediction; it does not support attributing every A1 failure solely to too few
optimization iterations. The paired budget and recovery results below further
describe that limitation without selecting a new winning procedure.

## Existing fitted models: training and saved inner OOF errors

{markdown(['Family', 'Raw train MAE', 'Raw inner-OOF MAE', 'Date train MAE', 'Date inner-OOF MAE'], audit_rows)}

These are the independently selected family candidates for final Random1000.
The benchmark uses the median fitted within each inner training fold for OOF
prediction. Inner OOF already selected candidates; it is not a fresh unbiased
confirmation. Full refit training has 1,000 people but each inner fit has 750,
so the displayed gap is not a pure comparison at an identical training size.
All model/candidate/fold details are preserved in the audit worker outputs.

## Original convergence-warning audit

The audit verified {audit['tasks']} original task manifests, all recorded file
hashes and {audit['unique_model_objects_scored']} unique saved model objects.
There were {audit['warning_records']} warning records, and
{audit['fit_entries_with_convergence_warning']} of {audit['warning_fit_entries']}
fitting entries had at least one convergence warning. A three-seed MLP fitting
entry can generate several warning records. The ten final selected-procedure
refits emitted {audit['selected_final_refit_warning_records']} warnings.

{markdown(['Representation', 'Family', 'Inner fits with convergence warning', 'Total inner fits', 'Fraction'], warning_rows)}

## Fixed-candidate MLP optimization-budget comparison

Each of five original 800/200 development splits uses its own original MLP
family winner, with the same three initializations and preprocessing. Only the
iteration/function-call caps differ: original 1,000/20,000 versus extended
5,000/100,000. No candidate, seed or budget is selected from these results.

{markdown(['Representation', 'Budget', 'Training MAE', 'Held-out MAE', 'Held-out RMSE', 'Seed fits with convergence warning / 15'], budget_rows)}

Held-out rows pool 1,000 distinct people per representation, one prediction per
person. Training MAE aggregates 4,000 fold-training predictions, with repeated
people across the five fits; it is not a 4,000-person sample.

{markdown(['Representation', 'Training MAE improvement', 'Held-out MAE improvement', 'Held-out RMSE improvement', 'Mean seed objective improvement'], changes)}

Positive improvement is original minus extended and favors the extended budget.
All differences are descriptive; no new p-value or confidence claim is made.
MLP optimizes squared error plus L2, so optimization-objective improvement need
not improve MAE. These folds have already been examined. Checking only the
original MLP family winners does not exclude an unselected candidate improving
under a larger budget, or another architecture working better.

## Fixed synthetic recovery controls

Targets are entirely synthetic: 2500 + 50 × (strength × standardized signal +
independent standard-normal noise). The 66 raw columns define additive,
pairwise and third-order functions with prespecified random category scores.
Zero-signal controls use noise only. Each condition has two fixed noise
replicates and five 800/200 folds. Each of five representative estimators is
fixed before fitting; there is no hyperparameter search. Actual Elo is not used
to create these targets or choose a representative candidate.

The table shows **mean MAE gain over the fold-training-median benchmark across
the two fixed noise replicates**; positive values favor the model. Every
replicate/model result, including failures, is in `synthetic_pooled_metrics.csv`.

{markdown(['Signal', 'Strength', 'Ridge gain', 'Pairwise Ridge gain', 'RBF gain', 'Boosting gain', 'MLP gain'], control_rows)}

{markdown(['Signal', 'Fit attempts', 'Failed fits', 'Fits with convergence warning', 'Warning records'], [[r[k] for k in ('signal', 'fit_attempts', 'failed_fit_attempts', 'fit_attempts_with_convergence_warning', 'warning_records')] for r in control_counts])}

Recovery concerns only these functions, strengths, noise and fixed covariate
design. Calendar dependencies can correlate the constructed interaction
signals with lower-order features; exclusively high-order effects are not
claimed. Success is not evidence for a real BaZi–Elo relation; failure cannot
rule out every other function. Two noise replicates do not establish a
universal detection threshold, and zero-signal gains can fluctuate by chance.

## Interpretation and next decision

This finite diagnostic checks optimization limits, training/validation gaps and
recovery of selected known signals. Lower training error alone does not show
better prediction. It cannot prove six symbols contain no information, that an
hour pillar must help, or that a larger model will improve. No A1 conclusion is
replaced by these post-result diagnostics. Further development should be a
separate version with a fixed budget, and final predictive confirmation needs
a predeclared evaluation sample not used for development. The old 2023 NEW
cohort remains previously seen.

The report's machine-readable summary records diagnostic code, plan, lock,
worker input and output SHA256 hashes. All ten workers are required, all
available predictions are realigned and numerical metrics are recomputed
before this report is created.
"""


def plots(output, models, pooled):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    family_labels = ["Median", "Ridge", "Pairwise\nRidge", "RBF", "Boosting", "MLP"]
    block = models[(models.task == "final_random_1000") & (models.representation.isin(["raw_A", "benchmark"]))]
    rows = [block[block.family == family].iloc[0] for family in MODELS]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(rows))
    ax.bar(x - .18, [r.train_mae for r in rows], .36, label="Full-refit training")
    ax.bar(x + .18, [r.inner_oof_mae for r in rows], .36, label="Saved inner OOF")
    ax.set(xticks=x, xticklabels=family_labels, ylabel="MAE (Elo points)", title="2013 raw six-symbol A1: training and inner OOF")
    ax.legend(); ax.grid(axis="y", alpha=.25); ax.set_axisbelow(True)
    fig.text(.5, .01, "Inner OOF selected candidates; its training fits are smaller than the full refit.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, 1))
    for suffix in ("png", "svg"): fig.savefig(output / f"existing_train_oof.{suffix}", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.5, 4.5)); x = np.arange(2)
    for offset, budget, label in ((-.25, "original", "Original MLP budget"), (0, "extended", "Extended MLP budget"), (.25, "median", "Fold median")):
        values = [pooled[(pooled.representation == rep) & (pooled.budget == budget)].iloc[0].mae for rep in REPS]
        ax.bar(x + offset, values, .25, label=label)
    ax.set(xticks=x, xticklabels=["Raw six symbols", "Date control"], ylabel="Pooled held-out MAE (Elo)", title="Fixed original MLP candidates: optimization-budget diagnostic")
    ax.legend(); ax.grid(axis="y", alpha=.25); ax.set_axisbelow(True); fig.tight_layout()
    for suffix in ("png", "svg"): fig.savefig(output / f"mlp_budget_comparison.{suffix}", dpi=160)
    plt.close(fig)


def run_summary(root, inputs, output, *, verify_lock=True, make_plots=True):
    root, inputs, output = map(lambda p: Path(p).resolve(), (root, inputs, output))
    if output == inputs or output.is_relative_to(inputs):
        raise ValueError("Summary output must not be inside immutable worker inputs")
    if verify_lock:
        from diagnostic_lock import verify
        verify(root)
    audit_path, mlp_paths, control_paths, workers = locate_workers(inputs)
    if verify_lock:
        study = root / "studies/chess_single_A_v2"
        config_sha, analysis_sha = digest(study / "config.json"), digest(study / "analysis_lock.json")
        for path, manifest in workers:
            if manifest.get("config_sha256") != config_sha or manifest.get("analysis_lock_sha256") != analysis_sha:
                raise ValueError("Worker configuration/analysis-lock provenance differs")
            script = ("audit_existing.py" if path == audit_path else
                      "mlp_budget.py" if path in mlp_paths else "synthetic_controls.py")
            recorded = manifest.get("script_sha256", manifest.get("diagnostic_script_sha256"))
            if recorded != digest(root / REL / script):
                raise ValueError("Worker executed a different diagnostic script")
            if path in control_paths and (manifest.get("actual_ratings_used_for_targets") is not False
                                         or manifest.get("hyperparameter_search") is not False):
                raise ValueError("Synthetic-control outcome or selection scope differs")
            if path in mlp_paths and (manifest.get("candidate_reselection") is not False
                                     or manifest.get("budget_selection_from_diagnostic_scores") is not False):
                raise ValueError("MLP diagnostic selection scope differs")
    audit = read_json(audit_path)
    models = read_csv(audit_path.parent / "existing_model_metrics.csv")
    warning_table = read_csv(audit_path.parent / "existing_warning_summary.csv")
    outer = read_csv(audit_path.parent / "existing_development_predictions.csv")
    pooled, differences, predictions, fold_metrics = aggregate_mlp(mlp_paths, outer)
    controls, control_counts = aggregate_controls(control_paths)
    output.mkdir(parents=True, exist_ok=True)
    pooled.to_csv(output / "mlp_pooled_metrics.csv", index=False, float_format="%.17g")
    differences.to_csv(output / "mlp_pooled_improvements.csv", index=False, float_format="%.17g")
    predictions.to_csv(output / "mlp_pooled_predictions.csv", index=False, float_format="%.17g")
    fold_metrics.to_csv(output / "mlp_fold_metrics.csv", index=False, float_format="%.17g")
    controls.to_csv(output / "synthetic_pooled_metrics.csv", index=False, float_format="%.17g")
    report = create_report(audit, models, warning_table, pooled, differences, controls, control_counts)
    (output / "REPORT.md").write_text(report)
    if make_plots: plots(output, models, pooled)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, FileNotFoundError): commit = None
    sources = [REL / name for name in ("PLAN.md", "diagnostic_lock.json", "summarize.py")]
    summary = {"status": "complete_fixed_post_result_diagnostics", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_commit": commit, "worker_count": len(workers), "external_predictive_scoring_performed": False,
        "new_blind_confirmation_claimed": False, "model_or_budget_selected_from_diagnostics": False,
        "mlp_pooled_metrics": json.loads(pooled.to_json(orient="records")),
        "mlp_pooled_improvements": json.loads(differences.to_json(orient="records")),
        "synthetic_fit_counts": control_counts,
        "existing_audit": audit,
        "sources": [{"path": p.as_posix(), "sha256": digest(root / p)} for p in sources],
        "worker_manifests": [{"path": p.relative_to(inputs).as_posix(), "sha256": digest(p)} for p, _ in workers],
        "inputs": [{"path": p.relative_to(inputs).as_posix(), "sha256": digest(p)} for p in sorted(inputs.rglob("*")) if p.is_file()],
        "outputs": [{"path": p.relative_to(output).as_posix(), "sha256": digest(p)} for p in sorted(output.rglob("*")) if p.is_file() and p.name != "diagnostic_summary.json"]}
    (output / "diagnostic_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--inputs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_summary(args.repo_root, args.inputs_dir, args.output_dir)
    print(json.dumps({"status": result["status"], "workers": result["worker_count"]}))


if __name__ == "__main__": main()
