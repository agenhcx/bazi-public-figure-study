Hemisphere sensitivity v2 — Windows UTF-8 fix

Fixes:
1. curl.exe stdout/stderr are now captured as bytes and decoded explicitly as UTF-8.
   This avoids Windows cp1252 UnicodeDecodeError.
2. The pandas Music regex now uses non-capturing groups, removing the warning.

Run 1986-1989:
python hemisphere_tengod_sensitivity_v2.py --proxy http://127.0.0.1:10808 --years 1986 1987 1988 1989

The cache files remain compatible:
hemisphere_cache\person_p19.json
hemisphere_cache\place_p625.json

If any cache batches were saved before interruption, v2 will resume from them.
