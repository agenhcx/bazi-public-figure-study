#!/usr/bin/env python3
"""Standalone figures for the prespecified chess Elo prediction comparisons.

This module consumes reported metrics only. It never fits or selects models.
Invalid family fits remain visible as labelled gaps, and missing result rows
raise an error rather than silently disappearing from a figure.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FAMILIES = [
    "ridge",
    "pairwise_ridge",
    "rbf_kernel_ridge",
    "shallow_gradient_boosting",
    "small_mlp",
]
FAMILY_LABELS = [
    "Ridge",
    "Pairwise\nRidge",
    "RBF kernel\nridge",
    "Gradient\nboosting",
    "MLP",
]
SERIES = [
    ("raw_A", "Six-symbol model", "#0072B2"),
    ("date_control", "Date control", "#D55E00"),
    ("benchmark", "Training median", "#777777"),
]
STYLE = {
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#666666",
    "axes.axisbelow": True,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.65,
    "svg.fonttype": "none",
    "svg.hashsalt": "chess-single-A-v2",
    "savefig.facecolor": "white",
}


def _row_value(frame: pd.DataFrame, **selectors) -> float:
    mask = pd.Series(True, index=frame.index)
    for key, value in selectors.items():
        if key not in frame:
            raise ValueError(f"Plot input omits column {key!r}")
        mask &= frame[key].eq(value)
    rows = frame.loc[mask]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one plot result for {selectors}; got {len(rows)}")
    row = rows.iloc[0]
    status = row.get("status", "complete")
    if status == "invalid_no_valid_candidate":
        return float("nan")
    if status != "complete":
        raise ValueError(f"Unrecognized plot-result status: {status!r}")
    value = float(row["mae"])
    if not np.isfinite(value) or value < 0:
        raise ValueError(f"Complete plot result has invalid MAE for {selectors}")
    return value


def _upper_limit(values) -> float:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    return max(1.0, float(finite.max()) * 1.24) if len(finite) else 1.0


def _labels(ax, positions, values, upper, numbers=True):
    for position, value in zip(positions, values):
        if np.isfinite(value) and numbers:
            ax.text(position, value + upper * .012, f"{value:.1f}",
                    ha="center", va="bottom", fontsize=8)
        elif not np.isfinite(value):
            ax.text(position, upper * .025, "invalid", ha="center",
                    va="bottom", fontsize=8, color="#666666", rotation=90)


def _save(fig, output_dir: Path, stem: str, title: str) -> list[str]:
    filenames = []
    for extension in ("png", "svg"):
        name = f"{stem}.{extension}"
        metadata = {"Title": title}
        if extension == "svg":
            metadata.update({"Creator": "chess-single-A-v2", "Date": None})
        fig.savefig(output_dir / name, dpi=200, metadata=metadata)
        filenames.append(name)
    plt.close(fig)
    return filenames


def _family_plot(metrics: pd.DataFrame, output_dir: Path) -> list[str]:
    values = {}
    for representation, _, _ in SERIES[:2]:
        values[representation] = [
            _row_value(metrics, cohort="primary_new", subset="random_1000",
                       representation=representation, model=family)
            for family in FAMILIES
        ]
    baseline = _row_value(metrics, cohort="primary_new", subset="random_1000",
                          representation="benchmark", model="training_median")
    if not np.isfinite(baseline):
        raise ValueError("Training-median baseline must have a complete result")
    upper = _upper_limit(values["raw_A"] + values["date_control"] + [baseline])
    fig, ax = plt.subplots(figsize=(10.5, 5.4), layout="constrained")
    positions = np.arange(len(FAMILIES))
    width = .36
    for offset, (representation, label, color) in zip((-.5, .5), SERIES[:2]):
        x = positions + offset * width
        ax.bar(x, values[representation], width=width, label=label,
               color=color, linewidth=0)
        _labels(ax, x, values[representation], upper)
    ax.axhline(baseline, color=SERIES[2][2], linestyle="--", linewidth=1.4,
               label="Training median")
    ax.set(xticks=positions, xticklabels=FAMILY_LABELS, ylim=(0, upper),
           ylabel="Mean absolute error (Elo points)")
    ax.set_title("2023 NEW: model families with 1,000 training people", loc="left")
    ax.grid(axis="y")
    ax.legend(loc="upper right", ncol=3, fontsize=9, frameon=True)
    fig.supxlabel("Each family is tuned on 2013 only; all bars use the same 2023 NEW people.",
                  fontsize=8, color="#555555")
    return _save(fig, output_dir, "primary_family_mae", "2023 NEW family MAE")


def _size_plot(metrics: pd.DataFrame, output_dir: Path) -> list[str]:
    sizes = [500, 800, 1000]
    values = {}
    for representation, _, _ in SERIES:
        model = "training_median" if representation == "benchmark" else "selected_pipeline"
        values[representation] = [
            _row_value(metrics, cohort="primary_new", subset=f"random_{size}",
                       representation=representation, model=model)
            for size in sizes
        ]
    upper = _upper_limit([value for series in values.values() for value in series])
    fig, ax = plt.subplots(figsize=(9.5, 5.4), layout="constrained")
    positions = np.arange(len(sizes))
    width = .24
    for offset, (representation, label, color) in zip((-1, 0, 1), SERIES):
        x = positions + offset * width
        ax.bar(x, values[representation], width=width, color=color, label=label,
               linewidth=0)
        _labels(ax, x, values[representation], upper)
    ax.set(xticks=positions, xticklabels=["500", "800", "1,000"], ylim=(0, upper),
           xlabel="2013 training people (nested random subsets)",
           ylabel="Mean absolute error (Elo points)")
    ax.set_title("2023 NEW: prespecified training-size comparison", loc="left")
    ax.grid(axis="y")
    ax.legend(loc="upper right", ncol=3, fontsize=9, frameon=True)
    fig.supxlabel("Model selection uses 2013 only; no training size is selected from these external scores.",
                  fontsize=8, color="#555555")
    return _save(fig, output_dir, "primary_training_size_mae", "2023 NEW training-size MAE")


def _development_plot(development: pd.DataFrame, output_dir: Path) -> list[str]:
    sizes = [400, 600, 800]
    values = {}
    for representation, _, _ in SERIES:
        model = "training_median" if representation == "benchmark" else "selected_pipeline"
        values[representation] = [
            _row_value(development, train_n=size, representation=representation, model=model)
            for size in sizes
        ]
    upper = _upper_limit([value for series in values.values() for value in series])
    fig, ax = plt.subplots(figsize=(9.5, 5.4), layout="constrained")
    for (representation, label, color), marker in zip(SERIES, ("o", "s", "^")):
        linestyle = "--" if representation == "benchmark" else "-"
        ax.plot(sizes, values[representation], marker=marker, linestyle=linestyle,
                color=color, linewidth=1.8, markersize=5.5, label=label)
        _labels(ax, sizes, values[representation], upper, numbers=False)
    ax.set(xticks=sizes, ylim=(0, upper), xlabel="Training people per outer fold",
           ylabel="Pooled held-out mean absolute error (Elo points)")
    ax.set_title("2013 development: nested CV learning curve", loc="left")
    ax.grid(axis="y")
    ax.legend(loc="upper right", ncol=3, fontsize=9, frameon=True)
    fig.supxlabel("Predictions pool five fixed outer test folds. Training sizes are per fold;\n"
                  "this is not a cross-validation estimate for training on 1,000 people.",
                  fontsize=8, color="#555555")
    return _save(fig, output_dir, "development_learning_curve", "2013 development learning curve")


def plot_results(metrics: pd.DataFrame, development_metrics: pd.DataFrame,
                 output_dir: Path) -> list[str]:
    """Save fixed-comparison PNG/SVG figures and return their relative filenames."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for frame, required, name in [
        (metrics, {"cohort", "subset", "representation", "model", "mae"}, "external"),
        (development_metrics, {"train_n", "representation", "model", "mae"}, "development"),
    ]:
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Missing {name} plot columns: {sorted(missing)}")
    filenames = []
    with plt.rc_context(STYLE):
        filenames.extend(_family_plot(metrics, output_dir))
        filenames.extend(_size_plot(metrics, output_dir))
        filenames.extend(_development_plot(development_metrics, output_dir))
    return filenames
