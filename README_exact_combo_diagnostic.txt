Exact-combination diagnostic — Music × BaZi
===========================================

Exploratory only: 1986–1992 outcomes are already revealed.

Target family A
---------------
戊辰 / 戊戌 / 己丑 / 己未

Target family B
---------------
甲午 / 乙巳 / 戊酉 / 己申 / 庚子 / 辛亥 / 壬卯 / 癸寅

Run
---
python postvalidation_exact_combo_diagnostic_1986_1992.py

Main output
-----------
postvalidation_exact_combo_diagnostic_1986_1992\EXACT_COMBO_DIAGNOSTIC_SUMMARY.txt

Other outputs
-------------
exact_combo_models.csv
exact_combo_direction_summary.csv
exact_combo_daily_analysis_table.csv
exact_combo_forest_M2_pooled.png

Key model
---------
M2:
Music/non-Music ~ exact combo
                  + Gregorian year
                  + Gregorian month
                  + weekday
                  + Day Stem
                  + Month Branch

This treats the exact Day-Stem × Month-Branch match as an interaction-like
feature beyond its marginal Day-Stem and Month-Branch composition.
