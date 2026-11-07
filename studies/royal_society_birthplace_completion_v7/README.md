# 英国皇家学会出生地补全 v7

以v6的4,983条原生完整生日记录为固定输入，本轮补定 **4人**的北半球，均在1835–1985出生窗内。全表未知656→652，出生窗内未知222→218，没有撤回已知判定。

| 范围 | 北半球 | 南半球 | 未知 | 合计 |
|---|---:|---:|---:|---:|
| 上轮v6 | 4,146 | 181 | 656 | 4,983 |
| 本轮v7 | 4,150 | 181 | 652 | 4,983 |
| 原生生日窗1835–1985（含首尾年） | 2,250 | 176 | 218 | 2,644 |

生日窗仅作既有原生生日的描述性筛选。原生日、历法、正式身份接受字段、原有资格字段、历史QID和DOB来源分组均保持不变；没有新增八字或结果变量分析、跨名录统计去重或最终样本冻结。active地理查询链接94条、旧错链隔离2条、身份未核3条及旧9个错误出生地候选的停用状态不变。

## 三条有界路线

**近年18人摘要：0新增。** 上轮列出的、官方姓名生命周期结束年为2022–2026的18名候选，均在同刊检索一次。18次HTTP200、单线程、实际请求起始间隔最短4.023秒；0重试、0新429。8条top3未找到完整目标匹配，5条目标完整匹配但摘要无出生地，4条同名标题缺生命周期且摘要无出生地，1条同名元数据无摘要。未命中或出版滞后不作为原数据错误，也未采入近名干扰人物的出生地。

**MacTutor编辑传记：3条S2新来源。** 核实官方目录后，2次目录请求取得3,459个传记链接。对222条窗内未定目标，匹配到7条链接/6人；5个未读正文各读一次，全部HTTP200。3条明确Born字段通过完整姓名、原生日、正文主体、原SHA及短引文复核：

| 人物 | 记录 | 新来源中的出生地 | 等级 | 半球 |
|---|---|---|---|---|
| Graham Higman | RS_PAST_NA4226 | Louth, Lincolnshire, England | S2 | 北 |
| John Stewart Bell | RS_PAST_NA3471 | Belfast, Northern Ireland | S2 | 北 |
| C. S. Seshadri | RS_PAST_NA4038 | Kanchipuram, India | S2 | 北 |

Higman和Seshadri首次补到有效出生地；Bell原有S2 Belfast，本轮另一条S2来源补了Northern Ireland地理限定，两条均保留。因此是3条新来源、2个首次补出生地的人。Seshadri旧拼写Conjeevaram/Conjeeveram在源正文中明确列出，未猜拼写。两篇实读同名异人、另两条索引身份冲突链接均拒绝；没有把William Watson(1884)或John Humphrey Smith的出生地转给原目标。

MacTutor为University of St Andrews托管的编辑历史传记；Higman/Seshadri页署名J J O'Connor和E F Robertson，Bell页实际署名Andrew Whitaker、Queen's University Belfast。目录维护者没有被笼统当作每篇作者，来源定S2，不升级原生日等级。3条地理均可用已有England/Northern Ireland/India范围规则判北，0新地理请求，无出生国家或精确出生点赋值。

**法德语链接小批：0新出生地事实，1条地理辅助。** 56条已有地名的未定记录中，44条在出生窗内；27条有冻结完整名/alias、原生日及membership的正面身份支持。1次sitelinks元数据请求仅找到2个法文页面，各读一次均HTTP200且QID匹配；其余不扩搜。Jerry Adams法文页未提供可采的新出生地，Macalister法文页没有可采的明确出生地点字段或literal出生句，accepted新事实表为空。

Macalister（RS_PAST_NA2873）原官方S1字段已经明确出生地Dublin。同人法文首段的生命年份括号写“1844 à Dublin en Irlande - 1919”，Dublin和Ireland岛的链接都属于1844侧，不是亲属、任职或死亡地。该地理句精度严格为year=1844；同页Naissance time=1844-04-09只独立支持身份日期，该日期字段没有地点，不能写成新出生地字段。结合原S1 Dublin，仅将爱尔兰岛全北范围作为独立S3地理辅助，补定北半球；原S1出生地、原raw和原SHA不变，0新出生地事实、0新出生点/国家。

原56条缓存复读阶段仅此1条可补定、55条保留未定；其中Bell后来又由新的MacTutor来源补定，故全表已有地名未定56→54。Home的Well Manor/Hampshire与London替代项完整保留；国籍、父亲工作地、童年住址、学校和女儿出生句均未挪作本人出生地。

## 剩余与文件

当前未知652人：**598人无有效明确出生地，54人已有地名但地理未定**；出生窗内未知218人。其余4,979条记录的完整JSON与v6相等，所有4,983条既有非地理字段均不变，其他国家逐行不变。零新增路线也有完整覆盖账本，不作全部可能文献已穷尽的声明。

- `outputs/uk_birthplaces.csv`、`remaining_unknown.csv`、`changed_records.csv`：全表、652条未知、本轮4条变更；完整证据及历史在`uk_birthplace_rows.jsonl.gz`。
- `outputs/summary.json`：统计与输入SHA；`all_country_birthplace_summary.csv`：仅英国一行更新。
- `inputs/geographic_reviews.jsonl.gz`：56条缓存与地理辅助复核；`new_birthplace_facts.jsonl.gz`：3条MacTutor S2来源；active链接替换表为空。
- `audit/recent18_coverage.jsonl.gz`：18条无新增的检索结论；`MacTutor_coverage.jsonl.gz`、`MacTutor_selection.json`：目录匹配与拒绝原因；`language_coverage.jsonl.gz`：44目标/27身份支持/2实读页面；`language_geographic_auxiliary.jsonl.gz`：Dublin辅助原证据。
- `audit/new_facts_final_facts_qa.json`、`new_facts_independent_QA.jsonl.gz`、`geographic_auxiliary_QA.jsonl.gz`、`independent_review.json`、`verification.json`：独立事实、辅助地理、整合及重放检查。

交付保存短引文、URL、定位、原源SHA及独立投影SHA，不打包完整传记HTML或3,459条完整目录。出生地等级与地理等级独立；S3辅助没有升级原DOB等级。v1–v6快照不变，名录之间仍可能同人重复，不可相加当独立总人数。

从仓库根目录离线重放：

```sh
python studies/royal_society_birthplace_completion_v7/scripts/assemble.py
python studies/royal_society_birthplace_completion_v7/scripts/verify.py
```

检查覆盖4,983唯一记录、原生字段及旧隔离证据不变、CSV/JSONL/统计一致、其他国家不变，以及全部7个输出逐字节重放一致。
