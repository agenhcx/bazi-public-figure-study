#!/usr/bin/env python3
"""Package already audited NAS element/conditional results without new tests."""
import hashlib
import html
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "nas_elements_conditional_work"
NAME = "scientist_US_NAS_reveal_v5_elements_conditionals"
DEST = ROOT / NAME
PARENT = ROOT / "scientist_US_NAS_reveal_v4_decade_trends.zip"
PARENT_SHA = "9bd837bc731263b81f1f81eff8050bfc1f20edc38dceae0c1a02bf03e21a6e8a"
LOCK = "abc127e14c23b0dbbcb3be6dfde5cf2de1c49d3c"
GIT = "https://github.com/agenhcx/bazi-public-figure-study/tree/" + LOCK + "/studies/scientist_north_bazi_v1/nas_elements_conditional_work"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def esc(value):
    return html.escape(str(value))


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(x) + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def pct(x):
    return f"{100*x:.2f}%"


def pvalue(x):
    return f"{x:.5f}" if x >= .0001 else f"{x:.4g}"


def main():
    results = json.loads((WORK / 'NAS_elements_conditional_results.json').read_text())
    qa = json.loads((WORK / 'INDEPENDENT_QA.json').read_text())
    assert qa['status'] == 'PASS' and qa['hashes']['results'] == sha(WORK / 'NAS_elements_conditional_results.json')
    assert sha(PARENT) == PARENT_SHA and not DEST.exists()
    DEST.mkdir()
    (DEST / 'baseline').mkdir()
    shutil.copy2(PARENT, DEST / 'baseline' / PARENT.name)
    for filename in ['NAS_elements_conditional_results.json', 'INDEPENDENT_QA.json', 'EXECUTION_RECEIPT.json', 'SCOPE.json', 'LOCKED_FILES.json', 'ANALYSIS_PLAN.md']:
        shutil.copy2(WORK / filename, DEST / filename)
    parts = ['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>美国科学院：五行与条件共现</title><style>
body{font:16px/1.65 system-ui,"Noto Sans CJK SC",sans-serif;color:#172536;max-width:1200px;margin:30px auto;padding:0 20px}h1{font-size:27px}h2{font-size:23px;margin-top:32px}h3{font-size:19px}.note{background:#edf5fa;border-left:4px solid #337d9b;padding:14px 18px}.scroll{overflow-x:auto}table{border-collapse:collapse;margin:16px 0;font-variant-numeric:tabular-nums;white-space:nowrap}th,td{padding:7px 11px;border-bottom:1px solid #d5dfe6;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#eaf0f5}tbody tr:nth-child(even){background:#f7f9fb}summary{cursor:pointer;font-weight:650}a{color:#206387}small{color:#4a5c70}code{word-break:break-all}</style><h1>美国科学院：五个位点的五行构成与四神条件共现</h1>''']
    parts.append('<p class="note"><strong>结论：</strong>水在本气、藏干两种口径及严格、扩展两组中均低于各自出生年日历期望，没有水富集证据。四个指定十神中偏财、偏印略高于基线，食神、七杀略低。食神制杀、财生杀、杀印相生的必要共现组件未得到经校正支持的富集。两组各42项均未通过Holm42校正。</p>')
    parts.append('<p>沿用冻结的北半球、剔除诺奖重叠NAS样本：严格S1+S2为908人，扩展S1+S2+S3为1462人，扩展组是来源敏感性对照，包含严格组，并非独立验证。未打开其他国家或诺奖子组结果。本轮为揭盲后探索，原18项、逐院36项及年代30项检验保持原状。</p>')
    parts.append('<p>每人五个位点：年干、月干、年支、月支、日支代表干。日干只作十神参照，不计五行数量、不作为透干源；没有时柱。M0取三支本气，M1按原规则优先采用透于年干或月干的藏干，多透按本气→中气→余气，均不透则回退本气。M1每支仍只选一个，五行/十神每人合计都为5。本表不同于历史音乐队列含日干的六字总体构成。</p>')
    water_rows = []
    for quality, title in [('strict', '严格组'), ('expanded', '扩展组')]:
        g = results['groups'][quality]
        byid = {r['id']: r for r in g['endpoints']}
        for model, label in [('M0', '本气'), ('M1', '藏干优先')]:
            x = byid[model + '_element_水']
            water_rows.append([title, label, f"{x['observed_count']}/{g['five_position_denominator']}", pct(x['observed_position_share']), pct(x['calendar_expected_position_share']), f"{x['enrichment_ratio']:.3f}", pvalue(x['p_two_sided']), pvalue(x['p_Holm42'])])
    parts += ['<h2>水的结果</h2>', table(['来源组', '口径', '水数量/总位点', '观察占比', '日历期望', '观察/期望', '双侧p', 'Holm42 p'], water_rows)]
    parts.append('<p>观察方向是水较少；严格组藏干口径的未校正p=0.00440，Holm42后为0.18204，因此也不能宣称已经证明水显著减少。金木水火土不应各自直接以20%作为零模型。土在本气口径约占28%，其匹配日历期望本来就约28%。这些分布检验没有测量智力，不能验证“水主智”的因果解释。</p>')
    parts.append('<h2>怎样读条件概率</h2><p>例如P(食神存在｜七杀存在)，分子是二者都至少出现一次的人数，分母是七杀至少出现一次的人数。日历基线对这些七杀阳性者逐人固定公历出生年，仅在同年、同口径下也含七杀的日期中计算食神出现概率，再按这批人的年份构成加权。不是与所有日期、各神10%或两个边际概率的乘积比较。</p><p>共现只检验必要组件，不判定强弱、位置、有效制化或完整格局。“七杀与偏财”按财生杀组件解释；P的条件方向不代表相生或因果方向。食神与偏财为食神生财组件，七杀与偏印为杀印相生组件。</p>')
    for quality, title in [('strict', '严格组：908人'), ('expanded', '扩展组：1462人（来源敏感性）')]:
        g = results['groups'][quality]
        parts.append('<h2>' + esc(title) + '</h2>')
        for model, label in [('M0', '本气 M0'), ('M1', '藏干优先 M1')]:
            items = [x for x in g['endpoints'] if x['model'] == model]
            parts.append('<h3>' + esc(label) + '</h3>')
            for kind, heading in [('element_count', '五行数量'), ('god_count', '四个指定十神数量')]:
                rows = [[x['category'], x['observed_count'], f"{x['calendar_expected_total']:.2f}", pct(x['observed_position_share']), pct(x['calendar_expected_position_share']), f"{x['difference_percentage_points']:+.2f}", f"{x['enrichment_ratio']:.3f}", pvalue(x['p_two_sided']), pvalue(x['p_Holm42'])] for x in items if x['kind'] == kind]
                parts.append('<p><strong>' + heading + f"；总位点分母={g['five_position_denominator']}" + '</strong></p>')
                parts.append(table(['类别', '观察个数', '期望个数', '观察占比', '日历期望', '差值/百分点', '观察/期望', '双侧p', 'Holm42 p'], rows))
            rows = [[f"{x['target']}｜{x['anchor']}", f"{x['observed_joint_people']}/{x['observed_anchor_people']}", pct(x['observed_conditional_probability']), pct(x['calendar_expected_conditional_probability']), f"{x['difference_percentage_points']:+.2f}", f"{x['enrichment_ratio']:.3f}", pvalue(x['p_two_sided']), pvalue(x['p_Holm42'])] for x in items if x['kind'] == 'conditional_presence']
            parts.append('<details open><summary>全部12个有向条件概率；两事件均为至少出现一次</summary>')
            parts.append(table(['目标｜条件', '联合人数/条件人数', '观察概率', '条件日历期望', '差值/百分点', '观察/期望', '双侧p', 'Holm42 p'], rows))
            parts.append('</details>')
    parts.append('<h2>检验与复核</h2><p>本轮42项＝五行5×2口径＋指定四神4×2口径＋四神所有有向条件对12×2口径。严格组统一Holm42；扩展组相同42项校正仅作来源敏感性参考。检验以人为单位，每人的完整日期五位计数保留位点依赖，不能将5N个位点当独立样本。各人的0—5计数分布或条件Bernoulli分布卷积得到有限支持总数分布；双侧尾包含与精确日历期望距离至少等于观察距离的整数总数。期望和尾界用有理数精确计算，概率用float64确定性卷积。</p>')
    parts.append('<p>独立复核PASS：55,152个日历日期以字面选干独立重建，全部计数和期望、条件分母与逐年候选池、尾界与Holm校正一致；预先选择的3项在两组采用按年多项式乘幂独立重算p，一致至浮点误差。没有因结果增加新的检验。</p>')
    parts.append('<p><a href="' + GIT + '">分析方案与代码的运行前Git锁</a>：<code>' + LOCK + '</code>。结果明细见NAS_elements_conditional_results.json；复核见INDEPENDENT_QA.json；baseline目录保留此前V4 ZIP完整快照。</p></html>')
    (DEST / 'NAS_ELEMENTS_CONDITIONAL_REPORT.html').write_text('\n'.join(parts))
    (DEST / 'README.txt').write_text('美国NAS五行与条件概率补充\n\n打开 NAS_ELEMENTS_CONDITIONAL_REPORT.html 阅读完整报告。\n严格908人，扩展1462人，均为北半球、剔除官方诺奖重叠的冻结样本。\n每人五位，不含日干和时柱；M0本气、M1藏干透干优先。\n本轮42项探索性检验，条件概率使用同公历年且anchor阳性的日期池。\n扩展组包含严格组，不能当独立验证。\n独立复核PASS。\nbaseline/ 保留此前V4出生年代分析ZIP原文件。\n新代码与完整方案存于Git：' + GIT + '\n')
    manifest = {str(p.relative_to(DEST)): sha(p) for p in sorted(DEST.rglob('*')) if p.is_file()}
    (DEST / 'SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    archive = ROOT / (NAME + '.zip')
    assert not archive.exists()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(DEST.rglob('*')):
            if p.is_file():
                z.write(p, str(p.relative_to(ROOT)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for rel, digest in manifest.items():
            assert hashlib.sha256(z.read(NAME + '/' + rel)).hexdigest() == digest
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': sha(archive), 'members': len(manifest)+1, 'QA': 'PASS'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
