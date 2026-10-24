# Shangguan and observed peak Elo

Exploratory description fixed before inspecting these associations. Earlier snapshot results were seen. Cohorts are analyzed separately; this is not a new blind preregistration or a causal result.

Peak means the highest audited published standard rating recorded through December 2023. Age is measured at the common 2024-01-01 boundary. No predictive model was trained.

Primary: month-branch main qi is Shangguan (0/1). Secondary: Shangguan count in the five effective positions (year stem, year-branch main qi, month stem, month-branch main qi, day-branch main qi). No hidden-stem or position weights are tuned.

| Cohort | Definition | N | Pearson r (95% interval) | Raw Elo/unit (95% HC3 interval) | Age-adjusted Elo/unit (95% HC3 interval) | Partial r |
|---|---|---:|---|---|---|---|
| development | month_main_shangguan | 1000 | -0.000 [-0.062, 0.062] | -0.00 [-14.73, 14.72] | -2.61 [-17.53, 12.30] | -0.012 |
| development | five_position_shangguan_count | 1000 | -0.008 [-0.070, 0.054] | -0.81 [-7.16, 5.55] | -1.84 [-8.08, 4.41] | -0.018 |
| primary_new | month_main_shangguan | 500 | 0.016 [-0.072, 0.104] | 4.36 [-20.55, 29.27] | -8.25 [-31.78, 15.27] | -0.033 |
| primary_new | five_position_shangguan_count | 500 | 0.019 [-0.069, 0.106] | 2.37 [-8.46, 13.20] | -0.09 [-10.57, 10.38] | -0.001 |

## Group descriptions

| Cohort | Definition | Level | N | Mean peak Elo | Median peak Elo |
|---|---|---:|---:|---:|---:|
| development | month_main_shangguan | 0 | 883 | 2597.31 | 2586.00 |
| development | month_main_shangguan | 1 | 117 | 2597.31 | 2582.00 |
| development | five_position_shangguan_count | 0 | 579 | 2597.27 | 2588.00 |
| development | five_position_shangguan_count | 1 | 328 | 2598.59 | 2582.00 |
| development | five_position_shangguan_count | 2 | 81 | 2592.62 | 2573.00 |
| development | five_position_shangguan_count | 3 | 12 | 2596.00 | 2600.50 |
| primary_new | month_main_shangguan | 0 | 449 | 2512.37 | 2509.00 |
| primary_new | month_main_shangguan | 1 | 51 | 2516.73 | 2523.00 |
| primary_new | five_position_shangguan_count | 0 | 303 | 2512.09 | 2508.00 |
| primary_new | five_position_shangguan_count | 1 | 161 | 2512.94 | 2510.00 |
| primary_new | five_position_shangguan_count | 2 | 31 | 2516.23 | 2513.00 |
| primary_new | five_position_shangguan_count | 3 | 5 | 2531.60 | 2555.00 |

Secondary count Spearman correlations: development -0.015; primary_new 0.035.

The adjusted description includes centered age and age squared. All people are retained. Unavailable estimates are explicitly marked in summary.json and effects.csv.

Intervals are descriptive and unadjusted for multiple estimates. A positive point estimate with an interval including zero is uncertain. Selection into elite chess, birth-calendar structure, omitted factors and unfinished careers limit interpretation; age adjustment does not resolve all of them. The two definitions are related. No confirmatory p-values, causal claims, age exclusions or model-selection decisions are made here.

Input manifest SHA256: `dd6340368dc0226264fe7d2875aaa7f2a43c4bf9becb8fca62fef19aff3de782`.
