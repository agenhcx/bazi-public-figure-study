#!/usr/bin/env python3
"""Render NAS-only descriptive decade heatmaps from completed trend output.

No chart data are read during import. Figures use only the predeclared common
birth-decade bins having at least20 people in each source group. The complete
bin table and full-sample trend tests remain in the underlying analysis output.
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
PANELS = [
    ("DM", STEMS, "日主：按人数计"),
    ("M0", GODS, "十神本气 M0：五位占比"),
    ("M1", GODS, "十神藏干优先 M1：五位占比"),
]
GROUP_LABELS = {"strict": "严格来源 S1＋S2", "expanded": "扩展来源 S1＋S2＋S3"}


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def set_font():
    # These paths are normal Noto package locations; choose only an observed
    # existing file, never silently export Chinese labels as missing glyphs.
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise RuntimeError("A Chinese-capable Noto CJK font is required for scientific figure labels")
    font_manager.fontManager.addfont(str(path))
    prop = font_manager.FontProperties(fname=str(path))
    plt.rcParams.update({
        "font.family": prop.get_name(),
        "axes.unicode_minus": False,
        "svg.fonttype": "path",
        "font.size": 11,
        "axes.titleweight": "medium",
    })
    return str(path)


def extract(data):
    require(data.get("country") == "NAS", "This figure renderer is restricted to completed NAS results")
    common = [int(y) for y in data["common_adequate_decades"]]
    require(common == sorted(set(common)) and bool(common), "Common-decade list is empty, duplicated or unsorted")
    prepared = {}
    for key in ("strict", "expanded"):
        source = data["groups"][key]
        bins = {int(row["decade"]): row for row in source["bins"]}
        require(all(y in bins and int(bins[y]["n"]) >= 20 for y in common),
                "Figure inclusion rule requires at least20 people per source and decade")
        matrices = {}
        for prefix, categories, title in PANELS:
            ids = [prefix + "_" + c for c in categories]
            matrix = np.asarray([
                [bins[y]["endpoints"][endpoint]["excess_percentage_points"] for y in common]
                for endpoint in ids
            ], dtype=float)
            require(matrix.shape == (10, len(common)) and np.isfinite(matrix).all(),
                    "Missing/nonfinite decade endpoint for " + key + "/" + prefix)
            matrices[prefix] = matrix
        ns = [int(bins[y]["n"]) for y in common]
        prepared[key] = {"matrices": matrices, "n_total": int(source["people"]),
                         "decade_n": ns, "n_displayed": sum(ns)}
    return common, prepared


def symmetric_limit(matrices):
    maximum = max(float(np.max(np.abs(v))) for v in matrices)
    # A shared, honest scale is computed from every displayed cell in both
    # groups. Round outward to half a percentage point for readable ticks.
    return max(0.5, math.ceil(maximum * 2) / 2)


def plot_one(group, common, prepared, limits, output):
    datum = prepared[group]
    fig, axes = plt.subplots(1, 3, figsize=(18.8, 7.0))
    fig.subplots_adjust(left=0.045, right=0.985, top=0.80, bottom=0.235, wspace=0.32)
    fig.suptitle("美国 NAS 非诺奖院士：出生年代分布相对日历期望的偏离", fontsize=20, y=0.975)
    fig.text(0.5, 0.895,
             f"{GROUP_LABELS[group]}　整组 n＝{datum['n_total']}；图示共同年代 n＝{datum['n_displayed']}",
             ha="center", fontsize=13, color="#344b5c")
    xlabels = [f"{year}–{str(year + 9)[-2:]}\nn＝{n}" for year, n in zip(common, datum["decade_n"])]
    for ax, (prefix, categories, title) in zip(axes, PANELS):
        values = datum["matrices"][prefix]
        limit = limits[prefix]
        image = ax.imshow(values, cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
                          interpolation="nearest", aspect="auto")
        ax.set_title(title, fontsize=14, pad=12)
        ax.set_xticks(np.arange(len(common)), xlabels, fontsize=9)
        ax.set_yticks(np.arange(10), categories, fontsize=11)
        ax.tick_params(axis="both", length=0)
        ax.set_xlabel("出生年代", labelpad=11, fontsize=11)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks(np.arange(-0.5, len(common), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, 10, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=0.8)
        ax.tick_params(which="minor", length=0)
        for i in range(10):
            for j in range(len(common)):
                value = float(values[i, j])
                label = "0.0" if abs(value) < 0.05 else f"{value:+.1f}"
                ax.text(j, i, label, ha="center", va="center", fontsize=8.8,
                        color="white" if abs(value) >= 0.64 * limit else "#172b3a")
        colorbar = fig.colorbar(image, ax=ax, location="bottom", pad=0.235, fraction=0.052,
                               ticks=[-limit, -limit / 2, 0, limit / 2, limit])
        colorbar.ax.tick_params(labelsize=9, length=2)
        colorbar.set_label("实测比例 − 同出生年日历期望（百分点）", fontsize=10, labelpad=4)
    fig.text(0.045, 0.055,
             "仅显示严格与扩展组均不少于20人的共同出生年代；其余年代仍保留在完整分段表和全样本趋势分析中。\n"
             "暖色＝高于期望；冷色＝低于期望。颜色与单元格数值为描述，不代表统计显著。两组共享色阶；两种十神编码共享色阶。",
             ha="left", va="bottom", fontsize=10, linespacing=1.7, color="#405566")
    basename = "NAS_decade_" + group + "_heatmaps"
    png, svg = output / (basename + ".png"), output / (basename + ".svg")
    fig.savefig(png, dpi=190, facecolor="white")
    fig.savefig(svg, facecolor="white")
    plt.close(fig)
    return [png, svg]


def main(args):
    require(args.allow_nas_result_render, "Explicit completed-NAS rendering authorization is required")
    output = Path(args.output_dir)
    require(not output.exists(), "Figure output directory exists; no overwrite")
    data = json.loads(Path(args.input).read_text())
    common, prepared = extract(data)
    font = set_font()
    dm_limit = symmetric_limit([prepared[k]["matrices"]["DM"] for k in prepared])
    god_limit = symmetric_limit([prepared[k]["matrices"][p] for k in prepared for p in ("M0", "M1")])
    limits = {"DM": dm_limit, "M0": god_limit, "M1": god_limit}
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for key in ("strict", "expanded"):
        files += plot_one(key, common, prepared, limits, output)
    manifest = {
        "schema": "NAS_birth_decade_scientific_heatmaps_v1",
        "country": "NAS", "source_result_sha256": sha(args.input), "plot_code_sha256": sha(__file__),
        "common_adequate_decades": common,
        "inclusion_rule": "both strict and expanded have at least20 people in the decade; all30canonical categories displayed",
        "other_bins_removed_from_analysis": False,
        "matrix_units": "observed_minus_same_birthyear_calendar_expected_share_percentage_points",
        "symmetric_color_limits_pp": limits,
        "color_scale_shared_across_groups": True, "TenGod_scale_shared_across_M0_M1": True,
        "font_path": font, "significance_stars_or_p_selection": False,
        "groups": {k: {key: value for key, value in datum.items() if key != "matrices"}
                   for k, datum in prepared.items()},
        "figure_file_sha256": {path.name: sha(path) for path in files},
    }
    (output / "FIGURE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "country": "NAS", "figures": len(files),
                      "common_decades": common, "limits_pp": limits}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-nas-result-render", action="store_true")
    main(parser.parse_args())
