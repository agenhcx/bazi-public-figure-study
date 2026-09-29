Music Day-Master distribution bundle
====================================

Purpose
-------
Replicate the table-tennis-style Day-Master distribution analysis for Music.

This version means:
1) 日主数量 = counts of 甲乙丙丁戊己庚辛壬癸
2) 五行数量 = those Day Masters collapsed to 木火土金水

It does NOT yet mean "count every Five Element appearing across all year/month/day
stems and branches". That would be a separate chart-composition analysis.

Default discovery cohort
------------------------
1986-1989 only.

Run
---
python music_daymaster_distribution.py --years 1986 1987 1988 1989

Input
-----
Uses the already-created files:
hemisphere_1986\1986_people_with_hemisphere.csv
...
hemisphere_1989\1989_people_with_hemisphere.csv

Output
------
music_daymaster_results\music_daymaster_summary.txt
music_daymaster_results\all_scopes_daymaster_10stem.csv
music_daymaster_results\all_scopes_daymaster_5element.csv
music_daymaster_results\all_scopes_global_tests.csv
music_daymaster_results\music_people_with_daymaster.csv

Null model
----------
For each observed Gregorian birth year, enumerate every calendar date and calculate
the Day Master at noon. Expected counts are matched to the actual Music sample's
birth-year composition.

This is the same key logic used in the table-tennis project instead of assuming
10% per stem or 20% per element.

Scopes
------
full:
    all Music people

known:
    only Music people with known P19/P625 latitude

north:
    only Music people with latitude > 0

Comparing known vs north is cleaner for hemisphere sensitivity than full vs north,
because full vs north also drops people with unknown birthplace coordinates.

1990-1992
---------
Do NOT run 1990-1992 yet if you want them to remain a clean validation cohort.
After freezing/preregistering any Day-Master hypotheses, run explicitly:

python music_daymaster_distribution.py --years 1990 1991 1992
