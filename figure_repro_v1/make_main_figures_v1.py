#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reproduce the current manuscript Figure 1–5 set.

Dependencies:
    pip install numpy pandas matplotlib

Run:
    python make_main_figures_v1.py

The script expects the bundled ./data directory and writes PNG files to ./outputs.
Each figure is generated as a separate matplotlib figure (no subplots).

Figure set
----------
Figure 1: Methodological workflow schematic.
Figure 2: Chess Ten-God profiles across 2013 discovery / 2023 full / 2023 new target.
Figure 3: Hurting-Officer conditional companion structures, displayed in Z / sigma units.
Figure 4: Table-tennis historical vs modern Ten-God profile.
Figure 5: Rob-Wealth temporal trajectory, table tennis vs chess.

Important provenance note
-------------------------
Figure 3 E1/E2 outlet analyses are a post-reveal frozen methodological extension.
The main Figure 3 uses pathway-level features; the broad "Any Major Outlet" union
is intentionally not shown because its conditional-null expectation is near saturation.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)


def save(fig, filename):
    fig.tight_layout()
    fig.savefig(OUT / filename, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------
# Figure 1 — methodological workflow
# ---------------------------------------------------------------------
def figure1():
    fig, ax = plt.subplots(figsize=(14, 4.8))
    ax.set_axis_off()

    labels = [
        "Traditional proposition\nor exploratory discovery",
        "Operationalize a\nmeasurable feature",
        "Calendar-conditioned\nnull model",
        "Freeze definition,\ncohort and direction",
        "Independent\nreplication",
    ]

    xs = np.linspace(0.08, 0.92, len(labels))
    y = 0.60
    box_w, box_h = 0.15, 0.22

    for i, (x, label) in enumerate(zip(xs, labels)):
        box = FancyBboxPatch(
            (x - box_w/2, y - box_h/2), box_w, box_h,
            boxstyle="round,pad=0.02,rounding_size=0.02",
            linewidth=1.4, fill=False
        )
        ax.add_patch(box)
        ax.text(x, y, label, ha="center", va="center", fontsize=11)
        if i < len(labels)-1:
            arr = FancyArrowPatch(
                (x + box_w/2 + 0.01, y),
                (xs[i+1] - box_w/2 - 0.01, y),
                arrowstyle="->", mutation_scale=14, linewidth=1.3
            )
            ax.add_patch(arr)

    ax.text(
        0.50, 0.22,
        "Positive result, null result, or reversal are all retained",
        ha="center", va="center", fontsize=11
    )
    ax.text(
        0.50, 0.08,
        "Necessary-component tests can precede subjective strength / favorable-element / full-configuration adjudication",
        ha="center", va="center", fontsize=10
    )
    ax.set_title(
        "Figure 1. From traditional propositions to reproducible population tests",
        fontsize=14, pad=14
    )
    save(fig, "figure1_methodological_workflow.png")


# ---------------------------------------------------------------------
# Figure 2 — Chess Ten-God profiles, ratio scale centered at R=1
# ---------------------------------------------------------------------
def figure2():
    df = pd.read_csv(DATA / "figure2_deviation_bar_source.csv")
    cohorts = [
        ("2013_M_DISCOVERY", "2013 discovery"),
        ("2023_M_FULL", "2023 full"),
        ("2023_M_NEW_TARGET", "2023 new target"),
    ]

    x = np.arange(len(df))
    w = 0.25
    fig, ax = plt.subplots(figsize=(13.5, 7.2))

    for i, (key, label) in enumerate(cohorts):
        vals = df[f"{key}_ratio"].to_numpy() - 1.0
        ax.bar(x + (i-1)*w, vals, width=w, label=label)

    # Pooled approximate ratio-scale sigma guide from the source table.
    sigma_cols = [f"{k}_sigma_r" for k, _ in cohorts]
    sigma_r = float(df[sigma_cols].to_numpy().mean())
    for mult in (1, 2, 3):
        ax.axhline(+mult*sigma_r, linestyle="--", linewidth=0.9)
        ax.axhline(-mult*sigma_r, linestyle="--", linewidth=0.9)

    ax.axhline(0, linewidth=1.3)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, pos: f"{1+y:.2f}"))
    ax.set_xticks(x)
    ax.set_xticklabels(df["Ten God"], rotation=28, ha="right")
    ax.set_ylabel("Observed / calendar-null ratio")
    ax.set_title("Figure 2. Chess Ten-God profile across discovery and validation cohorts")
    ax.legend(frameon=False, ncol=3)
    save(fig, "figure2_chess_tengod_profile.png")


# ---------------------------------------------------------------------
# Figure 3 — HO conditional pathway-level companion structures, Z / sigma
# ---------------------------------------------------------------------
def figure3():
    df = pd.read_csv(DATA / "figure3_ho_conditional_zscore_sigma_source.csv")

    # Strip Chinese parenthetical labels to keep a publication-safe English version.
    feature_order = [
        ("Direct Resource\n(正印)", "Direct Resource"),
        ("Indirect Resource\n(偏印)", "Indirect Resource"),
        ("Any Resource\n(配印 proxy)", "Any Resource\n(Resource pathway)"),
        ("Seven Killings\n(架杀 proxy)", "Seven Killings\n(Killings pathway)"),
        ("Any Wealth\n(生财 proxy)", "Any Wealth\n(Wealth pathway)"),
        ("Direct Officer\n(见官 proxy)", "Direct Officer"),
    ]
    cohorts = ["2013 discovery", "2023 full", "2023 new target"]

    x = np.arange(len(feature_order))
    w = 0.24
    fig, ax = plt.subplots(figsize=(13.2, 7.2))

    for i, cohort in enumerate(cohorts):
        sub = df[df["cohort"] == cohort].set_index("feature")
        vals = [float(sub.loc[src, "z"]) for src, _ in feature_order]
        ax.bar(x + (i-1)*w, vals, width=w, label=cohort)

    for y in (-2, -1, 1, 2):
        ax.axhline(y, linestyle="--", linewidth=0.9)
    ax.axhline(0, linewidth=1.3)

    ax.set_xticks(x)
    ax.set_xticklabels([dst for _, dst in feature_order], rotation=24, ha="right")
    ax.set_ylabel("Standardized deviation from HO-conditioned calendar null (Z, σ)")
    ax.set_title("Figure 3. Hurting-Officer conditional companion structures")
    ax.legend(frameon=False, ncol=3)
    ax.set_ylim(-2.8, 2.8)
    save(fig, "figure3_ho_conditional_sigma.png")


# ---------------------------------------------------------------------
# Figure 4 — Table-tennis historical vs modern profile
# ---------------------------------------------------------------------
def figure4():
    df = pd.read_csv(DATA / "figure4_tt_true_values_with_sigma_source.csv")

    x = np.arange(len(df))
    w = 0.34
    fig, ax = plt.subplots(figsize=(13.5, 7.2))

    hist = df["Historical 1950–1984 ratio"].to_numpy() - 1.0
    modern = df["Modern 1985–2008 ratio"].to_numpy() - 1.0
    ax.bar(x - w/2, hist, width=w, label="Historical 1950–1984")
    ax.bar(x + w/2, modern, width=w, label="Modern 1985–2008")

    hist_sigma = float(df["Historical sigma_R"].mean())
    modern_sigma = float(df["Modern sigma_R"].mean())
    for mult in (1, 2):
        ax.axhline(+mult*hist_sigma, linestyle=":", linewidth=0.9)
        ax.axhline(-mult*hist_sigma, linestyle=":", linewidth=0.9)
        ax.axhline(+mult*modern_sigma, linestyle="--", linewidth=0.9)
        ax.axhline(-mult*modern_sigma, linestyle="--", linewidth=0.9)

    ax.axhline(0, linewidth=1.3)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, pos: f"{1+y:.2f}"))
    ax.set_xticks(x)
    ax.set_xticklabels(df["Ten God"], rotation=28, ha="right")
    ax.set_ylabel("Observed / calendar-null ratio")
    ax.set_title("Figure 4. Table-tennis Ten-God profile: historical versus modern cohorts")
    ax.legend(frameon=False, ncol=2)
    save(fig, "figure4_tt_historical_modern_profile.png")


# ---------------------------------------------------------------------
# Figure 5 — TT vs Chess Rob-Wealth temporal trajectory
# ---------------------------------------------------------------------
def figure5():
    df = pd.read_csv(DATA / "figure5_6_tt_chess_window_compare_source.csv")
    fig, ax = plt.subplots(figsize=(11.5, 6.6))

    for domain in ["TT", "Chess"]:
        sub = df[df["domain"] == domain].sort_values("midpoint_year")
        ax.plot(
            sub["midpoint_year"], sub["ratio"],
            marker="o", linewidth=1.8, label=("Table tennis" if domain == "TT" else "Chess")
        )

    ax.axhline(1.0, linewidth=1.2)
    ax.axvline(1985, linestyle="--", linewidth=1.0)
    ax.set_xticks(
        df[df["domain"] == "TT"]["midpoint_year"],
        df[df["domain"] == "TT"]["window"],
        rotation=20
    )
    ax.set_ylabel("Observed / calendar-null ratio")
    ax.set_xlabel("Frozen birth-year windows")
    ax.set_title("Figure 5. Rob-Wealth temporal trajectory: table tennis versus chess")
    ax.legend(frameon=False)

    ax.text(
        0.02, 0.97,
        "TT: ρ = +0.11368, directional p = 0.0110\n"
        "Chess: ρ = +0.02198, directional p = 0.4275",
        transform=ax.transAxes, va="top"
    )
    save(fig, "figure5_tt_chess_robwealth_temporal.png")


def main():
    figure1()
    figure2()
    figure3()
    figure4()
    figure5()
    print(f"Saved Figure 1–5 to: {OUT}")


if __name__ == "__main__":
    main()
