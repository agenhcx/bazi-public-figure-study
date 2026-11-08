# 英国皇家学会出生地补齐 v17

本轮新增11条此前为空的出生地，出生地支持均保守列S2；其中6条新增北半球判定，另外5条只补出生地、半球仍未知。原生日及其来源等级、原DOB的S2与S2+S3分组均不变。

| 冻结对象 | 新出生地原文 | 支持来源 | 半球 |
|---|---|---|---|
| James Fairlie Gemmill | Hillhead, Mauchline, Ayrshire | RSE编纂传记索引 | 北 |
| Peter George Le Comber | Ilford, Essex | RSE编纂传记索引 | 北 |
| George Francis Mitchell | Ireland | RSE编纂传记索引 | 北 |
| Patrick Anthony Merton | Woldingham in Kent | RCP编辑传记 | 北 |
| Leonard George Goodwin | Wood Green, London | R Killick-Kendrick署名RCP传记 | 未知 |
| Sir Sheldon Francis Dudley | Lisbon | Richard R Trail署名RCP传记 | 未知 |
| Allan Watt Downie | the Mid Street cottage in Rosehearty, Aberdeenshire | K McCarthy署名RCP传记 | 北 |
| Albert Charles Chibnall | Hammersmith, London | S V Perry署名ODNB公开摘录 | 未知 |
| Sir Alan Sterling Parkes | Bank House, Castleton, near Rochdale | R B Heap署名ODNB公开摘录 | 未知 |
| Benjamin Moore | Paisley, Renfrewshire (near Glasgow) | Richard Froggatt署名Ulster Biography | 北 |
| Sir Alister Clavering Hardy | Nottingham | RSE编纂传记索引 | 未知 |

11条原来源均明确给出完整原姓名成分、相符的精确生日和出生地关系。生日可以位于同篇标题、单独Born字段或出生句；没有把日期精度推高或修复原日期。Le Comber的索引标题实际为`COMBER, PETER GEORGE LE`，直接对应原表姓名成分及顺序，没有重解析或改写原姓氏。Downie出生句明确涵盖他和孪生兄弟，不是把家族地址推成出生地。

六条北半球判定来自出生句／出生地字段直接限定的Ayrshire、Essex、Ireland、Kent、Aberdeenshire、Renfrewshire。Ireland无论指岛屿或现代国家，范围均在北半球；不作政治国家字段赋值。Kent按来源出生句原文保留，没有另行校正县名或城镇对应。其余地点不按知名城市、国籍、父母、成长、学校、工作、死亡地或页脚补国家。没有赋个人国家、唯一地点实体或经纬度。

| 范围 | 固定记录 | 北 | 南 | 未定 |
|---|---:|---:|---:|---:|
| 全表 | 4983 | 4169 | 186 | 628 |
| 原生DOB在1835–1985年内 | 2644 | 2269 | 181 | 194 |

窗口当前出生地空值159降至148，半球未定200降至194；未定中148条为空、46条已有地名。全表未定628条中570条为空、58条已有地名。完整对象4972条与v16逐字段不变；11条变更仅限当前出生地／地理字段及新的v17证据对象，旧字段值与缺失字段集合均保留回滚快照。原DOB、历法、身份、资格、QID、DOB等级、国家、坐标、旧选中证据、原哈希、官方字段状态及所有v15/v16补充保持历史原值。

本轮先固定159个空值窗口对象、8个逐人跟进目标和一条新RSE索引路线。RSE《Former Fellows … 1783–2002: Biographical Index》由C D Waterston及A Macmillan Shearer编纂，出版日期为2006年7月；两部分属于同一作品，不算两个独立佐证。该参考索引不是出生登记簿，也不因官方宿主而升为S1。RSE仅作为英国皇家学会队列的出生地支持，没有新增另一院士队列或改变成员资格。

两次原PDF字节请求均实际返回403，立即停止，没有保存PDF或重试。此前工具已提供两个原PDF的解析文本，因此转为159次格式化全名查找，每个目标在按姓氏选择的部分查找一次，并人工核对实际返回的条目。工具查找会给出宽泛或不相关窗口；该筛查不是规范化完整原文搜索，不能把未命中当成索引或所有文献中不存在该人。

索引中明确绑定6条目标条目：4条有出生地；Masterman和Chibnall的已见段落只有日期／职业等、没有出生地字段。另对Watson、John Brown两个目标审查并排除4条异人候选，依据不相符的寿年／职业，不当作已确定同一人的生日冲突。剩余151个目标的返回投影没有绑定目标标题。159次查找不是阅读159篇传记；实际相关索引条目段为6条正向绑定及4条异人排除。

逐人固定跟进8人中7人采用；与索引复核的8个目标有Chibnall一人重叠，故实际唯一复核对象为15人（8+8−1），11人采用、4人待定。Chibnall虽然索引未见出生地，但独立ODNB原文有明确出生句。Parkes起初只有RAI转录线索，根代理追加1次定向检索后读到新的原ODNB公开摘录，原转录未作为事实采用，原RS PDF403也未重试。四条主hold为Haydon原正文不可用、Masterman已见索引段无出生地，以及Watson／John Brown异人候选不能绑定。

来源质量细节保留在audit：Dudley同篇FRS年份出现1941／1951不一致，没有挑选年份或修复资格；完整姓名、精确生日、寿年与海军医学身份仍明确，不存在已见出生地／DOB冲突。Moore采集组记录一项无关历史叙述质量提示；根代理未裁定该奖项事实或修复其他数据，不把该提示当作新的出生地冲突。Merton编辑传记引用的Times正文未另读，不称独立佐证。

本轮共16次检索、24次网页导航（23次原来源、1次二手出处线索），另2次原PDF字节GET；解析文本查找162次（索引159、采集组1、根代理2）。根代理直接核读7个采用传记／公开摘录，并在本地保留的工具解析投影中核对4个索引出生字段。工具解析文本不是原始HTTP；未知实际状态、请求时刻和原字节哈希保持空值。只有两次真实GET日志保留403及真实起止时间，不宣称工具解析PDF等于HTTP200或成功下载PDF。Gemmill、Hardy、Masterman未见印刷页码，保持空值；只使用实际PDF页序和解析行，不按偏移猜页码。

初始范围计划在采集前；原PDF下载失败后改用已解析文本、根代理Parkes跟进及最终判定均按实际发生时序记录，没有倒签为来源盲预注册。RSE出生地是明确标记的结构化字段，保留字段值、条目号和原文定位，不强行编造英文句子引文；同一索引作品不分发整条正文或额外散引文。其他每个来源不同英文引文不超过25词。原网页、整本PDF、页面图像及解析窗口缓存均不分发。

直接基线为Git提交`72edac7cceca5cc4aa077dddc8c5fde401059b36`的v16对象，canonical JSONL SHA256为`4811ffec9a75ac2d9488bc2a1bd97922369bf40b27362a59fb9d4ddfdcfd3d9f`。包内v10载体和冻结v11–v16输入可独立重建主表：

```sh
python studies/royal_society_birthplace_completion_v17/scripts/replay.py
```

单独解压后也可进入该目录运行`python scripts/replay.py`。脚本只重放审定事实和主表，不再次联网采集；原文访问仍受网站限制。它核对159队列、固定8目标、实际15复核对象的采用／hold完备分区、冻结字段及未变对象，分别统计首个出生地和新增半球。输出完整gzip、4983行主CSV、变更表、窗口未定表及summary，保留旧CSV列并新增v17列；gzip固定空文件名和零mtime。Git保存输入、代码、CSV及审计，可再生主gzip也在ZIP内。

来源QA直接核读保留的RSE解析片段，其余7条审查采集／根代理观察，未重新联网抓取；验证范围明确披露。没有其他队列修改、跨队列统计去重、八字、表现分析或最终队列冻结。
