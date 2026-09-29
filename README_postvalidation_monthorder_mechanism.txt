Post-validation month-order mechanism analysis
=============================================

Status
------
EXPLORATORY ONLY. 1986–1992 outcomes have already been inspected.

Questions
---------
1) Does the month-order 比肩 signal come from:
   - non-Earth Jianlu-equivalent cases,
   - Earth mixed-qi cases,
   - or classical Jianlu when 戊巳 / 己午 are included?

2) Is month-order 劫财 a useful proxy for Yangren?
   No. This script tests strict Yangren separately because 戊午 is Yangren
   but is NOT month-order 劫财 under the main-qi Ten-God definition.

3) Does month-order 伤官 come mainly from Fire Day Masters?
   Fire Day Masters have two Earth-branch opportunities each:
   丙: 丑/未 (己 = 伤官)
   丁: 辰/戌 (戊 = 伤官)
   while non-Fire Day Masters generally have one month-branch opportunity.

Models
------
M0 = feature + year + Gregorian month + weekday
M1 = M0 + Day Stem
M2 = M1 + Month Branch

M2 is the most useful mechanism sensitivity because it asks whether
the feature remains beyond the marginal Day-Stem and Month-Branch mix.

Run
---
python postvalidation_monthorder_mechanism_1986_1992.py

Main outputs
------------
postvalidation_monthorder_mechanism_1986_1992\MECHANISM_SUMMARY.txt
postvalidation_monthorder_mechanism_1986_1992\mechanism_models.csv
postvalidation_monthorder_mechanism_1986_1992\exact_daystem_monthbranch_combo_descriptives.csv
