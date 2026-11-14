#!/usr/bin/env python3
"""Package the three separately audited institution reveals; no new tests.

No study outputs are opened on import. Country, source, and inference families
remain separate throughout; batch correction is read from the root receipt.
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
WORK = ROOT / "remaining_reveal_work"
NAME = "scientist_DE_FR_JP_reveal_v1"
LABELS = {"DE_Leopoldina": "德国科学院 Leopoldina", "France": "法国科学院", "Japan": "日本学士院"}
FAMILIES = {"DM10": "十天干日主", "M0": "十神：本气 M0", "M1": "十神：藏干优先 M1",
            "M0_elements": "五行：本气 M0", "M1_elements": "五行：藏干优先 M1"}
CASE_LABELS = {"strict_primary": "严格主分析", "expanded": "扩展来源", "strict_broad": "广义官印／伤官印组件",
               "strict_noJie": "排除节气边界±1日", "strict_yearMonth": "固定出生年月日历零模型",
               "expanded_withoutLOC": "排除LOC引用元数据", "strict_withoutFields": "排除Fields交叠者"}
METRIC_LABELS = {"PI_count": "偏印平均个数／人", "SG_count": "伤官平均个数／人", "GY_narrow": "正官＋正印必要共现组件",
                 "SGY_narrow": "伤官＋正印必要共现组件", "water_DM": "水日主比例（壬＋癸）", "DM_index": "十干日主总体Pearson距离"}
CSS = '''<style>body{font:16px/1.65 system-ui,"Noto Sans CJK SC",sans-serif;color:#172536;max-width:1360px;margin:28px auto;padding:0 20px}h1{font-size:28px}h2{font-size:23px;margin-top:34px}h3{font-size:19px}.note{background:#edf5fa;border-left:4px solid #337d9b;padding:14px 18px}.scroll{overflow-x:auto}table{border-collapse:collapse;margin:16px 0;font-variant-numeric:tabular-nums;white-space:nowrap}th,td{padding:7px 11px;border-bottom:1px solid #d5dfe6;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#eaf0f5}tbody tr:nth-child(even){background:#f7f9fb}summary{cursor:pointer;font-weight:650;padding:7px 0}a{color:#206387}code{word-break:break-all}figure{margin:24px 0}figure img{width:100%;height:auto;border:1px solid #e1e7ed}figcaption{font-size:14px;color:#465b70}</style>'''


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def esc(x):
    return html.escape(str(x))


def pct(x):
    return "—" if x is None else f"{100*x:.2f}%"


def num(x, decimals=3, signed=False):
    return "—" if x is None else (f"{x:+.{decimals}f}" if signed else f"{x:.{decimals}f}")


def pv(x):
    return "—" if x is None else (f"{x:.5f}" if x >= .0001 else f"{x:.4g}")


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th scope="col">' + esc(c) + '</th>' for c in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(c) + '</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def page_start(title):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title>' + CSS + '<h1>' + esc(title) + '</h1>'


def batch_maps(batch):
    """Accept the root's documented rows, with explicit IDs not positional joins."""
    answer = {"levels": {}, "trends": {}}
    for kind, field in [("levels", "p_Holm120"), ("trends", "p_Holm90")]:
        rows = batch.get(kind, batch.get(kind + "_rows", []))
        if isinstance(rows, dict):
            rows = rows.get("rows", rows.get("results", []))
        require(isinstance(rows, list), "Batch correction rows are missing")
        for row in rows:
            institution = row.get("institution", row.get("country"))
            endpoint = row.get("endpoint_id", row.get("id"))
            require(institution in LABELS and endpoint and field in row, "Batch correction identity or field missing")
            key = (institution, endpoint)
            require(key not in answer[kind], "Duplicate batch endpoint")
            answer[kind][key] = row
        require(len(answer[kind]) == (120 if kind == "levels" else 90), "Batch family cardinality differs")
    return answer


def figure_html(source, name, alt):
    return '<figure><a href="figures/' + source + '_' + name + '.svg"><img src="figures/' + source + '_' + name + '.png" alt="' + esc(alt) + '"></a><figcaption>' + esc(alt) + '；图为描述性展示，颜色及柱高不代表显著。</figcaption></figure>'


def country_table(case, primary=False):
    scalar = {x["metric"]: x for x in case.get("scalar_metrics", [])}
    rows = []
    for item in case.get("calendar_MC_tests", []):
        metric = item["metric"]
        x = scalar.get(metric)
        if x:
            count = metric in ["PI_count", "SG_count"]
            fmt = (lambda v: num(v, 4)) if count else pct
            obs, exp = fmt(x["observed_mean_or_rate"]), fmt(x["calendar_expected_mean_or_rate"])
            delta = num(x["observed_minus_expected"], 4, True) if count else num(100*x["observed_minus_expected"], 3, True) + "pp"
            ci = x.get("paired_excess_unadjusted_95CI")
            ci_text = "—" if ci is None else "[" + (", ".join(num(v, 4, True) for v in ci) if count else ", ".join(num(100*v, 3, True) for v in ci) + "pp") + "]"
        else:
            obs, exp, delta, ci_text = num(item.get("observed_Pearson_distance"), 5), "—", "—", "—"
        rows.append([METRIC_LABELS.get(metric, metric), obs, exp, delta, pv(item.get("p_nominal_plus_one")),
                     pv(item.get("p_Bonferroni_36_reference")), "是" if primary and item.get("primary_Bonferroni_36_reject_0_05") else ("否" if primary else "仅敏感性参考"), ci_text])
    return table(["指标", "观察", "日历期望", "差值", "原始p", "Bonf36 p", "主分析拒绝", "差值95% CI（未校正）"], rows)


def validate(institution, source, results, country, qa, manifest):
    require(results.get("country") == country.get("country") == institution, "Wrong institution in report")
    for q in qa:
        require(q.get("status") == "PASS", "All independent and visual QA must PASS")
    require(qa[0]["hashes"]["results"] == sha(source / "tables_results.json"), "Table QA result binding differs")
    require(qa[1]["hashes"]["results"] == sha(source / "country/country_results.json"), "Country QA result binding differs")
    require(manifest["country"] == institution and manifest["source_result_sha256"] == sha(source / "tables_results.json"), "Figure result binding differs")
    expected_sources = ["strict"] if results["source_groups_identical"] else ["strict", "expanded"]
    require(manifest["sources_plotted"] == expected_sources, "Figure source-group display differs")
    for name, digest in manifest["figure_file_sha256"].items():
        require(sha(source / "figures" / name) == digest, "Figure bytes differ")
    cases = {c["case"]: c for c in country["cases"]}
    for key, casekey in [("strict", "strict_primary"), ("expanded", "expanded")]:
        g, c = results["groups"][key], cases[casekey]
        require(c["n"] == g["people"] and c["person_ids_sha256"] == g["person_ids_sha256"], "Country and table populations differ")
        require(len(g["levels"]) == 40 and len(g["trends"]) == 30 and len(g["bins"]) == 16, "Incomplete table output")
        levels = {r["endpoint_id"]: r for r in g["levels"]}
        for x in c["ten_gods_five_position_descriptive_only"]:
            y = levels["M0_" + x["ten_god"]]
            require(x["observed_count_sum"] == y["observed_total"], "Country/table M0 numerator differs")
            require(abs(x["calendar_expected_count_mean_per_person"] * c["n"] - y["calendar_expected_total"]) < 1e-8, "Country/table M0 expectation differs")
        for x in c["day_master_distribution"]:
            y = levels["DM_" + x["stem"]]
            require(x["observed_people"] == y["observed_total"], "Country/table DM numerator differs")
            require(abs(x["calendar_expected_people"] - y["calendar_expected_total"]) < 1e-8, "Country/table DM expectation differs")
    return cases, expected_sources


def institution_report(institution, results, country, manifest, batch, git):
    groups = results["groups"]
    same = bool(results["source_groups_identical"])
    primary = country["cases"][0]
    main = groups["strict"]
    rejects6 = [x for x in primary["calendar_MC_tests"] if x["primary_Bonferroni_36_reject_0_05"]]
    rejects40 = [x for x in main["levels"] if x["reject_Holm40_0_05"]]
    rejects30 = [x for x in main["trends"] if x["reject_Holm30_0_05"]]
    batch120 = [x for x in main["levels"] if batch["levels"][(institution, x["endpoint_id"])]["p_Holm120"] <= .05]
    batch90 = [x for x in main["trends"] if batch["trends"][(institution, x["endpoint_id"])]["p_Holm90"] <= .05]
    title = LABELS[institution] + "：日主、十神、五行与出生年代"
    parts = [page_start(title), '<p><a href="../index.html">返回三院报告目录</a></p>']
    parts.append('<p class="note">冻结北半球、剔除官方诺奖重叠的合资格院士。严格S1+S2为<strong>' + str(main['people']) + '</strong>人，扩展S1+S2+S3为<strong>' + str(groups['expanded']['people']) + '</strong>人。' + ('两来源人物及生日完全相同，新增水平与年代结果只计算一次；扩展组不是独立验证。' if same else '扩展组为来源敏感性对照，包含严格组，不能视为独立验证。') + ' 院体标签不等于国籍或出生国家。</p>')
    parts.append('<p>出生窗1835—1985、会籍纳入截至2025，沿用原冻结生日、身份与来源规则。单院每人权重1，跨院成员资格沿原规则保留，不进行本轮院际差异检验。未打开中国科学院或诺奖子组，也不生成三个院体合并的人群性状统计。</p>')
    parts.append('<p>十神、五行每人5位：年干、月干、年支、月支、日支代表干。日干只作十神参照，不计五行单位、不参与透干；无时柱。M0取各支本气；M1按年／月干透出、本气→中气→余气优先选一个代表，无透干回退本气。水日主人数与五个位点中水的占比是不同指标。</p>')
    parts.append('<h2>预定检验范围</h2>' + table(['检验组', '本院校正后拒绝', '校正范围'], [
        ['原6项逐院补充诊断', str(len(rejects6))+'/6', '原六院×六指标，Bonferroni36不变'],
        ['完整水平统计', str(len(rejects40))+'/40', '本院严格40项Holm40'],
        ['年代线性趋势', str(len(rejects30))+'/30', '本院严格30项Holm30'],
        ['本批三个院体水平检视', str(len(batch120))+'/40', '将三院既有120个水平p作Holm120'],
        ['本批三个院体年代检视', str(len(batch90))+'/30', '将三院既有90个趋势p作Holm90']]))
    parts.append('<p>整批校正没有添加检验、合并人物性状或检验院体间差异，只防止在这批三院之间择显著项。原18项总体假设检验未运行；此前美国和英国结果不改写。原6项前5为预定上尾富集检验，十干总体为Pearson距离上尾；新增水平与年代为相对日历期望的双侧检验。</p>')
    for source in (["strict"] if same else ["strict", "expanded"]):
        g = groups[source]
        source_label = '严格组（扩展组相同）' if same else ('严格组' if source == 'strict' else '扩展组：来源敏感性')
        parts.append('<h2>' + source_label + '：完整水平统计</h2><p>人数分母' + str(g['people']) + '，十神与五行位点分母' + str(5*g['people']) + '；推断单位是人，不能把位点当独立样本。R＞1只表示数值高于基线，基线不是每神10%或每行20%。</p>')
        for family, label in FAMILIES.items():
            rows = []
            for x in g['levels']:
                if x['family'] != family:
                    continue
                b = batch['levels'][(institution, x['endpoint_id'])] if source == 'strict' else None
                rows.append([x['label'], x['observed_total'], num(x['calendar_expected_total'], 2), pct(x['observed_share']), pct(x['calendar_expected_share']), num(x['excess_percentage_points'], 3, True), num(x['enrichment_ratio']), pv(x['p_two_sided']), pv(x['p_Holm40']), pv(b['p_Holm120']) if b else '仅来源参考'])
            parts.append('<h3>' + label + '</h3>' + table(['类别','观察个数','日历期望个数','观察占比','期望占比','差值/百分点','R','原始双侧p','本院Holm40','整批Holm120'], rows))
        parts.append(figure_html(source, 'overall_elements', LABELS[institution] + '总体五行与日历期望'))
        parts.append('<h2>' + source_label + '：出生十年分布和趋势</h2>')
        parts.append('<p>1830年代只有1835—1839年在出生窗内，1980年代只有1980—1985年在窗内；全部16段保留，空段比例为“—”。热图只显示两来源都N≥20的共同年代，小组仍纳入主分析；若无共同充分年代则不绘热图。</p>')
        parts.append(table(['出生十年段','人数','两来源N≥20'], [[str(b['decade'])+'年代',b['n'],'是' if b['decade'] in results['common_adequate_decades'] else '否'] for b in g['bins']]))
        if results['common_adequate_decades']:
            parts.append(figure_html(source, 'decade_stems_gods_heatmaps', '日主与本气／藏干十神相对本段日历期望的偏离'))
            parts.append(figure_html(source, 'decade_elements_heatmaps', '两套五行逐十年描述，不新增五行年代检验'))
        adequate = g['common_adequate_bins_desc']
        common = {x['endpoint_id']: x for x in adequate['trends']}
        parts.append('<h3>全部30项线性趋势</h3><p>单位为出生年代每后移十年，比例变化多少个百分点。原始、日历自身期望、两者之差分别列出；超额斜率是检验对象。共同充分年代的斜率仅作描述性敏感性，不增加检验；未检出线性趋势不排除非线性起伏。</p>')
        for family in ['DM10','M0','M1']:
            rows=[]
            for x in g['trends']:
                if x['family'] != family:
                    continue
                c = common.get(x['endpoint_id'], {})
                b = batch['trends'][(institution,x['endpoint_id'])] if source == 'strict' else None
                rows.append([x['label'],num(x.get('raw_slope_pp_per_decade'),4,True),num(x.get('calendar_expected_slope_pp_per_decade'),4,True),num(x.get('calendar_excess_slope_pp_per_decade'),4,True),pv(x.get('p_nominal_two_sided')),pv(x.get('p_Holm30')),pv(b['p_Holm90']) if b else '仅来源参考',num(c.get('raw_slope_pp_per_decade'),4,True),num(c.get('calendar_excess_slope_pp_per_decade'),4,True)])
            parts.append('<h3>'+FAMILIES[family]+'</h3>'+table(['类别','原始斜率','日历斜率','超额斜率','原始p','本院Holm30','整批Holm90','充分年代原始斜率','充分年代超额斜率（描述）'],rows))
        parts.append('<h3>完整16段×40项数据</h3><p>每格为“观察个数；观察占比／日历期望占比”。完整期望个数及差值也在tables_results.json中。</p>')
        for family,label in FAMILIES.items():
            definitions=[x for x in results['endpoint_order'] if x['family']==family]
            rows=[]
            for b in g['bins']:
                row=[str(b['decade'])+'年代',b['n']]
                for e in definitions:
                    cell=b['endpoints'][e['id']]
                    row.append(str(cell['observed_total'])+'；'+pct(cell['observed_share'])+'／'+pct(cell['calendar_expected_share']))
                rows.append(row)
            parts.append('<details><summary>'+label+'</summary>'+table(['年代','人数']+[e['label'] for e in definitions],rows)+'</details>')
        parts.append('<h3>年干、月干纯描述附表</h3><p>主文十天干是日主；下面两套天干位置不增加检验。</p>')
        for key,label in [('year_stem','年干'),('month_stem','月干')]:
            rows=[[x['stem'],x['observed_people'],num(x['calendar_expected_people'],2),pct(x['observed_share']),pct(x['calendar_expected_share'])] for x in g['HeavenlyStem_positions'][key]]
            parts.append('<details><summary>'+label+'</summary>'+table(['天干','观察人数','期望人数','观察占比','日历期望'],rows)+'</details>')
    parts.append('<h2>原6项逐院诊断与全部预定对照</h2><p>狭义官印＝正官＋正印存在；伤官配印＝伤官＋正印存在，均是必要共现组件，不是完整格局。六院×六项Bonferroni36不缩小，原始及所有敏感性结果一并保留。</p>')
    parts.append(country_table(primary,True))
    for case in country['cases']:
        parts.append('<details><summary>'+esc(CASE_LABELS.get(case['case'],case['case']))+'，N='+str(case['n'])+'</summary><p>日历条件：'+esc(case.get('calendar_condition',''))+'；组件：'+esc(case.get('cooccurrence_encoding',''))+'；同时排除观察与日历交节±1日：'+('是' if case.get('observed_and_calendar_Jie_pm1_excluded') else '否')+'。</p>')
        parts.append(country_table(case,case['case']=='strict_primary'))
        t=case.get('birthyear_GY_trend',{})
        if t.get('status')=='descriptive_only':
            parts.append('<p>狭义／广义官印随实际出生年的斜率仅描述：原始'+num(100*t['raw_rate_slope_per_decade'],4,True)+'pp/十年，超额'+num(100*t['calendar_excess_rate_slope_per_decade'],4,True)+'pp/十年；不是原全体H2d检验。</p>')
        parts.append('</details>')
    parts.append('<h2>方法与复核</h2><p>固定每人的公历出生年，从该年所有有效公历日期均匀抽样；这是日历基线，不是实测人口出生分布。原年月匹配与交节排除对照保持旧方案。新增水平检验卷积每人的0／1或0—5日期计数PMF，有限支持分布概率用float64、期望与包含等值的绝对中心尾界用有理数；年代使用固定种子PCG64、99999次重复、整数中心化并包含并列值。bootstrap95%区间是描述性、未作多重校正，不替代主族判据。</p>')
    parts.append('<p>两套独立统计复核和实际图像视觉复核均PASS；逐日字面选干核验55,152个日期，核对完整水平、年代表、OLS、预选p及固定敏感性人群。代码与运行前方案在<a href="'+git+'">Git冻结记录</a>，本报告不复制代码。tables_results.json、country_results.json、各QA和figures目录保留全部结果及指纹。</p></html>')
    return '\n'.join(parts), {'institution':institution,'strict':main['people'],'expanded':groups['expanded']['people'],'identical':same,
                               'Bonf36_rejections':len(rejects6),'Holm40_rejections':len(rejects40),'Holm30_rejections':len(rejects30),
                               'Holm120_rejections':len(batch120),'Holm90_rejections':len(batch90)}


def main(args):
    work=Path(args.work).resolve();dest=Path(args.output).resolve() if args.output else ROOT/NAME
    archive=dest.with_suffix('.zip')
    require(not dest.exists() and not archive.exists(),'No overwrite of delivered report')
    receipt=load(work/'EXECUTION_RECEIPT.json')
    require(receipt.get('remote_plan_and_code_verified_before_summary') is True,'Verified execution lock required')
    require(set(receipt['allowed_institutions'])==set(LABELS),'Only the three authorized institutions')
    commit=receipt['commit'];require(re.fullmatch('[0-9a-f]{40}',commit),'Concrete Git execution commit required')
    batch_path=work/'BATCH_CORRECTION.json';batch_raw=load(batch_path);batch=batch_maps(batch_raw)
    batch_qa=load(work/'BATCH_CORRECTION_QA.json')
    require(batch_qa.get('status')=='PASS' and batch_qa['hashes']['batch_correction']==sha(batch_path),'Batch correction QA binding differs')
    git=f'https://github.com/agenhcx/bazi-public-figure-study/tree/{commit}/studies/scientist_north_bazi_v1/remaining_reveal_work'
    prepared=[]
    for institution in LABELS:
        source=work/'outputs'/institution
        require(batch_raw['input_result_sha256'][institution]==sha(source/'tables_results.json'),'Batch correction source binding differs')
        results=load(source/'tables_results.json');country=load(source/'country/country_results.json')
        qa=[load(source/p) for p in ['TABLES_INDEPENDENT_QA.json','COUNTRY_INDEPENDENT_QA.json','figures/VISUAL_QA.json']]
        manifest=load(source/'figures/FIGURE_MANIFEST.json')
        validate(institution,source,results,country,qa,manifest)
        report,summary=institution_report(institution,results,country,manifest,batch,git)
        prepared.append((institution,source,report,summary))
    dest.mkdir(parents=True)
    for institution,source,report,summary in prepared:
        target=dest/institution;target.mkdir()
        (target/'REPORT.html').write_text(report)
        for original,name in [(source/'tables_results.json','tables_results.json'),(source/'country/country_results.json','country_results.json'),(source/'TABLES_INDEPENDENT_QA.json','TABLES_INDEPENDENT_QA.json'),(source/'COUNTRY_INDEPENDENT_QA.json','COUNTRY_INDEPENDENT_QA.json')]:
            shutil.copy2(original,target/name)
        shutil.copytree(source/'figures',target/'figures')
    for name in ['EXECUTION_RECEIPT.json','BATCH_CORRECTION.json','BATCH_CORRECTION_QA.json']:
        shutil.copy2(work/name,dest/name)
    summary_rows=[]
    for institution,_,_,s in prepared:
        summary_rows.append([LABELS[institution],s['strict'],s['expanded'],'相同人群' if s['identical'] else '来源敏感性',s['Bonf36_rejections'],s['Holm40_rejections'],s['Holm30_rejections'],s['Holm120_rejections'],s['Holm90_rejections']])
    index=[page_start('德国、法国、日本：分院揭盲报告'),'<p class="note">按三个院体分别统计，不合并人物性状、不作院际差异推断。中国科学院保持未揭示，诺奖子组和原18项总体检验未开启。每院均沿用北半球、1835—1985出生窗、非诺奖、五个位点及固定日历基线。</p>',table(['院体','严格N','扩展N','来源关系','原6项Bonf36拒绝','本院水平Holm40拒绝','本院趋势Holm30拒绝','本批水平Holm120拒绝','本批趋势Holm90拒绝'],summary_rows)]
    index.append('<p>严格组为主；扩展来源不是独立复验。水平40项＝10日主＋20十神＋10五行；趋势30项＝10日主＋20十神，五行年代仅描述。三个院体已有p另外作120／90项整批Holm校正，没有新增检验或合并性状。原六院36项补充诊断范围不变。</p><ul>')
    for institution in LABELS:
        index.append('<li><a href="'+institution+'/REPORT.html">'+LABELS[institution]+'完整统计、逐十年表与图</a></li>')
    index.append('</ul><p>所有观察值、期望、名义p及校正p均在各院完整报告和JSON中；热图仅表示相对自身日历基线的偏离，不表示单十年显著。全部统计及视觉QA通过。代码和方案见<a href="'+git+'">运行前Git冻结记录</a>。</p></html>')
    (dest/'index.html').write_text('\n'.join(index))
    (dest/'README.txt').write_text('德国、法国、日本分院揭盲报告\n\n先打开 index.html，再进入各院 REPORT.html。\n三个院体分别统计；不包含中国或诺奖子组新结果，不合并trait统计。\n每院完整40水平、30年代趋势、16段×40描述、三干位置、原6诊断及7个预定case。\n本院Holm40/Holm30与本批Holm120/Holm90同时列出；原Bonf36不变。\n严格为主，扩展为来源敏感性，若同组则只计算一次不当验证。\n代码在Git，不复制入本ZIP：'+git+'\n')
    manifest={str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}
    (dest/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(dest.parent)))
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,'ZIP CRC failed')
        for rel,digest in manifest.items():
            require(hashlib.sha256(z.read(dest.name+'/'+rel)).hexdigest()==digest,'ZIP member hash mismatch')
    # Verify relative image destinations and expected HTML sections once.
    for institution in LABELS:
        text=(dest/institution/'REPORT.html').read_text()
        for image in re.findall(r'<img src="([^"]+)"',text):
            require((dest/institution/image).is_file(),'HTML image missing')
    print(json.dumps({'status':'PASS','archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'member_count':len(manifest)+1,'institution_summaries':[x[3] for x in prepared]},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',default=str(WORK))
    parser.add_argument('--output')
    main(parser.parse_args())
