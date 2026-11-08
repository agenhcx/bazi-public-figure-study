# 英国皇家学会出生地补全 v9

以v8的4,983条原生完整生日记录为固定基线，本轮补到 **2条S2出生地来源、2名首次有出生地的人，均判北半球**。全表未定647→645，1835–1985出生窗内未定213→211；没有撤回已有判定。

| 范围 | 北半球 | 南半球 | 未定 | 合计 |
|---|---:|---:|---:|---:|
| 上轮v8 | 4,153 | 183 | 647 | 4,983 |
| 本轮v9 | 4,155 | 183 | 645 | 4,983 |
| 原生生日窗1835–1985（含首尾年） | 2,255 | 178 | 211 | 2,644 |

生日窗仅作既有原生生日的描述性筛选。原生日、历法、正式身份接受字段、资格字段、历史QID及DOB来源分组均不变；不新增八字或结果变量分析、跨名录统计去重、最终样本冻结。active地理查询94条、旧错链隔离2条、身份未核3条及旧9个错误出生地候选的停用状态不变。

## 两条新证据

| 人物 | 记录 | 来源中的出生地 | 等级 | 半球 |
|---|---|---|---|---|
| Roger Valentine Short | RS_PAST_NA4156 | Weybridge, Surrey, England | S2 | 北 |
| John Stewart Pate | RS_PAST_NA4641 | Ilford, Essex, England | S2 | 北 |

两篇EOAS《Encyclopedia of Australian Science and Innovation》编辑传记均由Rosanne Walker撰写，出版方元数据为Swinburne University of Technology。实际Born字段的完整姓名、生命周期和完整生日分别与原生1930-07-31、1932-01-15一致。原始HTML字节SHA、字段定位及每源7词的短引文均通过独立核验；原生生日及DOB等级不因此升级。地理只使用来源明示的England全北范围，郡名与城市原样保留；0新地理查询，不指定出生国家、唯一地理实体或精确出生点。出生地来源等级S2与地理解析等级S3分开保存。

## 三条有界路线及实际覆盖

**EOAS扩展：部分索引成功，2条新来源。** v8已经读取L/M，本轮排除；A页所见导航明确列出其余字母URL。完成记录中有21次索引尝试：14个HTTP200（A、F、I、J、K、N、O、P、Q、R、S、T、U、V）、6个HTTP503（B、C、D、E、G、H），W传输中断。X可能在停止前进入下一请求，其启动时间及响应均未持久记录，作为1次可能请求单列；Y/Z未请求，不能声称其余24个字母已完整查完。初始A只请求一次。

14份成功索引包含2,856条传记链接、2,722个去重URL，与全部647条未定记录（其中窗内213条）做冻结全名及生命周期匹配，得到4名窗内候选。Jerry Adams的同一EOAS来源已在既有证据中保存，因此排除重读；只新读Townsend、Short、Pate三个人物URL各一次，结果为503、200、200。Townsend因正文失败暂存，没有把失败当作传记不存在。

索引停止时的历史状态单独保留在`index_stop_checkpoint.json`；之后只授权上述3个已匹配人物正文，没有恢复字母抓取。EOAS总计 **24次有记录的请求（21索引+3正文）**：16个HTTP200、7个HTTP503、1次传输失败，另有X的1次可能请求；另做1次检索用于目录发现。0重试、0重定向跟随、0 Crossref、0逐人生日检索。所有23份实际收到的HTTP响应体（含错误体）均核对原字节SHA，错误体不计有效目录或人物证据。647条覆盖记录区分候选、成功索引中未匹配及对应字母未成功覆盖；没有把所有647人说成正文已读。

**爱尔兰DIB：0新增。** 1次来源发现检索、5次只读导航尝试；原文传输出现307，全目录网页读取403。唯一取得的A页检索投影含25个人物标题，对全部647人做规范化权威全名匹配为0。最终匹配从644条past的`source_authorised_full_name`解析姓与名，3条current使用冻结全名，包含逗号顺序、头衔、标点和重音处理；没有用past常常缺姓的`name`字段冒充全名。其他字母、分页及人物正文未查，不声明完整DIB没有这些人。

**新西兰官方传记目录：0新增。** 3次检索、4次导航读取，其中3次403；Honorary Fellows入口读取成功但没有可用目录行。本次官方Fellows讣告目录的检索文本投影返回76个姓名及生命周期，对全部647人作规范化全名、全名加出生年、姓氏加出生年筛选，均为0。这里只计这76项实际投影；没有人物正文采入，Honorary讣告索引未查询，也不声明新西兰全部传记已穷尽。投影SHA标为检索文本捕获，不冒充原始HTTP正文SHA。

## 剩余、证据与复现

当前未定645人：**591人无有效明确出生地，54人已有地名但地理未定**；出生窗内未定211人。除本轮2人外，其余4,981条完整JSON与v8相等。所有4,983条既有非地理字段及其他国家均不变。Home的Well Manor/Hampshire与London替代项保留；国籍、亲属住址或职业、童年、学校、任职、死亡地均未用来推本人出生地。旧54条地名未定库存本轮没有重复批审。

- `outputs/uk_birthplaces.csv`、`remaining_unknown.csv`、`changed_records.csv`：全表、645条未定、本轮2条变更；完整证据在`uk_birthplace_rows.jsonl.gz`。
- `outputs/summary.json`：统计及输入SHA；`all_country_birthplace_summary.csv`只更新英国快照行。
- `inputs/new_birthplace_facts.jsonl.gz`：2条新S2来源及地理限定；库存重审与active链接替换表均为空。
- `audit/eoas/`：候选、647条覆盖账本、请求记录、失败及不确定边界；`dib/`、`new_zealand/`：明确范围的零结果审计。
- `audit/new_facts_geography.jsonl.gz`、`source_audit.json`、`independent_review.json`、`verification.json`：地理、事实、全量及离线重放复核。
- `audit/baseline_provenance.json`：固定Git基线及恢复文件SHA；`MANIFEST.sha256`：交付校验。

不打包完整传记HTML、完整原网站响应或全部2,722项目录；保留短引文、URL、定位、原源SHA及范围投影。零结果路线的检索投影与HTTP原文捕获类型分别标注。`scripts/source_routes/`是采集过程的代码快照，依赖当时的临时缓存与路径，不是独立重放入口。可直接运行的完整输出重放入口仅为下面的`assemble.py`和`verify.py`。

在既有仓库根目录离线重放：

```sh
python studies/royal_society_birthplace_completion_v9/scripts/assemble.py
python studies/royal_society_birthplace_completion_v9/scripts/verify.py
```

本轮ZIP是增量；上述重放依赖仓库内固定v8基线及v3选择规则。检查覆盖4,983唯一记录、原生字段及旧隔离状态、所有CSV与计数、其他国家不变，以及7个输出逐字节重放一致。v1–v8快照不变，名录之间仍可能同人重复，不可相加当独立总人数。
