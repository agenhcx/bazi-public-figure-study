# 法国科学院采集：当前交接检查点

更新：2026-10-20 UTC。本轮完成 Shard10，从 PR106 合并的 199 卷 / 675 条目录事件继续，211 卷目录端点的首次访问已经收尾。下一阶段：P2 旧卷来源复核。当前仍为历史会籍来源整理，正式入组、生日核定及八字分析尚未启动。

## 当前进度

| 指标 | 本轮开始 | 本轮结束 |
| --- | ---: | ---: |
| 已访问的唯一目录卷 | 199 | **211 / 211** |
| 可读取目录的卷 | 139 | **149** |
| 目录端点 HTTP404 的卷 | 60 | **62** |
| 目录事件候选 | 675 | **738** |
| 尚未访问的目录端点 | 12 | **0** |

权威机器检查点为 `data/france_academy_source_checkpoint_v9/summary.json`，同目录保存累计卷表、剩余队列和本批新增事件。CSV 沿用 v2 字段定义及文件名，文件夹 v9 表示新一轮不可变检查点。v8 的 199 行全部逐字段保持相同，本轮没有修订历史基线。`remaining_source_queue_v2.csv` 仅剩表头。

**738 是目录事件数**，包含不同会籍类别、角色待核记录及少量院内职务；独立人物数和正式入组人数仍须后续核定。HTTP404 表示该目录端点缺失，事件数保持未知。研究出生年范围保持 1835–1985，历史卷册来源范围 1835–1940。成员接受、生日接受及八字计算标记均为 0；CTHS 562 人来源和其中 529 个日级生日来源声明保持原状态。

## Shard10：最后 12 个新卷，63 条候选事件

冻结顺序：58、86、118、150、31、59、87、119、151、60、88、90。与基线无重叠，采集前这 12 卷均无本地来源缓存。首次访问为 HTTP200 10 卷、HTTP404 2 卷（31、150）。

结果目录：`data/france_academy_remaining_172_toc_batch_v1/shard_10/`。初始解析 54 条，来源审阅和 v1_15 修复后为 **63 条**：新增九条，修复三条既有记录的五个字段，其余 51 条逐字段不变，没有删除事件。首抓台账、初始状态及每卷 SHA 均保留；新旧解析使用相同来源字节。

| 卷 / 年 | 初始 → 最终事件数 | 审阅处置 |
| --- | ---: | --- |
| T59 / 1864 | 0 → 1 | 补 de La Rive 外籍条目 p68；会员任命标题省略 et de Correspondants，仍明确属于学院成员栏目 |
| T60 / 1865 | 1 → 9 | 补 Foucault p154 及七条共用任命标题的通讯条目；保留同次选举上下文及标题动作标记 |
| T58 / 1864 | 5 → 5 | Parade 的相邻续文补出 Économie rurale 和 p193，修复学部及两个页码字段 |
| T151 / 1910 | 6 → 6 | L. Teisserenc de Bort p847 改为自由院士；Francotte p912 的学部止于 Anatomie et Zoologie，移除误吞的替补短语 |

T60 的 Foucault 胜出条目承接紧邻的同次力学学部选举，保留 `FULL_SECTION_MEMBER_CONTEXTUAL_ELECTION` 与 `EST_PROCLAME_ELU_TRANSCRIBED`；p101 的同票未终局行不增加事件。七条通讯任命为 de Vergnette-Lamotte p397、Braun p545、Weber p660、Hofmeister p762、O. Struve p1012、Plantamour p1067、Clausius p1126，统一保留 `SONT_NOMMES_HEADER_TRANSCRIBED`；最后一人虽无破折号，仍在同表连续名单中，随后的字母 O 结束该组。

其余可读卷最终事件数为 T86=6、T87=5、T88=18、T90=4、T118=8、T119=1。全部 10 份可读目录均已审阅，T88 的 table 与 tableItem 混合结构也已覆盖。独立职务、外部委员会、候选准备及无效选举条目按既有边界处理。

本批角色为 通讯 39、分科正式成员 14、外籍 4、同次选举上下文支持的分科成员 1、自由院士 5。严格姓名匹配到既有 CTHS 候选池 1 条，仍不据此入组。本轮未打开原印刷事件页，未推断独立法令签署日期。

`final_source_review_v1.json` 保存九条新增、三条既有事件的字段变化、51 条原记录不变及逐卷审阅处置。累计为 **675 + 63 = 738**。

## 保存的证据与验证

解析器版本：`france-academy-legacy-heading-wikisource-source-only-v1_15`。本次修改覆盖省略通讯类别的会员标题、明确的同次选举续行、标题统领名单、跨表续文、自由院士角色及替补短语边界。恢复的角色和学部均保留其实际来源依据，不把上下文支持改写成逐行明确陈述。来源 SHA、403/429 停止、HTTP404 未知状态、去重续跑及研究门控规则保持。

源包：`data/france_academy_shard10_source_snapshot_v1/source_cache_v1.tar.gz`，14 个来源文件、471836 字节，包括 10 份目录 HTML、2 份真实 HTTP404 状态及目录类别和官方卷册入口，不含原书扫描图片。SHA-256：`c2c6e6e568acbd839bc9378162719837968e016d7ac37d883302f5caa2915c36`。

Python 3.10 / 3.13 工作流包含语法 fixtures、16 项续跑/P1完整性回归、旧九批 14 + 61 + 70 + 23 + 60 + 58 + 61 + 51 + 53 = 451 条来源台账逐字段兼容、Shard10 离线台账比对，以及新累计四文件逐字节重建比对。本地 v9 从独立目录恢复的源包重新生成。

Python >=3.10，依赖 beautifulsoup4==4.12.3。以下命令在仓库根目录执行，每条一行。独立离线复现本批检查点：

```powershell
python .\scripts\france_academy_source_cache_bundle_v1.py --restore .\data\france_academy_shard10_source_snapshot_v1\source_cache_v1.tar.gz
```

```powershell
python .\scripts\france_academy_update_source_checkpoint_v2.py --baseline .\data\france_academy_source_checkpoint_v8\cumulative_source_checked_unique_volumes_v2.csv --shard-dir .\data\france_academy_remaining_172_toc_batch_v1\shard_10 --out .\local_runs\france_academy_shard10_checkpoint_verify
```

## 下一阶段：P2 旧卷来源复核

211 卷首次访问完成，固定分片到 Shard10 结束，**没有 Shard11**。后续工作从 v9 基线开展旧卷修订；不要重新运行 Shard10 作为新批次。

P2 固定队列：`data/france_academy_source_review_queue_v2/pending_p2_source_review_queue_v2.csv`，16 卷为 **54、55、61、65、72、93、117、120、121、130、136、144、159、160、161、183**。队列 SHA-256：`6bb32085c70271c4884d9d693ab2aebeae3d5eaf7a84f0dab01f65cbd867f300`。其状态仍为 `UNRESOLVED_NOT_CONFIRMED_OMISSION`；尚未确认每卷是否存在真实漏项。

本轮交接检查时，这 16 卷在当前本地来源缓存中均没有 HTML 或对应状态文件；已保存的八个源归档也均未包含它们。这是来源字节缺失，尚无法进行历史 SHA 比对，不能声称可直接全离线复核。下一轮应先寻找与队列历史 SHA 一致的旧来源；如无法取得，须受控重新抓取、冻结新来源并记录新旧 SHA 对照，再开展离线审阅。P2 属于已访问卷的修订，不增加已访问唯一卷数。

下一轮先读取本文件、v9 summary 及固定 P2 队列，冻结有界复核范围和原始 SHA 证据，建立可验证的旧卷修订台账。若需重新取得来源，分别保留历史与新抓 SHA 及差异，不能宣称来源字节未变化。逐卷核实标题、事件和边界后，再以明确修订量生成后续累计检查点；目前没有已完成的 P2 专用采集命令可直接照搬。`france_academy_wikisource_legacy_election_headings_v1.py` 的历史五卷试点 CLI 不可冒充 P2 批次入口。

P1 五卷（3、35、94、124、125）恢复的 23 条、新旧源码 SHA 差异及处置记录，保存于 `data/france_academy_legacy_p1_review_v1/` 和来源复核队列目录。`data/france_academy_source_review_queue_v2/summary.json` 是历史 v4 快照；当前总量以 v9 为准，不改写历史队列摘要。

另有 **62 个 HTTP404 目录**需要寻找替代来源。原页待核事项保持：T22 Jacobi 类别措辞差异（见 Shard07 final_source_review）；T26 Constant Prévost 学部措辞差异和 T178 Sur William Pope 的转录称谓（见 Shard08）；T85 Godron p24 的 Correspoudant 角色措辞（见 Shard09）。这些问题仍待原页核验。

新 thread 只需先读本文件及 v9 summary，即可接续 P2。原始 HTML 和长日志留在来源快照与缓存，不要整段放入对话。目录首次访问完成后，旧卷复核、缺失来源恢复、原页核验及个人会籍/生日确认仍需继续。
