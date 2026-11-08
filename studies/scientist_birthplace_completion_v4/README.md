# 科学家出生地补全 v4：NAS第73、74卷

本轮新增 **9条S2出生地来源、8个北半球判定**。另1条只补入出生地原文，地理结论仍未定。NAS未定567→559；除本轮9条地理记录，其余11,085条完整对象与v3相同，原生日、历法、正式身份／资格字段、DOB来源组和QID均不变。

| 范围 | 固定记录 | 北半球 | 南半球 | 未定 |
|---|---:|---:|---:|---:|
| NAS全表 | 2,242 | 1,652 | 31 | 559 |
| NAS原生1835–1985窗 | 2,240 | 1,650 | 31 | 559 |
| Fields主表（保持v3） | 63 | 59 | 4 | 0 |
| 英国（保持v10） | 4,983 | 4,155 | 183 | 645 |

合并表仍为11,094条名录内记录，唯一键为`(cohort, record_id)`，不是跨名录独立人数。没有跨队列统计去重、最终样本冻结或八字／结果变量分析。Fields的63条主表与另记2026扩展分开，本轮未加入扩展人物。

## 取得的出生地事实

| 人物 | 来源原文地点 | 文集／原作者 | 地理结论 |
|---|---|---|---|
| Charles G. Abbot | Wilton, New Hampshire | Vol73／David H. DeVorkin | 北 |
| Carl D. Anderson | New York City | Vol73／William H. Pickering | 未定 |
| James F. Bonner | Ansley, Nebraska | Vol73／Frank B. Salisbury | 北 |
| Rodney L. Cool | Platte, South Dakota | Vol73／Robert K. Adair | 北 |
| Frederick Keyes | Kingston, Ontario, Canada | Vol73／John Ross | 北 |
| Lewis Longsworth | Somerset, Kentucky | Vol73／Robert A. Alberty | 北 |
| William Young | Colorado Springs | Vol73／John D. Roberts | 北 |
| Scott E. Forbush | a farm near Hudson, Ohio | Vol74／James A. Van Allen | 北 |
| Stephen Kuffler | Tap, a village in Hungary | Vol74／John G. Nicholls | 北 |

九篇均为署名编辑传记，定S2；官方网站托管本身没有使其升级为S1。原始章节HTML字节SHA、标题／作者／本人出生句、原生DOB兼容及与2,242条NAS记录的唯一对应均经独立核验。每独立署名章节只保存不超过25词的短引文，完整HTML不随包分发。

Abbot出生句仅给1872年5月，Forbush出生句仅给1904年，其他七条出生句给日级日期；各自标题日期另行与原生DOB核对。没有把较粗的出生句写成确认了具体日，也没有升级任何原DOB等级。农场、村庄及“near”粒度原样保留，未替换成城市中心点。

James F. Bonner使用本人全名、原生1910-09-01、NAS出版物语境作独立匹配，没有使用或修复旧的共享错误QID；没有把事实传播给J. T. Bonner（1920-05-12）。两者原有`dob_status`及其他冻结字段不变，David Bonner也保持不变。Keyes的NAS语境由明确的逝世院士文集前言／署名收录支持，未虚构个人当选年份。

## 实际覆盖与两个hold

两条并行路线各使用1次发现查询、1次已观察官方目录读取：

- Vol73：`https://www.nationalacademies.org/read/9650`，实际20个人物目录标题，对全部567条未定记录匹配出8条候选。正文先批准6篇，因Vol74仅匹配3篇，再明确转移2个未用额度给Keyes和Longsworth，最终8篇各读一次。
- Vol74：`https://www.nationalacademies.org/read/6201`，实际20个人物目录标题，对同一567条未定记录匹配出3条候选，正文3篇各读一次。

共2次查询、2次目录、11次不同章节全文请求，11篇原始HTML均HTTP200，0重试。每次调用前有持久intent；两条路线均在各自8分钟以内收束。Vol73实际首次查询至最后捕获约182秒、开始至冻结约302秒；Vol74首次查询至最后捕获约125秒。目录初筛只是路由，全名／日期及本人出生语义在正文独立核验；不能称567人均已读取正文或NAS全部文集已搜尽。

Alfred Mirsky及David Harker各保留一条hold：已读正文没有明确本人出生地，不采用就学、成长或生活地点替代。两人的原始记录不变。上一批Vol72章节及六个成员简介没有重复读取；Vol72 Chandrasekhar的日期冲突hold仍原样保留，本轮未处理。

## 地理复核及一个未决地点

出生地来源等级S2、地理解析等级S3与原DOB来源组分别保存。七条明确州／国家范围可直接判北：New Hampshire、Nebraska、South Dakota、Canada、Kentucky、Ohio、Hungary；不凭NAS会籍或国籍推断USA，也不把参考区域或城市点赋给本人出生点。

仅对裸地名New York City及Colorado Springs做 **1次** 合并精确英文字段label／alias查询，无LIMIT、无重试。保留全部94条bindings、80个同名实体及类型、国家、坐标、地球／rank／精度，未以城市知名度排除物理地点。

Colorado Springs的唯一地理城市候选Q49258具有直接地球纬度38.863333333333，精度0.000277777778度，安全全北；另一同名项是照片。Anderson的出生地原文“New York City”已收录，但查询还返回一个同名酒店Q39319400，没有坐标或州，只给United States；美国整体不能作全北替代，因此该行按现行保守规则仍为地理未定。纽约市及另一个mint候选虽有北方坐标，未据此忽略缺坐标的物理地点。没有利用父亲的USA语境或本人后续就学推出生地；Young的California死亡地也未用于出生地点限定。

这是一份有界同名检索，不是穷尽全球地名库。9条明确出生地事实仍全部保留，只有8条新增半球判定；没有新增国家字段、精确出生点、唯一地点实体或人员QID。参考点与原始地点文字分开，Carl的`locality_resolution`明确为地理held。

## 基线与复现

直接基线是完整v3主表，SHA256为`6df02f0b3a535c8b5447ee704ddc96f473509ed9c2df84b25d6b40064a5dff44`。v2／v3已有12条补充及英国4,983条完整对象保持相等。其他七个队列逐行不变：Nobel当前655条重建ID范围仍为634北、21南、0未定，全部原生DOB仍为空，旧最终DOB表未恢复；CAS1,230条仍是未裁定接受公历日期的日级声称。原生日窗口仅作描述，未重判NAS历法／资格hold。

- `outputs/birthplace_rows.jsonl.gz`、`birthplaces.csv`为当前完整合并记录；`remaining_unknown.csv`保留所有未定行。
- `outputs/changed_records.csv`、`changes.jsonl.gz`记录9条地理变化；`all_country_birthplace_summary.csv`、`summary.json`保存计数、窗口及输入SHA。
- `inputs/new_birthplace_facts.jsonl.gz`保留9条来源及独立地理复核；`audit/vol73/`、`vol74/`、`geography/`保存范围、hold、账本、发现查询记录及原始地理JSON响应。
- 独立事实、地理、全量、CSV、离线重放与正文准确性报告在`audit/`；`MANIFEST.sha256`锁定实际分发文件。地理捕获元数据的分发拷贝去除了非必要客户端／授权信息，注明原元数据SHA；来源HTML及原地理JSON响应字节SHA不变。

`scripts/source_routes/`为依赖临时路径及缓存的过程快照，不是独立入口。可以在既有仓库根目录运行：

```sh
python studies/scientist_birthplace_completion_v4/scripts/assemble.py
python studies/scientist_birthplace_completion_v4/scripts/verify.py
```

重放依赖固定v3主表，检查全部原生字段、英国及旧12条补充、不受影响队列、CSV与计数、9条变更和7个输出逐字节重放一致。ZIP含完整当前表及本轮审计；旧版本不变。
