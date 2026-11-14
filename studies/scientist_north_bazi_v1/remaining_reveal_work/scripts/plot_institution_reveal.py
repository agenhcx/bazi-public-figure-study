#!/usr/bin/env python3
"""Descriptive scientific figures for the three newly authorized institutions.

No result is read on import. N>=20 common support is chosen before outcomes;
categories and panels are never selected using a p-value or a large excess.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import TwoSlopeNorm
import numpy as np

LABELS = {"DE_Leopoldina": "德国科学院 Leopoldina", "France": "法国科学院", "Japan": "日本学士院"}
STEMS = list("甲乙丙丁戊己庚辛壬癸")
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
ELEMENTS = list("金木水火土")
SOURCES = {"strict": "严格来源 S1＋S2", "expanded": "扩展来源 S1＋S2＋S3"}
GOD_PANELS = [("DM", STEMS, "日主：按人数计"), ("M0", GODS, "十神本气 M0：五位占比"),
              ("M1", GODS, "十神藏干优先 M1：五位占比")]
ELEMENT_PANELS = [("M0_element", ELEMENTS, "五行本气 M0：五位占比"),
                  ("M1_element", ELEMENTS, "五行藏干优先 M1：五位占比")]


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def set_font():
    candidates = [Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                  Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc")]
    path = next((p for p in candidates if p.is_file()), None)
    require(path is not None, "Chinese Noto CJK font is required")
    font_manager.fontManager.addfont(str(path))
    prop = font_manager.FontProperties(fname=str(path))
    plt.rcParams.update({"font.family": prop.get_name(), "axes.unicode_minus": False,
                         "svg.fonttype": "path", "font.size": 11, "axes.titleweight": "medium"})
    return str(path)


def symmetric_limit(matrices):
    arrays = list(matrices)
    if not arrays:
        return .5
    return max(.5, math.ceil(max(float(np.max(np.abs(v))) for v in arrays) * 2) / 2)


def decade_label(year, count):
    return f"{1835 if year == 1830 else year}–{str(year + 9)[-2:]}\nn＝{count}"


def extract(data, institution):
    require(institution in LABELS and data.get("country") == institution, "Only the authorized institution is permitted")
    groups = data["groups"]
    common = [int(d) for d in data["common_adequate_decades"]]
    bins = {source: {int(b["decade"]): b for b in groups[source]["bins"]} for source in SOURCES}
    eligible = sorted(d for d in bins["strict"] if bins["strict"][d]["n"] >= 20 and bins["expanded"][d]["n"] >= 20)
    require(common == eligible, "Figure bin rule must be all and only both-source N>=20 bins")
    identical = bool(data.get("source_groups_identical"))
    if identical:
        require(groups["strict"]["person_ids_sha256"] == groups["expanded"]["person_ids_sha256"], "Identical-source IDs differ")
        require(groups["strict"]["people"] == groups["expanded"]["people"] and groups["strict"]["bins"] == groups["expanded"]["bins"], "Identical-source observations differ")
    plotted_sources = ["strict"] if identical else list(SOURCES)
    prepared = {}
    for source in plotted_sources:
        group = groups[source]
        matrices = {}
        if common:
            for prefix, categories, _ in GOD_PANELS + ELEMENT_PANELS:
                values = np.asarray([[bins[source][d]["endpoints"][prefix + "_" + c]["excess_percentage_points"]
                                      for d in common] for c in categories], dtype=float)
                require(values.shape == (len(categories), len(common)) and np.isfinite(values).all(), "Missing/nonfinite plotted cell")
                matrices[prefix] = values
        counts = [int(bins[source][d]["n"]) for d in common]
        prepared[source] = {"n_total": int(group["people"]), "n_displayed": sum(counts), "decades": common,
                            "decade_n": counts, "matrices": matrices,
                            "levels": {row["endpoint_id"]: row for row in group["levels"]}}
    return identical, common, prepared


def source_caption(source, datum, identical):
    return ("严格组＝扩展组" if identical else SOURCES[source]) + f"；整组 n＝{datum['n_total']}，图示年代 n＝{datum['n_displayed']}"


def heatmap(institution, source, datum, panels, limits, identical, output, kind):
    count = len(panels)
    is_elements = count == 2
    fig, axes = plt.subplots(1, count, figsize=((20.5, 5.8) if is_elements else (24, 7.3)))
    fig.subplots_adjust(left=.038, right=.985, top=.78, bottom=(.29 if is_elements else .26), wspace=.22)
    fig.suptitle(LABELS[institution] + ("：五行的出生年代分布相对日历期望的偏离" if is_elements else "：日主与十神的出生年代分布相对日历期望的偏离"), fontsize=21, y=.972)
    fig.text(.5, .88, source_caption(source, datum, identical), ha="center", fontsize=13, color="#344b5c")
    labels = [decade_label(d, n) for d, n in zip(datum["decades"], datum["decade_n"])]
    for ax, (prefix, categories, title) in zip(np.atleast_1d(axes), panels):
        values, limit = datum["matrices"][prefix], limits[prefix]
        graphic = ax.imshow(values, cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit), interpolation="nearest", aspect="auto")
        ax.set_title(title, fontsize=15, pad=12)
        ax.set_xticks(np.arange(len(labels)), labels, fontsize=8.8)
        ax.set_yticks(np.arange(len(categories)), categories, fontsize=12)
        ax.tick_params(axis="both", length=0)
        ax.set_xlabel("出生年份区间", labelpad=9, fontsize=11)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks(np.arange(-.5, len(labels), 1), minor=True)
        ax.set_yticks(np.arange(-.5, len(categories), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=.8)
        ax.tick_params(which="minor", length=0)
        for i in range(len(categories)):
            for j in range(len(labels)):
                value = float(values[i, j])
                ax.text(j, i, "0.0" if abs(value) < .05 else f"{value:+.1f}", ha="center", va="center",
                        fontsize=10.2 if is_elements else 9.2, color="white" if abs(value) >= .64 * limit else "#172b3a")
        cb = fig.colorbar(graphic, ax=ax, location="bottom", pad=.33 if is_elements else .23, fraction=.052,
                          ticks=[-limit, -limit / 2, 0, limit / 2, limit])
        cb.ax.tick_params(labelsize=10, length=2)
        cb.set_label("实测占比 − 同出生年日历期望（百分点）", fontsize=11, labelpad=5)
    fig.text(.038, .045, "仅显示两来源均不少于20人的共同年代；1830年代在出生窗内实际仅含1835–1839年。\n"
             "暖色＝高于期望；冷色＝低于期望。颜色为描述，不代表显著；小样本及空年代均保留在完整表，主检验不排除小样本年代。",
             ha="left", va="bottom", fontsize=11, linespacing=1.7, color="#405566")
    files = [output / f"{source}_{kind}.png", output / f"{source}_{kind}.svg"]
    fig.savefig(files[0], dpi=180, facecolor="white")
    fig.savefig(files[1], facecolor="white")
    plt.close(fig)
    return files


def overall_elements(institution, source, datum, identical, ymax, output):
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.1), sharey=True)
    fig.subplots_adjust(left=.075, right=.975, top=.74, bottom=.19, wspace=.16)
    fig.suptitle(LABELS[institution] + "：总体五行构成与日历期望", fontsize=21, y=.97)
    label = "严格组＝扩展组" if identical else SOURCES[source]
    fig.text(.5, .88, label + f"；n＝{datum['n_total']}，每人五位，总单位数＝{5*datum['n_total']}", ha="center", fontsize=12.8, color="#344b5c")
    xs = np.arange(5)
    for ax, model, title in zip(axes, ["M0", "M1"], ["本气 M0", "藏干优先 M1"]):
        rows = [datum["levels"][model + "_element_" + e] for e in ELEMENTS]
        observed = [float(row["observed_share"]) * 100 for row in rows]
        expected = [float(row["calendar_expected_share"]) * 100 for row in rows]
        bars = [ax.bar(xs - .19, observed, width=.36, color="#337fa3", label="观察占比"),
                ax.bar(xs + .19, expected, width=.36, color="#dbe3e8", edgecolor="#7c8b95", label="同出生年日历期望")]
        for group in bars:
            ax.bar_label(group, labels=[f"{b.get_height():.2f}" for b in group], padding=3, fontsize=10)
        ax.set_title(title, fontsize=15, pad=14)
        ax.set_xticks(xs, ELEMENTS, fontsize=13)
        ax.set_ylim(0, ymax)
        ax.grid(axis="y", color="#d7e0e6", linewidth=.6)
        ax.set_axisbelow(True)
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
        ax.tick_params(length=0)
    axes[0].set_ylabel("五个位点中的占比（%）", fontsize=12)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.5, .835), frameon=False, ncol=2, fontsize=11.5)
    fig.text(.075, .045, "日干只作参照，不计五行单位；无时柱。藏干口径每支只取一个代表干。\n"
             "日历期望保留实际出生年构成；五行基线并非各20%。柱高为描述，不代表统计显著。", ha="left", fontsize=10.5, linespacing=1.7, color="#405566")
    files = [output / f"{source}_overall_elements.png", output / f"{source}_overall_elements.svg"]
    fig.savefig(files[0], dpi=190, facecolor="white")
    fig.savefig(files[1], facecolor="white")
    plt.close(fig)
    return files


def synthetic_qa():
    require(symmetric_limit([np.asarray([[-.26, .74]])]) == 1., "Symmetric outward scale")
    require(symmetric_limit([]) == .5, "Empty common bin handling")
    require(decade_label(1830, 60) == "1835–39\nn＝60", "Partial first decade")
    require(len(GOD_PANELS[0][1]) == 10 and all(len(p[1]) == 5 for p in ELEMENT_PANELS), "Canonical categories")
    require(set(LABELS) == {"DE_Leopoldina", "France", "Japan"}, "Only authorized institutions")
    return {"status": "PASS", "study_data_loaded": False, "shared_source_and_model_symmetric_scales": True,
            "partial1830_bin": True, "empty_common_bin_skip_not_analysis_exclusion": True, "no_pvalue_selection": True,
            "allowed_institutions": list(LABELS)}


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2))
        return
    require(args.allow_institution_result_render and args.institution in LABELS, "Authorized institution render flag required")
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get("remote_plan_and_code_verified_before_summary") is True and args.institution in receipt["allowed_institutions"], "Verified institution execution receipt required")
    source = Path(args.input)
    identical, common, prepared = extract(json.loads(source.read_text()), args.institution)
    output = Path(args.output_dir)
    require(not output.exists(), "No overwrite of figures")
    font = set_font()
    matrices = [datum["matrices"] for datum in prepared.values()]
    gods = symmetric_limit(m[p] for m in matrices for p in ["M0", "M1"]) if common else .5
    elements = symmetric_limit(m[p] for m in matrices for p in ["M0_element", "M1_element"]) if common else .5
    limits = {"DM": symmetric_limit(m["DM"] for m in matrices) if common else .5,
              "M0": gods, "M1": gods, "M0_element": elements, "M1_element": elements}
    maximum = max(float(d["levels"][model + "_element_" + e][key]) * 100 for d in prepared.values()
                  for model in ["M0", "M1"] for e in ELEMENTS for key in ["observed_share", "calendar_expected_share"])
    ymax = math.ceil((maximum + 3) / 5) * 5
    output.mkdir(parents=True)
    files = []
    for source_name, datum in prepared.items():
        if common:
            files += heatmap(args.institution, source_name, datum, GOD_PANELS, limits, identical, output, "decade_stems_gods_heatmaps")
            files += heatmap(args.institution, source_name, datum, ELEMENT_PANELS, limits, identical, output, "decade_elements_heatmaps")
        files += overall_elements(args.institution, source_name, datum, identical, ymax, output)
    manifest = {"schema": "institution_scientific_figures_v1", "country": args.institution,
                "source_result_sha256": sha(source), "plot_code_sha256": sha(__file__),
                "execution_lock_commit": receipt["commit"], "source_groups_identical": identical,
                "sources_plotted": list(prepared), "people_by_source": {s: d["n_total"] for s, d in prepared.items()},
                "displayed_people_by_source": {s: d["n_displayed"] for s, d in prepared.items()},
                "common_adequate_decades": common, "decade_n_by_source": {s: d["decade_n"] for s, d in prepared.items()},
                "empty_common_support_no_heatmap": not bool(common), "other_bins_removed_from_analysis": False,
                "heatmap_units": "observed_minus_same_birthyear_calendar_expected_share_percentage_points",
                "symmetric_color_limits_pp": limits, "TenGod_scale_shared_M0_M1_both_sources": True,
                "element_scale_shared_M0_M1_both_sources": True, "overall_bar_ylim_shared_sources": [0, ymax],
                "font_path": font, "significance_stars_or_p_selection": False,
                "figure_file_sha256": {p.name: sha(p) for p in files}}
    (output / "FIGURE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "country": args.institution, "sources_plotted": list(prepared), "figures": len(files), "common_decades": common}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--institution", choices=list(LABELS))
    parser.add_argument("--input")
    parser.add_argument("--output-dir")
    parser.add_argument("--execution-receipt")
    parser.add_argument("--allow-institution-result-render", action="store_true")
    parser.add_argument("--synthetic-qa-only", action="store_true")
    main(parser.parse_args())
