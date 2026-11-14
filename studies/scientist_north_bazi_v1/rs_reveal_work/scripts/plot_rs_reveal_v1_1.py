#!/usr/bin/env python3
"""Descriptive Royal Society scientific figures from completed UK-only output.

No result file is read on import. Plot selection is the prospective N>=20
decade rule, never a p-value or a largest-excess selection.
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

STEMS = list("甲乙丙丁戊己庚辛壬癸")
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
ELEMENTS = list("金木水火土")
GOD_PANELS = [
    ("DM", STEMS, "日主：按人数计"),
    ("M0", GODS, "十神本气 M0：五位占比"),
    ("M1", GODS, "十神藏干优先 M1：五位占比"),
]
ELEMENT_PANELS = [
    ("M0_element", ELEMENTS, "五行本气 M0：五位占比"),
    ("M1_element", ELEMENTS, "五行藏干优先 M1：五位占比"),
]


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def set_font():
    candidates = [Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                  Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc")]
    path = next((p for p in candidates if p.is_file()), None)
    require(path is not None, "A Chinese-capable Noto CJK font is required")
    font_manager.fontManager.addfont(str(path))
    prop = font_manager.FontProperties(fname=str(path))
    plt.rcParams.update({"font.family": prop.get_name(), "axes.unicode_minus": False,
                         "svg.fonttype": "path", "font.size": 11,
                         "axes.titleweight": "medium"})
    return str(path)


def symmetric_limit(matrices):
    maximum = max(float(np.max(np.abs(v))) for v in matrices)
    return max(.5, math.ceil(maximum * 2) / 2)


def decade_label(year, count):
    first = 1835 if year == 1830 else year
    return f"{first}–{str(year + 9)[-2:]}\nn＝{count}"


def extract(data):
    require(data.get("country") == "UK_Royal_Society", "UK-only renderer")
    strict, expanded = data["groups"]["strict"], data["groups"]["expanded"]
    require(int(strict["people"]) == int(expanded["people"]) == 2293, "Frozen UK population differs")
    require(strict["person_ids_sha256"] == expanded["person_ids_sha256"], "Expanded UK source IDs differ")
    require(strict["levels"] == expanded["levels"] and strict["bins"] == expanded["bins"],
            "This single-source figure requires identical strict and expanded results")
    common = [int(d) for d in data["common_adequate_decades"]]
    bins = {int(row["decade"]): row for row in strict["bins"]}
    other_bins = {int(row["decade"]): row for row in expanded["bins"]}
    eligible = sorted(d for d in bins if int(bins[d]["n"]) >= 20 and int(other_bins[d]["n"]) >= 20)
    require(common == eligible and common, "Figure decades must be all and only common N>=20 bins")
    matrices = {}
    for prefix, categories, _ in GOD_PANELS + ELEMENT_PANELS:
        matrix = np.asarray([[bins[d]["endpoints"][prefix + "_" + c]["excess_percentage_points"]
                              for d in common] for c in categories], dtype=float)
        require(matrix.shape == (len(categories), len(common)) and np.isfinite(matrix).all(),
                "Missing or nonfinite displayed cell: " + prefix)
        matrices[prefix] = matrix
    ns = [int(bins[d]["n"]) for d in common]
    level = {row["endpoint_id"]: row for row in strict["levels"]}
    return {"decades": common, "decade_n": ns, "n_total": int(strict["people"]),
            "n_displayed": sum(ns), "matrices": matrices, "levels": level}


def heatmap(data, panels, limits, output, basename, title):
    n = len(panels)
    is_elements = n == 2
    fig, axes = plt.subplots(1, n, figsize=((20.5, 5.8) if is_elements else (24, 7.3)))
    fig.subplots_adjust(left=.038, right=.985, top=.78, bottom=(.29 if is_elements else .26),
                        wspace=(.20 if is_elements else .25))
    fig.suptitle(title, fontsize=21, y=.972)
    fig.text(.5, .88, f"严格组＝扩展组；整组 n＝{data['n_total']}，图示年代 n＝{data['n_displayed']}",
             ha="center", fontsize=13, color="#344b5c")
    labels = [decade_label(d, count) for d, count in zip(data["decades"], data["decade_n"])]
    for ax, (prefix, categories, panel_title) in zip(np.atleast_1d(axes), panels):
        matrix, limit = data["matrices"][prefix], limits[prefix]
        graphic = ax.imshow(matrix, cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
                            interpolation="nearest", aspect="auto")
        ax.set_title(panel_title, fontsize=15, pad=12)
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
                value = float(matrix[i, j])
                cell = "0.0" if abs(value) < .05 else f"{value:+.1f}"
                ax.text(j, i, cell, ha="center", va="center", fontsize=(10.2 if is_elements else 9.2),
                        color="white" if abs(value) >= .64 * limit else "#172b3a")
        cb = fig.colorbar(graphic, ax=ax, location="bottom", pad=(.33 if is_elements else .23),
                          fraction=.052, ticks=[-limit, -limit / 2, 0, limit / 2, limit])
        cb.ax.tick_params(labelsize=10, length=2)
        cb.set_label("实测占比 − 同出生年日历期望（百分点）", fontsize=11, labelpad=5)
    fig.text(.038, .045,
             "仅显示严格与扩展来源均不少于20人的年代；1830年代受冻结出生窗限制，实际仅含1835–1839年。\n"
             "暖色＝高于期望；冷色＝低于期望。颜色与数值均为描述，不代表统计显著；其余年代保留在完整表和全样本分析中。",
             ha="left", va="bottom", fontsize=11, linespacing=1.7, color="#405566")
    png, svg = output / (basename + ".png"), output / (basename + ".svg")
    fig.savefig(png, dpi=180, facecolor="white")
    fig.savefig(svg, facecolor="white")
    plt.close(fig)
    return [png, svg]


def overall_elements(data, output):
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.1), sharey=True)
    fig.subplots_adjust(left=.075, right=.975, top=.74, bottom=.19, wspace=.16)
    fig.suptitle("英国皇家学会：总体五行构成与日历期望", fontsize=21, y=.97)
    fig.text(.5, .88, f"严格组＝扩展组；n＝{data['n_total']}，每人五位，总单位数＝{5*data['n_total']}",
             ha="center", fontsize=12.8, color="#344b5c")
    maximum = max(float(data['levels'][model + '_element_' + e][key]) * 100
                  for model in ['M0', 'M1'] for e in ELEMENTS
                  for key in ['observed_share', 'calendar_expected_share'])
    ymax = math.ceil((maximum + 3) / 5) * 5
    xs = np.arange(5)
    for ax, model, title in zip(axes, ['M0', 'M1'], ['本气 M0', '藏干优先 M1']):
        rows = [data['levels'][model + '_element_' + e] for e in ELEMENTS]
        observed = [float(row['observed_share']) * 100 for row in rows]
        expected = [float(row['calendar_expected_share']) * 100 for row in rows]
        a = ax.bar(xs - .19, observed, width=.36, color="#337fa3", label="观察占比")
        b = ax.bar(xs + .19, expected, width=.36, color="#dbe3e8", edgecolor="#7c8b95", label="同出生年日历期望")
        for bars in [a, b]:
            ax.bar_label(bars, labels=[f"{bar.get_height():.2f}" for bar in bars], padding=3, fontsize=10)
        ax.set_title(title, fontsize=15, pad=14)
        ax.set_xticks(xs, ELEMENTS, fontsize=13)
        ax.set_ylim(0, ymax)
        ax.grid(axis="y", color="#d7e0e6", linewidth=.6)
        ax.set_axisbelow(True)
        for side in ['top', 'right']:
            ax.spines[side].set_visible(False)
        ax.tick_params(length=0)
    axes[0].set_ylabel("五个位点中的占比（%）", fontsize=12)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .835), frameon=False,
               ncol=2, fontsize=11.5)
    fig.text(.075, .045,
             "日干仅作参照，不计五行单位；无时柱。藏干口径每支只取一个代表干。\n"
             "日历期望保留实际出生年构成；五行基线并非各20%。柱高为描述，不代表统计显著。",
             ha="left", fontsize=10.5, linespacing=1.7, color="#405566")
    png, svg = output / 'UK_RS_overall_elements.png', output / 'UK_RS_overall_elements.svg'
    fig.savefig(png, dpi=190, facecolor="white")
    fig.savefig(svg, facecolor="white")
    plt.close(fig)
    return [png, svg]


def synthetic_qa():
    require(symmetric_limit([np.asarray([[-.26, .74]])]) == 1., "Outward symmetric scale failed")
    require(symmetric_limit([np.zeros((2, 3))]) == .5, "Zero scale failed")
    require(decade_label(1830, 60) == "1835–39\nn＝60", "Partial first decade label failed")
    require(decade_label(1950, 43) == "1950–59\nn＝43", "Ordinary decade label failed")
    require(len(GOD_PANELS[0][1]) == 10 and all(len(p[1]) == 5 for p in ELEMENT_PANELS),
            "All canonical categories must be retained")
    return {"status": "PASS", "study_data_loaded": False, "symmetric_outward_scales": True,
            "partial1830_bin_label": True, "all_canonical_categories": True,
            "no_pvalue_selection": True}


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2))
        return
    require(args.allow_uk_result_render, "Explicit completed-UK result rendering authorization is required")
    output = Path(args.output_dir)
    require(not output.exists(), "Figure output directory exists; no overwrite")
    source = Path(args.input)
    data = extract(json.loads(source.read_text()))
    font = set_font()
    god_limit = symmetric_limit([data['matrices'][p] for p in ['M0', 'M1']])
    element_limit = symmetric_limit([data['matrices'][p] for p in ['M0_element', 'M1_element']])
    limits = {'DM': symmetric_limit([data['matrices']['DM']]), 'M0': god_limit, 'M1': god_limit,
              'M0_element': element_limit, 'M1_element': element_limit}
    output.mkdir(parents=True, exist_ok=False)
    files = heatmap(data, GOD_PANELS, limits, output, 'UK_RS_decade_stems_gods_heatmaps',
                    '英国皇家学会：日主与十神的出生年代分布相对日历期望的偏离')
    files += heatmap(data, ELEMENT_PANELS, limits, output, 'UK_RS_decade_elements_heatmaps',
                     '英国皇家学会：五行的出生年代分布相对日历期望的偏离')
    files += overall_elements(data, output)
    manifest = {'schema': 'UK_RS_scientific_figures_v1', 'country': 'UK_Royal_Society',
                'source_result_sha256': sha(source), 'plot_code_sha256': sha(__file__),
                'strict_and_expanded_identical_single_plot': True, 'people': data['n_total'],
                'displayed_people': data['n_displayed'], 'common_adequate_decades': data['decades'],
                'decade_n': data['decade_n'], 'inclusion_rule': 'all_and_only_both_source_N>=20_decades',
                'other_bins_removed_from_analysis': False,
                'heatmap_units': 'observed_minus_same_birthyear_calendar_expected_share_percentage_points',
                'symmetric_color_limits_pp': limits, 'TenGod_scale_shared_M0_M1': True,
                'element_scale_shared_M0_M1': True, 'font_path': font,
                'significance_stars_or_p_selection': False,
                'figure_file_sha256': {p.name: sha(p) for p in files}}
    (output / 'FIGURE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'country': 'UK_Royal_Society', 'figures': len(files),
                      'common_decades': data['decades'], 'limits_pp': limits}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input')
    p.add_argument('--output-dir')
    p.add_argument('--allow-uk-result-render', action='store_true')
    p.add_argument('--synthetic-qa-only', action='store_true')
    main(p.parse_args())
