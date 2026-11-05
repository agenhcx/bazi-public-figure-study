# Royal Society birthplace completion v21

This batch adds four first stored birthplaces to the fixed 4,983 UK Royal Society records: three birthplace-support S2 observations and one S3 observation. Three resolve North and one resolves South. Original DOB-source grades and the existing DOB-based S2 versus S2+S3 panels are unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,175 | 187 | 621 | 4,983 |
| Native DOB 1835–1985, inclusive | 2,275 | 182 | 187 | 2,644 |

The native DOB window now has 133 unknown records with blank birthplace and 54 with stored birthplace but unknown geography. Across all records these numbers are 555 and 66. The initial 137-record blank-place pool is a queue, not 137 biographies read. Eight fixed subjects were individually followed up: four first-birthplace adoptions and four holds. There was no new geography-only pilot or bulk/cross-cohort screen. Exactly 4,979 complete objects remain identical to v20.

| Record | New raw birthplace | Birthplace support | Hemisphere | Source limit |
|---|---|---|---|---|
| NA4651, Donald Hill Perkins | Hull, east Yorkshire | S2 | North | Signed original obituary by Frank Close; original Oxford profile verifies relevant scientific expertise. No direct personal working relationship is asserted. |
| NA4834, Michael Derek Waterfield | Hampshire, United Kingdom | S2 | North | Signed original ASBMB Today obituary by Swarnali Roy. Exact DOB agrees; reported age82 differs from81 computed from stated dates. |
| NA4076, Albert Alan Townsend | Melbourne Australia | S2 | South | Original Cambridge publisher public Summary of an authored edited book chapter. Exact DOB agrees; no death endpoint observed in this passage. |
| NA5885, George Richard Pickett | Biddenham, Bedfordshire | S3 | North | Original signed edited obituary by Mick O'Hare. A professional-colleague role was not acquired; conservative S3 is retained. |

All four birthplaces are explicitly attached to their subjects and include birth-linked country or whole-region context supporting their hemisphere. No nationality, family, schooling, workplace, death place, familiar-city default, map or footer supplies birth geography. No personal country, entity/QID or coordinates are assigned.

Perkins's S2 source-genre decision is explicitly documented. The v20 review described a named professional colleague; the v21 initial plan allows a signed expert original. After the observed Guardian byline link returned an author article list without a biography, one declared adaptive query and original Oxford profile established Frank Close's theoretical-physics and nuclear/particle-history expertise. This supports expert authorship, without claiming a directly observed personal subject-author working relationship. The scope interpretation and actual timing are retained in method/parent audits. S2 does not mean civil-registration evidence, host-based S1 or peer review.

Waterfield's actual stated birthdate1941-05-14 matches native exactly, and the stated deathdate2023-05-11 agrees with native lifespan years1941–2023. The source nevertheless reports age82; conventional arithmetic from those dates gives81. Both are retained separately in `audit/source_derived_age_inconsistencies.json`, without correcting age, inventing another birthdate or changing native facts. No death-endpoint exception is needed. Townsend's accepted public Summary supplies exact birthdate but no source deathdate; the package does not claim independent confirmation of native2010 deathyear or acquisition of the paid full chapter/PDF.

Wells/NA8700 remains held. The acquired original BIR born sentence states1936-05-19, whereas native DOB is1936-06-19. Its birth-linked Bristol, England is not adopted while this explicit birth-month discrepancy is active. `audit/active_source_DOB_conflicts.json` adds Wells and preserves the two inherited Argyris/Laver conflict records unchanged. None is bypassed with dateless material or covered by the earlier death-endpoint-only exception. Midwinter's unrelated unresolved death-endpoint discrepancy is separately inherited; no native date correction or final correct-date verdict is made here.

The other three current holds are Matthews, Fletcher and O'Brien. Matthews's acquired original physiological tribute confirms full identity/exact DOB but gives no birthplace; Oxford routes were unavailable and the final new King's report URL returned tool404. Fletcher's original lecture confirms identity/date but no birthplace; the original memoir DOI returned403. O'Brien's LSW PDF was rejected as too large, and an original memoir carried on PMC returned only a reCAPTCHA page. Oldham/Lancashire remains a discovery lead, not adopted evidence. Failed routes were stopped without retry or access bypass.

Source work comprises 13 discovery queries: twelve by workers and one declared root author-credentials query. Fifteen worker navigation attempts plus seven root source/author-profile opens total22; there was one parsed find, no screenshots and no raw HTTP/PDF GET. Group A's aggregate intent file is a postcompletion index, explicitly distinguished from the actual prior own/child intents. All acquired-source failures and representation limits are retained. Parsed text is not raw HTTP bytes; unknown raw request time/status/hash stay null. No full source HTML/PDF, images, source-projection caches, contacts or family details are distributed. Repeated excerpts remain at most25 distinct English words per original work.

## Files and replay

`outputs/birthplace_rows.jsonl.gz` is the complete current master in the ZIP. `outputs/birthplaces.csv` is the readable projection; `outputs/remaining_unknown_window.csv` contains the187 remaining window records. `outputs/changes.json` and `outputs/summary.json` report exact deltas. Current facts contain previous values and previously absent fields for reversible updates. The56 prior CSV columns keep their meanings and positions; six v21 birthplace columns are appended. Earlier v20 geography support remains separate and unchanged.

Run from the repository root:

```sh
python studies/royal_society_birthplace_completion_v21/scripts/replay.py
```

The self-contained replay reconstructs exact v20 using the included v10 carrier and all frozen v11–v20 inputs before applying v21. It makes no web requests. Baseline v20 commit is `4f15eecc06904eee10005d1c2a09eaea9771e834`; baseline canonical JSONL SHA256 is `bbe9e22d00c4bfb3fb7a390df6a18a349e0abe64ba2986cd5075650f62ae9f2b`. Gzip uses a blank filename and zero mtime. The complete compressed output master is included for download and reproducible by code, rather than added as another Git blob. `MANIFEST.sha256` covers distributed files except itself and excludes Python caches.

Native DOB/calendar, authority identity, fixed cohort/eligibility, original DOB grades, country/QIDs/personal coordinates, prior selected evidence/hash/official-field status and every prior versioned fact are frozen. Only four current birthplace/geography updates and their versioned rollback facts differ. No other cohort, cross-cohort statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Independent source QA is documentary review of worker/root observations, with no additional original-source acquisition claim; independent local QA verifies exact reconstruction, frozen objects, rollback, CSV/counts and two isolated replays.
