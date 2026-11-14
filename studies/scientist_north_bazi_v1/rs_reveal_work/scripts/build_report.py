#!/usr/bin/env python3
"""Package audited Royal Society results; no new statistical tests.

Importing this module never opens study results.  Execution requires all study
and visual QA reports to have PASS status and a remotely verified lock receipt.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "rs_reveal_work"
NAME = "scientist_UK_Royal_Society_reveal_v1"
COUNTRY = "UK_Royal_Society"
FAMILY_LABELS = {"DM10": "十天干日主", "M0": "十神：本气 M0", "M1": "十神：藏干优先 M1",
                 "M0_elements": "五行：本气 M0", "M1_elements": "五行：藏干优先 M1"}
CASE_LABELS = {"strict_primary": "严格主分析", "expanded": "扩展来源（同一人群）", "strict_broad": "广义官印／伤官印组件",
               "strict_noJie": "排除节气边界±1日", "strict_yearMonth": "固定出生年月日历零模型",
               "expanded_withoutLOC": "排除LOC引用元数据", "strict_withoutFields": "排除Fields交叠者"}
METRIC_LABELS = {"PI_count": "偏印平均个数／人", "SG_count": "伤官平均个数／人",
                 "GY_narrow": "官印相生必要组件比例", "SGY_narrow": "伤官配印必要组件比例",
                 "water_DM": "水日主比例（壬＋癸）", "DM_index": "十干日主总体不均匀（Pearson距离）"}
FIGURE_FILES = ["UK_RS_decade_stems_gods_heatmaps.png", "UK_RS_decade_stems_gods_heatmaps.svg",
                "UK_RS_decade_elements_heatmaps.png", "UK_RS_decade_elements_heatmaps.svg",
                "UK_RS_overall_elements.png", "UK_RS_overall_elements.svg"]
DISPLAY_COMMIT = "cf9143f9518865d5f33c61761903c0312ba5e3f4"


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def esc(value):
    return html.escape(str(value))


def pct(value):
    return "—" if value is None else f"{100 * value:.2f}%"


def number(value, decimals=3, signed=False):
    if value is None:
        return "—"
    return f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"


def pvalue(value):
    if value is None:
        return "—"
    return f"{value:.5f}" if value >= .0001 else f"{value:.4g}"


def table(headers, rows, first_left=True):
    return ('<div class="scroll"><table' + (' class="first-left"' if first_left else '') + '><thead><tr>' +
            ''.join('<th scope="col">' + esc(c) + '</th>' for c in headers) + '</tr></thead><tbody>' +
            ''.join('<tr>' + ''.join('<td>' + esc(c) + '</td>' for c in row) + '</tr>' for row in rows) +
            '</tbody></table></div>')


def country_table(case, primary=False):
    scalar = {x["metric"]: x for x in case.get("scalar_metrics", [])}
    rows = []
    for item in case.get("calendar_MC_tests", []):
        metric = item["metric"]
        x = scalar.get(metric)
        if x:
            count = metric in ["PI_count", "SG_count"]
            fmt = (lambda v: number(v, 4)) if count else pct
            obs, exp = fmt(x["observed_mean_or_rate"]), fmt(x["calendar_expected_mean_or_rate"])
            delta = number(x["observed_minus_expected"], 4, True) if count else number(100*x["observed_minus_expected"], 3, True) + "pp"
            ci = x.get("paired_excess_unadjusted_95CI")
            ci_text = "—" if ci is None else "[" + (", ".join(number(v, 4, True) for v in ci) if count else ", ".join(number(100*v, 3, True) for v in ci) + "pp") + "]"
        else:
            obs, exp, delta, ci_text = number(item.get("observed_Pearson_distance"), 5), "—", "—", "—"
        rows.append([METRIC_LABELS.get(metric, metric), obs, exp, delta,
                     pvalue(item.get("p_nominal_plus_one")), pvalue(item.get("p_Bonferroni_36_reference")),
                     "是" if primary and item.get("primary_Bonferroni_36_reject_0_05") else ("否" if primary else "仅敏感性参考"), ci_text])
    return table(["指标", "观察", "日历期望", "差值", "原始p", "Bonf36 p", "主分析拒绝", "差值95% CI（未校正）"], rows)


def main(args):
    work = Path(args.work).resolve()
    output = Path(args.output).resolve() if args.output else ROOT / NAME
    archive = output.with_suffix('.zip')
    require(not output.exists() and not archive.exists(), "Do not overwrite delivered results")
    receipt_path = work / "EXECUTION_RECEIPT.json"
    receipt = load(receipt_path)
    require(receipt.get("country") == COUNTRY and receipt.get("remote_plan_and_code_verified_before_summary") is True,
            "Verified UK execution receipt required")
    commit = receipt.get("commit", "")
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "Receipt needs a concrete Git commit")
    result_path = work / "RS_tables_results.json"
    country_path = work / "country/UK_country_results.json"
    tables_qa_path = work / "INDEPENDENT_QA.json"
    country_qa_path = work / "COUNTRY_INDEPENDENT_QA.json"
    figure_qa_path = work / "figures/VISUAL_QA.json"
    figure_manifest_path = work / "figures/FIGURE_MANIFEST.json"
    for p in [tables_qa_path, country_qa_path, figure_qa_path]:
        require(load(p).get("status") == "PASS", "QA must PASS before packaging: " + p.name)
    results, country = load(result_path), load(country_path)
    require(results["country"] == country["country"] == COUNTRY, "Only UK results permitted")
    require(results["expanded_equals_strict"] is True and results["source_groups_identical"] is True,
            "Source identity display contract differs")
    g = results["groups"]["strict"]
    require(g["people"] == 2293 and country["primary_n"] == 2293, "UK population differs from frozen2293")
    require(results["groups"]["expanded"]["reused_from"] == "strict", "Expanded must reuse strict results")
    require(load(tables_qa_path).get("hashes", {}).get("results", sha(result_path)) == sha(result_path),
            "Independent table QA result hash differs")
    figure_manifest = load(figure_manifest_path)
    require(figure_manifest["source_result_sha256"] == sha(result_path), "Figures must use these exact results")
    display_patch_path = work / "DISPLAY_PATCH.json"
    display_patch = load(display_patch_path) if display_patch_path.exists() else None
    if display_patch:
        require(display_patch["analysis_or_test_changed"] is False and display_patch["original_locked_script_preserved"] is True,
                "Display patch must preserve the statistical lock")
        require(display_patch["new_sha256"] == figure_manifest["plot_code_sha256"], "Display patch figure code differs")
    for name in FIGURE_FILES:
        p = work / "figures" / name
        require(p.exists() and figure_manifest["figure_file_sha256"][name] == sha(p), "Figure is missing or changed: " + name)
    git = f"https://github.com/agenhcx/bazi-public-figure-study/tree/{commit}/studies/scientist_north_bazi_v1/rs_reveal_work"
    case_map = {c["case"]: c for c in country["cases"]}
    primary = case_map["strict_primary"]
    level_by_id = {x["endpoint_id"]: x for x in g["levels"]}
    require(primary["person_ids_sha256"] == g["person_ids_sha256"], "Country and table engines selected different people")
    require(primary["n"] == g["people"], "Country and table person denominators differ")
    for x in primary["ten_gods_five_position_descriptive_only"]:
        y = level_by_id["M0_" + x["ten_god"]]
        require(x["observed_count_sum"] == y["observed_total"], "Country/table M0 observed count mismatch")
        require(abs(x["calendar_expected_count_mean_per_person"] * primary["n"] - y["calendar_expected_total"]) < 1e-8,
                "Country/table M0 calendar expectation mismatch")
    for x in primary["day_master_distribution"]:
        y = level_by_id["DM_" + x["stem"]]
        require(x["observed_people"] == y["observed_total"], "Country/table DM observed count mismatch")
        require(abs(x["calendar_expected_people"] - y["calendar_expected_total"]) < 1e-8,
                "Country/table DM calendar expectation mismatch")
    level_reject = [x for x in g["levels"] if x["reject_Holm40_0_05"]]
    trend_reject = [x for x in g["trends"] if x["reject_Holm30_0_05"]]
    country_reject = [x for x in primary["calendar_MC_tests"] if x.get("primary_Bonferroni_36_reject_0_05")]
    parts = ['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>英国皇家学会：日主、十神、五行与出生年代</title><style>
body{font:16px/1.65 system-ui,"Noto Sans CJK SC",sans-serif;color:#172536;max-width:1360px;margin:28px auto;padding:0 20px}h1{font-size:28px}h2{font-size:23px;margin-top:34px}h3{font-size:19px}.note{background:#edf5fa;border-left:4px solid #337d9b;padding:14px 18px}.scroll{overflow-x:auto}table{border-collapse:collapse;margin:16px 0;font-variant-numeric:tabular-nums;white-space:nowrap}th,td{padding:7px 11px;border-bottom:1px solid #d5dfe6;text-align:right}.first-left th:first-child,.first-left td:first-child{text-align:left}th{background:#eaf0f5}tbody tr:nth-child(even){background:#f7f9fb}summary{cursor:pointer;font-weight:650;padding:7px 0}a{color:#206387}small{color:#4a5c70}code{word-break:break-all}figure{margin:24px 0}figure img{width:100%;height:auto;border:1px solid #e1e7ed}figcaption{font-size:14px;color:#465b70}</style><h1>英国皇家学会：日主、十神、五行数量与出生年代</h1>''']
    parts.append('<p class="note">固定北半球、剔除官方诺奖重叠的皇家学会院士2293人。严格S1+S2与扩展S1+S2+S3的人物和生日完全相同，所有新增水平与年代结果只计算一次；扩展组的重复展示<strong>不是独立验证</strong>。以下“英国”指合资格皇家学会院籍，<strong>不等于英国国籍或英国出生地</strong>。</p>')
    parts.append('<p>出生窗口1835—1985，院士纳入时点截至2025；同一院内每人权重1。保留原跨院成员资格：与美国已揭盲组共享的8人仍按单院口径保留，不能因此把两院比较当完全独立人群。保留5名Fields交叠者，另有预定排除Fields敏感性分析；不生成含诺奖英国全体的性状表。</p>')
    parts.append('<p>每人5个有效位点：年干、月干、年支、月支、日支的代表干。日干只作十神参照，不计入五行数量、也不作为透干来源；无时柱。M0取支本气；M1按冻结规则，在年／月干透出的藏干中依本气→中气→余气取一个，均不透则回退本气，每人仍为5单位。水日主的人数比例与五个位点中水的数量占比是不同指标。</p>')
    parts.append('<h2>本次检验范围与拒绝结果</h2>')
    parts.append(table(["检验组", "固定范围", "本次校正后拒绝数量"], [
        ["逐院原6项补充诊断", "六院×六指标，Bonferroni36；本次只开英国6项", str(len(country_reject)) + '/6'],
        ["英国新增40项水平分布", "日主10＋两套十神20＋两套五行10，Holm40", str(len(level_reject)) + '/40'],
        ["英国新增30项年代线性趋势", "日主10＋两套十神20，Holm30；五行年代仅描述", str(len(trend_reject)) + '/30']]))
    parts.append('<p>三组校正范围各有预先固定的用途，不能把不同组的p值混作同一个检验。原18项总体检验仍未运行、规则不变；既有美国结果及其校正不变。原6项中前5项为上尾富集检验，十干总体分布为Pearson距离上尾；新增40项与30项均为相对日历期望的双侧检验。</p>')
    rejection_rows = []
    for x in country_reject:
        rejection_rows.append(['原6项/Bonf36', METRIC_LABELS.get(x['metric'], x['metric']), pvalue(x['p_nominal_plus_one']), pvalue(x['p_Bonferroni_36_reference'])])
    for x in level_reject:
        direction = '高于期望' if x['excess_percentage_points'] > 0 else '低于期望'
        rejection_rows.append(['水平/Holm40', x['endpoint_id'] + '：' + direction, pvalue(x['p_two_sided']), pvalue(x['p_Holm40'])])
    for x in trend_reject:
        direction = '每出生十年上升' if x['calendar_excess_slope_pp_per_decade'] > 0 else '每出生十年下降'
        rejection_rows.append(['年代/Holm30', x['endpoint_id'] + '：' + direction, pvalue(x['p_nominal_two_sided']), pvalue(x['p_Holm30'])])
    parts.append(table(['检验组', '校正后拒绝项目', '原始p', '校正p'], rejection_rows) if rejection_rows else '<p>这三组检验在英国主分析中均没有校正后拒绝项目；下列完整表仍保留每一项观察值、期望和p值。</p>')
    parts.append('<h2>完整水平统计</h2><p>日主分母2293人，其余表分母11465个位点。位点只用于展示比例，检验单位始终是人：不能将11465个位点当成独立样本。观察／期望比R&gt;1表示数值高于基线，不自动代表统计显著；基线既不是每神10%，也不是每行20%。</p>')
    for family, label in FAMILY_LABELS.items():
        selected = [x for x in g['levels'] if x['family'] == family]
        rows = [[x['label'], x['observed_total'], number(x['calendar_expected_total'], 2), pct(x['observed_share']), pct(x['calendar_expected_share']),
                 number(x['excess_percentage_points'], 3, True), number(x['enrichment_ratio']), pvalue(x['p_two_sided']), pvalue(x['p_Holm40'])] for x in selected]
        parts.append('<h3>' + esc(label) + '</h3>' + table(['类别', '观察个数', '期望个数', '观察占比', '日历期望', '差值/百分点', 'R观察/期望', '双侧p', 'Holm40 p'], rows))
    parts.append('<figure><a href="figures/UK_RS_overall_elements.svg"><img src="figures/UK_RS_overall_elements.png" alt="英国五行总体观察占比与同出生年日历期望"></a><figcaption>五行总体构成；图为描述性展示，显著性判断见Holm40表。</figcaption></figure>')
    parts.append('<h2>出生年代分布与趋势</h2>')
    parts.append('<p>按公历出生年分十年段：1900年代＝1900—1909年；1830年代只有1835—1839年，1980年代只有1980—1985年落在窗口内。所有16段均保留。空段计数和期望为0，比例用“—”；人数少的段保留但不能把大幅百分比起伏解释成稳定变化。</p>')
    parts.append(table(['出生年代', '人数', '两来源均≥20人'], [[str(b['decade']) + '—' + str(b['decade']+9), b['n'], '是' if b['decade'] in results['common_adequate_decades'] else '否'] for b in g['bins']]))
    adequate = g['common_adequate_bins_desc']
    parts.append('<p>热图仅显示两来源人数均≥20的十年段（由于来源相同，等于单组N≥20）：' + esc('、'.join(str(d) for d in results['common_adequate_decades'])) + '，共' + str(adequate['people']) + '人；完整样本2293人仍全部进入主趋势检验。颜色为观察占比减去该段自身出生年日历期望，<strong>热图颜色不是显著性标记</strong>。</p>')
    parts.append('<figure><a href="figures/UK_RS_decade_stems_gods_heatmaps.svg"><img src="figures/UK_RS_decade_stems_gods_heatmaps.png" alt="英国按出生十年的日主与十神相对日历期望差值"></a><figcaption>日主与两套十神的年代描述；列下方标人数。</figcaption></figure>')
    parts.append('<figure><a href="figures/UK_RS_decade_elements_heatmaps.svg"><img src="figures/UK_RS_decade_elements_heatmaps.png" alt="英国按出生十年的两套五行相对日历期望差值"></a><figcaption>五行逐十年仅做描述，没有新增五行年代趋势假设检验。</figcaption></figure>')
    common_map = {x['endpoint_id']: x for x in adequate['trends']}
    parts.append('<h3>全部30项线性趋势</h3><p>斜率单位为出生年代每后移十年，比例变化多少个百分点。分别列原始斜率、日历自身期望斜率、两者差值；后者是检验对象。主模型为按人数加权的十年均值线性回归，等价于每个人分配其出生十年值的OLS。未检出线性趋势不能排除非线性起伏。共同充分年代的斜率仅为描述性敏感性，不增加检验。</p>')
    for family in ['DM10', 'M0', 'M1']:
        rows = []
        for x in g['trends']:
            if x['family'] != family:
                continue
            c = common_map[x['endpoint_id']]
            rows.append([x['label'], number(x['raw_slope_pp_per_decade'], 4, True), number(x['calendar_expected_slope_pp_per_decade'], 4, True),
                         number(x['calendar_excess_slope_pp_per_decade'], 4, True), pvalue(x['p_nominal_two_sided']), pvalue(x['p_Holm30']),
                         number(c.get('raw_slope_pp_per_decade'), 4, True), number(c.get('calendar_excess_slope_pp_per_decade'), 4, True)])
        parts.append('<h3>' + esc(FAMILY_LABELS[family]) + '</h3>' + table(['类别', '原始斜率', '日历期望斜率', '超额斜率', '原始p', 'Holm30 p', '充分年代原始斜率', '充分年代超额斜率（描述）'], rows))
    parts.append('<h3>完整16段×40项数值</h3><p>每格按“观察个数；观察占比／日历期望占比”排列。所有原始与期望总数、占比差值也保留在RS_tables_results.json中。</p>')
    for family, label in FAMILY_LABELS.items():
        definitions = [x for x in results['endpoint_order'] if x['family'] == family]
        rows = []
        for b in g['bins']:
            row = [str(b['decade']) + '年代', b['n']]
            for e in definitions:
                x = b['endpoints'][e['id']]
                row.append(str(x['observed_total']) + '；' + pct(x['observed_share']) + '／' + pct(x['calendar_expected_share']))
            rows.append(row)
        parts.append('<details><summary>' + esc(label) + '</summary>' + table(['年代', '人数'] + [e['label'] for e in definitions], rows) + '</details>')
    parts.append('<h2>年干与月干：纯描述附表</h2><p>主文“十天干”以日主为准。下表另外保留年干、月干分布，未新增水平或趋势检验；日干表已在日主10项中展示。</p>')
    for key, label in [('year_stem', '年干'), ('month_stem', '月干')]:
        rows = [[x['stem'], x['observed_people'], number(x['calendar_expected_people'], 2), pct(x['observed_share']), pct(x['calendar_expected_share'])] for x in g['HeavenlyStem_positions'][key]]
        parts.append('<h3>' + label + '</h3>' + table(['天干', '观察人数', '期望人数', '观察占比', '日历期望'], rows))
    parts.append('<h2>原6项逐院补充诊断</h2><p>这些定义和统计函数沿用原国家揭盲锁，Bonferroni36保留六院×六项的范围。本次只计算英国，其他尚未揭盲院所未打开。官印与伤官配印为冻结的必要组件定义，不是完整传统格局判定。</p>')
    parts.append(country_table(primary, primary=True))
    parts.append('<h3>全部7个预定case：主分析＋6项敏感性</h3><p>敏感性不用于补救主分析，也不从中挑选最有利版本。其Bonf36数值只是参考。bootstrap以完整人为重采样单位，区间未经多重比较校正；各case完整参数与结果在UK_country_results.json中。</p>')
    for case in country['cases']:
        parts.append('<details><summary>' + esc(CASE_LABELS.get(case['case'], case['case'])) + '，N=' + str(case['n']) + '</summary>')
        parts.append('<p>日历条件：' + esc(case.get('calendar_condition', '')) + '；组件口径：' + esc(case.get('cooccurrence_encoding', '')) + '；节气边界±1日排除：' + ('是' if case.get('observed_and_calendar_Jie_pm1_excluded') else '否') + '。</p>')
        parts.append(country_table(case, primary=case['case'] == 'strict_primary'))
        trend = case.get('birthyear_GY_trend', {})
        if trend.get('status') == 'descriptive_only':
            parts.append('<p>官印组件按实际出生年拟合的描述性斜率：原始' + number(100*trend['raw_rate_slope_per_decade'], 4, True) + 'pp/十年，扣除日历期望后' + number(100*trend['calendar_excess_rate_slope_per_decade'], 4, True) + 'pp/十年；无假设检验，亦不是原总体H2d。</p>')
        parts.append('</details>')
    parts.append('<h2>方法、复核与文件</h2><p>日历零模型逐人固定公历出生年，在该年全部有效公历日期中等概率取日；原年月匹配和节气排除敏感性另按原锁执行。它不是实测人口出生分布，也没有补入未知出生时辰。新增水平检验使用每人完整日期得到的0—5计数或日主0／1指标，卷积得到总数的有限支持分布；期望与双侧尾界用有理数精确计算，概率用float64。年代检验沿用99999次固定种子PCG64模拟，整数中心化双侧包含并列值，不自适应增加次数。</p>')
    parts.append('<p>水平与年代独立复核、原国家诊断独立复核及图像视觉复核均PASS。独立代码逐日字面重建55,152个日期，并检查冻结选样、完整水平与年代表、OLS与预选p值；没有改变冻结生日、地点、源等级或院籍。所有结果而非仅显著项均保留。</p>')
    parts.append('<p><a href="' + git + '">运行前方案与代码Git锁</a>：<code>' + esc(commit) + '</code>。本ZIP不复制Git代码。RS_tables_results.json为完整40水平／30趋势／40×16年代表；UK_country_results.json为原6项及全部case；INDEPENDENT_QA.json、COUNTRY_INDEPENDENT_QA.json、EXECUTION_RECEIPT.json及figures目录提供复核和图像记录。SHA256.json逐文件记录哈希。</p>')
    if display_patch:
        parts.append('<p>绘图读取最终结果时仅修正了字段名levels/bins，原锁定绘图文件保留，统计与图像筛选算法没有改变。展示补丁另见<a href="https://github.com/agenhcx/bazi-public-figure-study/commit/' + DISPLAY_COMMIT + '">' + DISPLAY_COMMIT + '</a>及DISPLAY_PATCH.json；图像仍绑定同一统计结果文件哈希。</p>')
    parts.append('</html>')
    output.mkdir(parents=True)
    (output / 'UK_REPORT.html').write_text('\n'.join(parts))
    (output / 'README.txt').write_text('英国皇家学会统计报告\n\n打开 UK_REPORT.html 阅读日主十干、M0/M1全十神、五位五行、完整出生年代与原6项逐院诊断。\n严格与扩展均2293人，ID与生日相同，只计算一次，不是独立验证。\n北半球、出生窗1835–1985、剔除官方诺奖重叠；院籍不等于国籍。\n新增40水平Holm40，另30年代线性趋势Holm30；原六院36诊断不变，原18总体未运行。\n每人五位，日干只作参照；不计时柱；M1每支只选一个藏干代表。\n全部统计与视觉QA PASS。图像均为描述性展示。\n代码与冻结方案存于Git：' + git + '\n')
    files = {result_path: 'RS_tables_results.json', country_path: 'UK_country_results.json',
             tables_qa_path: 'INDEPENDENT_QA.json', country_qa_path: 'COUNTRY_INDEPENDENT_QA.json', receipt_path: 'EXECUTION_RECEIPT.json'}
    for source, target in files.items():
        shutil.copy2(source, output / target)
    if display_patch:
        shutil.copy2(display_patch_path, output / display_patch_path.name)
        display_receipt = {"schema": "UK_RS_display_render_receipt_v1", "display_git_commit": DISPLAY_COMMIT,
                           "statistical_execution_commit": commit, "source_result_sha256": sha(result_path),
                           "plot_code_sha256": figure_manifest["plot_code_sha256"], "visual_QA": "PASS",
                           "analysis_or_test_changed": False, "plot_files_match_manifest": True}
        (output / 'DISPLAY_RENDER_RECEIPT.json').write_text(json.dumps(display_receipt, ensure_ascii=False, indent=2) + '\n')
    shutil.copytree(work / 'figures', output / 'figures')
    manifest = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    (output / 'SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():
                z.write(p, str(p.relative_to(output.parent)))
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None, 'Archive CRC check failed')
        for rel, digest in manifest.items():
            require(hashlib.sha256(z.read(output.name + '/' + rel)).hexdigest() == digest, 'Archive member mismatch')
    print(json.dumps({'status': 'PASS', 'archive': str(archive), 'sha256': sha(archive),
                      'bytes': archive.stat().st_size, 'member_count': len(manifest) + 1,
                      'rejections': {'Bonf36_primary6': len(country_reject), 'Holm40_levels': len(level_reject), 'Holm30_trends': len(trend_reject)}}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', default=str(WORK))
    parser.add_argument('--output')
    main(parser.parse_args())
