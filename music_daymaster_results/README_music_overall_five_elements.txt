Music overall Five-Element composition
======================================

Definition
----------
Each person contributes exactly 6 units:

1. 年干
2. 年支本气
3. 月干
4. 月支本气
5. 日干
6. 日支本气

Each unit maps to 木/火/土/金/水.

This is deliberately a clean "main-qi" definition:
- no birth hour
- no arbitrary hidden-stem weights
- every person has the same total weight = 6

Transition dates
----------------
Dates where year/month pillar changes between 00:30 and 22:30 are excluded,
because exact birth time is unknown.

Statistical null
----------------
Matched to the actual Music sample's Gregorian birth-year composition.

The Monte Carlo samples WHOLE date-level 6-component vectors from eligible
calendar dates within each birth year. This preserves dependence among the
six components and avoids pretending the 6*N element slots are independent.

Scopes
------
full  = all Music people
known = Music people with known P19/P625 latitude
north = Music people with latitude > 0

Run now
-------
python music_overall_five_elements.py --years 1986 1987 1988 1989

Main output
-----------
music_overall_five_elements_results\music_overall_five_elements_summary.txt

Other outputs
-------------
all_scopes_five_element_summary.csv
all_scopes_global_tests.csv
all_scopes_per_person_element_count_distribution.csv
music_people_with_6component_elements.csv

1990-1992
---------
Keep 1990-1992 untouched until any new hypotheses are frozen/preregistered.
After that, run explicitly:

python music_overall_five_elements.py --years 1990 1991 1992
