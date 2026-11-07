# Royal Society birthplace completion v22

This batch adds two first stored birthplaces to the fixed4,983 UK Royal Society records. Both new birthplace-support grades are S2. One resolves North; one remains geographically unknown. Original DOB-source grades and DOB-based S2 versus S2+S3 panels are unchanged.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,176 | 187 | 620 | 4,983 |
| Native DOB1835–1985, inclusive | 2,276 | 182 | 186 | 2,644 |

The native DOB window now has131 unknown records with blank birthplace and55 with stored birthplace but unresolved geography. Across all records these numbers are553 and67. The initial133-record blank-place pool is a queue, not133 biographies read. Eight fixed individual subjects were followed up: two first-birthplace adoptions and six holds. There was no new geography-only pilot, bulk screen or cross-cohort screen. Exactly4,981 complete objects remain identical to v21.

| Record | New raw birthplace | Birthplace support | Geography | Evidence |
|---|---|---|---|---|
| NA4747, Sir Derek Harry Roberts | 24 Polygon Avenue, Ardwick, Manchester | S2 | Unknown | Michael Pepper's original signed ODNB public Extract gives full name, exact matching DOB and birth address. No birth-linked country/whole-region qualifier is acquired. |
| NA3635, Alan Marmaduke Wetherell | South Shields, England | S2 | North | James V. Allaby's original published scientific-society memoir was read by a worker as parsed PDF on the CERN repository. Full identity, exact DOB and explicit birth-linked England are observed. |

Roberts's birthplace source supplies the compatible1932–2021 lifespan header and exact1932-03-28 birthday. A separate worker-acquired original UCL tribute supplies exact deathdate2021-02-17 and career identity context; it is not represented as independent birthplace confirmation. Only the public ODNB Extract was read, not its paid full chapter or PDF. No country is inferred from workplace, relatives, education or the familiar city name.

Wetherell has an explicit acquisition limit. The worker first read the original memoir body, including full Alan Marmaduke Wetherell, matching1932-12-31, compatible1998-09-13 deathdate, direct birthplace, byline/author CERN affiliation, journal volume/pages/copyright/DOI and professional collaboration context. The later root first open of the same URL returned an Anubis HTML challenge rather than the PDF body and was stopped. Adoption relies on the earlier worker original parsed-PDF observation. No independent parent PDF-body/byte verification, raw HTTP200, exact retrieval time, byte hash or source-version-change claim is made. The worker body reference and later root challenge are separately identified in the accepted fact and audits. There was no retry, cached-ref reopening, URL variant or access bypass. This applies the existing documentary-verification scope, rather than a new DOB or source-grade exception.

The memoir's original journal header gives2000 publicationyear. The DOI/filename1999 and repository download stamp01February2023 are not substituted as publicationdate. CERN is the carrier of an authored original published memoir; host identity alone does not confer S1. No original PDF/HTML/images or source-projection cache is distributed.

Six records remain held. Barnard's original UCL obituary supplies full identity/exact DOB but no birthplace; South London describes orphanage upbringing. Ridley's original repository metadata identifies an authored memoir and dates but no birthplace, and its full attachment exceeded the tool size limit. Hewitt's memoir/award routes failed; two distinct root followups yielded a signed IChemE career obituary without birthplace/exact DOB/full middle component and a failed December award profile. Warrington/England remains search-only. Bagshawe's Lancet, BMJ and distinct RS memoir routes were unavailable; Marple near Manchester/UK remains search-only. Hunt's original college entry states the exact birthdate but no place; its memoir body was unavailable. Lilly's archival catalogue exceeded the size limit and the memoir body was unavailable. An unopened catalogue-title year projection is an unverified lead, not an acquired original-body DOB conflict or a cleared discrepancy. The final hold records preserve these distinctions.

All three active DOB-conflict records—Argyris, Laver and Wells—are copied unchanged in `audit/active_source_DOB_conflicts.json`. Waterfield's reported82 versus computed81 age inconsistency and Midwinter's unresolved death-endpoint discrepancy are inherited separately and unchanged. No date correction, source-header verdict or dateless bypass occurs here.

Source work comprises12 discovery queries,16 worker navigation attempts and4 root source opens, totaling20 navigation attempts. Two parsed finds, zero screenshots and zero raw HTTP/PDF GETs were used. Root made no discovery query. Requests, prior intents and failures are recorded. Unknown raw status/time/byte hashes remain null; tool errors and challenge representations are separate from raw HTTP evidence. Failed routes were stopped. Source excerpts contain12 words for Roberts and10 for Wetherell, repeated without extra distinct source prose. No family/contact details or full original sources are redistributed.

## Files and replay

`outputs/birthplace_rows.jsonl.gz` is the complete current master included in the ZIP. `outputs/birthplaces.csv` is a readable projection, and `outputs/remaining_unknown_window.csv` contains186 records. `outputs/changes.json` and `outputs/summary.json` report exact deltas and counts. The62 prior CSV columns retain their positions and meanings; six v22 birthplace columns are appended. Existing geography-support columns remain separate and unchanged. Each new versioned fact includes previous and previously absent fields for reversible current-field updates.

Run from the repository root:

```sh
python studies/royal_society_birthplace_completion_v22/scripts/replay.py
```

Replay reconstructs exact v21 using the included v10 carrier and frozen v11–v21 inputs, then applies v22. It performs no web collection. Baseline commit is `065a8a5e438b6fadb85756df6ad513fb9aba27ae`; baseline canonical JSONL SHA256 is `91b14b75fa13811abed8122644ed4b10f739fef5695ee72ed62ad5fd296bcac2`. Gzip uses a blank filename and zero mtime. The complete compressed output master is packaged for download and reproducible by code, rather than duplicated as another Git blob. `MANIFEST.sha256` covers distributed files except itself and excludes Python caches.

Native DOB/calendar, authority identity, fixed cohort/eligibility, original DOB grades, country/QIDs/personal coordinates, prior selected evidence/hash/official-field status and every prior versioned fact remain frozen. Only the two declared current birthplace/geography updates and their versioned rollback facts differ. No other cohort, cross-cohort statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Independent source QA reviews worker/root documentary observations, without claiming another original-source acquisition. Independent local QA verifies exact reconstruction, frozen objects, rollback, CSV/counts and two isolated replays.
