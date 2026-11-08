# Royal Society birthplace completion v23

This batch adds one first stored birthplace to the fixed4,983 UK Royal Society records: Bryan Randell Coles, Cardiff, with conservative birthplace-support S3. Geography remains unknown because only the city is directly birth-linked. There is no new North/South classification. Original DOB-source grades and the DOB-based S2 versus S2+S3 panels remain unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,176 | 187 | 620 | 4,983 |
| Native DOB1835–1985, inclusive | 2,276 | 182 | 186 | 2,644 |

The native DOB window now has130 unknown records with blank birthplace and56 with stored birthplace but unresolved geography. Across all records these numbers are552 and68. The initial131-record blank-place pool is a queue, not131 biographies read. Twelve fixed individual subjects were followed up in three groups: one first-birthplace adoption and11 holds. There was no new geography-only pilot, bulk screen or cross-cohort screen. Exactly4,982 complete objects remain identical to v22.

Coles/NA3474 is bound by the primary original Independent obituary's full Bryan Randell Coles, exact native1926-06-09, compatible1997-02-24 deathdate, explicit Cardiff and distinctive Imperial solid-state-physics/Pro-Rector/FRS career. David Edwards's byline was acquired, but the original author-profile link returned404 and no relevant expert/colleague role was acquired. ConservativeS3 is retained; authorship or host alone does not establish expertS2 or S1. University of Wales is education, Imperial London is workplace and London is the death place; none supplies a birth-linked country. The original primary body was verified by worker and root.

The original Felix student-paper tribute separately supplies full name, Cardiff and birthyear1926, with a headline reporting age71. It supplies a relative Monday death, not both exact dates. Conventional arithmetic from the primary Independent exact dates gives70. `audit/cross_source_reported_age_contrasts.json` preserves this cross-source reported-age contrast. It does not label Felix internally inconsistent with its own exact dates, infer an alternate birthdate, correct either source's age or claim informational independence. The separate inherited Waterfield sidecar concerns a different, one-source own-date/age inconsistency and remains byte-identical.

Menter/NA4591 has a newly acquired blocking DOB-source conflict. The original signed Independent obituary's subject vital line states1921-08-02; native DOB is1921-08-22. Full James Woodham Menter, compatible1921–2006 lifespan and electron-microscopy/TIRL/QMC/FRS roles bind the same subject. Its Teynham, Kent birthplace is held, with no birthday or geography adoption. An unopened memoir-title lead agrees with native22August but does not clear the acquired contrary born line. The source date is not corrected or adjudicated here. `audit/active_source_DOB_conflicts.json` preserves the previous Argyris/Laver/Wells objects unchanged and appends Menter as the fourth active conflict. No dateless bypass or death-endpoint-only exception applies to a birthday-day discrepancy.

| Other held subject | Acquired evidence or access limit |
|---|---|
| Stanley Desmond Smith | Original2025 memoir DOI returned403; no qualified full born-place body acquired. |
| Michael George Hall | Original short RS profile has career/death context but lacks the full native name/date/birthplace gate. |
| Rex Malcolm Chaplin Dawson | Full-name/date memoir metadata and abstract do not supply acquired born-place fulltext; Stoke Golding refers to growing up. Original routes were unavailable. |
| Robert Francis Hudson | No bound original biographical birth-place body acquired; a musician's different-person discovery lead was not adopted or treated as the target's DOB conflict. |
| Cecil Edwin Henry Bawn | Original memoir and Who Was Who DOI routes unavailable; discovery identity/date references are not born-place proof. |
| John Arthur Joseph Pateman | Original tribute timed out, memoir route unavailable and carrier returned no readable lines; no missing-middle-name expansion or born-place inference. |
| Henton Morrogh | Memoir unavailable, Japanese tribute timed out, and institutional people page has name/photo only. Workplace and patent affiliations are not birthplace. |
| Phillip Sadler Nutman | Original PDF restricted and publisher route inaccessible. The search projection's Phillip spelling matches native; no original born body or manufactured identity/DOB conflict. |
| Frank Reginald Farmer | Original16-page newsletter returned no readable text; one cached award-page screenshot yielded no dependable verified birth relation/date/place. Unreadable-body hold, not a claim the source contains no birthplace. |
| Charles Gorrie Wynne | Original obituary confirms full name/exact DOB/death but no birth relation; Leicester describes work/school context. Other original article routes provided metadata/unsupported preview or failed. |

The inherited Waterfield internal age inconsistency, Midwinter death-endpoint discrepancy and all prior facts remain unchanged. No source-grade or DOB exception is introduced in this batch. Only the precision of the Coles cross-source age comparison and Menter's explicit day conflict required a documentary method note.

Source work comprises24 discovery queries,27 worker navigation attempts and3 root source opens, totaling30 navigation attempts. There were zero parsed finds/raw HTTP/PDF GETs and one cached screenshot attempt. The screenshot supplied no qualifying birth fact; no unsupported count of usable image blocks is asserted. Requests, prior intents and exact failures are retained, without retries, URL variants or access bypass. Unknown raw request time/status/byte hashes remain null. Source excerpts contain5 words for accepted Coles and6 for held Menter; no extra Felix prose excerpt is distributed. No full source HTML/PDF/images, source-projection caches, contacts or family details are redistributed.

## Files and replay

`outputs/birthplace_rows.jsonl.gz` is the complete current master in the ZIP. `outputs/birthplaces.csv` is a readable projection and `outputs/remaining_unknown_window.csv` contains186 records. `outputs/changes.json` and `outputs/summary.json` report exact deltas and counts. The68 prior CSV columns retain their positions and meanings; six v23 birthplace columns are appended. Existing geography-support columns remain separate and unchanged. The new versioned fact contains previous values and previously absent fields for reversible current-field updates.

Run from the repository root:

```sh
python studies/royal_society_birthplace_completion_v23/scripts/replay.py
```

Replay reconstructs exact v22 using the included v10 carrier and frozen v11–v22 inputs before applying v23. It makes no web requests. Baseline commit is `b3c22b66be309470b5e17ad1d0f681bf71ed581f`; baseline canonical JSONL SHA256 is `728502a5f0a71570a262a894dc800a9073ff19bbba68e2c7a7dd7027a5f8f2b9`. Gzip uses a blank filename and zero mtime. The complete compressed output master is packaged for download and reproducible by code, rather than duplicated as another Git blob. `MANIFEST.sha256` covers distributed files except itself and excludes Python caches.

Native DOB/calendar, authority identity, fixed cohort/eligibility, original DOB grades, country/QIDs/personal coordinates, prior selected evidence/hash/official-field status and every prior versioned fact remain frozen. Only Coles's declared current birthplace fields and versioned rollback fact differ. No other cohort, cross-cohort statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Independent source QA reviews worker/root documentary observations without claiming another source acquisition; independent local QA verifies exact reconstruction, frozen objects, rollback, CSV/counts and two isolated replays.
