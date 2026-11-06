# Royal Society birthplace completion v28

This batch adds two first stored birthplaces to the fixed 4,983 UK records: Charles Sykes, S2, and Charon Robin Ganellin, S3. Both resolve North from explicitly birth-linked county/country context. Original DOB-source grades and DOB-based S2 versus S2+S3 panels are unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,183 | 187 | 613 | 4,983 |
| Native DOB 1835–1985, inclusive | 2,283 | 182 | 179 | 2,644 |

The window's 179 unknown records comprise 112 blank birthplaces and 67 stored places with unresolved geography. Across all records those counts are 534 and 79. The initial 114-record blank-place queue is an eligibility pool, not 114 biographies read. Twelve previously unreviewed subjects received individual followup: two adoptions and ten holds. Exactly 4,981 complete objects remain identical to v27. No geography-only pilot, bulk screen or cross-cohort screen was performed.

| Subject | New raw birthplace | Support | Actual original evidence |
|---|---|---|---|
| Sir Charles Sykes, NA2245 | Clowne, Derbyshire | S2 / North | Attributed ODNB public Extract, T E Allibone; exact 1905-02-27/full subject/lifespan1905–1982/physics-metallurgy career/direct born clause |
| Charon Robin Ganellin, NA4189 | London, England | S3 / North | Original uncredited NIHF inductee biography; exact1934-01-25/full subject/cimetidine career/direct born clause |

Sykes's actual ODNB public Extract supports S2 under the existing attributed edited biography rule. The literal author initials remain unexpanded; the access-limited remainder was not read. Birth-linked Derbyshire supports North under the existing whole-region rule. The worker originally held Sykes after an observed legacy ODNB link led to a generic landing page. That report and its separate encyclopedia observation remain unchanged. A dated root decision supersedes only the current Sykes hold after acquiring the actual original Extract; no encyclopedia wording is attributed to ODNB and no informational independence is claimed.

The root's single adaptive-query purpose was explicitly broadened, after observing the legacy landing and before the query, from author context to author-or-observed-original-work location. The one-query limit was unchanged. The search returned the actual current OUP article URL, which was then opened. This is a disclosed retrieval-purpose amendment, not a source-admission exception, guessed URL, access bypass or failed-access retry. The legacy landing was not an access failure. Original intents, amendment timestamp, query and source references are retained.

Ganellin's NIHF biography is conservatively S3 because no named personal editor, verified expert byline or claim-specific civil authority was acquired. Its actual full name is Charon Robin Ganellin, matching native data; there is no observed Charles/Charon conflict or component substitution. England is directly birth-linked and supports North. No personal country, entity or coordinates are added. The profile's undated present-tense occupational prose supplies neither a death date nor dated evidence of life in2026. It does not confirm, contradict or correct the unchanged native2026 endpoint. Induction1990 and crawl dates are not article publication dates.

| Held subject | Evidence or limit |
|---|---|
| Roman Mieczyslaw Sawicki | Memoir projection has a place lead; original PDF route restricted, so no original birthplace body acquired. |
| Alfred Maurice Binnie | Original memorial PDF exceeds tool size limit; school/work/travel and secondary date projections do not supply birthplace or a new qualified date conflict. |
| Thomas Philip Stroud Powell | Original PubMed memoir citation metadata only; no acquired born-place body. |
| Harry Smith | Both original obituary/memoir DOI routes tool-inaccessible. |
| Lionel Edward Aston Rowson | Actual authored experiments history gives career context only; original memoir route unavailable. |
| John Hugh Chesters | Actual AIME award body gives full name/career, without birthdate or birthplace. |
| Joseph Arthur Colin Nicol | Original memoir carrier, reminiscence PDF and separate report routes failed; projections are not body evidence. |
| Leslie Clifford Bateman | Actual encyclopedia page has12March1915 versus native21March1915, but no original cited obituary body was acquired. This remains a secondary discrepancy, not a new qualified original DOB conflict or date correction. |
| William Lionel Wilkinson | No acquired original date/place/endpoint body; correspondence address is not birthplace. |
| Richard Henry Treisman | Historical2002 Jeantet biography states year1954 only, omits Henry and gives no birthplace. Historical present tense is not datedalive2026 evidence or a contrary death assertion. |

No death-endpoint or omitted-middle exception is invoked. All nine inherited issue/method sidecars are byte-identical to v27: six qualified active DOB conflicts remain separate from Tomes's provisional glyph uncertainty, Gotch's place conflict, Malet's approximate-year hold, Waterfield's internal age arithmetic, Midwinter's endpoint discrepancy, Coles's cross-source age contrast, Wager's middle-name admission and Shortt's qualified ordinal-age wording. No new case or inherited hold clearance is added.

Source work comprises24 worker queries plus one root query,18 worker navigation attempts plus two root first opens, and two worker cached finds. There were no root cached finds, screenshots or raw GETs. Group A's exact later query strings5–8 were ledgered after execution under a prior general adaptive purpose, without backdating. In Group C, a local SyntaxError prevented writing an exact three-navigation intent append, but the same cell continued to those navigations without checking the exit. Their prior general adaptive purpose existed; the exact list was only recorded afterwards. These three calls concern Bateman/Wilkinson/Treisman holds. The adopted Ganellin acquisition was earlier and prospectively intented. This deviation and actual timestamps are retained. Group B reports no deviation. Failed routes stopped without retries, variants or bypass; actual errors and aggregate-ref mapping limits remain. Parsed text is not raw bytes; unknown raw status/request times/byte hashes remain null. Excerpts are nine words for ODNB and six for NIHF, within25 per original work. No full source HTML/PDF/images or projection caches are distributed.

## Files and replay

The cumulative ZIP contains the complete current `outputs/birthplace_rows.jsonl.gz`, CSV projections, changes, summary, facts, audits and frozen inputs. The remaining-window CSV has179 records. All98 prior CSV columns retain positions/meaning; six v28 columns are appended, for104. Versioned `birthplace_followup_v28` facts preserve previous and absent-field snapshots for exact rollback.

```sh
python studies/royal_society_birthplace_completion_v28/scripts/replay.py
```

This self-contained command reconstructs exact v27 from the v10 carrier and frozenv11–v27 inputs before applying v28, without web requests. Baseline commit: `688209fe6319dc3f4c70a74918d72cf7ebbdb016`; baseline canonical JSONL SHA256: `ac6d3db5594801b9c55e271b392eb245fc8ae66216c0031eb5686ba82a545118`. Current canonical SHA256: `697389a67f48c88f214b8efc832a1f8744fcab34a4882f581215d75c8755403e`. Gzip uses blank filename/zero mtime; its output master is packaged and reproducible, not duplicated as another Git blob. The manifest excludes itself and Python caches.

Native DOB/calendar/authority identity/cohort/eligibility/DOB grades/country/QIDs/personal coordinates/prior selected evidence/hash/official status/all prior facts/untargeted complete objects remain frozen. No other cohort, statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Documentary source QA and independent final QA are separate; the latter checks reconstruction, rollback, CSV/counts and two isolated replays against five production pins.
