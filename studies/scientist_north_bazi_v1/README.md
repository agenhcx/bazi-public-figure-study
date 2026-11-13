科学家北半球日期三柱排盘 V1

先锁定 ASSUMPTIONS_LOCK_V1.json、PROTOCOL_V1.md、输入指纹和转换代码，核实远程 Git 提交之后才运行 build_charts.py。
当前阶段只排盘，不执行假设检验。四组假设主族共18项，规则见方案。

复现依赖：requirements-calendar.txt。源输入：已固定 SHA256 的 scientist_north_data_freeze_v4.zip。
完整源归档与假设草案的持续文件标识在 JSON 输入指纹中。

运行命令：
PYTHONPATH=<依赖安装目录> python3 scripts/build_charts.py --input-zip <V4.zip> --lock-receipt <LOCK_RECEIPT.json> --output <新输出目录>

只有日期，时柱未知。12点是固定计算参照，不是出生时刻估计。
输出CSV为UTF-8 BOM，可用Excel打开；JSONL保留完整来源与标签。
