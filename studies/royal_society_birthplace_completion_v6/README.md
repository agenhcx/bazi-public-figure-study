# 英国皇家学会出生地补全 v6

以v5的4,983条原生完整生日记录为固定输入，本轮新增 **15人**的北半球判定，全部在1835–1985出生窗内。全表未知从671降至656，出生窗内未知从237降至222；没有撤回已知判定。

| 范围 | 北半球 | 南半球 | 未知 | 合计 |
|---|---:|---:|---:|---:|
| 上轮v5 | 4,131 | 181 | 671 | 4,983 |
| 本轮v6 | 4,146 | 181 | 656 | 4,983 |
| 原生生日窗1835–1985（含首尾年） | 2,246 | 176 | 222 | 2,644 |

生日窗仅按原生生日作描述性筛选。原生日、历法、正式身份接受字段、原有资格字段、历史QID及DOB来源分组均不变；出生地等级与地理等级另记。没有新增八字或结果变量分析、跨名录统计去重或最终样本冻结。原有94条active地理查询链接、2条旧错链隔离、3条身份未核及旧9个错误出生地候选均保持原状态。

## 本轮覆盖与来源

**上轮待查53人全部处理。** 先查3名早期会员的正确前身期刊，再查50名上轮因限流未发请求的后期会员。53次人物检索全部HTTP200，0重试、0新429；实际请求起始间隔最短4.43秒，只有一个单线程Crossref采集作业。每次结束后才发下一次，请求前及等待后重查共享停止信号；错误响应头和Retry-After捕获逻辑已保留。

21人取得明确本人出生地，来源S2（早期3、后期18）；32人暂缓并逐人留原因。读取的是皇家学会出版社经Crossref提供的编辑传记摘要，没有把它写成传记全文阅读或S1。成长地、父亲任职地、家族籍贯、终身工作地及仅有生日的句子未提升为本人出生地。Wells标题月份与原生日的差异另存，原生日不变。

**官方诺奖出生字段补充1人。** 现有其他名录中只找到同生日、不同姓名的碰撞，未转抄。官方Nobel API两页实际覆盖1,028个唯一ID；本轮英国出生地未定目标中，完整姓名与原生日匹配且可补出生地的唯一记录是既有英国记录Churchill（RS_PAST_NA8169）。原API出生字段为`Woodstock, United Kingdom`，地点明确链接Q752111；继承已有地点精度坐标，出生地S1、地理辅助S3。没有将它改写成更细的Blenheim地点，也没有读取死亡地点London当出生地。当前API生日仅作人物支持，原DOB等级不改。

交付只保存匹配者身份和birth字段投影、两页请求元数据及原响应SHA；完整API的prize/outcome字段不纳入此study，也未扩展任何Nobel或英国名录。

**地理层。** 原49条已有地名的记录，以旧缓存新增依据补清3北、46暂缓：Whitby的同源England地域回指、Glasgow的本人明确“Scottish-born”出生地域、County Durham既有县域证据；没有新增网络请求。它们是出生区域/地理限定，不是普通国籍词。Home的Well Manor/Hampshire与London替代项完整保留，仍未知。

22条新事实（21条S2、1条S1）均独立复核通过，地理解析12北、10未知；加上旧地名3条，合计新增15人判定。所有地理辅助均为独立S3，无出生国家或精确出生点赋值。仅执行1次新精确地名批量查询、1次3个地理实体补取，未重查旧同名或查询人物生日。

NA5011原文的Leningrad/Petrograd双名已沿历史名称实体链解析到同一城市Q656，北纬坐标及精度有据。原生日1908早于Petrograd名称期1914–1924，原源“then Petrograd”的年代措辞疑点作为独立注记保留；没有改原地名、生日或历法，也不把城市坐标当出生点。

## 剩余、文件与校验

当前未知656人：**600人无有效明确出生地，56人已有地名但地理未定**；其中出生窗内未知222人。上轮53人的待查队列本轮已全部读取，32条暂缓不等于未请求，也不等于所有可能文献已经搜尽。

- `outputs/uk_birthplaces.csv`：全表；`remaining_unknown.csv`：656条未知；`changed_records.csv`：新增事实或地理解析变更；完整证据在`uk_birthplace_rows.jsonl.gz`。
- `outputs/summary.json`：统计与输入SHA；`all_country_birthplace_summary.csv`：只更新英国一行，其他国家逐行不变。
- `inputs/geographic_reviews.jsonl.gz`：49条复核；`new_birthplace_facts.jsonl.gz`：22条事实与地理依据；本轮active链接替换表为空。
- `audit/pending53_coverage.jsonl.gz`、请求账本、源SHA和日期差异：真实53条结果；`crosswalk_*`：官方出生字段投影及有限API覆盖核对。
- `audit/new_facts_final_facts_qa.json`、`new_facts_independent_QA.jsonl.gz`、`independent_review.json`、`verification.json`：独立事实、整合及重放检查。
- `audit/collector_code/`：本轮实际采集代码和离线停止防护测试。3种模拟均通过，真实网络请求与socket连接为0：已有标记、模拟429捕获Retry-After并停止后续52人、等待期间新增标记。真实53次HTTP200账本未受测试影响。

保存短引文、URL、定位、原响应SHA与独立投影SHA，不打包传记全文或全部诺奖API原响应。v1–v5快照不变；各名录仍可能同人重复，不能相加当独立总人数。

从仓库根目录离线重放：

```sh
python studies/royal_society_birthplace_completion_v6/scripts/assemble.py
python studies/royal_society_birthplace_completion_v6/scripts/verify.py
```

校验覆盖4,983条唯一记录、全部既有非地理字段不变、旧错误候选继续停用、CSV/JSONL/统计一致、他国不变，以及所有输出逐字节重放一致。
