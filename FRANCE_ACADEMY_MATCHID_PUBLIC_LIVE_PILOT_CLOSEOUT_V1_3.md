# France Academy — public matchID/INSEE death-index pilot closeout v1_3

Checkpoint 2026-10-18 UTC, **evidence collection only**, never BaZi outcomes or cohort freeze.

## Why the previous pilot failed

User's Windows run of the original search script on 2026-10-18 reported 10/10 failed/unparsed calls: HTTP400 x6, HTTP422 x3, URLError x1. Zero true observed study matches. See historical initial personal upload `summary(20261018-080218).json` and `person_query_status_v1.csv` (not stored in repository).

Live bounded GitHub Actions tests established the actual matchID GET parameter rules:
- `q=jean dieudonne`: HTTP200, 20 result records in first page.
- `q` + `birthDate=01/01/1906 - 31/12/1906`: HTTP400 `invalid birthDate value`.
- `q` + compact `birthDate=01/01/1906-31/12/1906`: HTTP400 `simple and complex request at the same time`.
- **`firstName=jean&lastName=dieudonne&birthDate=01/01/1906-31/12/1906`**: HTTP200, **3 total** results.

The production v1_3 script now uses the final validated advanced query, *without* `q`, with birthDate compact range (no spaces), and correctly parses the official JSON envelope `response.persons`, `name.first/last`, `birth.date`, `death.date`, `birth.location.city`. It records HTTP error response messages safely, stops on first failed query, and uses new versioned cache hashes. Published specification https://deces.matchid.io/deces/api/v1/docs/swagger.json .

## 10-person public live source-only pilot

Reproducible code verification GitHub Action run: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39111078287 .

The workflow was a **temporary bounded probe**, no persisted polling. The probe step was subsequently removed from the ongoing CI; offline Python 3.10/3.13 tests remain.

- 10 historical CTHS targets selected from the fixed 17 persons citing the 1989 Academy member-only directory.
- 7 attempted; 6 HTTP200 with recognized schema, the seventh returned HTTP422 anonymous-use cap, so script stopped without querying remaining three.
- Six HTTP200 responses produced **46 total API candidate records**, 29 passed literal surname/first-given plus birthyear checking, and only **6** (one per queried CTHS person) also agreed with the CTHS death year. These six are **identity verification leads**, not automatically approved unique identities. Some returned pages had other candidates.
- DOB comparison among the six highest-specificity leads: **3 CTHS date agreements, 2 previous CTHS DOB gaps, 1 day/month conflict.**
- For **Jean Roche**, API reports 38 total records but only 20 appear in the first page. Even though one returned record agrees on surname/first given, 1901 birth year and 1992 death year, this is not an exhaustive one-to-one identity audit.
- **Source-set selection is not random** and cannot estimate France membership roster coverage or DOB completeness of the Academy. 1989 bibliographic references are NOT direct inspection of those member entries. No final study subject may be included on the strength of these 6 candidates.

One-row-per-person public date assertion overlay: `data/france_academy_matchid_public_live_pilot_v1_3/strict_provisional_6_dob_evidence_leads_v1.csv`. This is an authored summary of field claims and references, **not** the raw INSEE archive, source record IDs, nor underlying signed birth registers. The GitHub Action no longer retains complete transient raw response files, so do not invent their sha256 or individual index identifiers.

## One major date conflict: Jean Roche, CTHS 2067

The exact same scientist, French biochemist Jean Roche of Sorgues, died **1992-05-24**, has two competing birth-date claims:

**January 14, 1901**
- Public matchID index of INSEE deceased register (this v1_3 live pilot; CTHS matching birth year 1901/death year 1992).
- École pratique des hautes études (EPHE), named person's historical biography: https://prosopo.ephe.psl.eu/jean-roche .
- Contemporaneous **Le Monde 1961-09-07** appointment biography naming January 14: https://www.lemonde.fr/archives/article/1961/09/07/m-jean-roche-nouveau-recteur-de-l-academie-de-paris_2275367_1819218.html .
- Public **derived** death-register index supplies full name `Jean Casimir Henri Hilaire Roche`, reported born Sorgues 1901-01-14 and died Paris 1992-05-24: https://www.acte-deces.fr/recherche-deces-famille-roche-1992 . This is not the original scanned civil act.

**February 14, 1901**
- Collège de France original institutional biography: https://www.college-de-france.fr/fr/personne/jean-roche .
- CTHS historical dossier (claims Academy member in 1963): https://www.cths.fr/an/savant.php?id=2067 .

This is a **real conflict between reputable public sources**, not adequately resolved by majority voting. The contemporary 1961 biography and the public death register favor January, while a first-party employer biography favors February. Do not replace the frozen CTHS date. Highest-priority final adjudication is a **1901 Sorgues original civil birth register entry** for Jean Casimir Henri Hilaire Roche, available via the Vaucluse department official pre-1922 digitized état civil collections:
https://memento.vaucluse.fr/aide-a-la-recherche/genealogie/je-cherche-un-acte-de-bapteme-naissance-mariage-sepulture-deces-ou-divorce . Original January/February pages not accessed yet.

## Other five person-specific source leads

| CTHS ID | Name | matchID exact DOB claim | Comparison |
|---|---|---|---|
| 112083 | Jean Dieudonné | 1906-07-01 | CTHS missing; French Academy fonds inventory already independently states same date |
| 112087 | Charles Louis Dubost | 1914-10-01 | CTHS missing; historical medical journalist support; avoid same-name prosecutor |
| 2060 | Jean Wyart | 1902-10-16 | CTHS agrees |
| 101487 | Georges Millot | 1917-05-24 | CTHS agrees; preserve the separate metadata May 27 discrepancy |
| 102781 | Lucien Malavard | 1910-10-07 | CTHS agrees; no original source date independently inspected |

**DO NOT** treat a matchID/INSEE deceased-register entry as French Academy membership evidence: these are orthogonal questions.

## Stop condition and next stage

For CTHS ID **107885 Jean Piveteau**, the service explicitly responded HTTP422:
`No token provided and temporary anonymous usage expired, please register with email or wait 0 hours`.

This is an **anonymous service quota**, not an identity search failure. Script correctly stopped. No repeated requests to bypass API limits. The official provider says a limited number of public searches is available without signing in, but sustained or bulk usage requires a **free** login/API token, subject to rate caps: https://matchid.io/link-api . A user who obtains a token locally can set the PowerShell environment variable `MATCHID_API_TOKEN` (never share the token or check it into GitHub) and resume through the same source-only script. Otherwise continue original archival documents or genuinely public civil registers without this API.

No changes to original 562 CTHS HTML SHA-pinned source archive. No changes to frozen cohort counts, accepted birthdays, academy member categories, global Nobel-year 1835–1985 support, or pre-unblinding block. `bazi_variables_computed=0`; `final_exact_dob_accepted=0`; `final_academy_membership_accepted=0`.
