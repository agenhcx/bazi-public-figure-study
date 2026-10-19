# 法国科学院采集：当前交接检查点

更新：2026-10-19 UTC。本轮为 Shard04；从 PR100 合并的 104 卷 / 299 条目录事件继续。范围仍为历史会籍来源整理，最终入组、生日核定和八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已实际访问过的唯一目录卷 | 104 | **119 / 211** |
| 可读取目录的卷 | 72 | **83** |
| 目录子页 HTTP404 的卷 | 32 | **36** |
| 目录事件候选 | 299 | **369** |
| 从未访问过的目录端点 | 107 | **92** |

权威机器检查点为 `data/france_academy_source_checkpoint_v3/summary.json`，同目录保存累计卷表、剩余队列和本轮新增事件表。CSV 沿用 v2 字段定义和文件名，文件夹 v3 表示新一轮不可变检查点。

**369 是目录事件数，包含正式会籍类别、通讯、外籍和少量院内职务，不是 369 位独立正式院士。** HTTP404 仅说明该目录端点缺失，事件数仍未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。所有成员接受、生日接受和八字计算标记均为 0；CTHS 562 人来源与其中 529 个日级生日来源声明保持原状态。

## Shard04：15 个新卷 + 1 个已查卷复用

冻结计划包含 16 个条目，其中 Tome42 / 1856 已在此前专题核查中覆盖。本次复用其原有计数和来源 SHA，不发新请求、不重复增加卷数或事件数。其余新卷保持原冻结顺序：41、71、103、133、165、195、14、73、104、134、166、196、15、44、74。

新目录实际首次访问为 HTTP200 11 卷、HTTP404 4 卷（15、71、166、195）。初次解析 51 条；在同一来源字节上修复后为 **70 条，累计 299 + 70 = 369**。初次获取状态和每卷源 SHA 保存在该批 `first_capture_source_review_v1.json`。

| 本批语法修复 | 原解析 | 修复后 | 证据边界 |
| --- | ---: | ---: | --- |
| Tome14 / 1842 | 0 | 9 | 标题使用 `membres ou de correspondants`；会籍/通讯/外籍类别逐条判定 |
| Tome74 / 1872 | 0 | 9 | 保留未渲染 Wiki 表格；其中 de Quatrefages 是副院长职务，排除新会籍 |
| Tome44 / 1857 | 9 | 10 | `Le P. Secchi est nommé Correspondant` p970；不从“同一分科”猜补分科 |

本批70条角色构成为：正式类别候选22（明确分科14、libre 5、上下文任命3），通讯38、外籍9、院内职务1；严格姓名匹配到既有CTHS候选池4条，仍不据此入组。

本批结果目录：`data/france_academy_remaining_172_toc_batch_v1/shard_04/`。这些是原刊目录的 Wikisource 转录候选；本轮未新增原印刷事件页目视核验，也未从目录推断独立法令签署日期。上一轮 Tome37 职务原页核查、历史 14 条修订和 Shard03 的 61 条结果保留在原目录。

## 去重续跑与离线复现

Runner 新增 `--baseline`：校验累计 CSV、配套 summary 的 SHA/数量/来源状态后，计算“冻结批次减已查卷”。批次检查点保留完整冻结顺序、复用卷、baseline SHA 和复用卷的原计数/源 SHA。更新器再次独立推导新卷集合；漏掉未查卷、伪造复用记录、缺失或改动 baseline 均会被拒绝。

每卷保存进度，403/429 立即停止，缺少离线缓存报告未完成，HTTP404 状态可复用且保持事件数未知。源语法、断点续跑和 baseline 验证有针对性回归检查；Python 3.10/3.13 工作流重放来源并比对最终四份检查点文件，同时检查前轮 14 + 61 条事件逐字段保持一致。

本批源缓存包：`data/france_academy_shard04_source_snapshot_v1/source_cache_v1.tar.gz`，17 个文件，551047 字节；包括 11 份目录 HTML、4 份真实 HTTP404 状态，以及目录类别和官方卷册入口。不包含原书扫描图片。SHA-256：`e67e5f9844cc1da7a8a6b4d3bc750235483823dc92fcfe0369a033123496c598`。

Python >=3.10，依赖 beautifulsoup4==4.12.3。以下命令均在仓库根目录执行，每条一行。独立离线复现本轮检查点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard04_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --baseline .\data\france_academy_source_checkpoint_v2\cumulative_source_checked_unique_volumes_v2.csv --shard-dir .\data\france_academy_remaining_172_toc_batch_v1\shard_04 --out .\local_runs\france_academy_shard04_checkpoint_verify
```

## 未解决事项与下一步

历史可读零解析卷共有 **21 个待复核项**，已经保存为 `data/france_academy_source_review_queue_v1/legacy_zero_event_review_queue_v1.csv`；基于本轮开始的 104 卷及同 SHA 原始 inventory，未混入本批已解决事项。

- 优先级 P1：**3、35、94、124、125**，有选举标题但旧解析数为 0。当前只是疑点，尚未确认存在漏人。
- 优先级 P2：16 个未识别选举标题的可读旧卷，包括先前已标记的 Tome160/161。不能据此断言历史上没有选举。
- 36 个 HTTP404 目录的其它来源恢复仍待进行。

下一固定批次是 **Shard05，16 个新卷、零重叠**：105、135、167、197、16、45、75、106、138、170、200、17、46、76、107、139。其后 Shards06–09 各 16 卷，Shard10 为 12 卷；Shards05–10 合计剩余 92 卷，彼此及与已查卷不重叠。优先复核上述 5 个有标题零解析卷，然后继续剩余批次；两类进度分开记账。

本地下一批先查看请求计划（不会联网）：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 5 --baseline .\data\france_academy_source_checkpoint_v3\cumulative_source_checked_unique_volumes_v2.csv
```

实际本地采集命令：

```powershell
python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 5 --baseline .\data\france_academy_source_checkpoint_v3\cumulative_source_checked_unique_volumes_v2.csv --run
```

只需回传 `local_runs/france_academy_remaining_172_toc_batches_v1/shard_05/` 中的 summary、source_only_shard_checkpoint 和 person_event_ledger_summary；异常时同时回传 source_run_progress。原始页面、长日志留在缓存，聊天只保留进度、异常和下一步。
