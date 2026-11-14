#!/usr/bin/env python3
"""Deliver the audited targeted birth-decade study; no new statistics."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'dm_decade_work'
NAME = 'scientist_DM_birth_decade_targeted_v1'
TARGETS = ['CAS_xin', 'NAS_water']
SOURCES = ['strict', 'expanded']
LABELS = {'CAS_xin': '中国科学院：辛日主', 'NAS_water': '美国科学院：壬癸水日主'}
SOURCE_LABELS = {'strict': '严格来源', 'expanded': '扩展来源（敏感性参考）'}
KINDS = {'local': '单个出生十年局部偏多', 'global_heterogeneity': '总体年代分配差异',
         'global_linear': '线性年代关联'}


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
    return '—' if value is None else f'{100*value:.2f}%'


def num(value, digits=3):
    return '—' if value is None else f'{value:.{digits}f}'


def pvalue(value):
    if value is None:
        return '—'
    return f'{value:.5f}' if value >= .0001 else f'{value:.4g}'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(x) + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def bindings(obj):
    """Collect explicit SHA values from QA without assuming its wrapper."""
    answer = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value):
                answer.append(value)
            elif isinstance(value, (dict, list)):
                answer.extend(bindings(value))
    elif isinstance(obj, list):
        for value in obj:
            answer.extend(bindings(value))
    return answer


def test_label(row):
    base = KINDS.get(row['kind'], row['kind'])
    return f"{row['decade']}年代 · {base}" if row.get('decade') is not None else base


def legacy_table(legacy):
    rows = []
    # These old30-family p-values are shown as historical reference, never
    # substituted for the newly defined conditional-on-K tests.
    for target, oldkey in [('CAS_xin', 'CAS_辛'), ('NAS_water', 'NAS_壬癸水')]:
        for source in SOURCES:
            group = legacy['targets'][oldkey]['sources'][source]
            for endpoint, t in group['existing_component_linear_trends'].items():
                rows.append([LABELS[target], SOURCE_LABELS[source], endpoint,
                             f"{t['raw_slope_pp_per_decade']:+.3f}",
                             f"{t['calendar_excess_slope_pp_per_decade']:+.3f}",
                             pvalue(t['p_nominal_two_sided']), pvalue(t['p_Holm30'])])
    return table(['目标', '来源', '旧端点', '原始斜率pp/十年', '旧日历超额斜率pp/十年', '旧原始p', '旧Holm30 p'], rows)


def main(args):
    work = Path(args.work).resolve()
    result_path = Path(args.results).resolve() if args.results else work/'DM_DECADE_RESULTS.json'
    qa_path = Path(args.qa_file).resolve() if args.qa_file else work/'INDEPENDENT_QA.json'
    legacy_path = work/'EXISTING_DECADE_TABLES.json'
    receipt_path = work/'EXECUTION_RECEIPT.json'
    figure_dir = work/'figures_layout_v2'
    output = Path(args.output).resolve() if args.output else ROOT/NAME
    archive = output.with_suffix('.zip')
    require(not output.exists() and not archive.exists(), 'No overwrite of an existing deliverable')
    data = load(result_path); qa = load(qa_path); receipt = load(receipt_path); legacy = load(legacy_path)
    visual = load(figure_dir/'VISUAL_QA.json'); figures = load(figure_dir/'FIGURE_MANIFEST.json')
    require(qa['status'] == visual['status'] == figures['status'] == 'PASS', 'All statistical and visual QA must pass')
    digest = sha(result_path)
    require(digest in bindings(qa), 'Independent QA is not bound to these result bytes')
    require(figures['input_results_sha256'] == digest and digest in bindings(visual), 'Figure/visual QA result binding differs')
    require(receipt.get('remote_plan_and_code_verified_before_summary') is True, 'Remote execution lock absent')
    commit = receipt['commit']; require(re.fullmatch(r'[a-f0-9]{40}', commit), 'Concrete Git lock commit required')
    require(set(data['groups']) == set(TARGETS), 'Only the two fixed targets are authorized')
    for name, expected in figures['files'].items():
        require(Path(name).name == name and sha(figure_dir/name) == expected, 'Figure checksum differs')
    require(set(data['tests_by_source']) == set(SOURCES), 'Both source cases required')
    for source in SOURCES:
        tests = data['tests_by_source'][source]
        require(len(tests) == 19 and len({x['test_id'] for x in tests}) == 19, 'The19-test family differs')
        require(sum(x['kind'] == 'local' for x in tests) == 15, 'The15 local endpoints differ')
        require(sum(x['kind'] == 'global_heterogeneity' for x in tests) == 2 and
                sum(x['kind'] == 'global_linear' for x in tests) == 2, 'The4 global endpoints differ')
    output.mkdir()
    (output/'figures').mkdir()
    for path, filename in [(result_path, 'DM_DECADE_RESULTS.json'), (qa_path, 'INDEPENDENT_QA.json'),
                           (legacy_path, 'EXISTING_DECADE_TABLES.json'), (receipt_path, 'EXECUTION_RECEIPT.json')]:
        shutil.copy2(path, output/filename)
    for name in ['SCOPE.json', 'LOCKED_FILES.json']:
        if (work/name).exists():shutil.copy2(work/name, output/name)
    for name in [*figures['files'], 'FIGURE_MANIFEST.json', 'VISUAL_QA.json']:
        shutil.copy2(figure_dir/name, output/'figures'/name)
    # This is an original V4 policy member, copied byte for byte; no source
    # grades or source decisions are inferred by this report builder.
    policy_path = work/'inputs'/'SOURCE_GROUP_POLICY_V4.json'
    require(policy_path.exists(), 'Original V4 source policy extract required')
    shutil.copy2(policy_path, output/'SOURCE_GROUP_POLICY_V4.json')
    strict_rejected = [x for x in data['tests_by_source']['strict'] if x['reject_Holm19_0_05']]
    expanded_rejected = [x for x in data['tests_by_source']['expanded'] if x['reject_Holm19_0_05']]
    intro = ('严格组19项检验中，' + str(len(strict_rejected)) + '项通过Holm19校正；扩展来源参考为' +
             str(len(expanded_rejected)) + '项。')
    if not strict_rejected:
        intro += '尚未检出经校正支持的年代集中或线性关联；局部柱高只能描述观察方向。'
    else:
        intro += '通过项目请结合完整表和扩展来源敏感性阅读；它们不证明因果。'
    parts = ['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>中国辛日主与美国水日主：出生年代探索</title><style>
body{font:16px/1.65 system-ui,"Noto Sans CJK SC",sans-serif;color:#172b3b;max-width:1280px;margin:28px auto;padding:0 20px}h1{font-size:28px}h2{font-size:23px;margin-top:30px}h3{font-size:19px}.note{padding:14px 18px;background:#edf5fa;border-left:4px solid #3e7e9c}.scroll{overflow-x:auto}table{border-collapse:collapse;white-space:nowrap;font-variant-numeric:tabular-nums;margin:16px 0}th,td{padding:7px 11px;border-bottom:1px solid #d9e2e8;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#eaf0f5}tbody tr:nth-child(even){background:#f7f9fa}img{max-width:100%;height:auto;border:1px solid #e1e8ed}summary{font-weight:650;cursor:pointer}a{color:#22688a}code{word-break:break-all}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f8;padding:12px;font-size:12px}</style><h1>中国辛日主与美国水日主：是否集中在某些出生年代？</h1>''']
    parts.append('<p class="note">' + esc(intro) + '</p>')
    if strict_rejected:
        parts.append(table(['通过项目', '原始p', 'Holm19 p'],
                           [[LABELS[x['target']]+' · '+test_label(x), pvalue(x['p_nominal']), pvalue(x['p_Holm19'])] for x in strict_rejected]))
    parts.append('<p>本轮是已见总体结果后的定向探索，固定两个用户指定目标：中国科学院辛日主、美国科学院壬癸合计水日主。使用原冻结北半球、非诺奖人群、原公历出生年和原55152日历日期缓存；没有重排历法、补出生时刻或修改人群。没有计算诺奖组、全局18项或其他院体的新结果。</p>')
    parts.append('<p>来源口径沿用V4：严格组为S1＋S2，扩展组为S1＋S2＋S3。要求已确认同一人物、同一完整日期至少有一条已保留合格来源支持；明确属于S1或S2并集但未区分细类的记录仍可纳入。真正来源未知的记录本身不提供生日支持，其他同人同日合格来源可以支持人物，但不把原弱来源或未知来源的等级回写提高。扩展组的四条LOC引用元数据仍按原S3规则保留，来源警告不变。原始规则见包内SOURCE_GROUP_POLICY_V4.json。</p>')
    parts.append('<h2>整体偏多与年代集中是两个问题</h2><p>此前总体数量的观察仍保留。本轮另固定每个来源整组已有的目标人数K，再问这些人是否比相应日历模型更集中在某些出生年代。这样不会把“整组本来就偏多”直接当成“某个年代额外富集”。每人公历出生年保留；固定K后的分配仍保留各出生年日历概率的细小差异。</p>')
    rows=[]
    for target in TARGETS:
        for source in SOURCES:
            g=data['groups'][target][source]
            rows.append([LABELS[target], SOURCE_LABELS[source], g['people'], g['target_people'],
                         pct(g['overall_observed_share']), pct(g['calendar_expected_share']),
                         g.get('adequate_local_people',sum(b['n'] for b in g['bins'] if b['local_test_eligible'])),
                         g.get('adequate_local_target_people',sum(b['observed_target_people'] for b in g['bins'] if b['local_test_eligible']))])
    parts.append(table(['目标', '来源', '整组N', '整组目标人数K', '整体观察占比', '无条件日历期望', '图示充分年代N', '图示目标人数'],rows))
    parts.append('<p>扩展组包含严格组，是来源敏感性对照，不能当作独立复制。图中日主类别也不等于五个位点中的水／金总量。</p>')
    parts.append('<p>中国辛日主：严格来源中，1950年代为11／49（22.45%），1890年代为5／25（20.00%）；前者局部条件p＝0.04425，Holm19后为0.84083。扩展来源的1950年代变为12／72（16.67%），条件p＝0.16431，说明这段柱高对来源构成敏感。不能据此确认特定出生年代富集。</p>')
    parts.append('<p>美国水日主：严格来源1910、1940、1950年代观察占比分别为25.35%、25.49%、25.00%；1940、1950年代分母仅51和20。1910年代在扩展来源仍为25.23%，但局部条件p从0.16750变为0.06574，两个来源经Holm19后均为1。总体年代分配及线性检验也均未通过校正；这些数值高点仍属于描述。</p>')
    parts.append('<h2>出生十年分布</h2><p>柱为观察占比，灰线为同出生年无条件日历期望，黑线为固定整组目标人数K后的年代期望。只显示原定两来源均N≥20的年代：中国1890—1969年8段，美国1890—1959年7段。全部16段和小样本人数保留在后面的完整表中，图不按p值筛选柱子，也不以颜色编码显著性。</p><img src="figures/DM_targeted_birth_decades.png" alt="两个目标在严格及扩展来源中的出生十年观察占比与两种期望">')
    parts.append('<h2>新19项检验：完整结果</h2><p>每个来源的19项＝15个预定充分年代局部偏多检验＋两个目标各1项总体年代分配差异、1项线性年代关联。严格组统一Holm19；扩展同19项仅作来源参考。局部检验比较观察人数与固定全样本K后的条件分布，不与10%／20%直接比较。旧方案与旧p值保持不变。</p>')
    for source in SOURCES:
        parts.append('<h3>'+esc(SOURCE_LABELS[source])+'</h3>')
        rows=[]
        for x in data['tests_by_source'][source]:
            rows.append([LABELS[x['target']],test_label(x),pvalue(x['p_nominal']),pvalue(x['p_Holm19']),
                         '是' if x['reject_Holm19_0_05'] else '否'])
        parts.append(table(['目标','检验','原始p','Holm19 p','通过0.05'],rows))
    parts.append('<h2>全部16个十年段</h2>')
    for target in TARGETS:
        for source in SOURCES:
            g=data['groups'][target][source];parts.append('<details><summary>'+esc(LABELS[target]+' · '+SOURCE_LABELS[source])+'</summary>')
            rows=[]
            for b in g['bins']:
                rows.append([b['decade'],b['n'],b['observed_target_people'],pct(b['observed_share']),
                             num(b['calendar_expected_target_people'],3),pct(b['calendar_expected_share']),
                             num(b['conditional_expected_target_people'],3),pct(b['conditional_expected_share']),
                             '是' if b['local_test_eligible'] else '仅描述',pvalue(b.get('conditional_upper_p')),pvalue(b.get('p_Holm19'))])
            parts.append(table(['年代起点','N','目标人数','观察占比','日历E人数','日历E占比','固定K条件E人数','固定K条件E占比','预定局部检验','条件上尾p','Holm19 p'],rows))
            parts.append('<details><summary>两项总体检验与模拟细节</summary><pre>'+esc(json.dumps({'global_tests':g['global_tests'],'simulation':g.get('simulation',{})},ensure_ascii=False,indent=2))+'</pre></details></details>')
    parts.append('<h2>此前线性趋势：保留原始参照</h2><p>下表来自先前各院30项趋势族，使用原同年日历零模型；与本轮固定K的年代分配检验回答不同问题。中国辛的旧p不被新分析替换。美国此前只分别测过壬、癸，没有壬癸合计水日主的旧线性p；不能把两个p直接相加或说合计已检验。</p>')
    parts.append(legacy_table(legacy))
    git='https://github.com/agenhcx/bazi-public-figure-study/tree/'+commit+'/studies/scientist_north_bazi_v1/dm_decade_work'
    parts.append('<h2>复核与可复现记录</h2><p>独立统计QA和实际图像视觉QA均PASS。结果原文及条件分布/模拟配置见DM_DECADE_RESULTS.json，独立核验见INDEPENDENT_QA.json。源数据ZIP和日历缓存沿用原SHA；代码不在交付ZIP中，见<a href="'+git+'">运行前Git锁定的方案与统计代码</a>：<code>'+commit+'</code>。</p>')
    parts.append('<p>图另做运行后纯排版修订：拆分年代／N／目标人数标签、调整间距、为百分比标签加白底。预锁绘图脚本未修改，原图与修订图的面板数据清单完全相同。修订脚本SHA256：<code>'+esc(figures['plot_code_sha256'])+'</code>；预锁原脚本SHA256：<code>'+esc(figures['original_locked_plot_sha256'])+'</code>。图像及视觉核验绑定相同结果字节，见figures内的两份QA／manifest。</p>')
    parts.append('<pre>'+esc(json.dumps({'result_sha256':digest,'original_source_and_code_sha256':data['source_and_code_sha256'],'source_group_policy_V4_member_sha256':sha(policy_path)},ensure_ascii=False,indent=2))+'</pre>')
    parts.append('</html>')
    (output/'REPORT.html').write_text('\n'.join(parts))
    (output/'README.txt').write_text('中国辛日主、美国壬癸水日主：出生年代探索\n\n打开REPORT.html。\n本轮固定整组目标人数K，检验年代分配、线性关联及15个预定局部年代的偏多。\n严格组统一19项Holm；扩展组为来源敏感性，不是独立验证。\n全部16段保留，原CAS辛的Holm30等旧结果仍单列参照，未被替换。\n代码与方案：'+git+'\n')
    manifest={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(output.parent)))
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,'ZIP CRC failed')
        for name,digest in manifest.items():
            require(hashlib.sha256(z.read(output.name+'/'+name)).hexdigest()==digest,'ZIP manifest mismatch')
    print(json.dumps({'status':'PASS','archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),
                      'members':len(manifest)+1,'HTML_tables':''.join(parts).count('<table'),
                      'strict_Holm19_rejections':len(strict_rejected),'expanded_reference_Holm19_rejections':len(expanded_rejected)},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',default=str(WORK));p.add_argument('--results');p.add_argument('--qa-file');p.add_argument('--output')
    main(p.parse_args())
