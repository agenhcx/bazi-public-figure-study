#!/usr/bin/env python3
"""Post-run display-only revision: separate decade, N, and K labels. No new tests."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

TARGETS = ['CAS_xin', 'NAS_water']
SOURCES = ['strict', 'expanded']
LABELS = {'CAS_xin': '中国科学院：辛日主', 'NAS_water': '美国科学院：壬癸水日主'}
SHORT = {'CAS_xin': '辛', 'NAS_water': '水'}
SOURCE_LABEL = {'strict': '严格来源 S1＋S2', 'expanded': '扩展来源 S1＋S2＋S3'}
DECADES = {'CAS_xin': list(range(1890, 1970, 10)), 'NAS_water': list(range(1890, 1960, 10))}
PEOPLE = {'CAS_xin': {'strict': 821, 'expanded': 904}, 'NAS_water': {'strict': 908, 'expanded': 1462}}


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def font():
    p = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    require(p.exists(), 'Chinese-capable Noto font is required')
    font_manager.fontManager.addfont(str(p))
    prop = font_manager.FontProperties(fname=str(p))
    plt.rcParams.update({'font.family': prop.get_name(), 'axes.unicode_minus': False,
                         'svg.fonttype': 'path', 'font.size': 11})
    return str(p)


def extract(data):
    require(set(data['groups']) == set(TARGETS), 'Only the two fixed targets may be plotted')
    result = {}
    for target in TARGETS:
        source_groups = data['groups'][target]
        require(set(source_groups) == set(SOURCES), 'Both fixed source groups required')
        result[target] = {}
        for source in SOURCES:
            g = source_groups[source]
            require(g['people'] == PEOPLE[target][source], 'Frozen cohort size differs')
            bins = g['bins']
            require([int(b['decade']) for b in bins] == list(range(1830, 1990, 10)), 'Full decade boundaries differ')
            require(sum(int(b['n']) for b in bins) == g['people'], 'Bin people do not sum to cohort')
            require(sum(int(b['observed_target_people']) for b in bins) == g['target_people'], 'Bin targets do not sum to K')
            picked = [b for b in bins if b['local_test_eligible']]
            require([int(b['decade']) for b in picked] == DECADES[target], 'Display must use the preselected common N>=20 bins')
            arrays = {key: np.asarray([b[key] for b in picked], dtype=float) for key in
                      ['observed_share', 'calendar_expected_share', 'conditional_expected_share']}
            require(all(np.isfinite(a).all() and np.all((a >= 0) & (a <= 1)) for a in arrays.values()), 'Invalid plotted proportions')
            require(all(int(b['n']) >= 20 for b in picked), 'Tiny bin included in figure')
            result[target][source] = {'group': g, 'bins': picked, 'arrays': arrays,
                                     'displayed_people': sum(int(b['n']) for b in picked),
                                     'displayed_targets': sum(int(b['observed_target_people']) for b in picked)}
        require([b['decade'] for b in result[target]['strict']['bins']] ==
                [b['decade'] for b in result[target]['expanded']['bins']], 'Source supports differ')
    return result


def plot(data, output):
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.subplots_adjust(left=.065, right=.985, top=.82, bottom=.19, hspace=.68, wspace=.19)
    fig.suptitle('中国辛日主与美国水日主：哪些出生年代数值偏高？', fontsize=21, y=.978)
    fig.text(.5, .932, '观察占比、出生年日历期望，以及固定整组目标人数 K 后的年代期望',
             ha='center', fontsize=13, color='#3b5362')
    handles = None
    manifest_panels = []
    for col, target in enumerate(TARGETS):
        maximum = max(float(a.max()) for source in SOURCES for a in data[target][source]['arrays'].values()) * 100
        ymax = max(25., math.ceil((maximum + 3) / 5) * 5)
        for row, source in enumerate(SOURCES):
            ax = axes[row, col]
            d = data[target][source]; g = d['group']; bins = d['bins']; a = d['arrays']; xs = np.arange(len(bins))
            bars = ax.bar(xs, a['observed_share'] * 100, width=.62, color='#4386a4', label='观察占比', zorder=3)
            calendar, = ax.plot(xs, a['calendar_expected_share'] * 100, color='#7d8790', linestyle='--',
                                linewidth=1.8, marker='o', markersize=3, label='同出生年日历期望', zorder=4)
            conditional, = ax.plot(xs, a['conditional_expected_share'] * 100, color='#172b3b', linestyle='-.',
                                   linewidth=1.9, marker='s', markersize=3, label='固定整组目标人数 K 后的年代期望', zorder=5)
            ax.bar_label(bars, labels=[f'{100*v:.1f}%' for v in a['observed_share']], padding=4, fontsize=10, zorder=6, bbox={'facecolor':'white','edgecolor':'none','pad':.7,'alpha':.95})
            title = f"{LABELS[target]} · {SOURCE_LABEL[source]}\n整组 n＝{g['people']}，{SHORT[target]}日主 K＝{g['target_people']}"
            ax.set_title(title, fontsize=13, pad=14)
            labels = [f"{b['decade']}–{str(b['decade']+9)[-2:]}\nn＝{b['n']}\n{SHORT[target]}＝{b['observed_target_people']}" for b in bins]
            ax.set_xticks(xs, labels, fontsize=9)
            ax.set_ylim(0, ymax); ax.set_ylabel('人数占比（%）', fontsize=11)
            ax.grid(axis='y', color='#dbe3e8', linewidth=.7, zorder=0); ax.set_axisbelow(True)
            ax.tick_params(axis='both', length=0)
            for side in ['top', 'right']:
                ax.spines[side].set_visible(False)
            ax.text(.99, .975, f"图示 n＝{d['displayed_people']}，{SHORT[target]}＝{d['displayed_targets']}",
                    transform=ax.transAxes, ha='right', va='top', color='#4b6170', fontsize=9.5)
            if handles is None:
                handles = [bars, calendar, conditional]
            manifest_panels.append({'target': target, 'source': source, 'people': g['people'], 'K': g['target_people'],
                                    'displayed_people': d['displayed_people'], 'displayed_targets': d['displayed_targets'],
                                    'decades': [b['decade'] for b in bins], 'shared_target_ymax': ymax})
    fig.legend(handles, ['观察占比', '同出生年日历期望', '固定整组目标人数 K 后的年代期望'],
               loc='upper center', bbox_to_anchor=(.5, .9), frameon=False, ncol=3, fontsize=11)
    fig.text(.065, .047,
             '只画事先规定的两来源均不少于20人的年代；全部16个十年段和小样本人数保留在报告。\n'
             '黑线控制整组已经有多少辛／水日主，用于区分“整体偏多”与“集中在某些年代”。柱高及颜色本身不表示显著性。\n'
             '扩展组包含严格组，是来源敏感性对照，不是独立验证。日主类别不同于五个位点的五行总量。',
             fontsize=10.5, linespacing=1.6, color='#405767')
    png = output / 'DM_targeted_birth_decades.png'; svg = output / 'DM_targeted_birth_decades.svg'
    fig.savefig(png, dpi=190, facecolor='white'); fig.savefig(svg, facecolor='white'); plt.close(fig)
    return [png, svg], manifest_panels


def synthetic_qa():
    fake = {'groups': {}}
    for target in TARGETS:
        fake['groups'][target] = {}
        for source in SOURCES:
            n = PEOPLE[target][source]; chosen = DECADES[target]; count = len(chosen)
            ns = [n // count] * count; ns[-1] += n - sum(ns); bins = []; j = 0
            for decade in range(1830, 1990, 10):
                eligible = decade in chosen
                number = ns[j] if eligible else 0
                if eligible:j += 1
                k = number // 10
                bins.append({'decade': decade, 'n': number, 'observed_target_people': k,
                             'observed_share': k/number if number else None,
                             'calendar_expected_share': .1 if number else None,
                             'conditional_expected_share': .11 if number else None,
                             'local_test_eligible': eligible})
            fake['groups'][target][source] = {'people': n, 'target_people': sum(b['observed_target_people'] for b in bins), 'bins': bins}
    extracted = extract(fake)
    require(len(extracted) == 2 and len(extracted['CAS_xin']['strict']['bins']) == 8 and
            len(extracted['NAS_water']['strict']['bins']) == 7, 'Synthetic complete schema failed')
    return {'status': 'PASS', 'real_study_results_loaded': False, 'four_panel_schema': True,
            'fixed_decades_and_counts': True, 'no_pvalue_based_display': True, 'target_shared_source_yaxes': True}


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2)); return
    require(args.allow_completed_result_render, 'Explicit completed-result rendering required')
    source = Path(args.input); output = Path(args.output_dir)
    require(not output.exists(), 'Do not overwrite figures')
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get('remote_plan_and_code_verified_before_summary') is True, 'Verified analysis receipt required')
    raw = json.loads(source.read_text()); data = extract(raw); used_font = font(); output.mkdir(parents=True)
    files, panels = plot(data, output)
    manifest = {'schema': 'DM_targeted_decade_figure_manifest_v1', 'status': 'PASS',
                'input_results_sha256': sha(source), 'plot_code_sha256': sha(__file__),
                'execution_lock_commit': receipt['commit'], 'panels': panels,
                'display_revision': 'postrun_layout_v2_three_line_counts',
                'statistics_and_data_changed': False,
                'original_locked_plot_sha256': sha(Path(__file__).with_name('plot_dm_decades.py')),
                'font_file': used_font, 'files': {p.name: sha(p) for p in files},
                'all_preselected_bars_shown': True, 'pvalue_or_significance_selection': False,
                'description_only_not_significance_encoding': True}
    (output/'FIGURE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': 'PASS', 'files': [str(p) for p in files], 'panels': 4}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-qa-only', action='store_true')
    parser.add_argument('--allow-completed-result-render', action='store_true')
    for name in ['input', 'output-dir', 'execution-receipt']:
        parser.add_argument('--'+name)
    main(parser.parse_args())
