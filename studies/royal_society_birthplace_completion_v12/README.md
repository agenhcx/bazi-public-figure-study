# 英国皇家学会出生地补齐 v12

本批继续核查12条已有出生地但缺明确地域限定的记录，新增1条北半球判定：Sir Henry Capel Lofft Holden。其OUP《Oxford Dictionary of National Biography》原始出版社可读节选，由P W J Bartrip署名，直接把出生地址写为24 Priory Street, Cheltenham, Gloucestershire，并给出与冻结值一致的1856-01-23生日及1856–1937生卒范围。新增的是Gloucestershire地域上下文，不是首次出生地或新增院士；原出生地Cheltenham及原来源等级保持不变。新增支持为S2，与原生日来源等级分开记录。

| 范围 | 固定记录 | 北 | 南 | 未定 |
|---|---:|---:|---:|---:|
| 全表 | 4983 | 4159 | 183 | 641 |
| 原生DOB在1835–1985年内 | 2644 | 2259 | 178 | 207 |

本批其余11条保留未定：9条新来源没有合格地域限定或正文不可读；另2条出现新冲突。Barber的署名原论文直接写Letchworth,Hertfordshire,U.K.，与原皇家学会字段Hatfield不一致；Thompson的Peter Williams署名BMJ原讣告写出生年1913，与冻结1912不一致。保留两种观察，不纠正出生地或生日，也不借另一来源的模糊年份绕过冲突。

直接基线是Git提交`6a34d2d003507c47e8dd27f67b889b70f6fdfad4`的v11对象，canonical JSONL SHA256为`577515b90cff05d61288222a4daf595aaaed76a1baa16ab96391720b02c32da6`。本包包含完整v10载体和冻结v11补充，先精确重建v11，再叠加本批事实。因此无需依赖旧临时目录，也不把Python版本造成的gzip头差异当成对象变化。

4982个完整对象不变；更新对象的原姓名、DOB、历法、身份、资格、QID、原来源等级和既有证据全部不变。新决定及原文定位放在`birthplace_followup_v12`，旧选中证据保留为历史证据。v11的3条已补充记录、全部已有候选及替代地点不变。v11旧hold及v10/v11已查路线另存于audit，避免失去先前冲突和重复检索。

重放命令：

```sh
python studies/royal_society_birthplace_completion_v12/scripts/replay.py
```

输入、代码、CSV和审计保存在Git；完整gzip主表可确定性重放，下载ZIP也直接包含它。输出gzip使用空文件名与零时间戳；基线身份按canonical对象校验。日期窗口用有效公历日期对象计算，仅为描述性窗口，不新增资格裁决。没有改其他队列，没有赋国家、唯一地点或个人出生点坐标，没有跨队列统计去重、八字、表现分析或最终冻结。

只分发短引文、定位和真实请求账本，不分发论文全文、整页图片或网页正文。解析文本不冒充原始HTTP字节；未知时间和HTTP状态保持未知。可读出版社节选不称整篇已读，错误页和付费预览不当作人物不存在。
