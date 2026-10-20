# 法国科学院采集：当前交接检查点

更新：2026-10-20 UTC。本轮从 PR107 合并的 v9（211 卷 / 738 条目录事件）完成固定 16 卷 P2 来源复核。当前检查点为 **v10：211 卷 / 811 条目录事件候选**。下一阶段：缺失目录恢复。正式入组、生日核定及八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已访问的唯一目录卷 | 211 | **211 / 211** |
| 可读取目录的卷 | 149 | **149** |
| 目录端点 HTTP404 的卷 | 62 | **62** |
| 目录事件候选 | 738 | **811** |
| 尚未访问的目录端点 | 0 | **0** |
| P2 旧卷来源复核待办 | 16 | **0** |

权威机器检查点为 `data/france_academy_source_checkpoint_v10/summary.json`，同目录保存累计卷表、剩余首次访问队列和本批修订事件。CSV 沿用 v2 字段定义及文件名，文件夹 v10 表示本轮不可变检查点。P2 为纯旧卷修订；其它 **195 卷逐字段保持不变**，修订的 16 卷保留各自旧计数和旧 SHA。

811 是目录事件数，包含不同会籍、少量院内职务及角色待核记录；独立人物数和正式入组人数还须后续确认。62 个 HTTP404 的事件数继续为空、语义为未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。所有成员接受、生日接受和八字计算标记均为 0；CTHS 562 人来源及其中 529 个日级生日来源声明保持原状态。

## P2：16 卷来源复核结果

冻结卷号：54、55、61、65、72、93、117、120、121、130、136、144、159、160、161、183。固定输入队列为 `data/france_academy_source_review_queue_v2/pending_p2_source_review_queue_v2.csv`，SHA-256：`6bb32085c70271c4884d9d693ab2aebeae3d5eaf7a84f0dab01f65cbd867f300`。

这 16 卷历史记录均为 HTTP200、未识别标题且解析为 0；本轮开始时历史 HTML 在可用缓存和八个既有源包中均缺失。受控重新抓取后全部 HTTP200，**16 份新 SHA 均与历史 SHA 不同**。完整的旧/新 SHA 对照和首抓原始 inventory 已保存。首次请求完成后，后续审阅与重放均使用冻结的新来源。

两个增量必须区分：

- **历史零结果 → 本次最终 73 条**：累计检查点净增 73 条，包含来源替换及当前解析器的结果，不能归因于单独的历史解析器修复。v10 的旧兼容字段 `grammar_revision_net_added_index_events` 仍为73，新语义字段明确它是来源修订净增量。
- **同一批新来源上的 67 → 73 条**：v1_15 首抓67，v1_16 确证新增6条；另修复3条既有记录的5个字段，64条首抓记录全部18列不变，无删除。

| 卷 / 年 | 本次首抓 → 最终 | 审阅处置 |
| --- | ---: | --- |
| T144 / 1907 | 1 → 7 | 裸 Nominations 栏目先列秘书职务，随后六条明确会员当选仍属同栏；保留秘书条目并补 H. Douvillé881、Henry Le Chatelier958、le Prince Roland Bonaparte249、J. Tannery554、J. Carpentier1017、Aimé Witz791 |
| T117 / 1893 | 5 → 5 | Ludwig 的 p157 粘在完整选举句句号后、第二格为空；补两个页码字段 |
| T130 / 1900 | 23 → 23 | Darboux 的相邻跨表续文提供 p1369，补两个页码字段并保留秘书职务；Bazin p1740 的 Section’de Mécanique 明确提供学部 Mécanique |

其余有事件卷为 T54=4、T55=1、T65=2、T120=13、T121=10、T136=8。本批73条分类为：分科成员13、上下文支持的分科任命1、自由院士6、通讯44、外籍6、院内职务3。严格姓名匹配到既有 CTHS 候选池 2 条，仍不据此入组。

七个当前零候选卷 **61、72、93、159、160、161、183** 已逐段审阅可见目录，包括相关混合 DOM。处置限定为“当前可见目录未确认符合本次范围的事件”，不推断历史上没有选举。独立 Académie 栏目的副院长、外部委员会、撤销选举的法令和仅批准既有选举的法令均按既定范围处理；具体排除依据和页码保存在本批 `final_source_review_v1.json`。

结果目录：`data/france_academy_legacy_p2_review_v1/`。新处置表与下一阶段队列位于 `data/france_academy_source_review_queue_v3/`。v1/v2 历史队列、P1五卷23条审阅及先前检查点均保持原样。

## 证据与复现

解析器为 `france-academy-legacy-heading-wikisource-source-only-v1_16`。新 P2 runner 和 updater 严格绑定 v9 SHA、16卷顺序、固定队列及每卷旧/新来源证据；纯修订必须使用 `--revision-only`，不能混入新 shard。失败来源不能替换旧证据，研究接受门控仍为0。

源包：`data/france_academy_legacy_p2_source_snapshot_v1/source_cache_v1.tar.gz`，18个来源文件、684711字节，包括16份目录HTML及目录类别/官方卷册入口。SHA-256：`c7647044bebe27fa2729c2abcb5adad51206bee57359ab2ee097decc708beea5`。不含原书扫描图片。

Python3.10/3.13 CI覆盖语法fixtures、32项完整性回归（旧resume10、P1六项、新P2十六项）、历史十批514条完整字段和逐卷来源兼容、本批台账及v10四文件逐字节离线重建。P2修订门控另经独立只读审查。

Python>=3.10，依赖 beautifulsoup4==4.12.3。下列命令在仓库根目录执行，每条一行。

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_legacy_p2_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --revision-only --baseline .\data\france_academy_source_checkpoint_v9\cumulative_source_checked_unique_volumes_v2.csv --revision-dir .\data\france_academy_legacy_p2_review_v1 --out .\local_runs\france_academy_p2_checkpoint_verify
```

## 下一阶段：缺失目录恢复

首次访问分片已在 Shard10 完成，P2来源复核也已结束。下一轮从 **v10 + source_review_queue_v3** 接续。

`missing_toc_source_recovery_queue_v3.csv` 保存全部62个HTTP404目录的已知失败URL、原来源组及未知计数语义，按卷号顺序分为4批（16、16、16、14）。下一固定批为 **第0批：2、4、5、6、7、9、10、11、12、13、15、16、18、19、20、21**。先从这些卷的 Wikisource 卷册入口和官方档案页查找替代目录或扫描线索，记录实际新URL、响应及SHA；确认来源可用和结构后，再建立有界恢复入口及后续修订检查点。当前尚无已验证的替代来源批量抓取命令。

原页措辞待核四项仍保留：T22 Jacobi 类别差异（Shard07）；T26 Constant Prévost 学部差异、T178 Sur William Pope 转录称谓（Shard08）；T85 Godron p24 的 Correspoudant 角色原词（Shard09）。这些问题尚未通过原印刷事件页解决。

新 thread 先读本文件、v10 summary 和 queue_v3 summary，即可接续。原始HTML、源码差分和长日志保留在文件；继续保持会员接受、精确生日接受和八字计算为0，直到各自证据审查完成。
