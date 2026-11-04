# 科学家出生地补全 v6：NAS第76–78卷

本轮新增 **12条S2传记出生地事实**，新增12个半球判定，NAS地理未定555→543。原生日、历法、正式身份／资格、DOB来源组、QID及全部既有版本证据保持不变；其余11,082条完整对象与v5相同。

| 人物 | 来源原文地点 | 出生地来源等级 | 地理结论 |
|---|---|---|---|
| A. M. Pappenheimer Jr. | Cedarhurst, New York | S2 | 北 |
| Carl W. Gottschalk | Salem, Virginia | S2 | 北 |
| E. M. Purcell | Taylorville, Illinois | S2 | 北 |
| Edward C. Franklin | Berlin, Germany | S2 | 北 |
| Gertrude S. Goldhaber | Mannheim, Germany | S2 | 北 |
| Glenn T. Seaborg | Ishpeming, Michigan, a small iron-mining town on the Upper Peninsula of Michigan | S2 | 北 |
| I. M. Kolthoff | Almelo, Netherlands | S2 | 北 |
| John Kirkwood | the small town of Gotebo, Oklahoma | S2 | 北 |
| Robert W. Briggs | Watertown, Massachusetts | S2 | 北 |
| T. L. Cairns | Canada in the city of Edmonton, Alberta | S2 | 北 |
| Willem J. Luyten | the city of Semarang in north-central Java | S2 | 南 |
| William D. Phillips | Kansas City, Missouri | S2 | 北 |

所有新事实来自署名编辑传记，定S2；官方网站托管本身不使其升级为S1。出生地来源等级、地理解析等级和原DOB来源分组分别保存。只采用明确的本人出生语义，保留小镇、城市及原始地域粒度；没有使用国籍、父母、求学、工作、成长或死亡地点替代。

## 实际来源范围

本轮三条路线并行，原始章节／页面字节SHA、逐次请求前的intent、定位、署名作者、身份审核和来源短引文均保留：

- 第76卷：复用v5已观察到的目录和Briggs、Cairns、Luyten三条待查链接，无新发现查询、目录请求或Woolsey重复请求。章节HTML为扫描图片包装，沿实际`data-original`链接读取并直接视觉核验原始页图。实际请求数及预算转移见`audit/request_scope_and_budget.json`，原图、完整HTML和OCR全文不随包分发。
- 第77卷：[官方目录](https://www.nationalacademies.org/read/9681)的20个人物标题与全部555条未定记录匹配，6篇正文各请求一次。5条接受；Cohen因来源标题及出生句为1908-09-28，与原生1908-09-26冲突而hold，整条原记录不变。实际1次发现查询、1次目录、6篇原始HTML，均HTTP200、0重试。
- 第78卷：[官方目录](https://www.nationalacademies.org/read/9977)的20个人物标题与全部555条未定匹配，4个不同章节各请求一次。Franklin用来源精确日期对应1928年出生的Edward C. Franklin，未传播给1862年同名记录；Phillips也使用本人日期及完整身份核对。实际1次发现查询、1次目录、4篇原始HTML，均HTTP200、0重试。

目录匹配是路由覆盖，不能称555人均已读正文，也不能称全部NAS传记搜尽。本轮没有重新请求已处理的第72–75卷章节。Briggs出生句只有1911年，Cairns及Kirkwood出生句没有日期；精确原生日期一致性另由本人标题核对。Seaborg首个出生地点分句无日期，原文后续另给日级日期；传记也明确说明Glen改用Glenn的姓名关系。其他条目的具体日期精度逐条记录；这些核对没有升级任何原DOB分组。原表没有死亡日期／完整生卒年字段，来源生卒年只作上下文，没有声称独立匹配。

## 地理与固定口径

明确的州、国家或岛屿范围与裸地名分别审核，参考地理信息定S3，出生地事实仍为S2。没有新增国家字段、精确出生点、唯一地点实体或人员QID；没有按城市知名度选择地点。本轮12条均依据明确区域范围判定，未发起新地理查询；Luyten由出生句的Java岛范围判南，父母定居句只作上下文。具体审核见`audit/geography/`。旧NYC、Colorado Springs、Berlin、Detroit查询保持冻结，不因本轮其他人的限定地点而改写其历史结论。

| 队列 | 固定记录 | 北 | 南 | 未定 |
|---|---:|---:|---:|---:|
| CAS | 1230 | 1003 | 3 | 224 |
| DE_Leopoldina | 778 | 655 | 6 | 117 |
| Fields_main | 63 | 59 | 4 | 0 |
| France | 775 | 702 | 3 | 70 |
| Japan | 368 | 234 | 0 | 134 |
| NAS | 2242 | 1667 | 32 | 543 |
| Nobel_science | 655 | 634 | 21 | 0 |
| UK_Royal_Society | 4983 | 4155 | 183 | 645 |

11,094条的单位是名录内记录，唯一键为`(cohort, record_id)`，不是跨队列独立人数；本轮没有统计去重、最终样本冻结或八字／结果变量分析。NAS原生1835–1985描述窗仍为2,240条：1665北、32南、543未定，未重新裁定原有历法或资格hold。Fields主表63条与2026扩展分开；Nobel655条重建ID范围的原生DOB仍全部为空，旧最终DOB表未恢复；CAS1,230条接受公历日期仍未裁定。

## 基线、审计与复现

直接基线为v5完整主表，SHA256 `15f3d58b3334fbc5c32229b0c122ff5e693379fbf9759794e1e3ae87ac06d152`。所有26条既有补充记录的完整对象、27个旧版出生地证据对象及英国4,983条完整记录保持相等；其他七个队列逐行不变。

七个`outputs/`文件包含当前完整表、全部未定行、逐条变更、计数与原生日期窗口。`inputs/new_birthplace_facts.jsonl.gz`保存新事实和地理审核；`audit/vol76/`、`vol77/`、`vol78/`保存路由、hold、身份核对、请求账本和原始响应SHA。每独立署名章节只分发不超过25词短引文。独立来源、地理、全量字段、CSV、重放、正文及分发审核在`audit/independent_qa/`。

分发元数据采用公开字段；若有非必要客户端／授权信息，仅从元数据拷贝剔除，保留原元数据SHA和变换记录，不改原始响应及其字节SHA。来源工作目录的manifest是分发前快照，实际分发文件以本目录`MANIFEST.sha256`为准。`audit/`采集脚本为依赖原工作路径和缓存的过程快照；主重放只依赖仓库固定v5主表及冻结输入：

```sh
python studies/scientist_birthplace_completion_v6/scripts/assemble.py
python studies/scientist_birthplace_completion_v6/scripts/verify.py
```

独立验证覆盖11,094键、全部原生及旧版字段、英国完整对象、其余队列、全部CSV、计数和七个输出逐字节重放。ZIP包含当前完整表及本轮审计，旧版本不变。
