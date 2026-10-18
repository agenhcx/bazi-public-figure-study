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

## ZIP preflight and failed downloads (v1_1, 2026-10-18)

An actual Windows curl invocation successfully wrote 7.25 MB but Python raised zipfile.BadZipFile. The official INSEE decade page explicitly describes the 1990–1999 source as **133 Mo (ZIP)**, and the direct URL on that page remains https://www.insee.fr/fr/statistiques/fichier/4769950/deces-1990-1999-csv.zip . A completed curl transfer does not prove a ZIP is valid. We do not have the 7.25 MB file's magic bytes, so we cannot yet distinguish HTML/proxy interception from a partial ZIP download.

With the latest \`main\`, FIRST run this lightweight source diagnosis (no network, no roster scan):

\`python .\scripts\france_academy_insee_death_crosswalk_v1.py --inspect-zip .\external\insee\deces-1990-1999-csv.zip\`

- \`valid_zip=true\`: ZIP directory exists; this does not certify official integrity. Compare file size to the official advertised ~133 MB and check ZIP member-list and contents before bulk analysis.
- \`reason=html_or_xml_instead_of_zip_check_http_proxy_or_site_error\`: downloaded website/proxy response, not archival data. Save HTTP headers, try official INSEE page through an ordinary browser instead.
- \`reason=zip_header_but_missing_directory_possible_truncated_download\`: likely incomplete ZIP. Only use resume when the endpoint supports HTTP ranges and the head bytes really are \`PK\`; do not append to HTML.
- Other reasons: inspect the saved beginning and HTTP status/Content-Type from the download. Delete corrupt file only AFTER diagnosing it.

If the official INSEE bulk transfer is very slow or unavailable, the public <https://deces.matchid.io/> search UI can be used to check a small number of historical people. Its documented API allows limited unauthenticated searches and a **free token** after signup for larger/bulk queries, subject to rate limits. See <https://matchid.io/link-api> . This is a third-party redistributed/indexed INSEE data service, not original 1989 French Academy member-class evidence; all identity and DOB claims still need independent review.
