# 法国科学院采集：当前交接检查点

更新：2026-10-19 UTC。本轮完成 Shard08，从 PR104 合并的 167 卷 / 571 条目录事件继续。当前仍为历史会籍来源整理，正式入组、生日核定及八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已访问的唯一目录卷 | 167 | **183 / 211** |
| 可读取目录的卷 | 117 | **129** |
| 目录端点 HTTP404 的卷 | 50 | **54** |
| 目录事件候选 | 571 | **622** |
| 尚未访问的目录端点 | 44 | **28** |

权威机器检查点为 `data/france_academy_source_checkpoint_v7/summary.json`，同目录保存累计卷表、剩余队列和本批新增事件。CSV 沿用 v2 字段定义及文件名，文件夹 v7 表示新一轮不可变检查点。v6 的 167 行全部逐字段保持相同，本轮没有修订历史基线。

**622 是目录事件数，包含正式会籍类别、通讯、外籍、待核类别及少量院内职务，不是 622 位独立正式院士。** HTTP404 仅说明该目录端点缺失，事件数未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。成员接受、生日接受及八字计算标记均为 0；CTHS 562 人来源和其中 529 个日级生日来源声明保持原状态。

## Shard08：16 个新卷，51 条候选事件

冻结顺序：81、112、145、177、207、26、52、82、113、146、178、208、27、53、83、114。与基线无重叠，采集前这 16 卷均无本地来源缓存。本次首次访问为 HTTP200 12 卷、HTTP404 4 卷（114、177、207、208）。

结果目录：`data/france_academy_remaining_172_toc_batch_v1/shard_08/`。初始解析 43 条，来源审阅和 v1_13 修复后为 **51 条**：新增八条、修复两条既有记录的字段、其余 41 条逐字段不变，没有删除事件。首抓 43 行、初始状态及每卷 SHA 均保留；新旧解析使用相同来源字节。

| 卷 / 年 | 初始 → 最终事件数 | 审阅处置 |
| --- | ---: | --- |
| T83 / 1876 | 0 → 1 | 标题 Nomination des membres et correspondants 的 des membres 用词此前未识别；补 Favé 自由院士条目 p125 |
| T112 / 1891 | 0 → 7 | 旧 div.tableItem 浮动布局使用 tableDots/tablePage，没有 ws-titre/ws-titrex；恢复会员栏目七条明确任命 |
| T178 / 1924 | 9 → 9 | p1592 已计事件的空姓名补为目录原写 Sur William Pope；Charles Rabut p1871 补跨表续文中的 division des applications de la science à l’industrie，均不增计数 |
| T27 / 1848 | 0 → 0 | 可读 A–Z 目录含委员会、外籍空缺候选准备与死亡公告，未见明确会员选举/任命条目；不据此断言历史没有选举 |
| T26 / 1848 | 2 → 2 | Constant Prévost p168 任命栏写 Minéralogie et de Zoologie，而 p233 批准栏写 Minéralogie et de Géologie；保留前者并登记原页待核 |

T112 新增事件指向印刷页 81、148、470、509、846、930、1298。其余可读卷最终事件数为 T52=4、T53=8、T81=1、T82=8、T113=1、T145=5、T146=5。全部 12 份可读目录均已审阅；独立职务、候选申请、批准敕令与外部委员会没有混作新增会籍。

本批角色为 分科正式成员 14、通讯 29、外籍 3、院内职务 2、自由院士 3。T146 的 H. Becquerel 仍单列为秘书职务。严格姓名匹配到既有 CTHS 候选池 3 条，仍不据此入组。本轮未打开原印刷事件页，未推断独立法令签署日期。

`final_source_review_v1.json` 保存八条新增、两处字段变化、41 条原记录不变及逐卷审阅处置。Pope 用同卷、同源 SHA、同动作/角色/学部及印刷页的唯一对应，确认是既有空姓名行的修复，未当作新增事件。累计为 **571 + 51 = 622**。

## 保存的证据与验证

解析器版本：`france-academy-legacy-heading-wikisource-source-only-v1_13`。旧浮动布局限定于自身 tableItem 内的 tableDots/tablePage 结构；跨表分组续文要求相邻完整片段与明确页码。来源姓名照录，未把 Sur 改为 Sir。来源 SHA、403/429 停止、HTTP404 未知状态、去重续跑及研究门控规则保持。

源包：`data/france_academy_shard08_source_snapshot_v1/source_cache_v1.tar.gz`，18 个来源文件、575311 字节，包括 12 份目录 HTML、4 份真实 HTTP404 状态及目录类别和官方卷册入口，不含原书扫描图片。SHA-256：`62566a576363e2c56b8e83d3a3498fbe1cb51eb207978fd528677c3289bfb8ac`。

Python 3.10 / 3.13 工作流包含语法 fixtures、16 项续跑/P1完整性回归、旧七批 14 + 61 + 70 + 23 + 60 + 58 + 61 = 347 条来源台账逐字段兼容、Shard08 离线台账比对，以及新累计四文件逐字节重建比对。本地 v7 从独立目录恢复的源包重新生成。

Python >=3.10，依赖 beautifulsoup4==4.12.3。以下命令在仓库根目录执行，每条一行。独立离线复现本批检查点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard08_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --baseline .\data\france_academy_source_checkpoint_v6\cumulative_source_checked_unique_volumes_v2.csv --shard-dir .\data\france_academy_remaining_172_toc_batch_v1\shard_08 --out .\local_runs\france_academy_shard08_checkpoint_verify
```

## 剩余事项与下一步

P1 五卷恢复的 23 条、新旧源码 SHA 差异及处置记录，仍保存于 `data/france_academy_legacy_p1_review_v1/` 和 `data/france_academy_source_review_queue_v2/`。这些历史快照没有改写。

**16 个 P2 旧卷仍待复核**：54、55、61、65、72、93、117、120、121、130、136、144、159、160、161、183；未识别标题不能据此判定没有选举。54 个 HTTP404 目录还需另找来源。本批 T83/T112 零解析项已经解决，T27 已记录目录审阅处置。

原页待核事项保持：上一批 T22 Jacobi 类别措辞差异（见 Shard07 final_source_review）；本批 T26 Constant Prévost 学部措辞差异，以及 T178 Sur William Pope 的转录称谓。这些事项没有通过推测自动解决。

下一固定批次为 **Shard09，16 个新卷、零重叠**：147、179、209、28、56、84、115、148、180、29、57、85、116、149、181、30。Shard09 为 16 卷，Shard10 为 12 卷，合计剩余 28 卷。先推进 Shard09；P2 复核、原页核验及缺失目录恢复按独立有界批次继续。

下一批先查看计划（不联网）：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 9 --baseline .\data\france_academy_source_checkpoint_v7\cumulative_source_checked_unique_volumes_v2.csv
```

实际采集命令：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 9 --baseline .\data\france_academy_source_checkpoint_v7\cumulative_source_checked_unique_volumes_v2.csv --run
```

只需回传 `local_runs/france_academy_remaining_172_toc_batches_v1/shard_09/` 中的 summary、source_only_shard_checkpoint 和 person_event_ledger_summary；异常时同时回传 source_run_progress。原始页面、长日志保留在缓存。新 thread 先读本文件及 v7 summary，即可从 Shard09 续接。
