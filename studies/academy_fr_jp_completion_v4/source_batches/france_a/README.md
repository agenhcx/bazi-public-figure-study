# France v4 historical A: membership-only evidence

Baseline: `f5058c523402f1ed6df19df815400969a9c0a4de`. Exclusive queue: `academy_v4_workers/queues/france_historical_a.csv` (60 candidates, all previously accepted identity and DOB, held membership).

The bounded review yields **9 new strict full-membership approvals** (3 exact days, 6 year-only) and **10 additional positive ordinary-role / pre-2025 bounds** whose actual election years remain unresolved. The latter retain `membership_accepted=0`. There are 41 candidates without a positive new decision. This is not a set of 41 nonmembers.

## Review and evidence

`decisions.json` is the canonical replay input. Each positive decision contains source URL, SHA256, page or HTML locator, brief quote, typed role, event type, precision, body verification, identity bridge, and review status. `decisions.csv` is a convenience view. `queue_status.json` covers all 60 baseline cases without treating unreviewed/unresolved cases as exclusions.

`source_manifest.json` inventories all 30 new URL attempts plus two reused original Academy PDFs. The fresh capture budget was 30 unique URLs: 15 real PDFs and one real HTML body succeeded, and 14 URLs returned HTTP404. There were 10 search queries in 3 calls. No network retries or fresh requests were made beyond the bound. Exact query strings were not locally persisted; their retained count/composition is reported transparently in `log.json`.

All successful body hashes were recomputed. All PDF evidence pages and the rejected Charcot title were visually inspected. The actual Academy HTML was read. A shared full-body hash counts as one source regardless of which candidate is its subject or author. The quote total across this metadata is at most 25 words per document. `private/` contains full licensed/source bodies, extractions and review images for local provenance and is excluded from the publishable manifest.

## Distinctions retained

Nonresident members (Depéret, Bataillon, Grignard) and free member Maurice de Broglie retain their full-member subtypes. Earlier correspondent events for Depéret and Bataillon are separate; they do not exclude later full membership. Louis and Maurice de Broglie are separate people. The medical Jean Charcot source does not match the queued polar navigator Jean-Baptiste Charcot; this source assignment is explicitly rejected without excluding the candidate. Tilho’s source also gives the speaker Donatien Cot’s 1946 admission; it is not assigned to Tilho.

The printed Grignard funeral year 1936 is retained as a conservative documentary bound, not silently corrected and not used as an election or death-date acceptance. Memorial/source years for Le Chatelier and other role-only cases are retrospective attestations; they are not assertions of active service in that year. D’Arsonval’s 1917 presidency gives an earlier membership upper bound, not an election date. Candidacy, presidency, foreign academies and document dates are not substituted for election.

No accepted identity or DOB is changed; no date is completed by inference; all original source conflicts and existing holds remain. No lifetime exclusion, BaZi computation or analysis freeze is introduced. No shared repository files were edited.

## Publishable files

Use the relative file list and SHA256s in `MANIFEST.json`. The collector, transcriber, raw fetch log and `private/` are working files and are not included. `source_assignment_rejections.json` is source-assignment QA, not negative membership adjudication. `summary.json` and `log.json` report counts and limits.
