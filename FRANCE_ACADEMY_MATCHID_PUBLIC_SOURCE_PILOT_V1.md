# France Academy: public matchID / INSEE death-index pilot v1

**Purpose**: source-only validation of birth/death dates for an existing, fixed historical French Academy CTHS candidate roster, **without downloading 133 MB decadal archives**. The INSEE deceased-person public register is indexed by third-party matchID. Its returned names/DOBs are external record *claims* and can be independently useful, but are **not** proof of French Academy ordinary/full membership, not proof that the identified person is the same as the CTHS individual, and not a proof of the absence of a person if no hit is found.

Source documentation:
- INSEE 1970–2019 public decade archive: https://www.insee.fr/fr/information/4769950
- matchID API spec: https://deces.matchid.io/deces/api/v1/docs/swagger.json
- matchID developer rules, free token, and one search/second: https://matchid.io/link-api
- Original frozen CTHS 562-page source harvest on main: `data/france_academy_cths_profile_dob_harvest_v1/`.

## Preconditions and strict research criteria

- Python >=3.10, **standard library only**; this script reuses read-only name/roster functions from `scripts/france_academy_insee_death_crosswalk_v1.py`.
- Default search is **at most 10 deceased persons among the 17 CTHS candidates who cite the 1989 French Academy member-only historical directory**. Prioritization uses missing CTHS day precision only, not astrology or outcome variables.
- CTHS's 1989 directory *citation* is NOT original-directory person-entry verification. French Academy membership and exact DOB admission flags are always zero.
- A birth year 1835–1985, death year from frozen CTHS lifespan, and a safe surname/first-given parse are required. This is not a complete Academy denominator. Foreign/unknown status remains unclassified.
- API search rate is capped at a minimum delay **1.1 seconds between requests**, 1.3 seconds by default. The unregistered developer API supports limited searches (roughly 100), so never run 562 person requests repeatedly without creating a **free API token** or following provider rules. Authenticated search remains rate-limited to approximately 1/s.
- `MATCHID_API_TOKEN`, when needed, is read from the local environment. **Never provide your access token in chat or commit it to GitHub.** Do not query living persons to infer death status. 
- Raw per-person JSON responses stored in `local_runs` are gitignored. Cache keys include source input checksums and query parameters; query failure or unsupported API result shape is NOT interpreted as a zero-result person.

## Commands for Windows PowerShell: each command one line

At `C:\chenxi\bazi_project\1986wiki`:

`git pull --ff-only`

1. Zero-network synthetic QA:
`python .\scripts\france_academy_matchid_public_pilot_v1.py --fixture-check`

2. See the selected identities and exact request parameters **without contacting matchID**:
`python .\scripts\france_academy_matchid_public_pilot_v1.py --dry-run --limit 10`

3. Actual 10-person **public no-token** pilot (after inspecting the dry-run):
`python .\scripts\france_academy_matchid_public_pilot_v1.py --limit 10`

4. Optional explicit set of CTHS IDs (for tighter testing):
`python .\scripts\france_academy_matchid_public_pilot_v1.py --ids 112083,112087 --limit 2 --out .\local_runs\france_academy_matchid_two_case_pilot_v1`

On the same 10-person run repeated, successful and failed query JSON is cached so it is **0 new API requests** until `--refetch` is used deliberately. If HTTP 401, 403 or 429 occurs, the script stops immediately; no retry floods. For large-scale follow-up, use official authenticated search or the officially documented asynchronous `/search/csv` route with proper matching rules, **but do not switch without a validated small pilot**.

## Output contract

- `local_runs/france_academy_matchid_public_pilot_v1/summary.json`: number selected, queried/cached, parsed candidate rows, query outcomes, frozen input hashes and zero acceptance.
- `person_query_status_v1.csv`: each person checked, source response status, reason if not found/unsupported and local source cache path. Share this small file for schema-debugging.
- `matchid_source_candidates_v1.csv`: unaccepted returned source claims, exact date agreement/conflicts, first name/surname/birth-year/death-year checks; share only if it helps resolve conflicts.
- `_responses/CTHSID_HASH.json`: local raw public API JSON and its SHA fingerprint; for unmatched schema, share **one small example without any secrets** if required.

No BaZi features, no acceptance or member-status promotions are computed. A single matching INSEE entry is a **human-verification lead**, not sufficient to accept a person into the academy study cohort.

## Pilot verification status

Fixtures validate representative JSON envelope and exact comparison; **no live matchID API query has been executed by the author of this checkpoint**. The first local Windows real search must confirm the API response schema and documented public unauthenticated availability. If it is denied or incompatible, report the status without inventing records. 
