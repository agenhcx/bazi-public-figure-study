# French Academy historical members: INSEE public deceased-register crosswalk v1

This is a **public-source-only local pilot** and does NOT require contacting the French Academy or obtaining the Leridon 3,218-person Excel file. Code: `scripts/france_academy_insee_death_crosswalk_v1.py`. Tested with Python 3.13 and stdlib synthetic CSV-in-ZIP / fixed-width fixtures; written for Python >=3.10. No genuine INSEE ZIP was downloaded or processed during this checkpoint.

## Public issuer and direct source

- National source: INSEE, public register of persons whose deaths were recorded since 1970: https://www.insee.fr/fr/information/4190491
- Historical decadal ZIPs: https://www.insee.fr/fr/information/4769950
- Initial suggested decade: **1990–1999** (133 MB compressed at official site); direct downloadable official URL: https://www.insee.fr/fr/statistiques/fichier/4769950/deces-1990-1999-csv.zip
- This public register provides surnames and given names, full DOB (sometimes partial or erroneous), birth place, and death date. Recorded-death month may lag actual date; 1970–1975 incomplete; foreign deaths/identities may be absent. Absence of a match means NO inference about identity or life status.
- If re-publishing death-register data, respect INSEE rights/opposition and licence conditions. This pipeline stores candidates only under a local ignored folder, does not redistribute INSEE bulk records, and never publishes the raw files.

## Run: Windows PowerShell (single-line commands)

Project root: `C:\chenxi\bazi_project\1986wiki`. Local CTHS input files must exist and match the established France Academy project.

1. Smoke test with synthetic records: `python .\scripts\france_academy_insee_death_crosswalk_v1.py --fixture-check`
2. Download the official historical ZIP to `C:\chenxi\bazi_project\1986wiki\external\insee\deces-1990-1999-csv.zip` manually, or by using these two **single-line** PowerShell commands:
   - `New-Item -ItemType Directory -Force .\external\insee | Out-Null`
   - `curl.exe -L --retry 2 --connect-timeout 30 -o .\external\insee\deces-1990-1999-csv.zip https://www.insee.fr/fr/statistiques/fichier/4769950/deces-1990-1999-csv.zip`
3. Offline source match: `python .\scripts\france_academy_insee_death_crosswalk_v1.py --insee-zip .\external\insee\deces-1990-1999-csv.zip --out .\local_runs\france_academy_insee_deaths_1990s_v1`
4. To add decades in ONE run, repeat `--insee-zip path\to\decade.zip`; duplicates are flagged by distinct person/date/name signatures. ZIP+CTHS input SHA256 hashes guard the cache.

## Outputs and QA

- `local_runs/.../insee_cths_candidate_matches_v1.csv`: source candidates (linked by normalised surname, first given, CTHS birth year and, where present, death year) with original-source file SHA256, record SHA256, birth/death dates and provisional comparison.
- `local_runs/.../summary.json`: source hashes, number of candidates, matched/ambiguous statuses and **zero accepted cohort members/DOBs**.
- `local_runs/.../target_name_parse_failures_v1.csv`: unsupported surname/particle structures, for manual review.
- `local_runs/.../_cache/<fingerprint>.json`: resumable cache keyed to ZIP file hash plus CTHS roster/role-source hashes, so roster revisions cannot reuse stale matches.

For unambiguous-looking matches, the status remains `UNIQUE_INSEE_LEAD_MANUAL`: **not** accepted DOB, **not** verified French full-member status. Compare against Academy election documentation and independent biographies, and manually adjudicate foreign birth-calendar conventions (e.g. Łódź 1908), variant surnames, aliases, and same-name identities.

This program does not parse or calculate BaZi, construct statistical hypotheses, or change the frozen France Academy source acceptance flags.
