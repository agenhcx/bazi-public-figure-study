"""Write v7 docs from frozen outputs; root runs this after assembly and QA inputs exist."""
from pathlib import Path
from collections import Counter
import gzip,json

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
s=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v7'
w=ROOT/'academy_v7_workers'
a=json.loads((s/'outputs/summary.json').read_text())
with gzip.open(s/'inputs/new_birthplace_facts.jsonl.gz','rt',encoding='utf-8') as f:
 facts=[json.loads(line) for line in f if line.strip()]
cohorts={r['cohort']:r for r in a['country_summary']}
n=cohorts['NAS'];nw=a['observed_native_DOB_windows']['NAS'];win=nw['hemisphere_counts']
obs=a['retained_source_observation_count'];grades=a['retained_source_observation_grade_counts']
assert len(facts)==a['new_fact_candidates']==29
assert len({(f['cohort'],f['record_id']) for f in facts})==29
assert obs==30 and grades=={'S1':26,'S2':4}
assert sum(f.get('source_observation_count',1) for f in facts)==obs
multi=[f for f in facts if f.get('source_observation_count',1)>1]
assert len(multi)==1 and 'Hershey' in multi[0]['name'] and multi[0]['source_grade']=='S1'
assert multi[0]['source_observation_count']==2
assert len(multi[0].get('additional_source_supports',[]))==1
assert multi[0]['additional_source_supports'][0]['source_grade']=='S2'
assert set(cohorts)=={'CAS','DE_Leopoldina','Fields_main','France','Japan','NAS','Nobel_science','UK_Royal_Society'}
assert a['cohort_records']==11094 and n['baseline_rows']==2242
lab={'north':'北','south':'南','unknown':'未定','equator':'赤道'}
def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
ftable='\n'.join('| '+' | '.join(cell(v) for v in [f['name'],f['raw_birthplace'],f['source_grade']+('；另S2' if f.get('source_observation_count',1)>1 else ''),lab[f['hemisphere']]])+' |' for f in facts)
ctable='\n'.join('| '+' | '.join(str(v) for v in [r['cohort'],r['baseline_rows'],r['north'],r['south'],r['unknown']])+' |' for r in a['country_summary'])
new_geo=Counter(f['hemisphere'] for f in facts)

readme=f'''# 科学家出生地补全 v7：官方批量资料与NAS第79、80卷

本轮更新 **29个NAS名录键**，保留 **{obs}条来源观察（S1 {grades['S1']}、S2 {grades['S2']}）**，新增{a['newly_classified']}个半球判定；NAS未定543→{n['unknown']}。Hershey的S1主来源与S2传记支持都保留，同一NAS记录只更新一次；没有跨队列统计去重。

| 人物 | 主来源原文地点 | 主来源等级／附支持 | 地理结论 |
|---|---|---|---|
{ftable}

出生地来源等级、地理等级与原DOB分组分别保存；本轮S1不升级任何原DOB等级。保留农场、near及历史地名限定，不以国籍、父母、求学、工作或死亡地替代出生地。

## 实际来源范围

- 物理API：离线复用230个已冻结官方对象，得9条S1；本轮0查询、0HTTP。Igor Tamm（1922／1895）、J. Herbert Taylor（1916／Joseph H. Taylor Jr. 1941）是两组不同人物，API只给Taylor的H.，不能据此展开为原生Herbert；排除不等于原生日有误。
- 化学／医学生理API：各重取已知引用地址一次，均原始HTTP200；200＋235个对象得17条S1，0搜索、0重试。Merrifield用官方preferred name、完整有序姓名及原生日期唯一对应，没有臆造姓名。
- 第79卷：20个实际目录人物，3篇正文200，3条S2、0 hold；第80卷：20个人物，2篇HTML＋1张已观察页图200，1条S2及Wilson一条hold。各1次发现查询、1次目录、0重试。署名编辑传记为S2。

每条路线筛543条未定，身份唯一性检查覆盖2,242条NAS记录；目录覆盖不等于543人均读正文。Wilson原图也印1915，出生句及原生日期为1914，保留冲突，不采用地点或更改日期。Chandrasekhar本轮独立API证据不裁定旧传记的日期分歧。

## 地理与固定口径

本轮29条结果为{new_geo.get('north',0)}北、{new_geo.get('south',0)}南、{new_geo.get('unknown',0)}未定。明确区域和官方`cityNow`参考坐标分别审核；参考点不等于本人出生点，不新增国家、出生点、唯一地点实体或人员QID。本轮未发起新地理查询。Cournand的Paris, France使用原始API所附同名cityNow参考点，未将France整体判北；原来源没有提供precision、rank或globe字段，这些字段保持未提供。审核及响应SHA见`audit/geography/`。

| 队列 | 固定记录 | 北 | 南 | 未定 |
|---|---:|---:|---:|---:|
{ctable}

全表仍为11,094条名录内记录，键为`(cohort, record_id)`。NAS原生1835–1985描述窗{nw['native_window_1835_1985_rows']:,}条：{win.get('north',0)}北、{win.get('south',0)}南、{win.get('unknown',0)}未定。原生日、历法、资格、DOB分组、QID及38条既有完整补充记录／39个旧证据对象保持不变；其余{a['other_unchanged_rows']:,}条完整对象不变。其他七队列逐行相同，英国4,983条完整对象保留。Nobel655条仍是重建ID范围，原生DOB全空，旧最终DOB未恢复；CAS公历接受字段仍空、未裁定；Fields63条主表与2026扩展分开。没有八字、结果变量或最终样本冻结。

## 审计与复现

直接基线v6 SHA256：`8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356`。七个输出保存完整表、变更、未定行和计数；冻结输入保留全部来源观察及Hershey额外支持。`audit/`含身份、hold、账本、原始SHA及独立复核；传记仅分发短引文，不分发全文或整页图片。本轮化学／医学原始API JSON和安全元数据随包保留；物理缓存原件固定在v5审计中，SHA及原路径另记。实际分发文件以`MANIFEST.sha256`为准。

采集脚本是依赖当时路径／缓存的过程快照；主重放依赖固定v6及本轮输入：

```sh
python studies/scientist_birthplace_completion_v7/scripts/assemble.py
python studies/scientist_birthplace_completion_v7/scripts/verify.py
```

验证涵盖全量键、原生字段、旧证据、CSV、计数和七个输出逐字节重放。旧版本不变。
'''

cont=f'''# Continue after scientist birthplace v7

CURRENT
Study scientist_birthplace_completion_v7. Direct baseline v6 master SHA2568e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356; current master SHA is in MANIFEST.sha256. Fixed11094 cohort records, unique(cohort,record_id), NOT cross-cohort independent people. This batch29 unique NAS keys /30 retained source observations =26S1 official API +4S2 memoirs. Primary rows are26S1+3S2. Hershey ONLY cross-lane overlap: S1 official medicineAPI primary, complete S2 Vol80 additional fact retained verbatim in additional_source_supports; light references in source_observations. One existing NAS key updated once; no statistical cross-cohort deduplication. Source observation counts must not be confused with updated-row counts.

RESULTS
NAS2242={n['north']}N/{n['south']}S/{n['unknown']}U; previous unknown543; newly classified{a['newly_classified']}. All29 new-row hemisphere counts={dict(new_geo)}. Native1835–1985 descriptive NAS window{nw['native_window_1835_1985_rows']}={win.get('north',0)}N/{win.get('south',0)}S/{win.get('unknown',0)}U; source birth years never fill native dates/window. All other7 cohort rows exact unchanged. All38 prior accepted-overlay complete rows and39 previous versioned evidence objects unchanged, including Anderson's prior S1 qualification and prior S2/hotel audit. Total unchanged complete objects this batch{a['other_unchanged_rows']}. All native DOB/calendar/formal identity/eligibility/DOB-sourcegroup/QID/status fields frozen. Source S1 birthplace observations do not upgrade original DOB tiers.

SOURCE79
Actual genuine official Volume79 TOC; URL/capture SHA in audit/vol79/toc_capture.json.20 named subjects compared with all543 current unknowns;3 observed chapters read once,3S2 facts,0holds,0pending. D.Stanley Tarbell: Hancock, New Hampshire, on a farm that had been in the family since the settlement of the village. Gerald Clemence: near Greenville, Rhode Island. Oliver R.Wulf: Norwich, Connecticut. Raw farm/near precision kept. Actual1 discovery query+1TOC+3HTML,all200,0retry;capture clock and freeze separate in source summary. No geography assigned by source worker. Edited signed memoirs areS2 regardless of official host.

SOURCE80
Actual genuine TOC https://www.nationalacademies.org/read/10269,20named subjects/all543unknowns,2 routes. Hershey S2 Owosso,Michigan, source heading/body/native1908-12-04 agree. Already retained as additional support under S1 API primary; do not drop either observation or count two NAS people. RobertRathbunWilson HOLD: printed heading March4,1915 vs born-clause/native March4,1914. Observed original page349 GIF directly visually confirmed1915, so not merely OCR ambiguity. Raw lowercase 'frontier Wyoming' is held audit only, not a selected town named Frontier and not integrated. No DOB correction or birthplace adoption. Actual1query1TOC2HTML1observedGIF,all200,0retry,0pending routes. Raw original HTML/GIF/PNG/derived fulltext excluded from distribution; hashes and short quotes retained. No need to reread the same Wilson heading to rediscover this conflict.

OFFLINE_PHYSICS
Cached original official physicsAPI JSON230objects SHA633002ff83120f9408d630209b24ebab7d1f3f1e999cf5bb51638ebb8976075e, previously captured v5. This lane0HTTP/0queries/0refreshes; all543unknowns screened, matching uniqueness checked against all2242NAS and all230APIobjects.9S1 accepted: H.A.Bethe,HansG.Dehmelt,JamesFranck,KennethG.Wilson,L.JamesRainwater,P.Kusch,RobertC.Richardson,S.Chandrasekhar,ValL.Fitch. Two exclusions are DIFFERENT PEOPLE: NASIgorTamm1922 vs physicsIgorTamm1895; NASJ.HerbertTaylor1916 vs JosephH.TaylorJr.1941. Do not call these native DOB errors. Exact date plus compatible full/initial name parts and bidirectional unique source binding required; no QID use or initials-only matching. Chandrasekhar uses independent officialAPI birth place; older Vol72 source13Oct vsnative19Oct hold remains in prior audit without readjudication. No individual birthday hunt and no original DOB-tier change.

CHEMISTRY_MEDICINE
Exactly two fresh original captures of already-cited known category URLs: chemistry200APIobjects, medicine235objects, both200,0search/0retry/no alternate endpoint.17S1 observations, with Hershey the only cross-lane overlap. Original chemistry SHA8fd0d5b3e4c6528b13c5993c13c14453e7d739a9fe7a57c7d2d6486d1c7040c8; medicine SHAdc4bd5e0d8f301273e8d5e4cb9955eff3c1ed316cb1f29fd468dec5b76b562d3. The public original JSON bodies are retained; duplicate scratch captures excluded; safe HTTP-header allowlist only. Every source full name/native date binding unique among all2242NAS and category source objects. BruceMerrifield is an EXPLICIT root-accepted official preferred-name case: knownName.en exactly BruceMerrifield; fullName.en RobertBruceMerrifield contains all native full tokens ordered; exact1921-07-15 and bidirectional uniqueness. Robert is explicitly observed in API fullName, not added to the frozen native name; no surname/initial-only acceptance. Birth.date is an identity consistency check, not adoption into Nobel native DOB. Do not re-request these3physics/chemistry/medicine collections as fresh work without a new reason.

GEOGRAPHY
Final decisions in audit/geography and each frozen fact. Birthplace S1/S2 grades separate from geographic lookup grades and frozen DOB source groups. Historic/raw birth.place text preserved. Official cityNow relation/coordinates, when used, are reference geography, NOT exact personal birth points; no new country fields, unique place entities, personQIDs or birthpointlat/lon. Do not copy latitude/longitude from an old Nobel cohort row into a NAS row. Source-qualified state/country extents may suffice; any unresolved alternatives stay held. Old NYC/ColoradoSprings/Berlin/Detroit query caches remain frozen; no famous-city choices or new inference from nationality/parents/work/upbringing/death. No blind repeat of old place queries. Preserve all candidate/coordinate/rank/globe/precision response details if another bounded query is needed.

FIXED_COHORTS
CAS1230=1003N/3S/224U, acceptedGregorianDOB blank/unadjudicated day claims. DE_Leopoldina778=655N/6S/117U. France775=702N/3S/70U. Japan368=234N/0S/134U. Fields_main63=59N/4S/0U; native window61=57N/4S; separate2026 extension not merged. Nobel_science655=634N/21S/0U is a reconstructed ID scope, ALL native DOBs blank; the old final accepted DOB table has NOT been recovered/hash-verified. UK_Royal_Society4983=4155N/183S/645U, native window2644=2255N/178S/211U; ALL complete UK objects opaque unchanged, including94supported/2quarantined/3identity-unverified,9wrong-place candidates inactive and Home alternatives. No DOB/calendar/eligibility readjudication for Esau/Breit/other old holds. No BaZi/outcomes/statistical analyses/final cohort freeze/cross-cohort statistical deduplication.

NEXT
Try genuinely new verified Vol81+ official TOCs or another cheap bulk source. Vol79 routes resolved3facts/0holds/0pending; Vol80 resolved1fact/1Wilsonhold/0pending. Old Vol72–80 chapters, original6profile pilot, and3Nobel API collections must not be silently rerun as new yield. Existing hold routes include source-date conflicts and no-literal-birthplace cases; preserve them until new independent evidence supports a change. Do not claim the whole NAS memoir collection is exhausted. Continue on existing draft branch codex/academy-fr-jp-reopen-20261029 /PR113, commit new study+ZIP without merging. Repo project artifacts remain Git-backed; local ZIP exports current table+audit. Audit scripts are process snapshots dependent on their original paths/caches, not standalone entry points. Main assemble.py/verify.py replay7outputs from fixedv6+frozen input; update baseline path/SHA together in nextversion. Reuse deterministic grouping/support retention and independent meaningful checks, without broad redundant tests afterPASS.
'''
(s/'README.md').write_text(readme,encoding='utf-8')
(s/'CONTINUATION.md').write_text(cont,encoding='utf-8')
print(json.dumps({'documents_written':['README.md','CONTINUATION.md'],'updated_NAS_keys':len(facts),'source_observations':obs,'source_observation_grade_counts':grades},ensure_ascii=False))
