# Royal Society birthplace completion v24

This batch adds five first stored birthplaces to the fixed4,983 UK Royal Society records: three birthplace-support S2 observations and two S3 observations. One resolves North; four retain unknown geography. Original DOB-source grades and the DOB-based S2 versus S2+S3 panels are unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,177 | 187 | 619 | 4,983 |
| Native DOB1835–1985, inclusive | 2,277 | 182 | 185 | 2,644 |

The window now has125 unknown records with blank birthplace and60 with stored birthplace but unknown geography. Across all records these numbers are547 and72. The initial130-record blank-place pool is a queue, not130 biographies read. Twelve previously unreviewed historical subjects were followed up: five adoptions and seven holds. Four were worker candidates; Wager was admitted separately under the explicit identity-binding amendment below. Worker reports retain their original strict hold. There was no new geography-only pilot, bulk screen or cross-cohort screen. Exactly4,978 complete objects remain identical to v23.

| Record | New raw birthplace | Birthplace support | Geography | Actually stated date precision |
|---|---|---|---|---|
| NA2863, Sir Alexander Pedler | 197 Fleet Street, London | S2 | Unknown | Exact native1849-05-21 in Roy M MacLeod's signed ODNB public Extract; source deathyear1918 only. |
| NA5494, Arthur Harry Church | Plymouth | S3 | Unknown | Birthyear1865 from subject lifespan context; native March28 is not confirmed by the council collection page. |
| NA6655, Charles Edward Groves | Highgate | S2 | Unknown | Birthyear1841 only in A.H.Tubby's signed original Alpine Journal memorial; native March4 is not confirmed. |
| NA6941, Edmond Herbert Grove-Hills | London | S3 | Unknown | Exact native1864-08-01 in an explicit named-child paragraph of Kevin Grice's compiled regional entry. |
| NA8294, native Harold William Taylor Wager | Stroud in Gloucestershire | S2 | North | Original obituary actually names Harold Wager and gives exact native1862-03-11 with compatible1862–1929 lifespan. Native middle names are unconfirmed in that source. |

All geography decisions use direct birth-linked country/whole-region context. London, Plymouth and Highgate alone remain unknown. Gloucestershire is explicitly attached to Wager's birth. No country is inferred from nationality, relatives, schooling, employment, death place, a familiar city or a source footer, and no personal country/QID/coordinates are assigned.

## Wager identity-binding amendment

The initial full-native-component rule correctly held Wager because the original source omits William and Taylor. After observing that hold, reading the actual original source and receiving independent documentary method review, the parent explicitly adopted a generic bounded omitted-middle-name exception before writing final facts. It is not source-blind preregistration or a claim that the original rule already allowed the case.

The exception requires a complete observed first name and surname matching native, exact unchanged native DOB, actually compatible lifespan, a coherent distinctive professional/fellowship fingerprint, a unique first/surname/exactDOB match in the fixed cohort and no competing person or contradictory name/birthdate/place observed. Only internal middle components may be omitted; initials, aliases or conflicting names are not expanded. All existing source-quality, explicit-birth, geography and rollback gates remain required.

Wager alone qualifies among this batch's12 records. The source actually states Harold Wager, born March11,1862, died November17,1929, with RS fellowship1904, Leeds botany1888, society presidencies and education-service context. These career details are source-only anchors; the native row does not independently corroborate all of them. The fixed-cohort name/date lookup has one match and is not a claim of global uniqueness or statistical deduplication. The source name remains short, William/Taylor remain explicitly unconfirmed, the signature A.C.S. is not expanded, and the native authority string/key/DOB/eligibility stay unchanged. No previous hold is automatically cleared. See `audit/omitted_middle_name_admission.json` and `audit/method_qa.json` for gates, timing and limits.

## Source and conflict limits

Church's original council body was read by the worker; the later root first open returned403 and was stopped. The earlier observation supplies proof, with no independent parent body/rawHTTP200/version-change claim. Groves's root parser reads bgrn; the worker inspected the cached original page image and verified born. The quotation follows that image observation, with the OCR/image roles explicit and no redistributed screenshot. The original signed edited club-journal memorial is S2, not civil registration or a peer-reviewed chemical memoir claim.

Grove-Hills's explicit child birth assertion is distinct from parent/family locations. The compiled entry receives conservativeS3 despite a named author. An unrelated parent-entry heading/body deathyear mismatch and an unacquired Nature deathday lead remain source caveats; they are not a child DOB conflict, native deathdate correction or independent corroboration. Source publicationdate is unknown. Pedler uses the original public ODNB Extract only, not a paid full chapter/PDF. Wager's original published obituary was read on an external carrier; the2021 download stamp is not its unknown original publicationdate.

McClelland/NA5506 adds a fifth active DOB conflict. The original RTI book chapter explicitly states birth on1870-11-18 and separately baptism on December1 without repeating that year in the baptism clause. The authored DIB entry supplies birthyear1870 only and explicitly labels1870-12-01 as baptism. Native DOB is1870-12-01. Correspondence of native date with the observed baptism is not a proven parser-error/provenance or correct-date verdict. No date or event type is corrected, no baptism is relabelled birth and no birthplace/geography is adopted. RTI's Macosquin-near-Coleraine and DIB's Dunalis/Dunboe wording remain separate without a geographic-equivalence/conflict adjudication. DIB is not represented as independent exactNovember18 confirmation.

Gotch/NA6228 remains held for a different issue: two acquired original bodies explicitly disagree on birthplace. Jan Marsh's NPG biography states Liverpool with exact native1853-07-13; Austin Elliott's Physiology News column states Bristol with compatible year/lifespan. Neither city is chosen or merged, and no DOB conflict is manufactured. `audit/birthplace_source_conflicts.json` covers this new v24 case, not an exhaustive global inventory. Malet/NA6648 has a circa1845 local-history claim versus native exact1847-12-25; no tolerance was stated. It remains a precision/binding hold rather than an invented exact1845 conflict or compatible interval. Brown, Procter, Veley and Festing lack qualified acquired birth-place bodies. Search projections, nationality, associated places and photographs are not adopted evidence.

The prior Argyris/Laver/Wells/Menter conflict objects are unchanged. The three distinct inherited Waterfield internal-age, Midwinter death-endpoint and Coles cross-source-age sidecars are byte-identical. No original DOB-source grade, prior fact or date verdict changes.

Source work comprises24 queries,26 worker navigation attempts and12 root source/context opens, totaling38. Four parsed finds, one cached screenshot attempt and zero raw HTTP/PDF GETs were used. Groves's screenshot was inspected for the birth word; no image is distributed. One A-group context intent was logged late. B discloses a minor query-text variation and lost abbreviated carrier-error text; unknown details are not reconstructed. Actual ledgers/intents remain. Failed routes were stopped without retries, variants or bypass. Raw request status/time/byte hashes remain null where unknown. Excerpts remain at most25 distinct English words per original work; no original full HTML/PDF/images or source-projection caches are distributed.

## Files and replay

`outputs/birthplace_rows.jsonl.gz` is the complete current master in the ZIP; CSV projections, exact changes and summary are alongside it. The remaining-window CSV contains185 records. The74 prior CSV columns retain positions/meaning and six v24 birthplace columns are appended. Versioned facts include previous values and previously absent fields for complete rollback.

```sh
python studies/royal_society_birthplace_completion_v24/scripts/replay.py
```

From the repository root, this self-contained command reconstructs exact v23 from the included v10 carrier and frozen v11–v23 inputs before applying v24. It makes no web requests. Baseline commit is `d0933cbe05a4a6549ac66a6c9078fbbb822666bf`; canonical JSONL SHA256 is `9547b9e958d6526acf578a20f3b42e63e5a95de3aeca91a3c244d9620ee7ab01`. Gzip has blank filename/zero mtime. The output compressed master is packaged and reproducible, not duplicated as another Git blob. The manifest excludes itself and Python caches.

Native DOB/calendar, authority identity, fixed cohort/eligibility, original DOB grades, country/QIDs/personal coordinates, prior selected evidence/hash/official-field status, all prior versioned facts and untargeted complete objects remain frozen. No other cohort, cross-cohort statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Source QA is documentary review of worker/root observations, without another source-acquisition claim. Local QA verifies exact reconstruction, frozen fields, rollback, CSV/counts and two isolated replays.
