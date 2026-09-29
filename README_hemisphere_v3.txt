Hemisphere sensitivity v3
=========================

Fixes compared with v2
----------------------
1. Keeps the Windows UTF-8 subprocess fix.
2. Adds an explicit research User-Agent for Wikimedia.
3. Detects HTTP status instead of relying on curl --fail.
4. HTTP 429 now triggers long exponential backoff:
      30s, 60s, 120s, 240s, then capped at 300s.
5. 5xx errors also back off automatically.
6. Safer defaults:
      --batch-size 40
      --pause 3.0

Resume
------
The existing cache is compatible. If v2 successfully saved the first
10 batches, v3 will skip those QIDs automatically.

Recommended command
-------------------
python hemisphere_tengod_sensitivity_v3.py --proxy http://127.0.0.1:10808 --years 1986 1987 1988 1989

If Wikimedia still rate-limits heavily, use the extra-safe setting:

python hemisphere_tengod_sensitivity_v3.py --proxy http://127.0.0.1:10808 --years 1986 1987 1988 1989 --batch-size 25 --pause 5

Do NOT delete:
  hemisphere_cache\person_p19.json
  hemisphere_cache\place_p625.json

Those files are what make the crawl resumable.
