Frozen Music 1990–1992 validation bundle
========================================

Frozen Git anchor
-----------------
tag:
    prereg-music-1990-1992-north-v1

commit:
    7b0de85

Hypotheses
----------
Primary:
H1 月令伤官 positive

Secondary:
S1 overall six-component Water lower
S2 月令劫财 negative
S3 月令比肩 positive

S1-S3:
BH-FDR across exactly 3 frozen secondary tests.

Primary cohort
--------------
north only:
P19 birthplace -> P625 latitude > 0

Unknown coordinates are excluded.
South is excluded.

Required input
--------------
hemisphere_1990\1990_people_with_hemisphere.csv
hemisphere_1991\1991_people_with_hemisphere.csv
hemisphere_1992\1992_people_with_hemisphere.csv

Run
---
python validate_music_1990_1992_north.py

Main result
-----------
validation_music_1990_1992_north\VALIDATION_RESULT_MUSIC_1990_1992_NORTH.txt

IMPORTANT
---------
Do not change the directions, hypothesis set, north rule, or multiplicity rule
after seeing the output.
