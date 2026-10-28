# 英国／日本院士数据：后台核验任务（2026-10-28）

这批任务只复核现有采集结果，不新增广泛检索，不改变已冻结输入，不计算或检查八字变量及后续结果。

## 当前边界

- **英国已冻结**：Royal Society primary Fellows 共 **8,669** 人（past **7,099**、current **1,570**）；exact DOB **4,983**（past **4,884**、current **99**）；unresolved **3,686**。以 `data/royal_society_dob_freeze_v1.json` 与 `ROYAL_SOCIETY_DOB_CLOSEOUT_V1.md` 为准，继续遵守停止广泛 DOB 采集的规则。
- **日本尚未完成全名册／DOB 冻结**：本次只核验既有 **239 个战后 section 歧义个案**，不能将 239 写成日本学士院全体名册人数。
- 日本已接受层为：**199** 人仅支持 broad Section II，不支持 subsection 4–7；**Hiratsuka Naohide** 为 Section II／6；**Yoshikawa Itsuji、Nanbara Shigeru、Doi Kōchi** 为 Section I。其余 **36** 人仍 unresolved。最新 Git closeout 的 36 取代旧 Library 材料中的 39，不得把 membership-only 的 Ōta Hirotarō 当成 section 已解决。

## 三个独立任务

工作流：`.github/workflows/academy_uk_japan_followup_v1.yml`。只在推送分支 `codex/academy-uk-japan-jobs-20261028` 时自动触发，另保留 `workflow_dispatch`；不设置 pull-request 触发，避免同一次提交重复执行。三项任务互不依赖，每项最多 10 分钟，仓库权限仅 `contents: read`，不使用 secrets。

| 任务 | 核验内容 | 输出目录 | GitHub artifact |
| --- | --- | --- | --- |
| UK frozen DOB replay | 在临时目录重建全部 5 份输出；逐一匹配 frozen manifest 的 SHA256；另与 4 份已跟踪 CSV 作语义比较；独立重新计数并确认原输入未变 | `local_runs/academy_followup_20261028/uk/` | `academy-uk-frozen-dob-replay-v1` |
| Japan 239-case integration | 校验 239 人的唯一身份键、199 个 broad-II 接受层、4 个直接证据接受层、36 个 unresolved 及标签边界 | `local_runs/academy_followup_20261028/japan_integration/` | `academy-japan-239-layer-integration-v1` |
| Japan four-case replay | 仅恢复四个已批准旧来源的精确字节，在临时目录核对原 SHA256 并重放四个已接受的显式 section 裁定；不扩展检索或接受新个案 | `local_runs/academy_followup_20261028/japan_replay/` | `academy-japan-four-accepted-section-replays-v1` |

每项输出含 `summary.json`、`summary.md`；失败时保留 `failure_summary.json` 和可用诊断。工作流在失败后仍尝试发布 GitHub step summary 和上传 artifact，提早失败而没有有效计数时明确显示 counts unavailable，不把预期计数冒充实际结果。artifact 保留 14 天；实际 counts 与通过／失败状态以该次运行的 summary 为准。

公开输入包 `data/academy_jobs_japan_inputs_v1/` 保留原 queue、inventory、已接受裁定表和最小事实／hash 清单，不包含原始 PDF、完整 HTML 或全文副本。GitHub replay 使用 `--rehydrate-approved-sources`：四个 inventory 指定的旧公开 HTTPS URL 各最多一次 GET，单次 timeout 20 秒、上限 8 MiB、请求间隔至少 1 秒；不跟随重定向、不重试、不搜索替代来源。不可访问、429 或字节 hash 改变均记为 `blocked_source` 并失败，不把 integration 中的既有结论冒充新的来源重放。原始文件只存在临时目录，上传内容仅为计数、hash、裁定结果及必要诊断，不上传原始来源或全文。

## 本地运行与已验证结果

在仓库根目录运行。Python 脚本不需要第三方 Python 包；UK 和 Japan integration 为离线核验。Japan replay 还需 Poppler 的 `pdftotext` 验证两份原 PDF 的显式措辞，工作流仅在缺少该程序时安装 `poppler-utils`：

```bash
python scripts/academy_jobs_uk_replay_v1.py --output-dir local_runs/academy_followup_20261028/uk
python scripts/academy_jobs_japan_integration_v1.py --output-dir local_runs/academy_followup_20261028/japan_integration
python scripts/academy_jobs_japan_replay_v1.py --rehydrate-approved-sources --output-dir local_runs/academy_followup_20261028/japan_replay
python scripts/test_academy_jobs_uk_replay_v1.py
```

英国本地重建已通过：实际 **8,669／4,983／3,686**，past/current 与 exact 分层计数均符合冻结值，5 个 SHA256 及 4 个 CSV 语义比较全部相同。3 项隔离测试通过，覆盖 CSV 序列化差异、故意破坏 manifest hash、故意改变已跟踪表格单元格；后两项均返回失败并生成失败诊断，原始冻结文件未改动。

日本 integration 本地通过：实际 **239 = 199 broad-II-only + 4 direct + 36 unresolved**，该项没有执行来源重放。使用准备阶段可用的原始私有归档快照，四个原裁定器重放 **4/4** 通过（II／6 为 **1**，Section I 为 **3**），两份 PDF 的原始 magic／hash／显式措辞检查通过，GET **0**，原始来源输出文件 **0**。公开包缺少 raw 时的默认离线重放已确认会失败，而不会降级使用事实摘要。此项本地归档通过不能保证公开 URL 仍提供完全相同字节。

工作流结构及三个任务的“脚本尚未生成 summary 即失败”分支已在本地检查通过。GitHub 是否已排队及远端最终结果应通过对应 run／artifact 核实；本文件不把本地通过写成远端已成功。

## 仍需通过的门槛

日本剩余 36 人只有出现可审计、明确支持 section 的来源后才能按现有标准另行版本化处理；大学、学位、研究领域或仅有会员身份均不能补成较窄 section／subsection。全名册对账和 DOB 冻结仍是独立未完成工作。这三项核验通过也不代表所有 primary cohorts 已冻结；继续维持解盲前门槛，八字变量计算与后续分析仍为 **0**。
