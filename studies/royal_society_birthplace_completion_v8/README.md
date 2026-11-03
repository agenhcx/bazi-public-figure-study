# 英国皇家学会出生地补全 v8

以v7的4,983条原生完整生日记录为固定输入。本轮新增 **6条来源（4条S2、2条S3）**，涉及6人，其中5人首次补到明确出生地。新增判定5人：3北、2南；其余保留地名与未定原因。

| 范围 | 北半球 | 南半球 | 未定 | 合计 |
|---|---:|---:|---:|---:|
| 上轮v7 | 4,150 | 181 | 652 | 4,983 |
| 本轮v8 | 4,153 | 183 | 647 | 4,983 |
| 原生生日窗1835–1985（含首尾年） | 2,253 | 178 | 213 | 2,644 |

生日窗只作既有原生生日的描述性筛选。原生日、历法、正式身份接受字段、资格字段、历史QID和DOB来源分组保持不变；不作跨名录统计去重、最终样本冻结或八字及结果变量分析。active地理查询链接94条、旧错链隔离2条、身份未核3条和旧9个错误出生地候选的停用状态不变。

## 新来源与实际覆盖

| 人物 | 记录 | 来源中的出生地 | 来源等级 | 本轮地理判定 |
|---|---|---|---|---|
| William Russell Levick | RS_PAST_NA4493 | Sydney, New South Wales, Australia | S2，EOAS | 南 |
| Bernard Yarnton Mills | RS_PAST_NA4596 | Sydney, New South Wales, Australia | S2，EOAS | 南 |
| Horace Newton Barber | RS_PAST_NA3193 | Warburton, Cheshire, England | S2，AAS编辑传记 | 北 |
| Jeremy David Pickett-Heaps | RS_PAST_NA4658 | Bombay (Mumbai), India | S2，AAS链接的完整编辑传记PDF | 北 |
| William Henry Broadbent | RS_PAST_NA1510 | Lindley | S3，DNB在线转录 | 未定 |
| David James Hamilton | RS_PAST_NA3559 | Falkirk | S3，DNB在线转录 | 北（同句城镇类型限定） |

**澳洲名录路线：4条S2。** 初始3次目录或导航请求只覆盖AAS首10项及EOAS导航，0条新事实，原阶段单独保存在`audit/australian_directory/partial_probe/`。随后沿已观察到的分页及字母链接扩展25次目录请求：AAS全部24页、239篇独立传记索引完成；EOAS只读M/L字母页，不代表完整EOAS。合计28次目录请求，目录中的1,372个去重人物链接与218条出生窗内未定目标比较，选出7条链接、5名候选。实际读5个HTML正文及1份明确链接的官方PDF，共6次正文请求；目录与正文共34次，全部HTTP200，0重试、0新429、0 Crossref请求。

Levick与Mills采EOAS明确Born字段；Barber采AAS完整编辑传记。Pickett-Heaps实际阅读PDF物理第1页，署名Peter Beech与Arthur Forer，原文出生时间只到1940年6月；原生1940-06-05不变，不能称这份来源确认了具体日。完整姓名、生命周期和主体出生句另行支持身份与出生地。索引近名John Malcolm Morris与目标John Gareth Morris不是同人，明确拒绝。

**历史DNB路线：2条S3。** 以218条窗内未定记录中、冻结姓名显示1932年前去世的24人为有界目标；5次检索用于来源发现，另有2次目录API与2次人物正文API请求，4次API均HTTP200，0重试或429。1912目录请求有500项上限且未跟随continuation，1927目录也只按本次保存范围比对，不声明整个DNB已穷尽。24个目标中2人有可采出生句，其余22人暂存，暂存不等于逐人正文已读或文献不存在。

Broadbent原有S1 Lindley，本轮只是另增一条S3佐证；Hamilton首次补到Falkirk。因此应区分6条新来源、5名首次有出生地的人。两篇均只核验Wikisource在线转录，未目视扫描原页，保留原书作者、卷页及转录定位，但不升S2。身份使用完整姓名与原生日核对，没有把David James Hamilton写成其他Hamilton。

## 地理与剩余

澳洲四条来源自身含New South Wales/Australia、Cheshire/England或India限定，依明确范围判2北2南；不赋出生国家字段或精确出生点。出生地来源等级、独立地理解析等级与DOB等级分别保存。

Lindley沿用已有同名异半球的未定结论，未重复查旧地名。Falkirk只新增1次精确英文label/alias地理查询，最初因南北候选冲突暂存。复读同一出生句时，后面的“该镇”明确回指已陈述的本人出生地Falkirk，直接限定其为城镇；这不是用父亲工作地推出生地。按该明示类型排除Perth的Maylands railway station之Falkirk别名对象，南方车站候选及排除理由完整保留；剩余兼容城镇或聚落候选均在北半球，因此只判北，不选唯一城镇、国家或出生点。初次held快照、短上下文引文、原源SHA及独立语法复核另存，0新增网络。该有界候选表不是穷尽全球地名库，S3等级不升级。

其他已审54条地名未定库存本轮没有重新批审，`inputs/geographic_reviews.jsonl.gz`为空；Hamilton使用本轮新事实及同句限定，未重复批查旧库存。

当前未定647人：**593人无有效明确出生地，54人有地名但地理未定**。出生窗内未定213人。原有已知判定无人撤回，除本轮6人外其余4,977条完整JSON与v7相等；全4,983条既有非地理字段不变，其他国家逐行不变。Home的Well Manor/Hampshire与London替代项仍完整保留。没有把国籍、父母职业或住址、童年、学校、任职及死亡地挪作本人出生地。

## 文件与复现

- `outputs/uk_birthplaces.csv`、`remaining_unknown.csv`、`changed_records.csv`：全表、未定表、本轮6条来源相关变更；完整候选与历史在`uk_birthplace_rows.jsonl.gz`。
- `outputs/summary.json`：统计及输入SHA；`all_country_birthplace_summary.csv`：只更新英国一行。
- `inputs/new_birthplace_facts.jsonl.gz`：6条带地理复核的来源；地理库存重审及active链接替换表均为空。
- `audit/australian_directory/`、`historical_dnb/`：有界覆盖、候选、拒绝理由、请求和原源SHA；`new_facts_geo/`：新地名查询与候选投影。
- `audit/new_facts_final_facts_qa.json`、`new_facts_independent_QA.jsonl.gz`、`independent_review.json`、`verification.json`：事实、地理、全量整合及离线重放复核。
- `MANIFEST.sha256`：交付文件校验。`scripts/source_routes/`保存本轮采集工作流，完整源缓存不随包分发。

交付只包含短引文、URL、定位、来源原字节SHA、覆盖投影与独立核验结果，不打包完整传记HTML/PDF或全部人物目录。下面的离线重放使用仓库中v7固定基线、v3选择规则和本轮冻结输入；ZIP是本轮增量，完整重放需在既有仓库内运行。

```sh
python studies/royal_society_birthplace_completion_v8/scripts/assemble.py
python studies/royal_society_birthplace_completion_v8/scripts/verify.py
```

检查覆盖4,983唯一记录、所有既有非地理字段及旧隔离证据不变、CSV/JSONL/统计一致、其他国家不变，以及全部7个输出逐字节重放一致。v1–v7快照不变，名录间仍可能同人重复，不可相加当独立总人数。
