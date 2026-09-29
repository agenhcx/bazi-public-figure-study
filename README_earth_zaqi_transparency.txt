Post-validation 杂气月透干 analysis
=================================

Purpose
-------
Study the four Earth-Day-Master tomb-month combinations:

    戊辰 / 戊戌 / 己丑 / 己未

and ask whether Music enrichment is related to which month-hidden stems
are visible ("透干").

Key point
---------
Exact birth hour is not required if we are willing to use an equal-hour
marginalization assumption.

The script enumerates 12 representative double-hours and reports the
probability that each hidden stem is exposed.

But this is still an ASSUMPTION:
real birth times are not proven to be uniformly distributed across the
12 double-hours.

Definition of 透干
-----------------
A month-hidden stem is counted as already exposed when it appears in:

    YEAR stem or MONTH stem

The DAY stem is deliberately excluded.

Then the hour stem is marginalized across 12 possible double-hours.

Four tomb branches contain three hidden stems:

    辰 = 戊 / 乙 / 癸
    戌 = 戊 / 辛 / 丁
    丑 = 己 / 癸 / 辛
    未 = 己 / 丁 / 乙

Outputs
-------
postvalidation_earth_zaqi_transparency_1986_1992\
    EARTH_ZAQI_TRANSPARENCY_SUMMARY.txt
    earth_zaqi_transparency_models.csv
    earth_zaqi_combo_summary.csv
    earth_zaqi_daily_analysis_table.csv
    earth_zaqi_people_with_transparency.csv

Run
---
python postvalidation_earth_zaqi_transparency_1986_1992.py

Interpretation
--------------
All results are exploratory because 1986–1992 Music outcomes are already known.
Any new hypothesis generated here requires a new untouched cohort.
