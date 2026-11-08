# France/Japan continuation v15 — 2026-11-01

This bounded continuation starts from immutable v14 commit `2ba3d1161a6151a1f18dccda25e5073411c06f2c`. Root-frozen selection contains two French membership gaps and no Japanese cases. Professor collection remains paused; Fields and Japanese hard routes remain parked. No analysis cohort is frozen, no BaZi variables are computed, and nobody is contacted.

| French working ledger | v14 | v15 |
|---|---:|---:|
| Identity approved | 787 | 787 |
| Exact DOB approved | 775 | 775 |
| Strict ordinary membership | 642 | 643 |
| Identity, DOB and membership all supported | 639 | 640 |
| Remaining multidimensional gaps | 238 | 237 |

## One independent own-subject election

Hélène Bouchiat's ordinary election is accepted at day precision, 30 November 2010, from physical page 4 of the actual Academy-issued 2011 press-release PDF retained in v14. Its governing heading identifies nine ordinary Members elected that day; her own name, CNRS/LPS career and birthday identify the daughter. The newly fetched Academy web profile is a different source: its header identifies Hélène, its role line gives 1986/1988 events, and its biography explicitly names Marie-Anne. That current profile is quarantined for the daughter's event assignment. It is absent from positive membership evidence.

The unavailable historical bad response is not described as re-read. Existing raw flags, source-origin metadata and warnings remain literally unchanged. The new decision appends a separately bound source-assignment disposition. The mother's entire accepted row remains unchanged. The PDF is the sole positive membership source; the mixed profile supplies no accepted birth or election date. All prior 483 membership decisions and 32 individual-case adjudications are inherited in order, with two new membership dispositions appended and no new identity/DOB case.

## A genuine same-subject source conflict remains held

Nicole Le Douarin's newly fetched current Academy profile presents a January 2006 election heading and an ordinary-member line dated 15 February 1982, both assigned to her own subject. Neither event is selected. Her ordinary-membership approval remains zero, with all accepted identity/DOB values preserved.

The inherited `election_date_conflict` field remains its old blank value; it is never normalized or silently rewritten. Separate machine-readable v15 fields retain the unresolved actual-source conflict status, both observed years and the actual source hash. The positive-membership validator blocks that status even when the legacy flag is blank or an acceptance map is missing. Summary fields distinguish 25 inherited formal chronology holds from this one newly observed same-subject source conflict. The Pontifical Academy nomination is not used as a French event.

## Bounded source activity and preservation

Exactly two known Academy profile URLs are fetched once each, with two successful GETs, no redirects, no search queries and no retries. The existing PDF is rehashed and physically read locally. Selection size, HTTP requests, body reviews and approvals remain separate in processing metadata.

The bulk-route and residual-DOB audits are local read-only prospecting, not extra selected batches or a 25- or 73-person birthday search. They make no network requests and supply no new approvals. No new raw birthday claim or birthday adjudication is introduced. The 73 raw missing-day groups, four exact-DOB conflicts, alias-risk groups, all 25 formal chronology holds, father Dangeard's machine-readable 1862-versus-1867 hold, and all prior accepted values remain unchanged. No historical source response, exact day or ordinary role is inferred from metadata.

Japan uses `V14.final_japan()`, preserving 482 identities, 528 structured birth claims, 368 day statuses, 46 holds and all four older calendar outcomes. Scope remains 438 Section II, 10 Section I and 34 unresolved; 104 nonexcluded candidates lack a resolved DOB day and the combined queue contains 112. All three Japan CSVs are byte-identical to v14. These are working-ledger counts, not a national completion claim.

```sh
python3 studies/academy_fr_jp_completion_v15/scripts/continue.py baseline
python3 studies/academy_fr_jp_completion_v15/scripts/continue.py prepare --output-dir /tmp/academy-v15-inputs
python3 studies/academy_fr_jp_completion_v15/scripts/continue.py assemble --output-dir /tmp/academy-v15-outputs
python3 -m unittest discover -s studies/academy_fr_jp_completion_v15/tests -v
python3 studies/academy_fr_jp_completion_v15/scripts/continue.py verify
```

Use fresh output directories. Exact root approvals and independent actual-source QA bind the final decisions, source hashes, assignment dispositions and worker manifest. Preparation includes the complete Japanese claim ledger and both French histories. Verification checks predecessor pins, public metadata inventory, preservation gates and byte-identical replay. `final_japan()` remains the stable complete-state API for a successor. Raw PDFs, HTML and images remain private; deliverables contain bounded factual metadata, hashes and locators.
