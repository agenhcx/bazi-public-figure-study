# Royal Society birthplace completion v26

This batch adds five first stored birthplaces to the fixed 4,983 UK records. Three birthplace-support grades are S2 and two are S3. Two birth-linked county names resolve North; three city/address observations retain unknown geography. Original DOB-source grades and the DOB-based S2 versus S2+S3 panels remain unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,179 | 187 | 617 | 4,983 |
| Native DOB 1835–1985, inclusive | 2,279 | 182 | 183 | 2,644 |

The window's 183 unknown records comprise 118 blank birthplaces and 65 stored places with unresolved geography. Across all records those counts are 540 and 77. The initial 123-record blank-place queue is an eligibility pool, not 123 biographies read. Twelve previously unreviewed subjects received individual followup: five adoptions and seven holds. Exactly 4,978 complete objects remain identical to v25. There was no geography-only pilot, bulk screen or cross-cohort screen.

| Record and subject | New raw birthplace | Support | Geography | Actual source precision |
|---|---|---|---|---|
| NA1134, Robert Robison | 28 Stodman Street, Newark-on-Trent, Nottinghamshire | S2 | North | Exact 1883-12-29 in original ODNB public Extract |
| NA173, Charles William Bunn | Camberwell, South London | S2 | Unknown | Birthyear 1905 only in original signed journal obituary |
| NA187, George Douglas Hutton Bell | Swansea | S2 | Unknown | Exact 1905-10-18 in original Ralph Riley obituary |
| NA1855, Charles Rundle Davidson | Walton, Suffolk | S3 | North | Exact 1875-02-28 in original compiled history entry |
| NA780, John William Evans | Barbican, London (2 Beech Street, Barbican, London) | S3 | Unknown | Exact 1857-07-27 in original compiled family-history entry |

All five acquired original bodies state full native name components, compatible actual date precision/lifespan, distinctive career context and a direct subject-born relation. Root verification acquired all five after worker discovery. The existing whole-region rule applies to birth-linked Nottinghamshire and Suffolk, as previously to Gloucestershire; no new geography method is introduced. City/address familiarity, nationality, work, family and death locations do not assign geography. No personal country, entity or coordinates are added.

Robison's attributed ODNB reference Extract is S2; the access-limited remainder was not read. Its 2004 publication and 2009 version date remain distinct. Bunn's edited scientific obituary is signed literally R. Bunn and describes family/autobiographical provenance; initials are not expanded and the longer newsletter and underlying notes were not independently acquired. It confirms birthyear only, not native January 15. Bell's S2 uses the existing relevant-expert newspaper amendment: original Riley byline plus acquired expert-role context. No personal-colleague or independent birthplace-corroboration claim is needed or made.

Davidson's compiled Graham Dolan entry is conservatively S3. It warns of incorrect information in a linked Woolley memoir's first paragraph. The memoir fetch returned 403 and stopped; no actual contrary paragraph was acquired. An unopened search projection gives a different place, but is not promoted to original-body evidence. Walton, Suffolk is retained as this source's observation without a correct-place verdict, Suffolk/Essex equivalence, conflict clearance or grade upgrade. Evans's compiled family history is S3; underlying references were not acquired as civil records or independent corroboration. Its later England census residence and daughter's Middlesex birthplace are excluded from his birth geography. Its last-changed date is not publication date.

| Held subject | Acquired evidence or limit |
|---|---|
| George Walker Walker | Original catalogue/body routes failed; projections are not birthplace evidence. |
| Samuel Walter Johnson Smith | Memoir DOI unavailable; no acquired original born-place body. |
| Guy Dunstan Bengough | Chislehurst, Kent, England explicitly describes baptism, not birth. No alias or event relabelling. |
| Edgar Stedman | Memoir bibliographic metadata only. No original memoir body was acquired; no fetch attempt was made. |
| Ettrick William Creak | Acquired preview/catalogue lacks explicit subject birthplace; father's Norfolk context excluded. |
| Herbert Leader Hawkins | Acquired collections essay lacks explicit birthplace; original obituary routes unavailable. |
| Frederick William Carter | Original person body unavailable; homonymous search matches are not native conflicts. |

The eight inherited issue/method sidecars are byte-identical to v25. Six qualified active DOB conflicts remain separate from Tomes's provisional parsed-glyph uncertainty; Gotch's place conflict, Malet's approximate-year hold, Waterfield's internal age discrepancy, Midwinter's death endpoint, Coles's cross-source age contrast and the Wager middle-name admission are unchanged. This batch adds no qualified date/place conflict, glyph case or omitted-middle exception and clears no inherited hold.

Source work comprises 24 queries, 28 worker navigation attempts and six root first opens: 34 navigation attempts, plus two worker and three root cached finds. No screenshots or raw GETs were used. Group B's general four-subject intent and first four explicit queries preceded work; the exact later four queries were first ledgered after execution. The original intent is unchanged and the timing and aggregate-result mapping limits are disclosed, without backdating. Failed routes stopped without retries, URL variants or bypass. Unknown raw HTTP status, request time and byte hashes remain null. Short excerpts remain within 25 English words per original work; no full source HTML/PDF/images or projection caches are distributed.

## Files and replay

The ZIP contains the complete current `outputs/birthplace_rows.jsonl.gz`, CSV projections, changes, summary, facts, audits and frozen inputs. The remaining-window CSV has 183 records. CSV preserves all 86 prior columns and appends six v26 columns, for 92. Versioned `birthplace_followup_v26` facts contain previous values and absent-field snapshots for exact rollback.

```sh
python studies/royal_society_birthplace_completion_v26/scripts/replay.py
```

From the repository root this self-contained command reconstructs v25 from the v10 carrier and frozen v11–v25 inputs, then applies v26 without web requests. Baseline commit: `65494e28c0b3ad9bd28538bd45daca5df8232b07`. Baseline canonical JSONL SHA256: `b36383e9ac72642059c2f9b5ff6c57187c8b04477bb5830ebf85b61a12cda730`. Current canonical SHA256: `41aebb4d4c05b6c45889315892b5edcfa1f10c2a7d16fe75e6608e0e3dc07378`. Gzip has blank filename and zero mtime. The compressed output is packaged and reproducible, not duplicated as another Git blob. The manifest excludes itself and Python caches.

Native DOB/calendar, authority identity, cohort/eligibility, DOB grades, country/QIDs/personal coordinates, prior selected evidence/hash/official status, all prior versioned facts and untargeted complete objects remain frozen. No other cohort, statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Documentary source QA and independent final QA are recorded separately; the latter checks reconstruction, rollback, counts, CSV and two isolated replays against five production pins.
