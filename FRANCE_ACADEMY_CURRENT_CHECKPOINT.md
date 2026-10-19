# 法国科学院采集：当前交接检查点

更新：2026-10-19 UTC。本轮完成 Shard06，从 PR102 合并的 135 卷 / 452 条目录事件继续。当前仍为历史会籍来源整理，正式入组、生日核定及八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已访问的唯一目录卷 | 135 | **151 / 211** |
| 可读取目录的卷 | 93 | **104** |
| 目录端点 HTTP404 的卷 | 42 | **47** |
| 目录事件候选 | 452 | **510** |
| 尚未访问的目录端点 | 76 | **60** |

权威机器检查点为 `data/france_academy_source_checkpoint_v5/summary.json`，同目录保存累计卷表、剩余队列和本批新增事件。CSV 沿用 v2 字段定义及文件名，文件夹 v5 表示新一轮不可变检查点。v4 的 135 行全部逐字段保持相同，本轮没有修订历史基线。

**510 是目录事件数，包含正式会籍类别、通讯、外籍及少量院内职务，不是 510 位独立正式院士。** HTTP404 仅说明该目录端点缺失，事件数未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。成员接受、生日接受及八字计算标记均为 0；CTHS 562 人来源和其中 529 个日级生日来源声明保持原状态。

## Shard06：16 个新卷，58 条候选事件

冻结顺序：171、201、18、47、77、108、140、173、202、19、48、78、109、141、174、203。与基线无重叠，采集前这 16 卷均无本地来源缓存。本次首次访问为 HTTP200 11 卷、HTTP404 5 卷（18、19、108、202、203）。

结果目录：`data/france_academy_remaining_172_toc_batch_v1/shard_06/`。初始解析 48 条，来源审阅和 v1_11 修复后为 **58 条**；首抓 48 行、初始状态及每卷 SHA 均保留。新旧解析使用相同来源字节。

| 卷 / 年 | 初始 → 最终事件数 | 修复及证据边界 |
| --- | ---: | --- |
| T48 / 1859 | 2 → 8 | 六条省略任命动词，但明确列出通讯类别、学部、替补关系及页码：Ridolfi、Renault、Hofmann、Dujardin、Virchow、Lecoq |
| T171 / 1920 | 0 → 1 | 选举标题中明确记载 J.-L. Breton 属于 académiciens libres，p1045；原文为名词式省略表达 |
| T173 / 1921 | 1 → 4 | 补 Marcel Brillouin p962、Félix Mesnil p1148、P. Zeeman p1323 三条明确类别的省略式条目 |
| T77 / 1873 | 10 → 10 | 拼回跨表续文：F. de Lesseps 为 Membre libre，p190；只修类别和页码 |
| T109 / 1889 | 4 → 4 | 拼回跨表续文，补 Suess 的目录指向页 p957；不增加事件 |

另六卷最终事件数为 T47=3、T78=13、T140=2、T141=2、T174=7、T201=4。全部 11 份可读目录的会员栏目已逐段审阅。省略式事件分别保留 `NOMINAL_NOMINATION_INDEX_ENTRY_TRANSCRIBED` 或 `NOMINAL_ELECTION_INDEX_ENTRY_TRANSCRIBED`，未将省略的动词伪记为原文明写“当选/获任命”。

本批角色为正式类别候选 14（分科 10、libre 4）、通讯 40、外籍 3、院内职务 1。T141 的 A. Chauveau 是副院长职务，未当作新会籍。严格姓名匹配到既有 CTHS 候选池 6 条，仍不据此入组。原文姓名照录；本轮未打开原印刷事件页，未推断独立法令签署日期。

`final_source_review_v1.json` 保存 10 条新增事件及两条旧记录的逐字段变化。累计为 **452 + 58 = 510**。

## 保存的证据与验证

解析器版本：`france-academy-legacy-heading-wikisource-source-only-v1_11`。省略式分支限定于明确会员选举/任命标题，并要求完整类别结构及页码；跨表拼接限定于实际观察到的连续片段形态。来源 SHA、403/429 停止、HTTP404 未知状态、去重续跑及研究门控规则保持。

源包：`data/france_academy_shard06_source_snapshot_v1/source_cache_v1.tar.gz`，18 个来源文件、526909 字节，包括 11 份目录 HTML、5 份真实 HTTP404 状态及目录类别和官方卷册入口，不含原书扫描图片。SHA-256：`065c1810470588f5f12ed7c420b5117c5878ca21fa2f49799041d29df800e322`。

Python 3.10 / 3.13 工作流包含语法 fixtures、16 项续跑/P1完整性回归、旧五批 14 + 61 + 70 + 23 + 60 条来源台账逐字段兼容、Shard06 离线台账比对，以及新累计四文件逐字节重建比对。本地 v5 从独立目录恢复的源包重新生成。

Python >=3.10，依赖 beautifulsoup4==4.12.3。以下命令在仓库根目录执行，每条一行。独立离线复现本批检查点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard06_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --baseline .\data\france_academy_source_checkpoint_v4\cumulative_source_checked_unique_volumes_v2.csv --shard-dir .\data\france_academy_remaining_172_toc_batch_v1\shard_06 --out .\local_runs\france_academy_shard06_checkpoint_verify
```

## 剩余事项与下一步

上一轮 P1 五卷已恢复 23 条，其新旧源码 SHA 差异及处置记录仍保存于 `data/france_academy_legacy_p1_review_v1/` 和 `data/france_academy_source_review_queue_v2/`。本轮没有改写这些历史文件。

**16 个 P2 旧卷仍待复核**：54、55、61、65、72、93、117、120、121、130、136、144、159、160、161、183；未识别标题不能据此判定没有选举。47 个 HTTP404 目录还需另找来源。本批 T171 的有标题零解析项已经解决，没有增加新待复核项。

下一固定批次为 **Shard07，16 个新卷、零重叠**：22、49、79、110、142、175、204、23、50、80、111、143、176、205、25、51。Shards07–09 各 16 卷，Shard10 为 12 卷，合计剩余 60 卷。先推进 Shard07；P2 复核及缺失目录恢复按独立有界批次继续。

下一批先查看计划（不联网）：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 7 --baseline .\data\france_academy_source_checkpoint_v5\cumulative_source_checked_unique_volumes_v2.csv
```

实际采集命令：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 7 --baseline .\data\france_academy_source_checkpoint_v5\cumulative_source_checked_unique_volumes_v2.csv --run
```

只需回传 `local_runs/france_academy_remaining_172_toc_batches_v1/shard_07/` 中的 summary、source_only_shard_checkpoint 和 person_event_ledger_summary；异常时同时回传 source_run_progress。原始页面、长日志保留在缓存。新 thread 先读本文件及 v5 summary，即可从 Shard07 续接。
