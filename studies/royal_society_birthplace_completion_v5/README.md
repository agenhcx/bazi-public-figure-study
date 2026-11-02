# 英国皇家学会出生地补全 v5

本轮以 v4 的4,983条原生完整生日记录为固定输入，新增 **19人**的北半球判定；全部在1835–1985出生窗内。全表未知从690降至671，出生窗内未知从256降至237。没有撤回已知判定。

| 范围 | 北半球 | 南半球 | 未知 | 合计 |
|---|---:|---:|---:|---:|
| 上轮 v4 | 4,112 | 181 | 690 | 4,983 |
| 本轮 v5 | 4,131 | 181 | 671 | 4,983 |
| 原生生日窗1835–1985（含首尾年） | 2,231 | 176 | 237 | 2,644 |

生日窗仅按既有原生生日作描述性筛选。原生日、历法、正式身份接受字段、原有资格字段、历史QID和DOB来源分组均不变。出生地来源等级与地理解析等级单独保存，不据此升级生日来源。没有新增八字或结果变量分析、跨名录去重或最终分析样本冻结。

## 本轮证据与覆盖

- 原有48条“有出生地、半球未定”的记录复核，6人补定为北半球，42人保留未知。依据为旧缓存本人出生段的明确地点链接或原文完整的地理限定；不凭城市知名度、国籍或任职单位消歧。Home的Well Manor/Hampshire和London替代项继续保留，整体未知。
- 1955年以后传记摘要路线选出62名尚未检索的人。实际发起12次人物检索：11次HTTP200、1次HTTP429；随后停止，50人未请求。已保存摘要提供2条S2明确本人出生地。
- 新核实前身期刊《Obituary Notices of Fellows of the Royal Society》（皇家学会，Crossref入口ISSN2053-9118；1932–1954）并选出32名未覆盖的早期去世会员。真实32次人物检索均HTTP200，离线复核取得18条S2明确本人出生地，14人暂缓。实际读取的是出版社经Crossref提供的编辑摘要，未声称读取传记全文或将它标为S1。
- 两条摘要路线合计20人新增明确出生地，全部通过独立人物、原文语义、原源SHA和不超过25词摘录核验；地理解析13北、7未知。加上原有地名的6条，合计新增19人判定。
- Chen、Lauritzen、Jerry Adams共尝试6个未读URL：3个成功正文、另外分别403/503/404，均未取得新出生地。机构位置Victoria未作Jerry出生地。0新增事实，3人继续暂缓；各URL、状态和理由留账。

新事实出生地等级均为S2；地理辅助为独立S3，保留原地名拼写、near关系和同名替代项，不赋出生国家或精确出生点。即使来源给出了别的生日文字，也没有据此重定原生日。既有94条active查询链接、2条旧错链隔离、3条身份未核状态及旧9个错误出生地候选的隔离状态不变。

## 限流与停止机制事件

后期摘要路线遇429后停止，但并行早期采集器的外部停止信号未能及时送达：停止标记时已有16条完成、2条在途，另有14条在标记后发起。它实际完成了32次请求，**不能写成只请求16次或声称所有响应都在停止前取得**。

原采集进程结束后，没有再发起新的Crossref联网采集；已经保存的32条公开响应按同一人物与出生地事实标准离线复核。18条采纳事实中8条来自先完成组、1条来自在途组、9条来自停止后发起组。每条保留时序标记；这个操作事件与S2来源/内容标准分别记录，没有删除缓存或隐藏请求。

保留了原始运行代码，修补版本在队列入口、限速等待后和发起前检查共享停止标记，遇429写入共享标记。5类离线模拟均通过：既有标记、模拟429、剩余队列、新worker识别共享标记、等待期间新增标记。测试使用完全mock的网络入口并禁止真实socket，真实网络请求为0；修补后没有运行新的Crossref联网采集。后续Crossref仅运行一个采集作业，所有刊物共用停止信号；本轮未请求的50人留待以后。

## 剩余、文件与重放

当前未知671人：**622人无有效明确出生地，49人已有地名但地理仍未定**。其中1835–1985窗内未知237人。这是出生地层的缺项，原生生日记录数保持4,983。

- `outputs/uk_birthplaces.csv`：全表；`remaining_unknown.csv`：671条未知；`changed_records.csv`：本轮新增事实或地理解析变更。
- `outputs/uk_birthplace_rows.jsonl.gz`：全部有效证据及历史；`summary.json`：统计与输入SHA；`all_country_birthplace_summary.csv`：仅英国一行更新。
- `inputs/geographic_reviews.jsonl.gz`：48条复核；`new_birthplace_facts.jsonl.gz`：20条新S2事实与地理证据。`current_lookup_replacements.jsonl.gz`为空，本轮没有改active链接。
- `audit/memoir62_coverage.jsonl.gz`：含50条未请求；`early32_coverage.jsonl.gz`：真实32次请求、逐人结论与时序；`current3_audit.jsonl.gz`：6次URL尝试。
- `audit/early32_operation_stop_audit.json`、`early32_collector_code_audit.json`：操作事件与原/修补代码SHA；`audit/collector_code/`：两版源代码及可离线运行的模拟验证。这里的代码是审计快照，主数据重放不发网络请求。
- `audit/new_facts_final_facts_qa.json`、`new_facts_independent_QA.jsonl.gz`、`independent_review.json`、`verification.json`：独立复核和重放检查。

保存短引文、URL、定位、原响应SHA及转换后输入SHA，不打包传记全文。地理源响应另存于`audit/*sources.json.gz`。旧来源SHA缺失时保持缺失并核候选的canonical SHA，不补造来源哈希。其他国家逐行沿用v4，v1–v4快照不变；名录之间尚可能同人重复，不能相加当独立人数。

从仓库根目录离线重放：

```sh
python studies/royal_society_birthplace_completion_v5/scripts/assemble.py
python studies/royal_society_birthplace_completion_v5/scripts/verify.py
```

校验涵盖4,983唯一记录、全部既有非地理字段不变、旧错误候选继续停用、CSV/JSONL/统计一致、其他国家不变，以及所有输出文件逐字节重放一致。
