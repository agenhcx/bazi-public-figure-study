Music × BaZi 1993–1995 frozen validation bundle
================================================

This bundle contains:

1. crawl_music_1993_1995.py
   Orchestrates birthdate -> occupation -> hemisphere collection using
   the existing frozen project scripts.

2. validate_music_1993_1995_north.py
   Implements the preregistered 1993–1995 validation:
   - H1 primary: 戊辰 / 戊戌 / 己丑 / 己未 positive for Music
   - H2 secondary: 甲午 / 乙巳 / 戊酉 / 己申 / 庚子 / 辛亥 / 壬卯 / 癸寅 positive
   - north primary
   - grouped-binomial daily GLM
   - year + Gregorian month + weekday + Day Stem + Month Branch
   - HC0 robust covariance
   - one-sided positive tests
   - P106 >=95% annual QA gate before association analysis

Recommended workflow
--------------------

A) Put BOTH .py files into the repo root.

B) Commit implementation BEFORE outcome reveal:
   git add crawl_music_1993_1995.py validate_music_1993_1995_north.py
   git commit -m "Implement frozen Music 1993-1995 validation pipeline"
   git push origin HEAD

Do NOT move the preregistration tag.

C) Collect data:
   python crawl_music_1993_1995.py --proxy http://127.0.0.1:10808 --stage all

This is restartable: completed standard output files are skipped.

D) Confirm files:
   birthdate_scan_1993\1993_people.csv
   birthdate_scan_1994\1994_people.csv
   birthdate_scan_1995\1995_people.csv

   occupation_scan_1993\1993_people_with_occupations.csv
   occupation_scan_1994\1994_people_with_occupations.csv
   occupation_scan_1995\1995_people_with_occupations.csv

   hemisphere_1993\1993_people_with_hemisphere.csv
   hemisphere_1994\1994_people_with_hemisphere.csv
   hemisphere_1995\1995_people_with_hemisphere.csv

E) Run frozen validation ONCE:
   python validate_music_1993_1995_north.py

Main result:
   validation_music_1993_1995_north\VALIDATION_RESULT_MUSIC_1993_1995_NORTH.txt

Also produced:
   DATA_QA_1993_1995.csv
   frozen_H1_H2_scope_results.csv
   north_per_year_descriptive.csv
   north_exact_combo_supportive_descriptive.csv
