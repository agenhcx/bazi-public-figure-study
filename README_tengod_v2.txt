BaZi Music Ten-God 1986 v2
=============================

Contents
--------
bazi_music_tengod_1986_v2.py
    Updated exploratory Ten-God analysis.

Run in PowerShell
-----------------
python bazi_music_tengod_1986_v2.py --input occupation_scan_1986\1986_daily_category_stats.csv --year 1986

Main new output
---------------
bazi_tengod_music_1986_v2\1986_tengod_music_summary_v2.txt

The v2 summary reports, for each Ten-God:
- P(Music | Ten-God)
- share among Music = P(Ten-God | Music)
- share among all = P(Ten-God)
- enrichment ratio = P(Ten-God | Music) / P(Ten-God)

The 10 "share among Music" values sum to 100%.
The 10 "share among all" values sum to 100%.

It also exports:
- month-stem enrichment table
- month-order/main-qi enrichment table
- 6 targeted Food-God/Hurting-Officer tests
- all 20 one-vs-rest exploratory Ten-God tests with BH-FDR
