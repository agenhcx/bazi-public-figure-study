#!/usr/bin/env python3
"""Render saved Fields results without adding statistical tests."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
r = json.loads((ROOT / 'RESULTS.json').read_text())
qa_path = ROOT / 'POSTREVEAL_INDEPENDENT_QA.json'
qa = json.loads(qa_path.read_text()) if qa_path.exists() else {}
labels = {'overall_PI': '总体偏印', 'overall_SG': '总体伤官', 'year_PI': '年柱出现偏印',
          'year_SG': '年柱出现伤官', 'month_PI': '月柱出现偏印', 'month_SG': '月柱出现伤官'}

def esc(x):
    return html.escape(str(x))

def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>'+esc(x)+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def pct(x):
    return f'{100*x:.2f}%'

body = '<h1>菲尔兹奖：偏印与伤官</h1><p class="lead">伤官的总体数量和月柱出现率高于日历预期；六项主检验经校正均未显著。偏印没有稳定偏高。</p>'
body += '<p>北半球冻结样本57人，出生于1897–1985年。严格S1+S2与扩展S1+S2+S3为同一批人。原始名册64人：排除月级生日1人、南半球4人、超出生窗口2人。沿用截至2025年的1936–2022届名册。</p>'
body += '<h2>六项主检验</h2><p>每个人固定公历出生年份，枚举该年全部日期求预期，再联合模拟99,999次。单侧检验“高于预期”，六项共同做Holm校正。总体分母是57×5=285个位点；年柱、月柱分母是57人，一柱内出现两次仍只计一人。</p>'
rows=[]
for x in r['primary']:
    rows.append([labels[x['endpoint']], f"{x['observed_sum']} / {x['reporting_denominator']}（{pct(x['observed_fraction'])}）", pct(x['expected_fraction']),f"{x['difference_percentage_points']:+.2f}个百分点",f"{x['raw_p_one_sided']:.5f}",f"{x['holm6_p']:.5f}"])
body += table(['指标','观察值','日历预期','差值','原始p','Holm六项p'],rows)
body += '<p>总体偏印31次，预期30.41次；伤官35次，预期26.60次。月柱伤官16/57，预期10.71人。观察方向不能替代显著性证据；不显著也不等于证明没有差异。</p>'
body += '<h2>本气与藏干：描述性并行</h2><p>M1按既定规则选择透出的藏干：本气→中气→余气优先，按年干/月干判断透出；没有透出则保留本气，日干只作参照。下表“含量”是五个位点中的占比，“出现率”是每人至少一次的比例。没有增加或替换主检验。</p>'
selected=[x for x in r['descriptives']['hidden_models'] if x['model'] in ('M0_5','M1_priority_5')]
body += table(['模型','十神','含量：观察 / 预期','出现率：观察 / 预期'],[['本气' if x['model']=='M0_5' else '藏干优先替换','偏印' if x['trait']=='PI' else '伤官',pct(x['observed_position_share'])+' / '+pct(x['expected_position_share']),pct(x['observed_person_presence'])+' / '+pct(x['expected_person_presence'])] for x in selected])
body += '<h2>预先指定的敏感性分析</h2><p>下列只描述方向，不另加p值，也不作为独立复现。排除节气前后一天仅剔除样本，日历零模型仍为完整出生年。</p>'
case_labels={'M1_priority_5':'藏干优先替换','M0_birth_year_and_month_null':'同时固定出生年/月的预期','M0_noJie_plus_minus_one_day':'排除节气前后一天','M0_without_prior_academy_overlap':'排除曾揭露院士重叠人员'}
rows=[]
for name, values in r['sensitivities'].items():
    m={x['endpoint']:x for x in values}
    rows.append([case_labels[name],values[0]['N'],*(pct(m[k]['observed_fraction'])+' / '+pct(m[k]['expected_fraction']) for k in ['overall_PI','overall_SG','year_SG','month_SG'])])
body += table(['口径','人数','总体偏印：观察/预期','总体伤官：观察/预期','年柱伤官：观察/预期','月柱伤官：观察/预期'],rows)
body += '<h2>完整八模型</h2><p>七位模型加入均匀12时辰的边际平均；这不是已知出生时辰。“share”和“any”分别沿用冻结定义，分母与模型一致，不将藏干当成额外独立观测。</p>'
body += table(['模型','十神','位点数','位点含量：观察/预期','每人出现率：观察/预期'],[[x['model'],'偏印' if x['trait']=='PI' else '伤官',x['position_denominator'],pct(x['observed_position_share'])+' / '+pct(x['expected_position_share']),pct(x['observed_person_presence'])+' / '+pct(x['expected_person_presence'])] for x in r['descriptives']['hidden_models']])
body += '<h2>十神与日主：描述性统计</h2>'
for name,title in [('M0_all10_TG','本气十神（285个位点）'),('M1_all10_TG','藏干优先替换十神（285个位点）'),('day_master','十天干日主（57人）')]:
    body += '<h3>'+title+'</h3>'+table(['类别','观察数量','预期数量','观察占比','预期占比'],[[x['label'],f"{x['observed_sum']:.0f}",f"{x['expected_sum']:.2f}",pct(x['observed_fraction']),pct(x['expected_fraction'])] for x in r['descriptives'][name]])
body += '<h2>解释与复核</h2><p>这是在院士和诺奖已揭露之后、菲尔兹奖专项汇总计算之前锁定的新分析。57人中18人已在院士组出现，39人排除重叠后的结果仅作补充。年柱/月柱的统计不直接测量成名年龄；本次结果不能证明年少成名机制，也不构成个体择日或能力预测证据。</p>'
body += '<p>沿用原固定日历坐标与节气处理，不调整出生日期、时区、时柱。元数据审计、55152日历全量编码复现、合成检验和独立结果复核均随包保留。独立结果QA状态：'+esc(qa.get('status',qa.get('all_checks_pass','见JSON')))+'。</p>'
receipt=r['execution_receipt']
body += '<p>计算前Git锁定：<a href="'+esc(receipt['commit_url'])+'">'+esc(receipt['commit'])+'</a>。代码及输入SHA256、锁定回读记录、主结果JSON、个体排盘审计与复算说明均在本包。</p>'
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>菲尔兹奖偏印伤官统计</title><style>body{max-width:1120px;margin:38px auto;padding:0 22px;color:#203044;font:16px/1.75 system-ui,"Noto Sans CJK SC",sans-serif;background:#fff}h1{font-size:30px}h2{margin-top:38px;font-size:23px}.lead{font-size:20px;font-weight:600}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}th,td{text-align:right;padding:10px 12px;border-bottom:1px solid #d9e0e7;white-space:nowrap}th:first-child,td:first-child{text-align:left}thead{background:#edf2f7}a{color:#165d9e}@media print{body{max-width:none;font-size:12px}table{font-size:10px}}</style><body>'+body+'</body></html>'
(ROOT/'REPORT.html').write_text(page)
print(ROOT/'REPORT.html')
