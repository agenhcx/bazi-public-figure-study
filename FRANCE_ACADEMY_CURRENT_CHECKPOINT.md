# 法国科学院采集：当前交接检查点

更新：2026-10-19 UTC。本轮完成历史 P1 五卷复核及 Shard05，从 PR101 合并的 119 卷 / 369 条目录事件继续。当前仍处于历史会籍来源整理阶段，最终入组、生日核定和八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已实际访问过的唯一目录卷 | 119 | **135 / 211** |
| 可读取目录的卷 | 83 | **93** |
| 目录子页 HTTP404 的卷 | 36 | **42** |
| 目录事件候选 | 369 | **452** |
| 从未访问过的目录端点 | 92 | **76** |

权威机器检查点为 `data/france_academy_source_checkpoint_v4/summary.json`，同目录保存累计卷表、剩余队列和本轮 83 条新增或重建事件。CSV 沿用 v2 字段定义和文件名，文件夹 v4 表示新一轮不可变检查点。

**452 是目录事件数，包含正式会籍类别、通讯、外籍和少量院内职务，不是 452 位独立正式院士。** HTTP404 仅说明该目录端点缺失，其事件数仍未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。成员接受、生日接受和八字计算标记均为 0；CTHS 562 人来源与其中 529 个日级生日来源声明保持原状态。

## 历史 P1 五卷：恢复 23 条，不增加已查卷数

冻结对象是旧队列中有标题但旧解析为零的五卷。本轮重新获取五份目录 HTML，**五份新 SHA 均与历史记录不同**；累计表保留旧 SHA 和修订原因。23 条是本次源码的复核结果，不能称为对历史零结果原始字节的精确重放。

| 卷 / 年 | 旧累计事件数 | 本轮结果 | 复核结论 |
| --- | ---: | ---: | --- |
| T3 / 1836 | 0 | 1 | Nominations 为交叉引用；其指向的 Correspondants 栏明确记载 Baily 通讯任命，p611 |
| T35 / 1852 | 0 | 3 | 现有语法可读三条；外部教授候选呈报未计入 |
| T94 / 1882 | 0 | 6 | 标题含 des correspondants，新增该来源支持的变体 |
| T124 / 1897 | 0 | 10 | 现有语法可读十条；独立副院长栏目未计入新会籍 |
| T125 / 1897 | 0 | 3 | 现有语法可读三条；外部委员会任命未计入 |

角色为正式类别候选 13（分科 11、libre 2）、通讯 9、外籍 1。v1_9 对本次新源码先读取 16 条，v1_10 再恢复 T3 的 1 条和 T94 的 6 条。结果及首抓与旧基线对照位于 `data/france_academy_legacy_p1_review_v1/`。旧队列 v1 保持原字节；五项处置与剩余队列位于 `data/france_academy_source_review_queue_v2/`。

## Shard05：16 个新卷，60 条候选事件

冻结顺序为 105、135、167、197、16、45、75、106、138、170、200、17、46、76、107、139，与基线 119 个已查卷无重叠。首次访问为 HTTP200 10 卷、HTTP404 6 卷（16、76、105、135、167、200）；初次状态及源 SHA 保存在该批 `first_capture_source_review_v1.json`。

最终仍为 **60 条**：正式类别候选 19（明确分科 16、libre 1、上下文分科空缺任命 2）、通讯 38、外籍 3。T17 / 1843 的 Mauvais p1164、Morin p1327 原文明确指定分科空缺席位；解析器仅允许既有语法中的可选逗号，将两条 UNKNOWN 改为 `FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION`。**没有新增事件，也没有提升为已核准会员。** 首抓 60 行保留，`final_source_review_v1.json` 记录这两处分类变化。

结果目录为 `data/france_academy_remaining_172_toc_batch_v1/shard_05/`。目录人名照录，严格姓名匹配到 CTHS 候选池 2 条，仍不据此入组。本轮未新增原印刷事件页目视核验，未从目录推断独立法令签署日期。

累计计算为 **369 + 23（旧五卷修订）+ 60（新十六卷）= 452**；除上述五卷外，基线中的 114 行逐字段保持相同。

## 证据与离线复现

解析器为 `france-academy-legacy-heading-wikisource-source-only-v1_10`。P1 更新入口独立核验五卷集合及顺序、卷年及规范 URL、实际 baseline SHA，以及冻结旧队列路径和字节 SHA。断点续跑、403/429 停止、HTTP404 未知值、缓存 SHA 和研究门控检查保持。

本轮源包为 `data/france_academy_shard05_p1_source_snapshot_v1/source_cache_v1.tar.gz`：23 个来源文件、763282 字节，含 P1 HTML 5 份、Shard05 HTML 10 份、真实 HTTP404 状态 6 份，以及目录类别和官方卷册入口；不含原书扫描图片。SHA-256：`32fb02b021385a172fb246ddc6f82f496b116cf69a080cd68e9e5c57bf75ac33`。

Python 3.10 / 3.13 工作流检查来源语法、续跑及六项 P1 约束，核验旧三批 14 + 61 + 70 条记录不变，离线重放 Shard05，并逐字节比对重建的累计四份文件。当前检查点也从独立目录恢复的源包重新生成。

Python >=3.10，依赖 beautifulsoup4==4.12.3。以下命令在仓库根目录执行，每条一行。离线复现本轮检查点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard05_p1_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --baseline .\data\france_academy_source_checkpoint_v3\cumulative_source_checked_unique_volumes_v2.csv --revision-dir .\data\france_academy_legacy_p1_review_v1 --shard-dir .\data\france_academy_remaining_172_toc_batch_v1\shard_05 --out .\local_runs\france_academy_shard05_checkpoint_verify
```

## 未解决事项与下一步

旧零解析队列的 5 个 P1 项已处理，**16 个 P2 项仍待复核**：54、55、61、65、72、93、117、120、121、130、136、144、159、160、161、183。它们是未识别选举标题的可读旧卷，不能据此断言没有选举。42 个 HTTP404 目录的其它来源恢复仍待进行。

下一固定批次为 **Shard06，16 个新卷、零重叠**：171、201、18、47、77、108、140、173、202、19、48、78、109、141、174、203。Shards06–09 各 16 卷，Shard10 为 12 卷，合计剩余 76 卷。先推进 Shard06；P2 复核及缺失目录恢复另按有界批次推进。

下一批先查看计划（不会联网）：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 6 --baseline .\data\france_academy_source_checkpoint_v4\cumulative_source_checked_unique_volumes_v2.csv
```

实际采集命令：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 6 --baseline .\data\france_academy_source_checkpoint_v4\cumulative_source_checked_unique_volumes_v2.csv --run
```

只需回传 `local_runs/france_academy_remaining_172_toc_batches_v1/shard_06/` 中的 summary、source_only_shard_checkpoint 和 person_event_ledger_summary；异常时同时回传 source_run_progress。原始页面和长日志留在缓存，聊天仅保留进度、异常和下一步。新 thread 先读本文件和 v4 summary，即可从 Shard06 继续。
