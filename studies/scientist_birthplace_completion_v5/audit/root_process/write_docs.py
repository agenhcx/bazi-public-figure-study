from pathlib import Path
import json,gzip
s=Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout/studies/scientist_birthplace_completion_v5')
a=json.loads((s/'outputs/summary.json').read_text());c={r['cohort']:r for r in a['country_summary']};n=c['NAS'];w=a['observed_native_DOB_windows']['NAS']['hemisphere_counts'];facts=[json.loads(x) for x in gzip.open(s/'inputs/new_birthplace_facts.jsonl.gz','rt')]
labels={'north':'北','south':'南','unknown':'未定'}
table='\n'.join('| '+ ' | '.join([f['name'],f['raw_birthplace'],f['source_grade'],labels[f['hemisphere']]])+' |' for f in facts)
readme=f'''# 科学家出生地补全 v5：NAS第75、76卷及一条官方限定

本轮新增 **5条S2传记出生地事实**，另用诺奖官方S1资料给Anderson已有出生地增加州限定；共更新6条NAS地理记录，新增{a['newly_classified']}个北半球判定，NAS未定559→{n['unknown']}。原生日、历法、正式身份／资格、DOB来源组和QID保持不变，其余{a['other_unchanged_rows']:,}条完整对象与v4相同。

| 范围 | 固定记录 | 北半球 | 南半球 | 未定 |
|---|---:|---:|---:|---:|
| NAS全表 | 2,242 | {n['north']:,} | 31 | {n['unknown']} |
| NAS原生1835–1985窗 | 2,240 | {w['north']:,} | 31 | {w['unknown']} |
| Fields主表（保持v3） | 63 | 59 | 4 | 0 |
| 英国（保持v10） | 4,983 | 4,155 | 183 | 645 |

合并表仍为11,094条名录内记录，唯一键为`(cohort, record_id)`，不是跨名录独立人数。本轮没有统计去重、最终样本冻结或八字／结果变量分析。Fields主表63条与另记2026扩展保持分开。

## 来源及地理结果

| 人物 | 原文出生地 | 出生地来源等级 | 地理结果 |
|---|---|---|---|
{table}

第75卷四条及第76卷Woolsey均为署名编辑传记，定S2；官方网站托管本身不使其升级为S1。每个署名章节只分发不超过25词短引文，并保留原始字节SHA、作者、定位、身份及日期精度审核。完整HTML、整页扫描图和派生全文不随包分发。

Barschall、Bradbury、Bernstein的出生句均给日级日期；Leighton出生句没有日期，1919-09-10仅由标题核对。来源只展开为Robert B.，没有虚构中间名；以兼容姓名、精确原生DOB及NAS文集语境在2,242条中唯一匹配。Woolsey的标题及出生句均与原生1904-11-30一致；其全名、作者和出生句在原始第361页扫描图上直接视觉核实。没有把上述一致性检查转成原DOB等级升级，也没有声称与原表不存在的死亡日期／完整生卒年独立匹配。

Anderson的S1资料来自已知诺奖物理API集合地址的一次新捕获：id43的Carl David Anderson、1905-09-03、1936年物理奖和正电子主题，独立对应NAS原生记录及v4传记。官方结构化出生地给出`New York, NY, USA`，以NY州限定判北。此次原始响应SHA恰与旧诺奖引用相同，但没有因此填入诺奖表生日；该队列655条原生DOB仍全部为空。NAS中v4的S2事实、同名酒店疑点及全部旧版证据对象均原样保留在版本字段中；这次是跨队列证据对应，没有跨队列统计合并。

## 实际读取范围

- Vol75实际官方目录：`https://www.nationalacademies.org/read/9649`。20个人物标题与全部559条未定匹配出4条路线；4篇正文各读一次，均HTTP200。1次发现查询、1次目录读取、4次正文请求，0重试；首次查询至最后捕获约89秒，开始至冻结约202秒。
- Vol76实际官方目录：`https://www.nationalacademies.org/read/6477`。20个人物标题与同一559条未定匹配出4条路线；只读Woolsey的第21章HTML，其正文为图像包装，随后读取已观察到的第361页GIF。1次发现查询、1次目录、1次章节HTML、1次页面图像，均HTTP200，0重试，开始至冻结约218秒。Briggs、Cairns、Luyten三条路线保持待查，未声称已读正文。
- Anderson仅重取原记录已引用的官方API集合一次，没有新增人名搜索，也没有重试；全部请求前保存intent。旧Vol72–74及六个成员简介未重新请求。

两条目录匹配均是路由覆盖，不表示559人均已读正文，也不表示NAS全部文集搜尽。没有采用国籍、父母、工作、求学、成长或死亡地点替代本人出生地。

## 地理复核

出生地来源等级与地理解析等级分别保存。California、New York等明确州范围可判北，原文地点粒度不变；没有新增国家字段、精确出生点、唯一地点实体或人员QID。裸地名Berlin、Detroit仅进行一次合并精确label／alias查询，保留全部同名项及坐标的地球、rank和精度；没有按知名度选城市。Bernstein的New York City复用v4缓存的同名审计，未重跑该查询；移民父母及后续就学不提供出生地限定。新查询共314条bindings、151个实体。Berlin的45个地理候选中有40个北、1个南、4个缺坐标，保留未定；Detroit的8个地理候选全部在北半球。具体候选和审核在`audit/geography/`；NYC完整旧查询响应在v4审计中，本包保留其固定SHA及本轮复用说明。

## 固定基线与复现

直接基线为v4完整主表，SHA256 `abbce4e99ad51252dd5e127a0609bc6c4950c121afa2dd126bfc2187b39cd4e8`。所有旧非地理字段、21条既有版本证据及英国4,983条完整对象保持相等，其他七个队列逐行不变。CAS1,230条仍为未裁定接受公历日期的日级声称；Nobel655条仍是重建ID范围，旧最终DOB表没有恢复。生日窗口只作原生日期的描述，没有重判NAS历法／资格hold。

- `outputs/birthplace_rows.jsonl.gz`、`birthplaces.csv`为当前完整表；`remaining_unknown.csv`保留全部地理未定行。
- `changes.jsonl.gz`、`changed_records.csv`记录本轮6条变更；国家／队列计数及原生日期窗口在另外两个输出中。
- `inputs/new_birthplace_facts.jsonl.gz`保留6条事实、州限定及地理审核；`audit/vol75/`、`vol76/`、`geography/`保存实际范围、待查路线、请求账本、捕获摘要和短引文。
- 独立来源、地理、全表、CSV、重放和正文复核在`audit/independent_qa/`。`MANIFEST.sha256`锁定实际分发文件。捕获元数据分发拷贝只去除非必要客户端／授权信息，保留原始元数据SHA与变换记录，原始来源及查询响应字节SHA不变。

`audit/`中的采集脚本是依赖当时路径和缓存的过程快照。主重放只需既有仓库中的固定v4主表和本轮冻结输入：

```sh
python studies/scientist_birthplace_completion_v5/scripts/assemble.py
python studies/scientist_birthplace_completion_v5/scripts/verify.py
```

验证覆盖11,094键、所有旧非地理字段、英国完整对象、既有证据、未受影响队列、全部CSV和计数，以及七个输出逐字节重放。旧版本不变。
'''
(s/'README.md').write_text(readme)
cont=f'''# Continue after scientist birthplace v5

Currentstudy scientist_birthplace_completion_v5, directbaselinev4 SHAabbce4e99ad51252dd5e127a0609bc6c4950c121afa2dd126bfc2187b39cd4e8. CurrentmasterSHA recorded in MANIFEST.sha256. Fixed11094 cohortrecords,unique(cohort,record_id),notcrosscohortpeople. Thisround5newS2memoirfacts+1S1qualifiedpriorAndersonfact=6geographicrows, {a['newly_classified']}newNorth. NAS2242={n['north']}N31S{n['unknown']}U;nativewindow2240={w['north']}N31S{w['unknown']}U. Allother7cohortsunchanged,UK4983wholeobjectsopaqueequal. Fields63=59N4S0U(mainwindow61=57N4S),2026extensionseparate. Nobel655634N21S0U,allnativeDOBblank/reconstructedIDscope,oldfinalDOBunrecovered. CAS1230 acceptedGregorianblank/unadjudicated.

Vol75 https://www.nationalacademies.org/read/9649 20actualTOCsubjects/all559unknownsmatched4. All4readonce200: BarschallBerlin1915-04-29;BradburySantaBarbaraCalifornia1909-05-30;BernsteinNewYorkCity1923-10-31;LeightonDetroit1919-09-10. 1query1index4chapterbodies0retry. S2signedmemoirs;Leightonbornclausenodate,headingexactnativeDOB,sourceRobertBonly(partialexpansionunique2242),neverinventmiddle. Other3bornclausesdayprecision. NoNASsharedBonnerQIDused/fixed.

Vol76 https://www.nationalacademies.org/read/6477 20TOCsubjects/all559matched4. OnlyWoolseyread: chapter21HTMLimagewrapper plusobservedpage361GIF, visuallyverifiedfullClintonNathanWoolsey/RichardFThompson/bornBrooklynNewYork1904-11-30. 1query1index1chapterHTML1pageimage200,0retry. S2collectioncontext,noindividualelectionlineclaim. NEXTLOWHANGING: pending3observedroutes in audit/vol76/pending_routes.jsonl: RobertWBriggs1911-12-10 ch5;TLCairns1914-07-20 ch6;WillemJLuyten1899-03-07 ch14. Theyareunread,notnegativeholds. ReusealreadycapturedTOCobservedlinks,requestactualchapteronceifneededandfollowobservedimagehrefs;countimagesasbodyrequests. No guessedendpoints. DoNOTrepeatWoolseyimageorpriorVol72/73/74/75chapters.

AndersonNASpriorv4S2NewYorkCitygeographyhotelhold resolvedthisroundonlybyindependentlylinkedofficialNobelS1id43APIqualifiedNewYorkNYUSA,oneexactknowncollectionURLfreshcaptureSHA633002ff83120f9408d630209b24ebab7d1f3f1e999cf5bb51638ebb8976075e(sameasoldcitation). FullCarlDavidAnderson/native1905-09-03/Physics1936/positroncontextanchors. DoNOTadoptNobelDOB,doNOTstatisticaldedup. Preserveallv4versionedevidenceandhoteluncertaintyaudit. Stateextentonly,noexactbirthpoint/countrynewfields/personorplaceQIDs. GeoBerlin/Detroitqueryonefreshcombinedexactquery(allhomonyms/rank/globe/precision),NYC/Coloradoquerynotrepeated;cachedv4resultforBernstein. Seeall6finalgeoreviewsandholds.

All21previousversionedevidenceobjectsunchanged;Andersonwholeobjectcanchangebecausev5qualificationbutpriorversionedfieldsunchanged;other20prioroverlaywholeobjectsunchanged. AllnativeDOB/calendar/identity/eligibility/DOBtier/QIDsremain. CAS/Nobelblankguards;UKallactive942supported2quarantine3identityunverified/9wrongplaceinactive/Homealts preserved byopaqueobjects. Nooutcomes/BaZi/finalfreeze/crosscohortdedup. No placeinferencefromnationality,parents,education,work,death. SourcequalityindependentfromgeogradeandDOBtier. No famousbarecityselection.

FurthernewverifiedNASVol77+TOCspossibleafterpendingVol76routes;neverclaimallbookssearched. v4CONTINUATIONincludespriorVol72–74facts/holds andFieldscompletion;oldUKv10practicalclosureandroutesmustnotrestart. Gitexistingdraftbranch codex/academy-fr-jp-reopen-20261029/PR113,commit+ZIP,no merge. Sourceprocesssnapshotsin audit are provenance not standaloneentrypoints;mainassemble/verify replayfrozenv4+inputfacts byte-identically.
'''
# Keep prior shorthand only as a pointer; precise UK policy lives in unchanged objects.
cont=cont.replace('UKallactive942supported2quarantine3identityunverified/9wrongplaceinactive/Homealts','UKactive94supported/2quarantine/3identityunverified,9wrongplaceinactive/Homealts')
(s/'CONTINUATION.md').write_text(cont)
