# 科学家出生地补全 v7：官方批量资料与NAS第79、80卷

本轮更新 **29个NAS名录键**，保留 **30条来源观察（S1 26、S2 4）**，新增29个半球判定；NAS未定543→514。Hershey的S1主来源与S2传记支持都保留，同一NAS记录只更新一次；没有跨队列统计去重。

| 人物 | 主来源原文地点 | 主来源等级／附支持 | 地理结论 |
|---|---|---|---|
| Alfred D. Hershey | Owosso, MI, USA | S1；另S2 | 北 |
| André Cournand | Paris, France | S1 | 北 |
| Barbara McClintock | Hartford, CT, USA | S1 | 北 |
| Brian K. Kobilka | Little Falls, MN, USA | S1 | 北 |
| Bruce Merrifield | Fort Worth, TX, USA | S1 | 北 |
| D. Carleton Gajdusek | Yonkers, NY, USA | S1 | 北 |
| D. Stanley Tarbell | Hancock, New Hampshire, on a farm that had been in the family since the settlement of the village | S2 | 北 |
| E. A. Doisy | Hume, IL, USA | S1 | 北 |
| Frederick C. Robbins | Auburn, AL, USA | S1 | 北 |
| G. W. Beadle | Wahoo, NE, USA | S1 | 北 |
| George D. Snell | Bradford, MA, USA | S1 | 北 |
| George E. Palade | Iasi, Romania | S1 | 北 |
| Gerald Clemence | near Greenville, Rhode Island | S2 | 北 |
| Gregg L. Semenza | New York, NY, USA | S1 | 北 |
| H. A. Bethe | Strasbourg, Germany (now France) | S1 | 北 |
| H. Gobind Khorana | Raipur, India | S1 | 北 |
| Hans G. Dehmelt | Görlitz, Prussia (now Germany) | S1 | 北 |
| Herbert C. Brown | London, United Kingdom | S1 | 北 |
| Hermann Muller | New York, NY, USA | S1 | 北 |
| Jack W. Szostak | London, United Kingdom | S1 | 北 |
| James Franck | Hamburg, Germany | S1 | 北 |
| John H. Northrop | Yonkers, NY, USA | S1 | 北 |
| Kenneth G. Wilson | Waltham, MA, USA | S1 | 北 |
| L. James Rainwater | Council, ID, USA | S1 | 北 |
| Oliver R. Wulf | Norwich, Connecticut | S2 | 北 |
| P. Kusch | Blankenburg, Germany | S1 | 北 |
| Robert C. Richardson | Washington, D.C., USA | S1 | 北 |
| S. Chandrasekhar | Lahore, India (now Pakistan) | S1 | 北 |
| Val L. Fitch | Merriman, NE, USA | S1 | 北 |

出生地来源等级、地理等级与原DOB分组分别保存；本轮S1不升级任何原DOB等级。保留农场、near及历史地名限定，不以国籍、父母、求学、工作或死亡地替代出生地。

## 实际来源范围

- 物理API：离线复用230个已冻结官方对象，得9条S1；本轮0查询、0HTTP。Igor Tamm（1922／1895）、J. Herbert Taylor（1916／Joseph H. Taylor Jr. 1941）是两组不同人物，API只给Taylor的H.，不能据此展开为原生Herbert；排除不等于原生日有误。
- 化学／医学生理API：各重取已知引用地址一次，均原始HTTP200；200＋235个对象得17条S1，0搜索、0重试。Merrifield用官方preferred name、完整有序姓名及原生日期唯一对应，没有臆造姓名。
- 第79卷：20个实际目录人物，3篇正文200，3条S2、0 hold；第80卷：20个人物，2篇HTML＋1张已观察页图200，1条S2及Wilson一条hold。各1次发现查询、1次目录、0重试。署名编辑传记为S2。

每条路线筛543条未定，身份唯一性检查覆盖2,242条NAS记录；目录覆盖不等于543人均读正文。Wilson原图也印1915，出生句及原生日期为1914，保留冲突，不采用地点或更改日期。Chandrasekhar本轮独立API证据不裁定旧传记的日期分歧。

## 地理与固定口径

本轮29条结果为29北、0南、0未定。明确区域和官方`cityNow`参考坐标分别审核；参考点不等于本人出生点，不新增国家、出生点、唯一地点实体或人员QID。本轮未发起新地理查询。Cournand的Paris, France使用原始API所附同名cityNow参考点，未将France整体判北；原来源没有提供precision、rank或globe字段，这些字段保持未提供。审核及响应SHA见`audit/geography/`。

| 队列 | 固定记录 | 北 | 南 | 未定 |
|---|---:|---:|---:|---:|
| CAS | 1230 | 1003 | 3 | 224 |
| DE_Leopoldina | 778 | 655 | 6 | 117 |
| Fields_main | 63 | 59 | 4 | 0 |
| France | 775 | 702 | 3 | 70 |
| Japan | 368 | 234 | 0 | 134 |
| NAS | 2242 | 1696 | 32 | 514 |
| Nobel_science | 655 | 634 | 21 | 0 |
| UK_Royal_Society | 4983 | 4155 | 183 | 645 |

全表仍为11,094条名录内记录，键为`(cohort, record_id)`。NAS原生1835–1985描述窗2,240条：1694北、32南、514未定。原生日、历法、资格、DOB分组、QID及38条既有完整补充记录／39个旧证据对象保持不变；其余11,065条完整对象不变。其他七队列逐行相同，英国4,983条完整对象保留。Nobel655条仍是重建ID范围，原生DOB全空，旧最终DOB未恢复；CAS公历接受字段仍空、未裁定；Fields63条主表与2026扩展分开。没有八字、结果变量或最终样本冻结。

## 审计与复现

直接基线v6 SHA256：`8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356`。七个输出保存完整表、变更、未定行和计数；冻结输入保留全部来源观察及Hershey额外支持。`audit/`含身份、hold、账本、原始SHA及独立复核；传记仅分发短引文，不分发全文或整页图片。本轮化学／医学原始API JSON和安全元数据随包保留；物理缓存原件固定在v5审计中，SHA及原路径另记。实际分发文件以`MANIFEST.sha256`为准。

采集脚本是依赖当时路径／缓存的过程快照；主重放依赖固定v6及本轮输入：

```sh
python studies/scientist_birthplace_completion_v7/scripts/assemble.py
python studies/scientist_birthplace_completion_v7/scripts/verify.py
```

验证涵盖全量键、原生字段、旧证据、CSV、计数和七个输出逐字节重放。旧版本不变。
