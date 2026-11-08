# 科学家出生地补全 v3：Fields主表收口、NAS传记批次

本轮新增 **9条出生地来源（2条S1、7条S2）及9个北半球判定**。Fields固定63条主表的地域未定2→0；NAS未定574→567。其他队列、本轮以前的三条奖项补充及英国全部4,983条完整记录均保持不变。

| 组别 | 固定记录数 | 北半球 | 南半球 | 未定 | 本轮补定 |
|---|---:|---:|---:|---:|---:|
| Fields主表 | 63 | 59 | 4 | 0 | 2 |
| NAS | 2,242 | 1,644 | 31 | 567 | 7 |
| Nobel科学重建ID范围 | 655 | 634 | 21 | 0 | 0 |
| 英国Royal Society v10 | 4,983 | 4,155 | 183 | 645 | 0 |
| CAS | 1,230 | 1,003 | 3 | 224 | 0 |
| 德国Leopoldina | 778 | 655 | 6 | 117 | 0 |
| 法国 | 775 | 702 | 3 | 70 | 0 |
| 日本 | 368 | 234 | 0 | 134 | 0 |

这些是名录内记录，不是跨名录独立人数。唯一键为`(cohort, record_id)`，仍有11,094条，未做跨队列统计去重或最终样本冻结。Fields的63条主表与另记的2026扩展分开，本轮未加入扩展人物。原DOB、历法、正式身份／资格字段、DOB来源组及QID不变；不新增八字或结果变量。

## Fields两条S1

| 人物 | 来源原始出生地 | 实际证据与精度 |
|---|---|---|
| Stanislav Smirnov | St. Petersburg, Russia | IMU／ICM2010官方材料明确本人出生句，时间仅1970年；Fields2010语境另行支持身份 |
| Hugo Duminil-Copin | Châtenay-Malabry, France | HLF官方laureate profile姓名下独立星号日期／地点行；另有Fields Medal 2022语境 |

Hugo原始星号行作为`structured_birth_row`保存，不改写成来源中不存在的“born”句；它不是脚注或死亡行。该行完整日期与原生1985-08-26一致。Smirnov材料仅支持出生年，未升级原生1970-09-03的月日证据，也未用旧检索片段中的Leningrad替换本次原文St. Petersburg。

2次新来源发现查询、4次新正文请求，未重读v2的受阻、无地点或超时URL。新CNRS正文没有出生地，另一官方PDF只给日期，未额外制造事实。捕获SHA是检索工具文本JSON的SHA，不冒充原HTML／PDF字节或目视核验。

## NAS七条S2与一条hold

确认真实NAS Biographical Memoirs入口及其集合页后，集合页HTML及实际嵌入的搜索配置脚本可读，但成员结果数据不在其中。本轮没有额外探查下游runtime或成员数据端点。配置脚本本身的已观察URL含`/api/1/views`，故不笼统声称从未读取任何API路径。

实际取得的National Academies官方《Biographical Memoirs: Volume 72 (1997)》目录，与574条NAS未定记录做批量姓名／首字母候选匹配；目录匹配只是选线索，不等于身份已接受。获批8个实际观察到的chapter URL各读取一次，8篇完整HTML均HTTP200。按完整标题姓名、原生DOB兼容、独立署名及NAS会籍／当选语境复核后，采纳7篇署名编辑传记，定S2，未因官方网站托管而升成S1。

| 人物 | 原始出生地 | 原作者 |
|---|---|---|
| L. A. DuBridge | Terre Haute, Indiana | Jesse L. Greenstein |
| R. G. Herb | Navarino on a small farm in north-central Wisconsin | Henry H. Barschall |
| Donald W. Kerst | Galena, Illinois | Andrew M. Sessler、Keith R. Symon |
| Paul J. Kramer | Brookville, Indiana | John S. Boyer、Aubrey W. Naylor |
| W. W. Morgan | Bethesda, Tennessee | Donald E. Osterbrock |
| M. M. Rhoades | Graham, Missouri | Wayne R. Carlson、James A. Birchler |
| J. E. Varner | Nashport, Ohio | Maarten J. Chrispeels |

七篇标题DOB与冻结原生DOB一致，但出生句的精度分别保留：Herb出生句只给1908年，Kramer和Varner出生句没有日期，标题日期作为独立一致性核对，不能说出生句本身确认了具体日。Morgan原文描述其出生小村当时已不存在，此历史限定保留，未套用现代同名村落坐标。出生句中的Indiana、Wisconsin、Illinois、Tennessee、Missouri、Ohio范围均明确全北；没有凭NAS会籍、国籍或工作地推USA，也没有把城市／农场转成精确出生点。

**Chandrasekhar保留hold。** 所读HTML标题为1910-10-13，与冻结原生1910-10-19不符。原出生句与来源元数据保存在`held_source_candidates.jsonl.gz`，未进入新事实输入或半球计数，原生日与整条旧记录不变。本轮不裁定哪边日期正确。

NAS共3次发现查询、5次索引／导航、8次获批全文请求，即16次逻辑尝试；0重试。全部源请求在约376秒内完成，其后只有本地提取与复核。初轮0事实状态另存为`initial_probe_checkpoint/`，最终结果为7条事实＋1条hold，不能把初轮0状态当本轮最终结果。该次仅筛查所取得的Volume72目录和8篇正文，不能声称全部约2,100篇NAS memoir已读取；未重复v2的六个成员简介。

NAS七条采纳事实的SHA对应原始HTTP章节HTML字节。保留原始粒度、标题、作者、定位和每独立署名章节不超过25词的短引文，不打包完整章节。原表没有独立死亡年／生命周期字段，因此来源生命周期仅存作语境，没有虚称与不存在的旧字段精确相等。

## 地理、窗口与保留项

出生地质量S1／S2、地理解析质量S3与原DOB来源组分别保存。Smirnov依据来源明确Russia的全北范围；NAS七人依据明确州范围，均无新增查询。

Hugo不能只凭France推北。本轮仅一次精确英／法label或alias地名查询，无LIMIT、无重试，保留全部16条bindings和唯一返回的地理候选Q200945（法国commune，P17 France）。直接地球坐标纬度48.765277777778、精度0.00027777777777778度，在精度范围内仍全北。只采用半球结论；该参考点没有赋给本人出生点，也没有更新人员QID、国家字段或唯一地理实体。Fields原地理快照与新增NAS地理表分别保留，合并表9条均北。

原生1835–1985窗内Fields61条为57北、4南、0未定；NAS2,240条为1,642北、31南、567未定。窗口只描述原生日期，没有重判历法、年龄资格或Source Tier；NAS Esau／Breit及Bonner共享QID相关hold不变。CAS仍是1,230条未裁定接受公历日期的正文日级声称；Nobel655仍是重建奖项ID范围、全部原生DOB空值，未恢复旧最终DOB表。英国的active94／隔离2／身份未核3、旧9个错误候选停用及Home替代项全部保留。

## 文件和复现

直接基线为v2完整主表，SHA256为`2b7897d0c4e2655ecb6f10311e1bdf7b06b8eeae3f181e9bebe92cbc7f066ee0`，不重建或覆盖旧英国部分。仅9条地理记录变化，其余11,085条完整对象相等，所有旧非地理字段不变。

- `outputs/birthplace_rows.jsonl.gz`、`birthplaces.csv`：当前完整合并记录；`remaining_unknown.csv`：保留未定记录。
- `outputs/changed_records.csv`、`changes.jsonl.gz`：本轮9条变化；`all_country_birthplace_summary.csv`、`summary.json`：计数、描述性窗口及输入SHA。
- `inputs/new_birthplace_facts.jsonl.gz`：2条S1＋7条S2及独立地理复核；`audit/fields/`、`nas_memoirs/`、`geography/`：读取边界、hold及查询元数据。
- 独立事实、地理、全量与重放复核在`audit/`；`MANIFEST.sha256`校验交付文件。完整原网页／传记缓存不随包分发。

`scripts/source_routes/`保存过程快照，依赖当时临时路径及缓存，不作为独立重放入口。可在既有仓库根目录运行：

```sh
python studies/scientist_birthplace_completion_v3/scripts/assemble.py
python studies/scientist_birthplace_completion_v3/scripts/verify.py
```

入口依赖固定v2主表，检查11,094个队列内唯一键、原生字段、英国和v2三条旧奖项补充、未受影响队列、CSV计数，以及7个输出逐字节重放一致。ZIP包含完整当前表与本轮审计；旧版本不变。
