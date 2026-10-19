# 法国科学院采集：当前交接检查点

更新：2026-10-19 UTC。本轮完成 Shard07，从 PR103 合并的 151 卷 / 510 条目录事件继续。当前仍为历史会籍来源整理，正式入组、生日核定及八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已访问的唯一目录卷 | 151 | **167 / 211** |
| 可读取目录的卷 | 104 | **117** |
| 目录端点 HTTP404 的卷 | 47 | **50** |
| 目录事件候选 | 510 | **571** |
| 尚未访问的目录端点 | 60 | **44** |

权威机器检查点为 `data/france_academy_source_checkpoint_v6/summary.json`，同目录保存累计卷表、剩余队列和本批新增事件。CSV 沿用 v2 字段定义及文件名，文件夹 v6 表示新一轮不可变检查点。v5 的 151 行全部逐字段保持相同，本轮没有修订历史基线。

**571 是目录事件数，包含正式会籍类别、通讯、外籍、待核类别及少量院内职务，不是 571 位独立正式院士。** HTTP404 仅说明该目录端点缺失，事件数未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。成员接受、生日接受及八字计算标记均为 0；CTHS 562 人来源和其中 529 个日级生日来源声明保持原状态。

## Shard07：16 个新卷，61 条候选事件

冻结顺序：22、49、79、110、142、175、204、23、50、80、111、143、176、205、25、51。与基线无重叠，采集前这 16 卷均无本地来源缓存。本次首次访问为 HTTP200 13 卷、HTTP404 3 卷（111、204、205）。

结果目录：`data/france_academy_remaining_172_toc_batch_v1/shard_07/`。初始解析 60 条，来源审阅和 v1_12 修复后为 **61 条**：新增两条，删除一条跨栏目误入记录，另外 59 条逐字段不变。首抓 60 行、初始状态及每卷 SHA 均保留；新旧解析使用相同来源字节。

| 卷 / 年 | 初始 → 最终事件数 | 审阅处置 |
| --- | ---: | --- |
| T49 / 1859 | 0 → 1 | 裸 Nominations 标题先说明将补齐会员/通讯席位，下一行明确 Denis 获任通讯员，p935；补入该条 |
| T110 / 1890 | 7 → 8 | 原文明确 Lord Rayleigh 获任物理学通讯员，p508；解析补识别 Lord 称谓，姓名照录 |
| T50 / 1860 | 9 → 8 | 无 smallcap 标记的独立全大写主题标题未关闭栏目，误带入 Milne Edwards 副主席职务 p13；本批移除该行 |
| T23 / 1846 | 0 → 0 | 已读目录没有明确会籍选举/任命事件段，只有 Jacobi 批准敕令 p57；不重复计选举，不据此断言历史无选举 |
| T22 / 1846 | 7 → 7 | Jacobi p920 的 associé libre 与 T23 批准栏 associé étranger 措辞有差异；保留未知类别，留待原事件页核对 |

其余可读卷最终事件数为 T25=2、T51=2、T79=2、T80=7、T142=5、T143=1、T175=5、T176=13。全部 13 份可读目录均已审阅；批准敕令、候选申请及外部委员会任命没有作为新增会籍事件混入。

本批角色为正式类别候选 15（分科 12、libre 3）、通讯 39、外籍 5、院内职务 1、未知类别 1。T79 的 J. Bertrand 保留为院内职务；T22 Jacobi 保留 `NOMINATION_UNKNOWN_MEMBER_CLASS_MANUAL`。严格姓名匹配到既有 CTHS 候选池 7 条，仍不据此入组。本轮未打开原印刷事件页，未推断独立法令签署日期。

`final_source_review_v1.json` 保存两条新增、一条删除、59 条原记录不变的差分、T23 目录处置及 Jacobi 待核事项。累计为 **510 + 61 = 571**。

## 保存的证据与验证

解析器版本：`france-academy-legacy-heading-wikisource-source-only-v1_12`。本次修复覆盖真实会员任命标题的引导行、Lord 称谓以及无 smallcap 标记的独立全大写主题边界；会员栏目内的职务仍保留原分类。来源 SHA、403/429 停止、HTTP404 未知状态、去重续跑及研究门控规则保持。

源包：`data/france_academy_shard07_source_snapshot_v1/source_cache_v1.tar.gz`，18 个来源文件、619139 字节，包括 13 份目录 HTML、3 份真实 HTTP404 状态及目录类别和官方卷册入口，不含原书扫描图片。SHA-256：`a24e25e11b4b92741b25a55e34dccf160d305bae72879737c6b9c0f5fe654e38`。

Python 3.10 / 3.13 工作流包含语法 fixtures、16 项续跑/P1完整性回归、旧六批 14 + 61 + 70 + 23 + 60 + 58 条来源台账逐字段兼容、Shard07 离线台账比对，以及新累计四文件逐字节重建比对。本地 v6 从独立目录恢复的源包重新生成。

Python >=3.10，依赖 beautifulsoup4==4.12.3。以下命令在仓库根目录执行，每条一行。独立离线复现本批检查点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard07_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --baseline .\data\france_academy_source_checkpoint_v5\cumulative_source_checked_unique_volumes_v2.csv --shard-dir .\data\france_academy_remaining_172_toc_batch_v1\shard_07 --out .\local_runs\france_academy_shard07_checkpoint_verify
```

## 剩余事项与下一步

上一轮 P1 五卷恢复的 23 条、新旧源码 SHA 差异及处置记录，仍保存于 `data/france_academy_legacy_p1_review_v1/` 和 `data/france_academy_source_review_queue_v2/`。这些历史快照没有改写。

**16 个 P2 旧卷仍待复核**：54、55、61、65、72、93、117、120、121、130、136、144、159、160、161、183；未识别标题不能据此判定没有选举。50 个 HTTP404 目录还需另找来源。本批 T49 有标题零解析项已经解决，T23 已记录目录审阅处置；另保留 T22 Jacobi 的原页角色核验事项。

下一固定批次为 **Shard08，16 个新卷、零重叠**：81、112、145、177、207、26、52、82、113、146、178、208、27、53、83、114。Shards08–09 各 16 卷，Shard10 为 12 卷，合计剩余 44 卷。先推进 Shard08；P2 复核、Jacobi 原页核验及缺失目录恢复按独立有界批次继续。

下一批先查看计划（不联网）：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 8 --baseline .\data\france_academy_source_checkpoint_v6\cumulative_source_checked_unique_volumes_v2.csv
```

实际采集命令：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 8 --baseline .\data\france_academy_source_checkpoint_v6\cumulative_source_checked_unique_volumes_v2.csv --run
```

只需回传 `local_runs/france_academy_remaining_172_toc_batches_v1/shard_08/` 中的 summary、source_only_shard_checkpoint 和 person_event_ledger_summary；异常时同时回传 source_run_progress。原始页面、长日志保留在缓存。新 thread 先读本文件及 v6 summary，即可从 Shard08 续接。
