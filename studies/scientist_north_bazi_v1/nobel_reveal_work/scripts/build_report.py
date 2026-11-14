#!/usr/bin/env python3
"""Chinese report and fixed, descriptive plots for the frozen global18 reveal.

No input is opened by import. Real rendering requires the root execution receipt,
completed main/descriptive results, and independent statistical QA.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

WORK = Path(__file__).resolve().parents[1]
GODS = ['比肩','劫财','食神','伤官','偏财','正财','七杀','正官','偏印','正印']
STEMS = list('甲乙丙丁戊己庚辛壬癸')
CASE_ORDER = ['strict_primary','expanded','strict_broad','strict_noJie','strict_yearMonth','expanded_withoutLOC','strict_withoutFields']
CASE_LABELS = {'strict_primary':'严格来源／狭义／同年日历（主方案）','expanded':'扩展来源 S1＋S2＋S3','strict_broad':'严格来源／广义组合','strict_noJie':'严格来源／观察与日历同时剔除交节±1日','strict_yearMonth':'严格来源／同年同公历月日历','expanded_withoutLOC':'扩展来源／剔除仅依赖四条LOC引用支持者','strict_withoutFields':'严格来源／非诺奖院士排除Fields兼得者'}
TEST_LABELS = {'H1a_PI':'诺奖偏印高于自身日历期望','H1a_SG':'诺奖伤官高于自身日历期望','H1b_PI':'非诺奖院士偏印高于自身日历期望','H1b_SG':'非诺奖院士伤官高于自身日历期望','H1c_PI':'诺奖偏印高于非诺奖院士','H1c_SG':'诺奖伤官高于非诺奖院士','H2a':'非诺奖院士官印率高于自身日历期望','H2b':'非诺奖院士伤官配印率高于自身日历期望','H2c':'非诺奖院士官印率高于诺奖','H2d':'非诺奖院士官印率随出生年上升','H3a':'诺奖＋非诺奖院士并集十干分布偏离日历期望','H3b':'同一并集水日主率高于日历期望','H4_PI':'六院偏印条件异质性','H4_SG':'六院伤官条件异质性','H4_GY':'六院官印率条件异质性','H4_SGY':'六院伤官配印率条件异质性','H4_DM10':'六院十干日主条件异质性','H4_WATER':'六院水日主率条件异质性'}
METRIC_LABELS = {'PI_count':'偏印','SG_count':'伤官','GY':'官印共现','SGY':'伤官配印共现','water_DM':'水日主'}
MODEL_NAMES = ['M0_5','M1_priority_5','M1_share_5','M1_any_5','M2_main_7','M3_priority_7','M3_share_7','M3_any_7']
RULE_LABELS = ['本气','优先透干','透干均分','任一透干']
COLORS = {'obs':'#2c6c92','expected':'#aab7c2','expanded':'#d88340','expected_expanded':'#edc6a6'}


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain(value):
    if value is None:
        return '—'
    if isinstance(value,bool):
        return '是' if value else '否'
    if isinstance(value,float):
        if not np.isfinite(value):
            return '—'
        return f'{value:.6g}'
    if isinstance(value,(list,dict)):
        return json.dumps(value,ensure_ascii=False,separators=(',',':'))
    return str(value)


def pct(value, digits=2):
    return '—' if value is None else f'{100*float(value):.{digits}f}%'


def esc(value):
    return html.escape(plain(value))


def table(headers,rows,classes=''):
    head='<thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead>'
    body='<tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody>'
    return '<div class="table-scroll"><table class="'+classes+'">'+head+body+'</table></div>'


def details(title,value):
    return '<details><summary>'+esc(title)+'</summary><pre>'+html.escape(json.dumps(value,ensure_ascii=False,indent=2))+'</pre></details>'


def metrics(pop):
    return {r['metric']:r for r in pop['scalar_metrics']}


def figure_setup():
    font_path=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    if not font_path.exists():raise ValueError('CJK report font is unavailable')
    font_manager.fontManager.addfont(str(font_path))
    font_name=font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams.update({'font.family':font_name,'axes.unicode_minus':False,'font.size':10,'axes.titlesize':12,'axes.labelsize':10,'svg.fonttype':'none'})


def style_axes(ax,ylabel):
    ax.set_ylabel(ylabel)
    ax.grid(axis='y',color='#dce3e9',linewidth=.7,zorder=0)
    ax.spines[['top','right']].set_visible(False)
    ax.set_axisbelow(True)


def bar_labels(ax, bars, digits=1):
    for bar in bars:
        value=bar.get_height()
        ax.text(bar.get_x()+bar.get_width()/2,value+0.20,f'{value:.{digits}f}',ha='center',va='bottom',fontsize=8,color='#26394a')


def population_pair_panel(ax,nobel,academy,keys,title,unit_scale=100):
    names=[];obs=[];exp=[]
    for pop,label in [(nobel,'诺奖'),(academy,'非诺奖院士')]:
        m=metrics(pop)
        for key in keys:
            names.append(label+'\n'+METRIC_LABELS[key])
            divisor=5 if key.endswith('_count') else 1
            obs.append(unit_scale*m[key]['observed_mean_or_rate']/divisor)
            exp.append(unit_scale*m[key]['calendar_expected_mean_or_rate']/divisor)
    x=np.arange(len(names));w=.34
    b=ax.bar(x-w/2,obs,w,color=COLORS['obs'],label='观察',zorder=3)
    ax.bar(x+w/2,exp,w,color=COLORS['expected'],label='出生年日历期望',zorder=3)
    ax.set_xticks(x,names);ax.set_title(title,pad=12)
    ax.set_ylim(0,max(obs+exp)*1.27+1)
    style_axes(ax,'五位占比（%）' if keys[0].endswith('_count') else '人数比例（%）')
    bar_labels(ax,b)


def dm_panel(ax,pop,title):
    rows=pop['day_master_distribution'];lookup={r['stem']:r for r in rows}
    x=np.arange(10);w=.36
    obs=[100*lookup[s]['observed_fraction'] for s in STEMS]
    exp=[100*lookup[s]['calendar_expected_fraction'] for s in STEMS]
    b=ax.bar(x-w/2,obs,w,color=COLORS['obs'],zorder=3)
    ax.bar(x+w/2,exp,w,color=COLORS['expected'],zorder=3)
    ax.set_xticks(x,STEMS);ax.set_title(title+f"（n={pop['n']}）",pad=12)
    ax.set_ylim(0,max(obs+exp)*1.27+1)
    style_axes(ax,'日主人数比例（%）');bar_labels(ax,b)


def plot_main(result,outdir):
    primary=result['cases']['strict_primary']['populations'];expanded=result['cases']['expanded']['populations']
    fig,axs=plt.subplots(2,2,figsize=(14.2,10.4))
    population_pair_panel(axs[0,0],primary['Nobel'],primary['academy'],['PI_count','SG_count'],'偏印与伤官：严格来源、本气五位')
    population_pair_panel(axs[0,1],primary['Nobel'],primary['academy'],['GY','SGY'],'狭义组合：严格来源、满足条件的人数')
    dm_panel(axs[1,0],primary['Nobel'],'诺奖严格来源十天干日主')
    dm_panel(axs[1,1],expanded['Nobel'],'诺奖扩展来源十天干日主')
    fig.suptitle('诺奖与非诺奖院士：观察分布及出生年日历期望',fontsize=18,y=.98)
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.945),ncol=2,frameon=False)
    fig.subplots_adjust(top=.85,bottom=.12,hspace=.45,wspace=.21)
    fig.text(.065,.065,'一人是一个样本。偏印、伤官占比＝五位计数总和／(5×人数)；组合与日主按人数计。',fontsize=10,color='#425a6c')
    fig.text(.065,.037,'日历期望是同出生年有效日期均匀抽样的模型基线。诺奖十干图仅作描述；H3正式检验使用诺奖与非诺奖院士去重并集。',fontsize=10,color='#425a6c')
    save_figure(fig,outdir,'Nobel_primary_descriptives')


def hidden_rows(desc,source):
    group=desc['groups'][source]
    # The descriptor adapter is explicit: this list must expose all eight models
    # and both traits; no model is chosen after inspecting the values.
    value=group.get('hidden_PI_SG_models',group.get('hidden_models',group.get('hidden_PI_SG')))
    if value is None:
        raise ValueError('Descriptor hidden-model schema is missing')
    if isinstance(value,list):
        return {(r['model'],r['trait']):r for r in value}
    rows={}
    for model,traits in value.items():
        if isinstance(traits,list):
            for row in traits:rows[(model,row['trait'])]=row
        else:
            for trait,row in traits.items():rows[(model,trait)]=row
    return rows


def hvalue(row,field):
    aliases={'observed_share':['position_share','observed_share_of_positions','observed_position_share','observed_share'],
             'expected_share':['calendar_expected_share_of_positions','calendar_expected_position_share','calendar_expected_share']}
    for key in aliases[field]:
        if key in row:return float(row[key])
    raise ValueError('Hidden metric absent: '+field)


def plot_hidden(desc,outdir):
    strict=hidden_rows(desc,'strict');expanded=hidden_rows(desc,'expanded')
    fig,axs=plt.subplots(2,2,figsize=(14.2,10.6))
    x=np.arange(4);width=.18
    for r,trait in enumerate(['PI','SG']):
        for c,start in enumerate([0,4]):
            ax=axs[r,c];models=MODEL_NAMES[start:start+4]
            vals=[100*hvalue(source[(model,trait)],field) for source,field in [(strict,'observed_share'),(strict,'expected_share'),(expanded,'observed_share'),(expanded,'expected_share')] for model in models]
            for k,(source,field,color,label) in enumerate([(strict,'observed_share',COLORS['obs'],'严格观察'),(strict,'expected_share',COLORS['expected'],'严格日历期望'),(expanded,'observed_share',COLORS['expanded'],'扩展观察'),(expanded,'expected_share',COLORS['expected_expanded'],'扩展日历期望')]):
                heights=[100*hvalue(source[(model,trait)],field) for model in models]
                ax.bar(x+(k-1.5)*width,heights,width,color=color,label=label,zorder=3)
            ax.set_xticks(x,RULE_LABELS)
            ax.set_ylim(0,max(vals)*1.25+1)
            ax.set_title(('偏印' if trait=='PI' else '伤官')+'：'+('五个已知日期位置' if c==0 else '七位、12时支等权边际化'),pad=12)
            style_axes(ax,'对应五位／七位的占比（%）')
    fig.suptitle('偏印与伤官：冻结藏干编码和未知时柱敏感性',fontsize=18,y=.98)
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.94),ncol=4,frameon=False)
    fig.subplots_adjust(top=.84,bottom=.14,hspace=.4,wspace=.22)
    fig.text(.065,.083,'所有模型均预先保留，柱色不表示显著性。五位口径排除日干与时柱；七位模型不是已知出生时刻。',fontsize=10,color='#425a6c')
    fig.text(.065,.055,'严格来源与扩展来源互相包含，不是独立验证。藏干和时柱结果仅作描述；原18项确认性检验使用严格来源、本气五位。',fontsize=10,color='#425a6c')
    fig.text(.065,.027,'至少一次出现的人数概率与位点占比不同；完整概率及对应日历期望见报告表。',fontsize=10,color='#425a6c')
    save_figure(fig,outdir,'Nobel_hidden_descriptives')


def save_figure(fig,outdir,name):
    outdir.mkdir(parents=True,exist_ok=True)
    fig.savefig(outdir/(name+'.png'),dpi=180,facecolor='white')
    fig.savefig(outdir/(name+'.svg'),facecolor='white')
    plt.close(fig)


def test_table(tests,primary=False):
    rows=[]
    for t in tests:
        test_id=t['test_id'];diagnostics=t.get('diagnostics',{})
        reject=t.get('reject_primary_Holm18_0_05',False)
        gated=diagnostics.get('raw_direction_gate',True)
        support=t.get('supports_original_directional_prediction',reject and gated)
        status=('通过' if support else '未通过') if primary else '敏感性参照'
        if t.get('status')=='not_estimable':status='不可估计'
        rows.append([test_id,TEST_LABELS.get(test_id,test_id),t.get('observed_statistic'),t.get('raw_effect'),t.get('excess_effect'),t.get('p_nominal'),t.get('p_Holm18_reference'),status,t.get('unadjusted95CI')])
    return table(['ID','预设检验','观察统计量','原始效应','日历超额效应','原始 p','Holm18' if primary else 'Holm18参照','主决策' if primary else '角色','未校正95%区间'],rows)


def group_summary_table(case):
    rows=[]
    for key,label in [('Nobel','诺奖'),('academy','非诺奖院士'),('union','两组去重并集')]:
        pop=case['populations'][key]
        for row in pop['scalar_metrics']:
            rows.append([label,pop['n'],METRIC_LABELS.get(row['metric'],row['metric']),row['unit'],row['observed_mean_or_rate'],row['calendar_expected_mean_or_rate'],row['observed_minus_expected'],row.get('raw_unadjusted95CI'),row.get('excess_unadjusted95CI')])
    return table(['人群','人数','指标','单位','观察','日历期望','观察−期望','观察95%区间','超额95%区间'],rows)


def dm_table(pop):
    return table(['日主','人数','日历期望人数','观察比例','日历期望比例'],[[r['stem'],r['observed_people'],r['calendar_expected_people'],pct(r['observed_fraction']),pct(r['calendar_expected_fraction'])] for r in pop['day_master_distribution']])


def tg_table(pop):
    return table(['十神','五位总计数','每人均数','日历期望每人均数','五位占比','日历期望五位占比','每人均数超额'],[[r['ten_god'],r['observed_count_sum'],r['observed_count_mean_per_person'],r['calendar_expected_count_mean_per_person'],pct(r['observed_share_of_five_positions']),pct(r['calendar_expected_share_of_five_positions']),r['excess_count_mean_per_person']] for r in pop['ten_gods']])


def h4_tables(h4):
    reference=h4['H4_PI'];countries=reference['institution_order'];weights=reference['effective_weights'];rows=[]
    for j,country in enumerate(countries):
        row=[country,weights[j]]
        for key in ['H4_PI','H4_SG','H4_GY','H4_SGY','H4_WATER']:
            a=h4[key];obs=float(np.asarray(a['raw_means'][j]).reshape(-1)[0]);exp=float(np.asarray(a['calendar_expected_means'][j]).reshape(-1)[0])
            row.append((plain(obs)+' / '+plain(exp)) if key in ['H4_PI','H4_SG'] else (pct(obs)+' / '+pct(exp)))
        rows.append(row)
    result=table(['院体','分数归属有效人数','偏印每人均数：观察 / 期望','伤官每人均数：观察 / 期望','官印率：观察 / 期望','伤官配印率：观察 / 期望','水日主率：观察 / 期望'],rows)
    dm=h4['H4_DM10']
    result+='<h3>六院十干日主：分数归属人数比例</h3>'
    result+=table(['院体',*STEMS],[[country,*[pct(x) for x in dm['raw_means'][j]]] for j,country in enumerate(countries)])
    result+='<h3>对应日历期望十干比例</h3>'
    result+=table(['院体',*STEMS],[[country,*[pct(x) for x in dm['calendar_expected_means'][j]]] for j,country in enumerate(countries)])
    return result


def descriptive_section(desc):
    result=''
    for source in ['strict','expanded']:
        group=desc['groups'][source]
        result+='<h3>'+('严格来源' if source=='strict' else '扩展来源')+'完整描述</h3>'
        rows=hidden_rows(desc,source)
        result+=table(['模型','指标','每人均数','日历期望均数','位点占比','日历期望位点占比','至少一次人数概率','日历期望至少一次概率'],[[model,trait,rows[(model,trait)].get('mean_count_per_person'),rows[(model,trait)].get('calendar_expected_mean_count'),pct(hvalue(rows[(model,trait)],'observed_share')),pct(hvalue(rows[(model,trait)],'expected_share')),pct(rows[(model,trait)].get('person_presence_probability')),pct(rows[(model,trait)].get('calendar_expected_person_presence_probability'))] for model in MODEL_NAMES for trait in ['PI','SG']])
        if 'TenGod_M0' in group:
            result+='<h4>本气十神：人数至少出现一次的概率</h4>'
            result+=table(['十神','至少一次人数','观察人数概率','日历期望人数概率','观察−期望（百分点）'],[[r['label'],r['people_at_least_one'],pct(r['person_presence_probability']),pct(r['calendar_expected_person_presence_probability']),r['excess_person_presence_pp']] for r in group['TenGod_M0']])
        if 'decade_tables' in group:
            bins=group['decade_tables']
            result+='<h4>全部出生十年段：日主人数</h4>'
            result+=table(['出生十年段','人数',*STEMS],[[b['decade'],b['people'],*b['DM_people']] for b in bins])
            result+='<h4>全部出生十年段：本气五位十神计数</h4>'
            result+=table(['出生十年段','人数',*GODS],[[b['decade'],b['people'],*b['TG_count_totals']] for b in bins])
            result+='<p class="muted">这些是完整描述表，不含新的年代富集或趋势检验。人数少于20的年代也保留；各段对应日历期望及完整概率见下方完整描述。</p>'
        for key in ['TenGod_M0','DayMaster10','decade_tables','ten_gods','ten_god_distribution','day_master_distribution','decades','birth_decades']:
            if key in group:result+=details(key+'：完整精确数值',group[key])
        result+=details('该来源全部描述与编码元数据',group)
    return result


CSS='''body{font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif;color:#20313f;background:#f5f7fa;margin:0;line-height:1.65}main{max-width:1450px;margin:32px auto;padding:34px 40px;background:#fff;border-radius:12px}h1{font-size:28px;line-height:1.4;margin-top:0}h2{font-size:21px;margin-top:38px;border-bottom:2px solid #dce5ec;padding-bottom:8px}h3{margin-top:28px;font-size:17px}.lead{font-size:17px}.note{padding:14px 18px;background:#edf4f8;border-left:4px solid #377b9e}.muted{color:#61717f;font-size:13px}.table-scroll{overflow-x:auto;margin:14px 0 24px}table{border-collapse:collapse;width:100%;font-size:13px;white-space:normal}th,td{border:1px solid #dce3e9;padding:9px 11px;text-align:left;vertical-align:top}th{background:#e9f0f5;font-weight:700}tbody tr:nth-child(even){background:#f8fafc}td{max-width:350px;overflow-wrap:anywhere}img{display:block;width:100%;height:auto;border:1px solid #e5ebef;margin:18px 0}details{margin:10px 0;padding:10px 14px;border:1px solid #dce3e9;border-radius:5px}summary{cursor:pointer;font-weight:600}pre{font-family:ui-monospace,monospace;font-size:12px;overflow-x:auto;background:#f6f8fa;padding:15px;white-space:pre-wrap;overflow-wrap:anywhere}a{color:#246b94}@media print{body{background:#fff}main{margin:0;padding:15px;border-radius:0}.table-scroll{overflow:visible}details{break-inside:avoid}img{break-inside:avoid}}'''


def render_html(result,desc,receipt,qa,manifest):
    main=result['cases']['strict_primary'];primary=main['tests']
    rejected=[t['test_id'] for t in primary if t.get('supports_original_directional_prediction',t.get('reject_primary_Holm18_0_05') and t.get('diagnostics',{}).get('raw_direction_gate',True))]
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>诺奖与院士：原18项总体检验</title><style>'+CSS+'</style><main>',
           '<h1>诺奖与院士：原18项总体检验揭晓</h1>',
           '<p class="lead">北半球、1835—1985年出生、截至2025年会籍／获奖。严格来源 S1＋S2 为主，扩展来源再加入 S3。主组为完整官方名录已确认的诺奖科学奖获得者，不以旧候选组替代。</p>',
           '<p class="note">严格来源、狭义、本气五位、同出生年日历零模型的18项检验统一使用 Holm FWER＝0.05。通过主决策的项目：'+esc('、'.join(rejected) if rejected else '无')+'。单一指标不能代表整套理论获得验证。</p>',
           '<p class="muted">该页数值来自完成的结果文件；原始假设先于V4排盘锁定，诺奖／总体检验代码与执行范围亦在本次聚合结果计算前远程锁定。主18项与此前逐院36项、年代补充检验分开。</p>',
           '<h2>人群与统计口径</h2>']
    parts.append(table(['方案','诺奖','非诺奖院士','两组去重并集'],[[CASE_LABELS[k],result['cases'][k]['populations']['Nobel']['n'],result['cases'][k]['populations']['academy']['n'],result['cases'][k]['populations']['union']['n']] for k in CASE_ORDER]))
    parts.extend(['<p>五位＝年干、年支本气、月干、月支本气、日支本气；日干只作十神参照，不加入恒定比肩。每人是一个样本。官印主口径＝正官与正印至少各一次；伤官配印＝伤官与正印至少各一次，属于共现指标。</p>',
                  '<p>日历期望固定每人的公历出生年，在该年365／366个有效日期中均匀抽日；它不是普通人实际出生日期样本，也不把所有十神强设为10%。99,999次Monte Carlo、PCG64、逐检验固定种子，包含等值，原始 p＝(1＋极端次数)／100,000。区间为10,000次人物bootstrap的未多重校正95%描述区间。</p>',
                  '<h2>18项确认性主检验</h2>',test_table(primary,primary=True),
                  '<p>表中原始效应与日历超额效应不能互换；偏印／伤官的均数以每人五位计数计，组合及水日主以人数率计。直接对比按两组共有出生十年段标准化，须同时满足完整原始差方向一致；H2d还须原始、超额斜率均为正。</p>',
                  '<h2>主方案：两组与并集的观察值和期望</h2>',group_summary_table(main),
                  '<img src="figures/Nobel_primary_descriptives.png" alt="严格来源诺奖与非诺奖院士主指标，以及诺奖严格和扩展十干日主描述">',
                  '<h2>诺奖完整十神与日主分布</h2>'])
    for source,key in [('strict_primary','严格来源'),('expanded','扩展来源')]:
        pop=result['cases'][source]['populations']['Nobel'];parts.extend(['<h3>'+key+'：本气五位十神</h3>',tg_table(pop),'<h3>'+key+'：十天干日主</h3>',dm_table(pop)])
    parts.extend(['<h2>直接比较、年代趋势与六院异质性</h2>',
                  '<p>直接比较在每个共有出生十年段内置换诺奖／院士标签，固定组别人数与合并人数权重。H2d以出生年为轴，同时控制前五列院体分数归属，显示每十年原始及年历超额斜率。H4按出生十年段×有效来源支持类，移动完整人物指标向量，固定每个人的1/k多院归属向量。</p>',
                  '<p>六院标签表示院体所在国家，不能解释为国籍、出生国或民族差异；同一人物跨院身份保留。H3的十干／水检验人群是诺奖＋非诺奖院士去重并集，不能将并集显著性写成诺奖组单独显著。</p>'])
    for t in primary:
        if t['test_id'] in ['H1c_PI','H1c_SG','H2c','H2d']:parts.append(details(t['test_id']+'：'+TEST_LABELS[t['test_id']]+'完整效应、年代与区间',t))
    if main['H4_description']:parts.append(h4_tables(main['H4_description']))
    parts.append(details('六院完整有效权重、观察均数、日历期望与中心化均数',main['H4_description']))
    parts.extend(['<h2>全部预声明敏感性</h2>',
                  '<p>以下六项敏感性与主方案一并披露，不是独立验证。敏感性中的Holm18为对应方案内参照，不能替代原确认性主族或挽救未通过的主预测。</p>'])
    for key in CASE_ORDER[1:]:
        case=result['cases'][key];parts.extend(['<h3>'+CASE_LABELS[key]+'</h3>',test_table(case['tests']),details('该方案的完整人群、效应、区间、诊断与不能估计项',case)])
    parts.extend(['<h2>藏干与未知时柱：描述性结果</h2>',
                  '<p>五位藏干编码沿用本气、优先透干、透干均分、任一透干规则；七位模型对12个传统时支均匀边际化，不声称恢复了真实出生时辰。下表与图不新增确认性检验，不用它们选择最有利模型。</p>',
                  '<img src="figures/Nobel_hidden_descriptives.png" alt="偏印伤官的所有冻结藏干及均匀时柱编码描述">',descriptive_section(desc),
                  '<h2>来源、限制与复核</h2>',
                  '<p>保留V4日期来源分级、跨院人物去重、日期／会籍hold与CAS26搁置决定。扩展来源包含严格来源，来源缺失与生日缺失机制不同，未伪造逆概率权重。已知日期为既有公历分析坐标；统一正午只是历法参照，不代表出生时刻。</p>',
                  '<p>这是选定科学家样本与条件日历模型的比较，不能据此估计普通人凭出生日期成为院士／诺奖的概率，亦不构成因果结论。没有独立确认队列。</p>',
                  details('执行收据',receipt),details('独立统计QA',qa),details('图像与结果文件绑定',manifest),
                  '<p class="muted">结果、完整描述、元数据及QA均随ZIP提供；代码在Git记录。本报告未将旧PR31结果重新加入当前主分析。</p></main></html>'])
    return '\n'.join(parts)


def verify_gate(result,desc,receipt,qa):
    if qa.get('status')!='PASS':raise ValueError('Independent statistical QA must PASS')
    if not (receipt.get('remote_plan_and_code_verified_before_summary') or receipt.get('remote_Git_lock_verified_before_inference')):raise ValueError('Remote prereveal receipt is required')
    if set(result['cases'])!=set(CASE_ORDER):raise ValueError('All seven cases must be present')
    order=result['test_order']
    if len(order)!=18 or set(order)!=set(TEST_LABELS):raise ValueError('Original18 test order differs')
    for key in CASE_ORDER:
        if [t['test_id'] for t in result['cases'][key]['tests']]!=order:raise ValueError('Case lost/reordered a test')
    if result['cases']['strict_primary']['populations']['Nobel']['n']!=621:raise ValueError('Nobel main N changed')
    if result['cases']['expanded']['populations']['Nobel']['n']!=627:raise ValueError('Nobel expanded N changed')
    for source in ['strict','expanded']:
        hidden=hidden_rows(desc,source)
        if set(hidden)!=set((m,t) for m in MODEL_NAMES for t in ['PI','SG']):raise ValueError('Hidden models incomplete')


def build(args):
    work=Path(args.work).resolve();result_path=Path(args.results or work/'GLOBAL18_RESULTS.json');desc_path=Path(args.descriptives or work/'NOBEL_DESCRIPTIVES.json');qa_path=Path(args.qa or work/'INDEPENDENT_QA.json');receipt_path=Path(args.execution_receipt or work/'EXECUTION_RECEIPT.json')
    result,desc,qa,receipt=map(load,[result_path,desc_path,qa_path,receipt_path]);verify_gate(result,desc,receipt,qa)
    if qa.get('hashes',{}).get('results')!=sha(result_path):raise ValueError('Independent QA is not bound to this exact result file')
    out=Path(args.output or work/'report').resolve()
    if out.exists():raise FileExistsError('Do not overwrite an already built report')
    out.mkdir(parents=True);figdir=out/'figures';figdir.mkdir()
    figure_setup();plot_main(result,figdir);plot_hidden(desc,figdir)
    manifest={'schema':'Nobel_global18_report_figure_manifest_v1','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'input_results_sha256':sha(result_path),'input_descriptives_sha256':sha(desc_path),'builder_sha256':sha(__file__),'fixed_design_sha256':sha(work/'FIGURE_DESIGN.md'),'files':{p.name:sha(p) for p in sorted(figdir.iterdir())}}
    (figdir/'FIGURE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (out/'REPORT.html').write_text(render_html(result,desc,receipt,qa,manifest))
    for src,name in [(result_path,'GLOBAL18_RESULTS.json'),(desc_path,'NOBEL_DESCRIPTIVES.json'),(qa_path,'INDEPENDENT_QA.json'),(receipt_path,'EXECUTION_RECEIPT.json'),(work/'FIGURE_DESIGN.md','FIGURE_DESIGN.md')]:shutil.copyfile(src,out/name)
    for name in ['SCOPE.json','POPULATION_METADATA.json']:
        if (work/name).exists():shutil.copyfile(work/name,out/name)
    if (work/'inputs/POPULATION_QA_METADATA.json').exists():shutil.copyfile(work/'inputs/POPULATION_QA_METADATA.json',out/'POPULATION_QA_METADATA.json')
    # Actual visual QA is intentionally a separate step after PNG inspection.
    print(json.dumps({'status':'RENDERED_AWAITING_VISUAL_QA','output':str(out),'manifest_sha256':sha(figdir/'FIGURE_MANIFEST.json'),'figures':list(manifest['files'])}))


def package(args):
    out=Path(args.output or Path(args.work)/'report').resolve();visual=load(out/'figures/VISUAL_QA.json');manifest=load(out/'figures/FIGURE_MANIFEST.json')
    if visual.get('status')!='PASS':raise ValueError('Actual visual QA must PASS before packaging')
    if visual.get('input_results_sha256')!=manifest['input_results_sha256']:raise ValueError('VisualQA is not bound to these results')
    for name,digest in manifest['files'].items():
        if sha(out/'figures'/name)!=digest:raise ValueError('Figure bytes changed after rendering')
    checks={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'MANIFEST.sha256.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    archive=Path(args.archive or out.parent.parent/'scientist_Nobel_global18_reveal_v1.zip').resolve()
    if archive.exists():raise FileExistsError('Do not overwrite existing report ZIP')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(out.parent)))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise AssertionError('ZIP corruption')
        if any(Path(name).suffix=='.py' for name in z.namelist()):raise AssertionError('Code accidentally included')
        if not any(name.endswith('/REPORT.html') for name in z.namelist()):raise AssertionError('Report missing')
    print(json.dumps({'status':'PASS','archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'members':len(checks)+1}))


def self_test():
    # Synthetic renderer fixtures only; no study file is read.
    rows=[{'test_id':k,'observed_statistic':0.1,'raw_effect':0.02,'excess_effect':0.01,'p_nominal':0.2,'p_Holm18_reference':1.,'reject_primary_Holm18_0_05':False,'unadjusted95CI':[-.01,.04],'diagnostics':{}} for k in TEST_LABELS]
    text=test_table(rows,True)
    assert text.count('<tbody>')==1 and all(k in text for k in TEST_LABELS)
    assert plain(None)=='—' and plain(float('nan'))=='—' and pct(.1234)=='12.34%'
    assert '&lt;' in table(['x'],[['<script>']])
    assert set(TEST_LABELS)==set(t['test_id'] for t in rows) and len(CASE_ORDER)==7
    def fixture_pop(n):
        return {'n':n,'scalar_metrics':[{'metric':m,'unit':'synthetic','observed_mean_or_rate':.2,'calendar_expected_mean_or_rate':.18,'observed_minus_expected':.02} for m in METRIC_LABELS],
                'ten_gods':[{'ten_god':g,'observed_count_sum':n//2,'observed_count_mean_per_person':.5,'calendar_expected_count_mean_per_person':.5,'observed_share_of_five_positions':.1,'calendar_expected_share_of_five_positions':.1,'excess_count_mean_per_person':0.} for g in GODS],
                'day_master_distribution':[{'stem':s,'observed_people':n//10,'calendar_expected_people':n/10,'observed_fraction':.1,'calendar_expected_fraction':.1} for s in STEMS]}
    h4={key:{'institution_order':list('ABCDEF'),'effective_weights':[100]*6,'raw_means':[[.2]* (10 if key=='H4_DM10' else 1)]*6,'calendar_expected_means':[[.18]* (10 if key=='H4_DM10' else 1)]*6} for key in ['H4_PI','H4_SG','H4_GY','H4_SGY','H4_DM10','H4_WATER']}
    fake={'test_order':list(TEST_LABELS),'cases':{k:{'populations':{'Nobel':fixture_pop(627 if k=='expanded' else 621),'academy':fixture_pop(1000),'union':fixture_pop(1621)},'tests':rows,'H4_description':h4} for k in CASE_ORDER}}
    hidden=[{'model':m,'trait':t,'mean_count_per_person':.5,'calendar_expected_mean_count':.45,'position_share':.1,'calendar_expected_position_share':.09,'person_presence_probability':.4,'calendar_expected_person_presence_probability':.38} for m in MODEL_NAMES for t in ['PI','SG']]
    desc={'groups':{s:{'hidden_PI_SG_models':hidden} for s in ['strict','expanded']}}
    receipt={'remote_plan_and_code_verified_before_summary':True};qa={'status':'PASS'}
    verify_gate(fake,desc,receipt,qa)
    text=render_html(fake,desc,receipt,qa,{})
    assert text.count('<table')>=14 and all(label in text for label in CASE_LABELS.values())
    with tempfile.TemporaryDirectory(prefix='nobel-report-synthetic-') as tmp:
        figure_setup();plot_main(fake,Path(tmp));plot_hidden(desc,Path(tmp))
        assert len(list(Path(tmp).glob('*.png')))==2 and len(list(Path(tmp).glob('*.svg')))==2
    return {'schema':'Nobel_report_synthetic_QA_v1','status':'PASS','study_results_read':False,'test_rows':18,'cases':7,'fixed_models':8,'HTML_escaping':True,'all_preselected_metrics_retained':True,'complete_fixture_HTML_render':True,'synthetic_eight_panel_PNG_SVG_render':True}


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',default=str(WORK));p.add_argument('--results');p.add_argument('--descriptives');p.add_argument('--qa');p.add_argument('--execution-receipt');p.add_argument('--output');p.add_argument('--archive');p.add_argument('--package',action='store_true');p.add_argument('--self-test',action='store_true');args=p.parse_args()
    if args.self_test:print(json.dumps(self_test(),ensure_ascii=False));return
    if args.package:package(args)
    else:build(args)


if __name__=='__main__':main()
