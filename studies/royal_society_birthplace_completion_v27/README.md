# Royal Society birthplace completion v27

This batch adds four first stored birthplaces to the fixed 4,983 UK Royal Society records: two S2 and two S3 birthplace-support observations. Two explicit birth-linked India assertions resolve North; Kensington and Leeds remain geographically unknown. Original DOB-source grades and the DOB-based S2 versus S2+S3 panels are unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,181 | 187 | 615 | 4,983 |
| Native DOB 1835–1985, inclusive | 2,281 | 182 | 181 | 2,644 |

The window's 181 unknown records comprise 114 blank birthplaces and 67 stored places with unresolved geography. Across all records these counts are 536 and 79. The initial 118-record blank-place queue is an eligibility pool, not 118 biographies read. Twelve previously unreviewed subjects received individual followup: four adoptions and eight holds. Exactly 4,979 complete objects remain identical to v26. No geography-only pilot, bulk screen or cross-cohort screen was performed.

| Subject | New raw birthplace | Support | Geography | Actually acquired source |
|---|---|---|---|---|
| William Kenneth Hutchison, NA1951 | Assam, India | S2 | North | Named-authored 1999 NCUACS catalogue biographical outline; exact 1903-10-30/full subject/lifespan/career/direct born clause |
| Geoffrey Morse Binnie, NA2016 | Kensington | S2 | Unknown | Alan Muir Wood's original ODNB public Extract; exact 1908-11-13/full subject/lifespan/civil-engineering career |
| Norman Laurence Franklin, NA1994 | Leeds | S3 | Unknown | Original February 1969 ATOM Ministry of Technology-attributed appointment biographical note; exact 1924-09-01/full subject/nuclear-engineering career |
| Henry Edward Shortt, NA2005 | Dhariwal, India | S3 | North | Original anonymous auction-catalogue biographical footnote; exact 1887-04-15/full subject/compatible 1987 death/parasitology career |

Hutchison's catalogue explicitly names Alan Hayward and Peter Harper and dates its original compilation to 1999. The upload path's 2024 date is not publication date. Its attributed institutional archival biographical outline supports S2, without a host-only S1, civil-record or informational-independence claim. Binnie's actual public Extract supports S2; the access-limited remainder was not read. His parents' origins, family firm and international projects do not supply birth geography.

Franklin's original ATOM note was successfully acquired by the worker before the root's later first attempt returned tool-reported `(400) Timeout fetching`. That route stopped without retry or variants. The earlier original-body observation supports adoption under the existing acquisition-role rule. No independent root primary-body acquisition, raw HTTP 200, byte hash or source-version change is claimed. The source is institutionally attributed but lacks a named personal biographer or acquired claim-specific birth-record authority, so its birthplace support is conservatively S3. A subject alive in a dated 1969 appointment note is temporally compatible with the unchanged native 1986 endpoint; the note does not confirm that later death. A separately acquired IChemE profile gives Leeds/September 1924 only and does not confirm day 1 or informational independence.

Shortt's auction footnote is conservative S3. Documents described with the lot and an inaccessible BMJ article were not acquired as corroboration or grade upgrades. A separately acquired Wellcome catalogue states Punjab/April 1887, with compatible full subject/lifespan/career. The two place wordings remain separate without an asserted exact nested-place equivalence or adjudicated place conflict; the month-only catalogue does not confirm April 15. India is directly birth-linked in the selected footnote. No personal country, QID or coordinates are assigned.

## Qualified ordinal-age wording

The Shortt footnote also says “in his 100th year” at death on 1987-11-09. Its stated 1887-04-15 birth and death dates yield 100 completed years, conventionally the 101st ordinal year of life. A literal ordinal reading therefore differs from the date arithmetic, but the wording may be loose. This is a qualified one-source wording observation, not a reported integer age of 99, a wording-error verdict, an alternate DOB/death date or a correction to native data. `audit/source_ordinal_age_wording_observations.json` keeps it separate from existing integer-age arithmetic, cross-source age contrasts and the six active DOB conflicts. This observation does not overturn agreement of the actual source DOB with native DOB.

| Held subject | Evidence or limit |
|---|---|
| William Watt | Original award PDF unavailable; newspaper search projection is not acquired birthplace proof. |
| Montague Mattinson Pennell | Acquired exact-DOB compiled entry lacks birthplace. A Barnstaple lead under a different name is not transferred or alias-expanded. |
| Alan Richard Powell | Original memoir route unavailable; no acquired born-place body. |
| Leonard Francis La Cour | Original memoir route reported tool-inaccessible, without an invented HTTP status. |
| Richard Edmund Reason | Acquired authored text gives full subject/exact DOB/career, but the Devon locations concern his parents. Another carrier exposed an index, not his biography. |
| Arthur Herbert Cook | Original memoir DOI unavailable; no acquired birthplace assertion. |
| James Dyson | Observed original memoir link returned 403; stopped. |
| Reginald Charles Rainey | Original memoir DOI unavailable; no acquired birthplace assertion. |

All eight inherited issue/method sidecars are byte-identical to v26. The six qualified active DOB conflicts remain separate from Tomes's provisional parsed-glyph case, Gotch's place conflict, Malet's approximate-year hold, Waterfield's internal age arithmetic, Midwinter's endpoint, Coles's cross-source age contrast and the Wager middle-name admission. This batch adds no qualified DOB/place conflict, glyph case or omitted-middle exception and clears no inherited hold.

Source work comprises 24 queries, 20 worker navigation attempts and five root first opens, totaling 25 navigation attempts, plus three worker and one root cached finds. No screenshots or raw GETs were used. Group A's later query strings 5–7 were first ledgered after execution under a prior explicit general adaptive purpose; query 8 was additionally prelisted. No exact-query intent was backdated. Group B's first three-find display was truncated: the Binnie/Franklin paragraphs remained visible; the third byline-find result identifier was unretained, with the byline already observed and no new fact depending on it. This is distinct from disclosed aggregate-query mapping limits. Group C's one-line Reason JSTOR display detail was unretained and supplies no invented body/status verdict. All original limits and actual errors remain in ledgers. Failed routes stopped without retries, variants or bypass. Unknown raw HTTP status/request times/byte hashes remain null. Quotes are at most 25 English words per original work, including Shortt's 9-word born clause plus 4-word ordinal phrase. No full source HTML/PDF/images or projection caches are distributed.

## Files and replay

The cumulative ZIP contains the complete current `outputs/birthplace_rows.jsonl.gz`, CSV projections, changes, summary, facts, audits and frozen inputs. The remaining-window CSV has 181 records. All 92 prior CSV columns retain positions/meaning; six v27 columns are appended, for 98. Versioned `birthplace_followup_v27` facts preserve previous values and absent-field snapshots for exact rollback.

```sh
python studies/royal_society_birthplace_completion_v27/scripts/replay.py
```

The command reconstructs exact v26 from the v10 carrier and frozen v11–v26 inputs, then applies v27 without web requests. Baseline commit is `3d51d6739c7319a1a39b2c4d7f730b4a8b02fb05`; baseline canonical JSONL SHA256 is `41aebb4d4c05b6c45889315892b5edcfa1f10c2a7d16fe75e6608e0e3dc07378`. Current canonical SHA256 is `ac6d3db5594801b9c55e271b392eb245fc8ae66216c0031eb5686ba82a545118`. Gzip has blank filename/zero mtime. Its output master is packaged and reproducible, not duplicated as another Git blob. The manifest excludes itself and Python caches.

Native DOB/calendar/authority identity/cohort/eligibility/DOB grades/country/QIDs/personal coordinates/prior selected evidence/hash/official status/all prior facts/untargeted complete objects remain frozen. No other cohort, statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Documentary source QA and independent final QA are separate; the latter verifies reconstruction, rollback, CSV/counts and two isolated replays against five production pins.
