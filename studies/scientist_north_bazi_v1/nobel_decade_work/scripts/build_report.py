#!/usr/bin/env python3
"""Fixed report/figure renderer for the post-reveal Nobel decade exploration."""
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

WORK=Path(__file__).resolve().parents[1]
SOURCES=['strict','expanded']
SOURCE_LABEL={'strict':'严格来源 S1＋S2','expanded':'扩展来源 S1＋S2＋S3'}
DECADES=list(range(1830,1990,10))
DISPLAY=list(range(1850,1970,10))
GODS=['比肩','劫财','食神','伤官','偏财','正财','七杀','正官','偏印','正印']
STEMS=list('甲乙丙丁戊己庚辛壬癸')
COLORS={'strict':'#21658d','expanded':'#d47a37'}


def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value(obj,*keys,default=None):
    for key in keys:
        if key in obj:return obj[key]
    return default


def plain(v):
    if v is None:return '—'
    if isinstance(v,bool):return '是' if v else '否'
    if isinstance(v,float):return f'{v:.6g}' if np.isfinite(v) else '—'
    if isinstance(v,(list,dict)):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
    return str(v)


def esc(v):return html.escape(plain(v))
def pct(v):return '—' if v is None else f'{100*v:.3f}%'


def table(headers,rows):
    return '<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+esc(v)+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def details(title,obj):return '<details><summary>'+esc(title)+'</summary><pre>'+html.escape(json.dumps(obj,ensure_ascii=False,indent=2))+'</pre></details>'


def endpoint_order(r):return value(r,'endpoint_order','target_order')


def definitions(r):
    raw=value(r,'endpoint_definitions','target_definitions',default={})
    return {x.get('id',x.get('endpoint_id')):x for x in raw} if isinstance(raw,list) else raw


def endpoint_label(r,eid):
    d=definitions(r).get(eid,{})
    return value(d,'label','name',default=eid)


def denominator(r,eid):
    d=definitions(r).get(eid,{})
    v=value(d,'position_denominator','display_denominator','denominator')
    if v is not None:return int(v)
    # Fixed25 order: TG10, DM10, water, GY, SGY, priorityPI/SG.
    idx=endpoint_order(r).index(eid)
    return 5 if idx<10 or idx>=23 else 1


def group(r,eid,source):return r['groups'][eid][source]
def bins(g):return g['bins']
def n_people(g):return int(value(g,'people','n','N'))
def total_K(g):return int(value(g,'total_K','target_total','target_people','observed_total','K'))


def normalize_bin(b,denom):
    n=int(value(b,'n','people'))
    o=value(b,'observed_total','observed_sum','observed_target_people','observed_count')
    cal=value(b,'calendar_expected_total','calendar_expected_sum','calendar_expected_target_people','calendar_expected_count')
    con=value(b,'conditional_expected_total','conditional_expected_sum','conditional_expected_target_people','conditional_expected_count')
    if o is None or cal is None or con is None:raise ValueError('Required count field absent in decade bin')
    return {'decade':int(b['decade']),'n':n,'observed_total':o,'calendar_expected_total':cal,'conditional_expected_total':con,
            'observed_share':None if n==0 else o/(n*denom),'calendar_expected_share':None if n==0 else cal/(n*denom),'conditional_expected_share':None if n==0 else con/(n*denom)}


def test_rows(r,source):return r['tests_by_source'][source]
def test_endpoint(t):return value(t,'endpoint_id','endpoint','target')
def test_kind(t):return value(t,'kind','test_kind')
def nominal_p(t):return value(t,'p_nominal','p_nominal_plus_one')
def adjusted_p(t):return value(t,'p_Holm50','p_Holm50_reference')


def setup_figure():
    font=Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    if not font.exists():raise ValueError('CJK font unavailable')
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font)).get_name(),'axes.unicode_minus':False,'font.size':10,'axes.titlesize':12,'svg.fonttype':'none'})


def render_figure(r,outdir):
    order=endpoint_order(r)
    selected=[order[i] for i in [8,3,20,22]]
    titles=['本气五位偏印','本气五位伤官','水日主（壬＋癸）','狭义伤官配印共现']
    fig,axs=plt.subplots(2,2,figsize=(15.2,10.8))
    data_limits=[]
    for ax,eid,title in zip(axs.flat,selected,titles):
        den=denominator(r,eid);x=np.arange(len(DISPLAY));values=[]
        for source in SOURCES:
            bb={b['decade']:b for b in [normalize_bin(b,den) for b in bins(group(r,eid,source))]}
            if any(bb[d]['n']<20 for d in DISPLAY):raise ValueError('Display bins violate fixed both-sourceN rule')
            obs=[100*bb[d]['observed_share'] for d in DISPLAY];con=[100*bb[d]['conditional_expected_share'] for d in DISPLAY]
            ax.plot(x,obs,color=COLORS[source],marker='o' if source=='strict' else 's',markersize=4.2,linewidth=1.8,label=('严格观察' if source=='strict' else '扩展观察'),zorder=3)
            ax.plot(x,con,color=COLORS[source],linestyle='--',linewidth=1.4,alpha=.9,label=('严格固定K期望' if source=='strict' else '扩展固定K期望'),zorder=2)
            values+=obs+con
        upper=max(values)*1.22+1;data_limits.append(upper)
        ax.set_ylim(0,upper);ax.set_xticks(x,[str(d) for d in DISPLAY],rotation=45,ha='right')
        ax.set_ylabel('五位占比（%）' if den==5 else '人数比例（%）');ax.set_title(title,pad=12)
        ax.grid(axis='y',color='#dce4eb',linewidth=.7);ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True)
    for ax in axs[0]:ax.set_ylim(0,max(data_limits[:2]))
    fig.suptitle('诺奖出生年代：观察分布与固定总体数量后的期望',fontsize=18,y=.985)
    handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.945),ncol=4,frameon=False)
    fig.subplots_adjust(top=.85,bottom=.17,hspace=.50,wspace=.22)
    fig.text(.065,.097,'只画预先规定的两来源人数均≥20的1850—1960年代；全部16段及各段人数保留在报告。横轴为出生十年段。',fontsize=10,color='#435d71')
    fig.text(.065,.065,'每个端点、来源各自固定整组观察总计数K，检验这些计数是否集中于某些年代。普通出生年日历期望另见完整表。',fontsize=10,color='#435d71')
    fig.text(.065,.033,'实线高点本身不是显著富集；没有局部年代p。扩展包含严格，并非独立验证。原18项总体检验不受本探索更改。',fontsize=10,color='#435d71')
    outdir.mkdir(parents=True,exist_ok=True)
    for ext in ['png','svg']:fig.savefig(outdir/('Nobel_birth_decades.'+ext),dpi=180,facecolor='white')
    plt.close(fig)


CSS='''body{margin:0;background:#f4f7fa;color:#223443;line-height:1.65;font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif}main{max-width:1420px;margin:30px auto;padding:35px 40px;background:white;border-radius:12px}h1{font-size:28px;line-height:1.4}h2{font-size:21px;margin-top:36px;border-bottom:2px solid #dae5ed;padding-bottom:7px}h3{font-size:17px;margin-top:25px}.note{background:#edf4f8;border-left:4px solid #397a9f;padding:14px 18px}.muted{font-size:13px;color:#617280}.table-scroll{overflow-x:auto;margin:14px 0 24px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dbe3e9;padding:8px 10px;vertical-align:top;text-align:left;max-width:350px;overflow-wrap:anywhere}th{background:#e8f0f6}tbody tr:nth-child(even){background:#f8fafc}img{width:100%;height:auto;border:1px solid #e3ebf0;margin:18px 0}details{border:1px solid #dce4ea;border-radius:5px;padding:10px 14px;margin:12px 0}summary{font-weight:600;cursor:pointer}pre{font:12px ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9fb;padding:14px}a{color:#246b91}@media print{body{background:white}main{padding:10px;margin:0}.table-scroll{overflow:visible}img{break-inside:avoid}}'''


def test_table(r,source):
    rows=[]
    for t in test_rows(r,source):
        eid=test_endpoint(t);kind=test_kind(t);p=adjusted_p(t)
        detail=group(r,eid,source).get('global_tests',{}).get(kind,{})
        statistic=value(t,'observed_statistic','statistic',default=value(detail,'observed_statistic','observed_integer_L'))
        den=denominator(r,eid)
        raw_slope=detail.get('raw_slope_score_per_decade')
        excess_slope=detail.get('conditional_excess_slope_score_per_decade')
        raw_pp=None if raw_slope is None else 100*raw_slope/den
        excess_pp=None if excess_slope is None else 100*excess_slope/den
        status='未通过' if p is None or p>.05 else '达到探索性校正门槛'
        if source=='expanded':status='来源敏感性参照'
        if t.get('status')=='not_estimable':status='不可估计'
        rows.append([value(t,'test_id','id'),endpoint_label(r,eid),'年代异质性Q' if kind in ['global_heterogeneity','heterogeneity','Q'] else '双侧线性L',statistic,raw_pp,excess_pp,nominal_p(t),p,status])
    return table(['ID','端点','总体问题','观察统计量','原始比例斜率（百分点／十年）','固定K超额比例斜率（百分点／十年）','原始p','严格Holm50' if source=='strict' else '扩展Holm50参照','结果角色'],rows)


def mapping_section(mapping):
    rows=[]
    for p in mapping['people']:
        elig=p['year_pillar_eligible'];same=p.get('nearest_same_day_date')
        result='无三柱完全对应；最近同日柱日期的月柱不同' if elig else '年柱已不同，不能完整对应2027／2028'
        if p['full_matches_2027_2028']:result='完整对应：'+','.join(p['full_matches_2027_2028'])
        rows.append([p['name'],p['DOB'],' '.join(p['original_pillars']),same,' '.join(p.get('nearest_same_day_pillars',[])) or None,result])
    return '<h2>诺奖生日对应2027／2028</h2><p>沿用上一轮的日期范围，自1967-08-16起，现有冻结诺奖组共有'+esc(mapping['total_people_after_threshold'])+'人，其中'+esc(mapping['same_year_pillar_candidates'])+'人的年柱与丁未／戊申相符。逐日搜索公历2027—2028，完整年月日三柱对应人数为'+esc(mapping['full_matching_people'])+'。未知时柱不补填。</p><p class="note">表中“最近同日柱日期”仅用于解释未匹配原因，不能当作三柱对应日期；这些日期的月柱与原生日不同。</p>'+table(['人物','原生日','原年月日三柱','最近同日柱日期（非完整对应）','该日三柱','完整匹配结论'],rows)+details('日期对应独立核验完整记录',mapping)


def render_html(r,receipt,qa,mapping,manifest):
    order=endpoint_order(r);strict_rej=sum(adjusted_p(t) is not None and adjusted_p(t)<=.05 for t in test_rows(r,'strict'))
    first=group(r,order[0],'strict');expanded=group(r,order[0],'expanded')
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>诺奖出生年代探索与日期对应</title><style>'+CSS+'</style><main>',
           '<h1>诺奖出生年代探索与2027／2028日期对应</h1>',
           '<p>沿用冻结北半球诺奖科学奖人群：严格来源'+esc(n_people(first))+'人，扩展来源'+esc(n_people(expanded))+'人，出生窗口1835—1985。原诺奖／院士18项总体检验保持原输出不变。</p>',
           '<p class="note">本次是诺奖揭晓后的探索。25个端点各做年代异质性Q与双侧线性L两个总体检验，严格来源共50项统一Holm校正；达到该探索性门槛的项目数为'+esc(strict_rej)+'。扩展仅作来源敏感性参照，没有局部年代p。</p>',
           '<h2>这次检验什么</h2>',
           '<p>先固定每个端点在整组观察到的总计数K，再看这些计数如何分布在出生年代。它区分“整组某十神／日主偏多”和“这批计数额外集中于某年代”。固定K后的条件期望不同于普通同出生年日历期望，二者均保留在完整表中。</p>',
           '<p>端点为本气五位十神10项、十天干日主10项、水日主、狭义官印、狭义伤官配印、五位优先透干偏印和伤官。十神／优先透干每人贡献0—5计数，位点占比＝总计数／(5×人数)；日主、组合为0／1人数率。一个人始终是一个样本。</p>',
           '<p>所有16个十年段都进入完整表与总体检验；图只展示事先按样本量选定的12段。1830段只含1835—1839，1980段止于1985；空段比例不定义，小样本段不删除。线性L为双侧偏离条件期望的检验，不预设正向或负向。</p>',
           '<img src="figures/Nobel_birth_decades.png" alt="诺奖本气偏印、本气伤官、水日主、狭义伤官配印的固定出生年代展示">',
           '<h2>严格来源：全部50项总体检验</h2>',test_table(r,'strict'),
           '<h2>扩展来源：全部50项来源敏感性参照</h2>',test_table(r,'expanded'),
           '<p>扩展来源包含严格来源，不是独立重复验证。不可根据某一版本更小的p值选择最终口径。局部柱高、线高或某段百分比大，不等于该段已被证实富集。</p>',
           '<h2>全部25端点 × 16年代 × 两来源</h2>']
    for eid in order:
        den=denominator(r,eid);parts.append('<h3>'+esc(endpoint_label(r,eid))+'</h3>')
        for source in SOURCES:
            g=group(r,eid,source);bb=[normalize_bin(b,den) for b in bins(g)]
            parts.append('<p><strong>'+SOURCE_LABEL[source]+'</strong>：n＝'+esc(n_people(g))+'，整组固定K＝'+esc(total_K(g))+'；'+('每人0—5计数，百分比以5×人数为分母。' if den==5 else '每人0／1，百分比以人数为分母。')+'</p>')
            parts.append(table(['出生十年段','人数N','观察总计数','普通年历期望总计数','固定K条件期望总计数','观察比例','普通年历期望比例','固定K条件期望比例'],[[b['decade'],b['n'],b['observed_total'],b['calendar_expected_total'],b['conditional_expected_total'],pct(b['observed_share']),pct(b['calendar_expected_share']),pct(b['conditional_expected_share'])] for b in bb]))
            parts.append(details(SOURCE_LABEL[source]+'：总体统计量与条件分布诊断',value(g,'global_tests','tests',default={})))
    if mapping is not None:parts.append(mapping_section(mapping))
    parts.extend(['<h2>复核与解释边界</h2>',
                  '<p>本分析不新增时柱模型、局部年代检验或结果选择的出生窗口。条件日历期望不是普通人出生日期的实测分布。出生队列关联不证明学术成就的因果机制，也不构成对未来婴儿成就的预测。</p>',
                  details('本次执行收据',receipt),details('统计独立核验',qa),details('结果与图形SHA256绑定',manifest),
                  '<p class="muted">完整结果、独立QA、日期对应QA、固定设计与元数据随ZIP保留。代码存于Git；本包不包含代码。所有展示类别与四面板指标在新年代结果产生前确定。</p></main></html>'])
    return '\n'.join(parts)


def verify(r,qa,receipt):
    if qa.get('status')!='PASS':raise ValueError('IndependentQA must PASS')
    if not (receipt.get('remote_plan_and_code_verified_before_summary') or receipt.get('remote_Git_lock_verified_before_inference')):raise ValueError('Remote prereveal receipt missing')
    order=endpoint_order(r)
    if len(order)!=25 or len(set(order))!=25:raise ValueError('Expected fixed25 endpoints')
    for source in SOURCES:
        tt=test_rows(r,source)
        if len(tt)!=50:raise ValueError('Expected all50 tests in each source')
        for eid in order:
            g=group(r,eid,source)
            if n_people(g)!=(621 if source=='strict' else 627):raise ValueError('Nobelpopulation changed')
            if [b['decade'] for b in bins(g)]!=DECADES:raise ValueError('All16bins required in original order')
            if sum(int(value(b,'n','people')) for b in bins(g))!=n_people(g):raise ValueError('Decade N total mismatch')


def build(args):
    w=Path(args.work).resolve();rp=Path(args.results or w/'NOBEL_DECADE_RESULTS.json');qp=Path(args.qa or w/'INDEPENDENT_QA.json');ep=Path(args.execution_receipt or w/'EXECUTION_RECEIPT.json')
    r,qa,receipt=map(load,[rp,qp,ep]);verify(r,qa,receipt)
    if value(qa.get('hashes',{}),'results',default=qa.get('input_results_sha256'))!=sha(rp):raise ValueError('QA is not bound to exact results')
    out=Path(args.output or w/'report').resolve()
    if out.exists():raise FileExistsError('Refuse report overwrite')
    out.mkdir(parents=True);figdir=out/'figures';figdir.mkdir();setup_figure();render_figure(r,figdir)
    manifest={'schema':'Nobel_birth_decades_figure_manifest_v1','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'input_results_sha256':sha(rp),'builder_sha256':sha(__file__),'fixed_design_sha256':sha(w/'DESIGN.md'),'display_decades':DISPLAY,'fixed_endpoint_indices':[8,3,20,22],'files':{p.name:sha(p) for p in sorted(figdir.iterdir())}}
    (figdir/'FIGURE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    mapping=load(w/'DATE_MAPPING_QA.json') if (w/'DATE_MAPPING_QA.json').exists() else None
    if mapping is not None and mapping.get('status')!='PASS':raise ValueError('Date mappingQA must PASS')
    (out/'REPORT.html').write_text(render_html(r,receipt,qa,mapping,manifest))
    for src,name in [(rp,'NOBEL_DECADE_RESULTS.json'),(qp,'INDEPENDENT_QA.json'),(ep,'EXECUTION_RECEIPT.json')]:shutil.copyfile(src,out/name)
    for name in ['DESIGN.md','DATE_MAPPING_QA.json','POPULATION_METADATA.json','SCOPE.json','LOCKED_FILES.json','EXECUTION_PLAN.md','RUNTIME_VERSIONS.json']:
        if (w/name).exists():shutil.copyfile(w/name,out/name)
    print(json.dumps({'status':'RENDERED_AWAITING_VISUAL_QA','output':str(out),'figure_manifest_sha256':sha(figdir/'FIGURE_MANIFEST.json'),'HTML_bytes':(out/'REPORT.html').stat().st_size}))


def package(args):
    out=Path(args.output or Path(args.work)/'report').resolve();q=load(out/'figures/VISUAL_QA.json');m=load(out/'figures/FIGURE_MANIFEST.json')
    if q.get('status')!='PASS' or q.get('input_results_sha256')!=m['input_results_sha256']:raise ValueError('Bound visualQA PASS required')
    for name,digest in m['files'].items():
        if sha(out/'figures'/name)!=digest:raise ValueError('Figure changed after render')
    checks={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'MANIFEST.sha256.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    archive=Path(args.archive or out.parent.parent/'scientist_Nobel_birth_decades_v1.zip').resolve()
    if archive.exists():raise FileExistsError('Refuse archive overwrite')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(out.parent)))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('Corrupt ZIP')
        if any(Path(n).suffix=='.py' for n in z.namelist()):raise ValueError('Code included in report')
    print(json.dumps({'status':'PASS','archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive),'members':len(checks)+1}))


def self_test():
    order=['TG_'+s for s in GODS]+['DM_'+s for s in STEMS]+['water','GY','SGY','priority_PI','priority_SG']
    r={'endpoint_order':order,'endpoint_definitions':{e:{'label':e,'position_denominator':5 if i<10 or i>=23 else 1} for i,e in enumerate(order)},'groups':{},'tests_by_source':{}}
    for i,eid in enumerate(order):
        r['groups'][eid]={}
        for s,n in [('strict',621),('expanded',627)]:
            nn=[2,10]+[48]*11+[81 if s=='strict' else 87,0,0]
            assert sum(nn)==n
            r['groups'][eid][s]={'people':n,'total_K':n//4,'bins':[{'decade':d,'n':a,'observed_total':a*.25,'calendar_expected_total':a*.20,'conditional_expected_total':a*.25} for d,a in zip(DECADES,nn)],'global_tests':{}}
    for s in SOURCES:r['tests_by_source'][s]=[{'test_id':e+'_'+kind,'endpoint_id':e,'kind':kind,'observed_statistic':1.,'p_nominal':.5,'p_Holm50':1.} for e in order for kind in ['global_heterogeneity','global_linear']]
    qa={'status':'PASS'};receipt={'remote_plan_and_code_verified_before_summary':True};verify(r,qa,receipt)
    m={'status':'PASS','total_people_after_threshold':1,'same_year_pillar_candidates':1,'full_matching_people':0,'people':[{'name':'Example','DOB':'1968-01-11','original_pillars':['丁未','癸丑','庚辰'],'year_pillar_eligible':True,'full_matches_2027_2028':[],'nearest_same_day_date':'2027-12-27','nearest_same_day_pillars':['丁未','壬子','庚辰']}]}
    text=render_html(r,receipt,qa,m,{})
    assert text.count('<table>')==53 and all(text.count('<td>'+e+'</td>')>=4 for e in order)
    assert '&lt;' in table(['x'],[['<script>']])
    with tempfile.TemporaryDirectory(prefix='nobel-decade-report-synthetic-') as tmp:
        setup_figure();render_figure(r,Path(tmp));assert len(list(Path(tmp).iterdir()))==2
    return {'schema':'Nobel_decade_report_synthetic_QA_v1','status':'PASS','real_outcomes_read':False,'endpoints':25,'sources':2,'global_tests_per_source':50,'all_decade_rows':800,'complete_synthetic_HTML_render':True,'fixed_four_panel_PNG_SVG_render':True,'date_nonmatch_label_checked':True}


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',default=str(WORK));p.add_argument('--results');p.add_argument('--qa');p.add_argument('--execution-receipt');p.add_argument('--output');p.add_argument('--archive');p.add_argument('--package',action='store_true');p.add_argument('--self-test',action='store_true');args=p.parse_args()
    if args.self_test:print(json.dumps(self_test(),ensure_ascii=False));return
    if args.package:package(args)
    else:build(args)


if __name__=='__main__':main()
