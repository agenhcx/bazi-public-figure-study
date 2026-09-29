BaZi Ten-God 1987–1989 + 1990–1992 crawler
================================================

FILES
-----
1. bazi_music_tengod_1986_v2.py
   Same v2 analyzer used for the 1986 exploratory analysis.

2. run_tengod_1987_1989.py
   Runs the v2 Ten-God analysis on already-existing 1987, 1988 and 1989
   daily occupation datasets, then creates a cross-year comparison.

3. crawl_1990_1992.py
   Resumable crawler for 1990, 1991 and 1992.

RECOMMENDED ORDER
-----------------
A. First inspect 1987–1989 Ten-God results:

   python run_tengod_1987_1989.py

   Main combined output:
     1987_1989_tengod_crossyear_summary.txt

B. Decide/freeze the hypotheses for the untouched 1990–1992 cohort.

C. Before preregistration, if you want to use the night for downloading,
   crawl only birth dates (predictor-side data; no P106 outcome):

   python crawl_1990_1992.py --proxy http://127.0.0.1:10808 --stage birthdates

D. After the new 1990–1992 hypotheses are frozen/preregistered:

   python crawl_1990_1992.py --proxy http://127.0.0.1:10808 --stage full

The full crawler fetches P106 and validates the data but intentionally does
NOT run a Ten-God association analysis. That keeps the inferential run separate.

NOTES
-----
- Put these scripts in the same project root as:
    birthdate_scan_v7.py
    occupation_scan_1986.py
    validate_year_dataset.py
- The crawler is resumable and skips completed outputs.
- Network stdout/stderr goes to crawl_1990_1992_logs/ so an overnight run
  is easier to diagnose.
