# Remaining non-China institution reveal: Germany, France, Japan

The user authorizes the remaining institutions except China, with separate institution-level results. Only DE_Leopoldina, France and Japan are opened in this execution. CAS, Nobel-specific groups, and any pooled all-academy trait analysis remain unopened; original global18 are not run. UK and NAS data/results are not changed. The original36-country diagnostic family, encodings and seeds remain fixed.

## Population and methods

Use frozen V4 North-born members, DOB1835–1985 and qualified admissions by2025, excluding full-official-roster Nobel overlap. Main strictS1+S2 N: Germany564, France469, Japan211. ExpandedS1+S2+S3 has the same people and analysisDOB in each institution, so the main table/decade results are calculated once and explicitly reused. Inclusive member counts are metadata only; do not publish subtractable inclusive trait tables. Fields members stay in the main sample under original rules, with predetermined exclusion sensitivity. Cross-institution identities remain qualified; do not sum institution sample sizes as independent unique people or perform new country-comparison tests.

All prior calendar/feature rules stay fixed: lunar-python1.4.8/sect2 noon cache, Gregorian analysisDOB, five positions YG/MG/YB/MB/DB representative stems, DayStem reference only, no hour. M0 main qi and M1 exposed-in-YG/MG priority representative (else main qi) each sum5 units/person. Null draws whole calendar dates conditional on each observed Gregorian birthyear. Do not assume all TenGods10% or all elements20% or treat5N slots as independent people. No birthdate/cutoff/source changes.

## Three result families per institution

1. Original6 diagnostics retain Bonferroni36 over all6 institutions: PI_count,SG_count,GY_narrow,SGY_narrow,water_DM upper-tail, DM_index Pearson upper-tail. Country indices DE2/France3/Japan4 give seeds2026111500..05/1600..05/1700..05. R99999, bootstrap10000, original7cases (primary +6sensitivities), same M0/narrow criteria; no replacement by favorable sensitivity. Statistical functions remain AST-identical to327cc legacy engine, reading equivalent observations by exactDOB index in the pinned calendar cache.
2. Supplementary complete levels:40 tests (10 DayMasters,20 M0/M1 TenGods,10 M0/M1 elements), exact finite independent-person sum distributions via float64 convolution and rational exact centered inclusive tail cutoffs, two-sided. Each institution has Holm40. YearStem/MonthStem tables are descriptive only.
3. Supplementary birth-decade linear trends:30 tests (10 DayMasters +20 TenGods), same person-weighted integer-decade OLS/calendar-excess test as NAS/UK, R99999 PCG64, LCM365*366 exact inclusive integer contrasts, no squared int64 contrasts. Seed=202611180000+countryindex*10000+sourceindex*1000+endpointindex (source0strict1expanded). Each institution has Holm30; expanded is sensitivity if distinct, exact reuse if identical.

As all3 institutions are opened together, retain the per-institution supplements for comparability and additionally report fixed-batch Holm120 over the existing120 strict level p-values and Holm90 over existing90 strict trend p-values. These are additional p adjustments, not extra tests or pooled trait comparisons. No result-selected family resizing or endpoint directions. Original36 stays36 although China remains unopened; original18 remain untouched.

## Decades and displays

All16 bins floor(year/10)*10=1830..1980 are retained with N,count,observedshare,calendarEshare,excesspp for all40 endpoints. Empty bins have0 counts and undefined shares. First1830bin means1835–1839 within frozen window. No per-bin significance tests; colors describe excess only. Five-element decade cells are descriptive, without added linear tests.

Display and common-window descriptive slopes use all decades withN>=20 in both source groups, selected from metadata before any trait summary. DE1840–1969 (13bins), France1840–1959 (12bins), Japan1880–1929 (5bins). Full primary trends retain small bins; common-window slopes have no new tests. M0/M1 God heatmaps share a scale and corresponding element panels share a scale, including both sources when needed. No p-selected categories/decades/figures.

## Freeze, QA, output

Scope, all statistical/audit/plot/batch scripts and dependencies, metadata and synthetic QA are remotely committed and verified before any new institution outcome. Each invocation is hard-whitelisted againstCAS and other groups. Separate independent audits reproduce literal calendar encodings, selected populations/IDs, all40 levels/16decades/30slopes, Holm adjustments, preselected exactlevel p and independentMC trend checks, original6diagnostics plus7cases, and unchanged legacy function AST. New scripts do not modify old locks.

Deliver one ZIP with3 separate institution directories and reports plus an index; every complete table, all results, p adjustments, figures and QA/receipts are kept. Code lives in Git. No trait pooling, global hypothesis testing, new conditional-component fishing, causal intelligence interpretation or nationality claims. Institution membership is not citizenship or birthplace country.
