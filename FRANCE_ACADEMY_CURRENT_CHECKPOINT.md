# 法国科学院采集：当前交接检查点

更新：2026-10-19 UTC。范围为历史会籍来源整理；最终生日核定和八字分析尚未启动。

## 当前结果

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已实际访问过的唯一历史目录卷 | 88 | **104 / 211** |
| 可读取目录的卷 | 63 | **72** |
| 目录子页 HTTP404 的卷 | 25 | **32** |
| 去重到卷/记录的目录事件候选 | 224 | **299** |
| 从未访问过的目录端点 | 123 | **107** |

权威机器检查点：

- `data/france_academy_source_checkpoint_v2/summary.json`
- `data/france_academy_source_checkpoint_v2/cumulative_source_checked_unique_volumes_v2.csv`
- `data/france_academy_source_checkpoint_v2/remaining_source_queue_v2.csv`
- `data/france_academy_source_checkpoint_v2/added_or_reparsed_index_events_v2.csv`

**299 的计数单位是目录事件，包含正式类别、通讯、外籍及少量院内职务。没有据此接受 299 位独立正式院士。** 目录子页 404 只说明该端点缺失，事件数量仍未知。研究出生年窗口保持 1835–1985；历史卷册来源范围为 1835–1940。

本轮正式院士入组、生日接受、八字计算全部为 0。旧 CTHS 562 人来源、已有生日冲突和旧批次输出未改写。CTHS 的 529 个日级生日仍为来源声明，不能改称已独立验证。

## 本轮增量：224 + 14 + 61 = 299

### 修订三个已访问卷：净增 14 条目录事件，不增加卷数

| 卷 | 年 | 旧解析 | 本轮解析 | 事件分类 |
| --- | ---: | ---: | ---: | --- |
| 37 | 1853 | 0 | 1 | Élie de Beaumont 常任秘书职务；明确排除新会籍 |
| 98 | 1884 | 0 | 6 | 正式分科 2、membre libre 3、通讯 1 |
| 128 | 1899 | 0 | 7 | 正式分科 2、通讯 5 |

修复了 `Nominations de membres et correspondants` 的标题变体、`Membre libre` 分类和 `Le R. P. Colin` 称谓。实际新 HTML 字节上，旧解析器为 0/0/0，修复后为 1/6/7。整页新 HTML SHA 与前一天的抓取不同；旧快照和旧结果保留，新来源 SHA、旧来源 SHA、修订原因分开记录，未声称恢复了前一天完全相同的网页字节。

Tome37 原印刷 p938、p965 两页已目视核验：属于秘书职务选举及批准，不是新院士入选。p938 只含首轮投票，不能称为最终票数；p965 是 1853-12-26 会议，记述敕令日期为 1853-12-21。单独签署的敕令原件未打开。两页定位、图像 SHA 与审查在 `data/france_academy_shard02_grammar_review_v2/original_tome37_office_pages/`。

### 固定 Shard03：新增 16 个不重叠卷、61 条目录事件

原冻结顺序：191、11、39、69、100、131、162、192、12、40、70、102、132、163、193、13。9 个目录返回 HTTP200、7 个目录子页返回 HTTP404；实际初次获取状态保存在该批 `first_capture_*` 文件中。之后全部使用缓存重放。

本批最终角色：正式分科 11、membre libre 1、非驻地正式类别 1、通讯 47、外籍 1。即正式类别候选 13，仍没有最终入组；严格姓名匹配到 CTHS 部分候选池的事件为 7 条。

初次解析为 44 条；进一步发现两处真实漏读，在同一源字节上补回 17 条：

- Tome40 / 1855：裸 `Nominations` 标题下明确会籍条目，恢复 7 条。外部机构候选推荐继续排除。
- Tome131 / 1900：恢复 10 条，含 Zambacco 的跨表格条目。只有姓名、明确通讯会籍/分科、页码三个邻接片段齐全时才拼接，缺片段时不补造。

批次结果：`data/france_academy_remaining_172_toc_batch_v1/shard_03/`。目录条目仍需在后续完整名册整理时去重、核对身份/会籍，不从目录推断原始签署法令日期。

## 可复现与断点续跑

本轮保存 21 个源缓存文件，合计压缩约 558 KB，包括 12 份目录 HTML、类别/官方卷册入口，以及 7 份有 URL 和时间的 HTTP404 状态。原书扫描图片未打包进入仓库。公共来源快照保留其原有来源和版权声明。

源缓存包：`data/france_academy_shard03_source_snapshot_v1/source_cache_v1.tar.gz`。

SHA-256：`972b54f75680555bff8a792d9723e1f72a330350805b7d95742678a0584ea79c`。

Python >=3.10，使用既有依赖 beautifulsoup4==4.12.3。以下命令均为单行，在仓库根目录执行；用于独立离线复现，无需重新访问来源站点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard03_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --revision-dir .\data\france_academy_shard02_grammar_review_v2 --out .\local_runs\france_academy_checkpoint_verify_v2
```

更新器验证每份新/修订的成功来源 SHA、当前解析结果与已存逐人事件表逐字段一致，然后才输出累计表。旧输出不会被覆盖为不同内容。新累积表使用准确字段名 `source_html_sha256`，保留旧累计表中误命名的 `source_image_sha256` 所代表的 HTML 哈希。

采集程序现在逐卷原子保存进度；403/429 会立即停止后续请求；离线缺缓存会报未完成；404 状态可在线/离线复用，事件字段保持未知。回归验证覆盖停止后无第二次目录请求、成功缓存恢复、缺缓存不充完成数、404 离线重放。另以 Python 3.10/3.13 做完整离线源重放和确定性检查点比对。

## 下一步：Shard04，注意一个既有卷

**不要回到 56 卷或 88 卷检查点重新抓取。** 1856 Hermite 原页核验及 Shard01/02 已在此前 PR98/99 完成；本轮以 PR99 合并后的 88 卷为起点。

冻结的 Shard04 有 16 个条目，但 **Tome42 / 1856 已被前序人工专题检查覆盖**。下一轮应复用其已有记录，按 `remaining_source_queue_v2.csv` 只访问 15 个新端点；原始 172 卷计划不改写。剩余新卷按原顺序为：41、71、103、133、165、195、14、73、104、134、166、196、15、44、74。当前通用更新器会拒绝把重叠卷当成新增，这是有意保留的检查。

旧 Shard02 的 Tome160、161 / 1915 两个可读目录仍保留“未检测到选举标题”的人工检查状态，不能据此推断历史上没有选举。32 个目录端点 404 的其它来源恢复也尚未完成。稳定的大批量抓取沿用本地运行安排；聊天中只需回传 summary 和异常队列。
