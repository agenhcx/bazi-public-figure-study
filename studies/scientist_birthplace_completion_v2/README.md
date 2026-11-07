# 科学家出生地补全 v2：奖项小批收口与NAS试查

本轮新增 **3条S1出生地来源、3个北半球判定**：菲尔兹奖主表补2人，诺奖科学当前重建ID范围补1人。英国按v10暂时收口，全部4,983条完整记录保持不变。NAS六人官方简介试查0新增。

## 本轮新证据

| 组别／人物 | 记录 | 来源明确写出的出生地 | 来源及精度 | 半球 |
|---|---|---|---|---|
| Fields：Akshay Venkatesh | fields-12ddab1dd74af07f | New Delhi, India | IAS托管的本人CV，S1；出生时间仅1981年 | 北 |
| Fields：Manjul Bhargava | fields-c847084f96ea991e | Canada | IMU官方2014获奖新闻传记，S1；出生时间仅1974年 | 北 |
| Nobel：John M. Martinis | 1052 | Los Angeles, CA, USA | 瑞典皇家科学院／诺奖官方2025物理奖PDF，第6页，S1 | 北 |

Venkatesh的CV全名与Fields Medal 2018共同支持身份；Bhargava在IMU官方2014获奖页面及所链接传记中绑定全名。两份材料都只支持出生年，没有确认原生日的具体月日，原生1981-11-21和1974-08-08保持不变。Bhargava只保留原文国家级“Canada”，没有把检索线索里的城市或省份升级为出生地。

Martinis的官方PDF第6页在本人姓名标题下直接写出生句，文末署名瑞典皇家科学院、文字作者Anna Davour及物理奖科学编辑。该来源独立于原API缺失的`birth.place`字段。其原生DOB继续为空，未采纳原文1958年或任何当前API日期来填生日、筛年龄或修改资格。

地理仅使用明确India、Canada及“Los Angeles, CA, USA”中California的全北范围；不笼统假定USA全部领土在北半球。出生地原始粒度保留，0新地理请求，不新增国家字段、唯一地理实体或精确出生点。出生地来源等级S1、地理解析等级S3和原DOB来源组分别保存；本轮没有升级任何DOB证据等级。

## 当前各组计数

| 组别 | 固定记录数 | 北半球 | 南半球 | 未定 | 本轮补定 |
|---|---:|---:|---:|---:|---:|
| CAS | 1,230 | 1,003 | 3 | 224 | 0 |
| 德国Leopoldina | 778 | 655 | 6 | 117 | 0 |
| Fields主表 | 63 | 57 | 4 | 2 | 2 |
| 法国 | 775 | 702 | 3 | 70 | 0 |
| 日本 | 368 | 234 | 0 | 134 | 0 |
| NAS | 2,242 | 1,637 | 31 | 574 | 0 |
| Nobel科学重建ID范围 | 655 | 634 | 21 | 0 | 1 |
| 英国Royal Society v10 | 4,983 | 4,155 | 183 | 645 | 0 |

合并文件有11,094条**名录内记录**，不是跨名录独立人数。唯一键为`(cohort, record_id)`，没有做跨队列统计去重。Fields主表与另外记录的2026扩展分开，本轮未加入扩展人物。Fields原生生日窗1835–1985内61条为55北、4南、2未定；英国窗内2,644条仍为2,255北、178南、211未定。窗口统计只描述既有原生日期，不重新裁定历法或资格。

CAS的1,230条仍是正文支持的日级日期声称，`dob`及正式接受公历日期仍为空、未裁定；不因这张地域表变成1,230个已接受公历生日。Nobel的655条沿用原项目1901–2025科学奖ID重建范围，旧最终DOB行表尚未恢复和逐行哈希核对，全部原生DOB仍为空。因此“诺奖出生地未定为0”只描述此重建ID范围的地域字段，不能当作旧655条最终生日表已恢复。本轮没有把来源出生年变成这两组的原生DOB或年龄窗。

## 有界读取及未解决项目

**Fields：4次发现检索、8次正文读取。** 4名原未定人物中取得上述2条明确出生句。Smirnov已保存的UniGE线索正文受阻；Duminil-Copin的官方访谈没有明确出生地，最后一次官方说明材料读取超时，均保留未定。没有把片段线索、国籍、童年、就学、任职或父母地点当出生地，也没有逐人寻找生日来改原值。

**Nobel：2次检索、同URL的3次逻辑读取。** 官方PDF检索正文可读；补取原PDF字节时HTTP403，随后第6页截图工具仅返回文本占位，没有图像像素。故事实依据明确绑定姓名和出生句的官方正文文本，不声明已目视核验版面或取得PDF原字节SHA。三次逻辑读取和失败分别记录，没有隐藏成只读一次。

**NAS：6个最早原生生日且在既有1835–1985窗内的未定人物试查。** 只读取冻结的官方目录URL：5个网页文本投影可读，Edward C. Franklin的一次读取超时；不是6个成功正文，也不是实时HTTP200。5份可读简介均没有明确出生地，并显示个人传记材料不可用，没有观察到可跟进的本人memoir链接。因此0次memoir读取、0新事实、0检索和0重试，其他568名未定NAS记录未在此试查中读取。共享错误Q6133587及原有Esau／Breit历法或资格hold均不变。

三条新事实的SHA均明确标为检索工具文本或JSON捕获SHA，**不是出版社PDF原字节SHA**。独立复核按实际文本、全名、获奖语境、原生日期的兼容精度、短引文及捕获哈希核验；未补造图像核验。完整网页／PDF／检索正文缓存不随包分发，只保留来源URL、定位、短引文、原始粒度和状态账本。

## 基线组合、文件与复现

当前基线以`academy_birthplace_screen_v1`的七个非英国队列为底，完整替换其旧英国部分为`royal_society_birthplace_completion_v10`的4,983条记录；没有把英国早期计数重新覆盖回去。两份固定输入的SHA及组合方式在`audit/baseline_composition.json`与输出统计中记录。

除新增3条地理记录外，其余11,091条完整对象与组合基线相等；英国4,983条逐行相等。所有旧DOB、历法、身份、资格、来源组、原QID及其他非地理字段均不变。没有新增八字或结果变量、最终样本冻结，也没有把名录记录总数当独立样本量。

- `outputs/birthplace_rows.jsonl.gz`与`birthplaces.csv`：完整当前合并记录；`remaining_unknown.csv`保留各队列未定行。
- `outputs/changed_records.csv`与`changes.jsonl.gz`：本轮3条地理变更；`all_country_birthplace_summary.csv`与`summary.json`：组别计数、原生日期的描述性窗及输入SHA。
- `inputs/new_birthplace_facts.jsonl.gz`：3条事实及地理限定；`audit/fields/`、`nobel/`、`nas/`保存读取边界与投影元数据。
- `audit/source_qa_report.json`、`independent_review.json`、`verification.json`及其他复核文件：事实、全量字段与独立重放检查；`MANIFEST.sha256`为交付校验。

采集过程脚本在`scripts/source_routes/`，依赖当时临时缓存及路径，只是过程快照。完整输出重放入口为：

```sh
python studies/scientist_birthplace_completion_v2/scripts/assemble.py
python studies/scientist_birthplace_completion_v2/scripts/verify.py
```

需在既有仓库中运行，依赖固定全球v1及英国v10主表。检查11,094个队列内唯一键、所有既有非地理字段、英国全部对象、CAS／Nobel空值和范围状态、未受影响队列、CSV与计数及7个输出逐字节重放。ZIP含当前完整合并表与本轮审计，原有各版本快照不变。
