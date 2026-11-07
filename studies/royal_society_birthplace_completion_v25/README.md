# Royal Society birthplace completion v25

This batch adds two first stored birthplaces to the fixed4,983 UK Royal Society records: Bernard Smith, Grantham, and Leonard Frank Spath, Munich. Both new birthplace-support grades are conservativeS3 and both retain unknown geography. There is no new North/South classification. Original DOB-source grades and DOB-based S2 versus S2+S3 panels remain unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,177 | 187 | 619 | 4,983 |
| Native DOB1835–1985, inclusive | 2,277 | 182 | 185 | 2,644 |

The native DOB window now has123 unknown records with blank birthplace and62 with stored birthplace but unknown geography. Across all records these numbers are545 and74. The initial125-record blank-place pool is a queue, not125 biographies read. Twelve fixed previously unreviewed subjects were followed up in three groups: two adoptions and ten holds. There was no new geography-only pilot, bulk screen or cross-cohort screen. Exactly4,981 complete objects remain identical to v24.

| Record | New raw birthplace | Support | Actually acquired evidence |
|---|---|---|---|
| NA1476, Bernard Smith | Grantham | S3 | Original BGS archive paragraph directly states full name and exact native1881-02-13, with compatible1936 death and distinctive Survey career. The born paragraph has no acquired named author or claim-specific birth authority. |
| NA1611, Leonard Frank Spath | Munich | S3 | Actual William James Kennedy historical conference abstract in the2022 Warsaw volume explicitly names Munich, full subject and lifespan1882–1957. Birthyear1882 only; native October20 is not confirmed by this text. |

Smith's linked authored histories give career context without a birth-place assertion; they are not used to upgrade this uncredited archive paragraph toS2. The page revision2020-09-01 is not original publicationdate. A root first attempt to inspect an observed1938 memoir DOI has no retained verified body; a display filter omitted its final result/status detail. Unknown details are not reconstructed and the route was not retried. It supplies no birthplace proof or grade upgrade.

Spath's source is the separately titled Kennedy abstract actually inside the full2022 scientific abstract volume. The institutional repository's cover metadata describes another deposited contribution and is not the Spath byline. The source is conservativelyS3 because this historical assertion is in a conference abstract without an acquired claim-specific birth-record citation; no civil-record, independent-corroboration or peer-review verification is claimed. Repository2026 download/crawl information is not publicationyear. An unacquired1957 memoir search projection describes unknown birthplace and unconfirmed South Africa hearsay; it is neither original-body corroboration nor an acquired contrary born-place fact, and South Africa is not adopted.

Only Grantham and Munich are directly birth-linked. Smith's survey-work regions and Spath's Oxford affiliation, Croydon upbringing, London work and German-by-birth wording do not assign a birthplace country/entity or hemisphere under the current rule. No personal country, QID or coordinates are added.

## Qualified and provisional date issues

Bisat/NA1090 is the sixth qualified active DOB-source conflict. The original SAGT HTML subject header states1887–1973, while native DOB is1886-10-19. A signed original YPS biography uses1886–1973 and states born in Doncaster; another paragraph on the same SAGT page also uses1886. These compatible observations do not prove a header typo or clear the contrary acquired header. This is a header birthyear conflict, not an exact source born-day conflict. No native birthday, place or hemisphere is changed. The five previous active conflict objects are retained unchanged before Bisat is appended.

Tomes/NA2684 is separately provisional. The original Dental Historian parsed text reads8June1846 versus native6June1846. One cached page screenshot returned only an MCP text marker and no ImageContent/pixels exposed to the worker; the actual printed6/8 glyph was not dependably visually verified. The screenshot is not described as a creation failure. The parsed date and native date remain separate; no literal printed8 quotation, alternate correct-DOB verdict or native/place/geography adoption is made. The safe excerpt contains only the London born clause. `audit/provisional_parsed_date_discrepancies.json` keeps this glyph-uncertainty hold distinct from the six qualified active conflicts, rather than counting it as a seventh confirmed source-date conflict.

| Other held subject | Acquired evidence or limit |
|---|---|
| Richard Assheton | Original journal PDF exceeded the tool size limit; no qualified acquired born-place body. |
| Clive Cuthbertson | Original article carrier supplied no readable body; no birth-place adoption. |
| Percival Spencer Umfreville Pickering | Original obituary routes gave a stub/challenge/unavailable publisher body; an archival catalogue supplies full identity/career but no birthplace. |
| Charles Drummond Ellis | Original reference/memoir routes unavailable; bibliographic leads are not birthplace proof. |
| Alfred William Porter | Original publisher and portrait routes failed; no qualified birthplace body. |
| James Ernest Marsh | Carrier timed out; parents' Rainhill context does not establish the subject's birthplace. |
| George Stuart Graham-Smith | Original authored obituary supplies full name/exact DOB and career but no qualifying birthplace; a father's Indian Army connection is not birth geography. |
| Thomas Wallace | Original routes unavailable; a targeted bibliographic Nature link led to an unrelated McKie article and was not adopted or repaired by guessing another URL. |

The inherited Gotch place conflict, Malet approximate-year hold, Waterfield internal age discrepancy, Midwinter death-endpoint discrepancy, Coles cross-source age contrast and v24 Wager omitted-middle admission record remain byte-identical. No new case invokes that middle-name rule. Native identity, middle-name uncertainty flags and all prior facts remain unchanged; no birth/registration/baptism event is relabelled.

Source work comprises24 queries,29 worker navigation attempts and6 root source opens, totaling35 attempts. Five parsed finds, one cached screenshot and zero raw HTTP/PDF GETs were used. Tomes's screenshot exposed zero ImageContent blocks to that worker, not a verified printed digit. Workers report no protocol deviations. The root optional DOI display-detail loss is disclosed. Actual ledgers/intents and failures remain; there were no failed-route retries, URL variants or access bypass. Unknown raw request status/time/byte hashes remain null. Excerpts contain8 words for Smith and4 for Spath; held Bisat/Tomes excerpts remain within25 distinct English words per original work. No full source HTML/PDF/images or source-projection caches are distributed.

## Files and replay

`outputs/birthplace_rows.jsonl.gz` is the complete current master in the ZIP. CSV projections, changes and summary are alongside it; the remaining-window CSV has185 records. The80 prior CSV columns retain positions/meaning and six v25 birthplace columns are appended. Versioned facts retain previous values and previously absent fields for exact rollback.

```sh
python studies/royal_society_birthplace_completion_v25/scripts/replay.py
```

From the repository root, this self-contained command reconstructs exact v24 from the included v10 carrier and frozen v11–v24 inputs before applying v25. It makes no web requests. Baseline commit is `4c0a23054048645b632bcaccc96f2fe7ae60dfef`; baseline canonical JSONL SHA256 is `77d03a85ab2c959d1fc34732907535c2fa465b36fa6b1ab176bb4e66de6c5d0d`. Gzip uses blank filename/zero mtime. The compressed output master is packaged and reproducible, not duplicated as another Git blob. The manifest excludes itself and Python caches.

Native DOB/calendar, authority identity, fixed cohort/eligibility, original DOB grades, country/QIDs/personal coordinates, prior selected evidence/hash/official-field status, all prior versioned facts and untargeted complete objects remain frozen. No other cohort, cross-cohort statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Source QA is documentary review without another source-acquisition claim. Local QA verifies exact reconstruction, frozen fields, rollback, CSV/counts and two isolated replays.
