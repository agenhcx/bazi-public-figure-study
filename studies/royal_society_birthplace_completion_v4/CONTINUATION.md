# Continue UK birthplace collection after v4

Use `outputs/uk_birthplace_rows.jsonl.gz` in this study as the fixed 4,983-row base. Counts: north 4,112; south 181; unknown 690. Native DOB window 1835–1985 has 2,644 rows: north 2,212; south 176; unknown 256. Do not change native DOB/calendar/formal identity/eligibility fields or DOB source groups during geography work.

Unknown breakdown: 642 with no active birthplace evidence; 48 with explicit birthplace but unresolved geography. A person can be in several academy/prize rosters; no cross-cohort deduplication or final cohort freeze has been performed.

Completed routes to avoid repeating:

- v2 official catalogue birthplace pass: all 4,884 past records; current99 separate source audit.
- v3: 300 previously unread bound enwiki pages; v4: the remaining66 pages, all read. Earlier9 probes are recorded in v3. Use coverage ledgers, not name guesses, for future selection.
- v3: Crossref40 same-journal memoir subjects; v4: a further100 selected window subjects, all HTTP200,26 accepted S2 facts. Exclude both source cohorts before another batch. Bare place names can still have unresolved geography despite explicit born claims.
- v3 original75 geographic holds were reviewed; v4 remaining45 were reviewed,12 resolved. The new48 holds include15 new explicit-but-unresolved places. Do not silently repeat earlier all-name queries or resolve naked London/Paris by fame.
- v3 quarantined23 wrong current-person lookup links and9 derived birthplace candidates. v4 found21 verified replacement active links;22 positive P2070 results include Lauritzen whose active link was already correct. Current state94 active,2 legacy links still quarantined,3 identity unverified. Chen and Timothy Behrens had no exact P2070 result; no-result is not a mismatch claim. Lauritzen has no P19 in the observed complete entity.

For future geography queries use `active_geography_lookup_qid`. Historical `lookup_qid` and `wikidata_qid` intentionally retain the old values; never reuse quarantined old QIDs. For corrected rows the current geographic identity review is updated and the v3 review is retained separately. Old9 candidates must stay inactive even after a correct replacement is found.

All new source facts were independently reviewed. Birthplace grades and geographic grades are separate from native DOB grades. Keep S1/S2 evidence ahead of S3 when comparable; retain disagreements and explicit alternatives. Do not use nationality, affiliation, schooling, family residences, death place, country centroid, or guessed fine birthplace as birthplace evidence. Do not assign birth country or precise birthpoint for hemisphere-only decisions.

Reproduce the outputs with the two one-line commands in README.md. The verifier checks unchanged non-geographic fields and byte-identical replay. Source response/metadata archives are under audit; short quotes and raw-source hashes do not imply full biography text is bundled. Other countries remain unchanged from v3. Continue on the existing draft branch; do not merge it without separate instruction.
