# 法国科学院采集：当前交接检查点

更新：2026-10-20 UTC。本轮完成 Shard09，从 PR105 合并的 183 卷 / 622 条目录事件继续。当前仍为历史会籍来源整理，正式入组、生日核定及八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已访问的唯一目录卷 | 183 | **199 / 211** |
| 可读取目录的卷 | 129 | **139** |
| 目录端点 HTTP404 的卷 | 54 | **60** |
| 目录事件候选 | 622 | **675** |
| 尚未访问的目录端点 | 28 | **12** |

权威机器检查点为 `data/france_academy_source_checkpoint_v8/summary.json`，同目录保存累计卷表、剩余队列和本批新增事件。CSV 沿用 v2 字段定义及文件名，文件夹 v8 表示新一轮不可变检查点。v7 的 183 行全部逐字段保持相同，本轮没有修订历史基线。

**675 是目录事件数，包含不同会籍类别、角色待核记录及少量院内职务，不是 675 位独立正式院士。** HTTP404 仅说明该目录端点缺失，事件数未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。成员接受、生日接受及八字计算标记均为 0；CTHS 562 人来源和其中 529 个日级生日来源声明保持原状态。

## Shard09：16 个新卷，53 条候选事件

冻结顺序：147、179、209、28、56、84、115、148、180、29、57、85、116、149、181、30。与基线无重叠，采集前这 16 卷均无本地来源缓存。本次首次访问为 HTTP200 10 卷、HTTP404 6 卷（28、29、30、115、116、209）。

结果目录：`data/france_academy_remaining_172_toc_batch_v1/shard_09/`。初始解析 49 条，来源审阅和 v1_14 修复后为 **53 条**：新增四条、补齐一条既有记录的两个页码字段、其余 48 条逐字段不变，没有删除事件。首抓台账、初始状态及每卷 SHA 均保留；新旧解析使用相同来源字节。

| 卷 / 年 | 初始 → 最终事件数 | 审阅处置 |
| --- | ---: | --- |
| T57 / 1863 | 4 → 5 | 补 Sylvester p945；会员任命栏目内的名词式条目省略谓词，标为 NOMINAL_NOMINATION_INDEX_ENTRY_TRANSCRIBED；de la même Section 不反推学部 |
| T84 / 1877 | 4 → 5 | 补 Sa Majesté don Pedro d’Alcantara 外籍条目 p1488，保留原文称谓与姓名 |
| T85 / 1877 | 2 → 3 | 补单一 Cailletet 姓名前带 MM. 的通讯条目 p1141；Godron p24 的原词 Correspoudant 保留为角色待核 |
| T148 / 1909 | 7 → 8 | 补 S. A. S. Albert Ier, prince de Monaco 外籍条目 p821，保留原文称谓 |
| T56 / 1863 | 10 → 10 | Mac Leur 跨表续文提供 p765；首个页码及全部页码字段由空补为765，姓名、角色及空学部保持，不增加事件 |

其余可读卷最终事件数为 T147=6、T149=3、T179=3、T180=8、T181=2。全部 10 份可读目录均已审阅；T147 的 Picard p18 与 van Tieghem p728 保留为院内职务。外部委员会、独立职务、候选准备及无效选举条目均按既有边界处理。

本批角色为 通讯 29、分科正式成员 16、外籍 4、角色待核 1、院内职务 2、自由院士 1。严格姓名匹配到既有 CTHS 候选池 6 条，仍不据此入组。本轮未打开原印刷事件页，未推断独立法令签署日期。

`final_source_review_v1.json` 保存四条新增、一条既有事件的两处字段变化、48 条原记录不变及逐卷审阅处置。累计为 **622 + 53 = 675**。

## 保存的证据与验证

解析器版本：`france-academy-legacy-heading-wikisource-source-only-v1_14`。新称谓和名词式任命规则以实际来源及栏目边界限定；跨表页码只从相邻且明确连续的片段恢复。来源姓名、角色拼写及省略的学部不通过推测规范化。来源 SHA、403/429 停止、HTTP404 未知状态、去重续跑及研究门控规则保持。

源包：`data/france_academy_shard09_source_snapshot_v1/source_cache_v1.tar.gz`，18 个来源文件、499331 字节，包括 10 份目录 HTML、6 份真实 HTTP404 状态及目录类别和官方卷册入口，不含原书扫描图片。SHA-256：`395181b131d1e5172b71e173399957d314a46e35869be4ecf4229eecabf22a96`。

Python 3.10 / 3.13 工作流包含语法 fixtures、16 项续跑/P1完整性回归、旧八批 14 + 61 + 70 + 23 + 60 + 58 + 61 + 51 = 398 条来源台账逐字段兼容、Shard09 离线台账比对，以及新累计四文件逐字节重建比对。本地 v8 从独立目录恢复的源包重新生成。

Python >=3.10，依赖 beautifulsoup4==4.12.3。以下命令在仓库根目录执行，每条一行。独立离线复现本批检查点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard09_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --baseline .\data\france_academy_source_checkpoint_v7\cumulative_source_checked_unique_volumes_v2.csv --shard-dir .\data\france_academy_remaining_172_toc_batch_v1\shard_09 --out .\local_runs\france_academy_shard09_checkpoint_verify
```

## 剩余事项与下一步

P1 五卷恢复的 23 条、新旧源码 SHA 差异及处置记录，仍保存于 `data/france_academy_legacy_p1_review_v1/` 和 `data/france_academy_source_review_queue_v2/`。这些历史快照没有改写。

**16 个 P2 旧卷仍待复核**：54、55、61、65、72、93、117、120、121、130、136、144、159、160、161、183；未识别标题不能据此判定没有选举。60 个 HTTP404 目录还需另找来源。

原页待核事项保持：T22 Jacobi 类别措辞差异（见 Shard07 final_source_review）；T26 Constant Prévost 学部措辞差异和 T178 Sur William Pope 的转录称谓（见 Shard08）；本批 T85 Godron p24 的 Correspoudant 角色措辞（见 Shard09）。这些事项没有通过推测自动解决。

下一固定批次为 **Shard10，最后 12 个未访问卷、零重叠**：58、86、118、150、31、59、87、119、151、60、88、90。首次访问完成后，P2 复核、原页核验及缺失目录恢复仍按独立有界批次继续，不能把211个端点全部访问等同于会籍或生日研究完成。

下一批先查看计划（不联网）：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 10 --baseline .\data\france_academy_source_checkpoint_v8\cumulative_source_checked_unique_volumes_v2.csv
```

实际采集命令：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 10 --baseline .\data\france_academy_source_checkpoint_v8\cumulative_source_checked_unique_volumes_v2.csv --run
```

只需回传 `local_runs/france_academy_remaining_172_toc_batches_v1/shard_10/` 中的 summary、source_only_shard_checkpoint 和 person_event_ledger_summary；异常时同时回传 source_run_progress。原始页面、长日志保留在缓存。新 thread 先读本文件及 v8 summary，即可从 Shard10 续接。
