Hemisphere sensitivity bundle
=============================

MAIN SCRIPT
-----------
hemisphere_tengod_sensitivity.py

PURPOSE
-------
Adds birthplace hemisphere using:
  person QID -> Wikidata P19 place of birth -> place QID -> P625 coordinates

Then compares the existing Ten-God × Music analysis in:
  1. full sample
  2. Northern-Hemisphere-only sample

Important:
- "unknown birthplace" is kept as UNKNOWN, never silently treated as north.
- Southern Hemisphere means P625 latitude < 0.
- Northern Hemisphere means P625 latitude > 0.
- Equator latitude == 0 is its own category.
- Country/nationality is NOT used as a proxy for hemisphere.

DEFAULT / RECOMMENDED NOW
-------------------------
Run only 1986-1989 first:

python hemisphere_tengod_sensitivity.py --proxy http://127.0.0.1:10808 --years 1986 1987 1988 1989

Main output:

hemisphere_sensitivity_results\hemisphere_sensitivity_summary.txt

Also useful:

hemisphere_sensitivity_results\full_vs_north_by_year.csv
hemisphere_sensitivity_results\pooled_full_vs_north_all20.csv

PER-PERSON ENRICHED FILES
-------------------------
hemisphere_1986\1986_people_with_hemisphere.csv
...
hemisphere_1989\1989_people_with_hemisphere.csv

CACHES / RESUME
---------------
hemisphere_cache\person_p19.json
hemisphere_cache\place_p625.json

The script saves caches after every batch, so it is resumable.

1990-1992
---------
Your 1990-1992 crawl can already exist; the script does not overwrite it.

If you want to ADD hemisphere metadata to 1990-1992 without looking at any
Ten-God association yet, use fetch-only:

python hemisphere_tengod_sensitivity.py --proxy http://127.0.0.1:10808 --years 1990 1991 1992 --fetch-only

After hypotheses are frozen/preregistered, you can explicitly analyze them:

python hemisphere_tengod_sensitivity.py --proxy http://127.0.0.1:10808 --years 1990 1991 1992

EXPECTED SOURCE FILE
--------------------
For each year the script looks for, in this order:

occupation_scan_YEAR\YEAR_people_with_occupations.csv
occupation_scan_YEAR\YEAR_people_occupations.csv
occupation_scan_YEAR\YEAR_people.csv

It auto-detects:
- QID column
- birth-date column
- individual Music category flag/list

If Music auto-detection fails, the script prints all available columns.
Then rerun with:

python hemisphere_tengod_sensitivity.py --proxy http://127.0.0.1:10808 --years 1986 1987 1988 1989 --music-column YOUR_COLUMN

DEPENDENCIES
------------
pip install pandas numpy statsmodels lunar_python

NETWORK
-------
Uses curl.exe and the proxy, matching the existing project setup.
