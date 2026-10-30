# France/Japan continuation v10 — 2026-10-30

This collection-only continuation starts from immutable v9 commit `c8d38ab3db34270d39d1c39e2aa368de612edc3f`. Prior source files and decisions remain unchanged. Professor collection remains paused and Fields data remain parked. No analysis cohort is frozen, no BaZi features or outcomes are computed, and nobody is contacted.

## Results

| Working ledger | v9 baseline | v10 |
|---|---:|---:|
| France strict ordinary membership | 394 | 408 |
| France identity, birth and membership all supported | 392 | 405 |
| France accepted exact DOB | 744 | 743 |
| Japan direct/broad Section II support | 428 | 438 |
| Japan section unresolved | 47 | 37 |
| Japan day statuses without known unresolved conflict | 368 | 368 |
| Japan broad Section II plus day status | 355 | 360 |
| Japan combined date/section queue | 120 | 115 |

France adds 14 strict memberships from 82 individually queried fixed candidates. The24 new membership decisions comprise 14 strict approvals and 10 holds. The remaining 58 people were queried without a new qualifying membership decision. All25 inherited election chronology holds remain. There are 877 stable French candidate groups, 755 identity approvals and 472 people whose three dimensions are not all supported; 472 is not a missing-birthday count.

One new source conflict is quarantined independently of membership. For Darius Paul Dassault (`CTHS_112065`), the actual CTHS body states 1882-01-13 while the actual Academy notice image states 1882-01-18. The CTHS entry credits/cites the same Academy material, so these are not treated as independent votes. Both source expressions and the prior accepted13 January value remain explicit. The accepted DOB is cleared, `dob_accepted` becomes 0 and the existing conflict convention records both dates; neither day is selected. His separately supported 1953 membership remains accepted, but he is excluded from the all-three table. All other people's DOB fields remain unchanged. `inputs/france_dob_conflict_approvals.json` and the prepared decision bind the exact person, old value, two captured bodies and an independent original/image QA report.

Japan adds ten exact Section II attestations from the Academy-issued1906 directory digitized by NDL. Actual cover and same-column person/第二部 images were read by the collector, root and an independent reviewer; the volume is1906, not the 1912 endpoint of generic series metadata. The 10 identities were previously section-unresolved. No known section is overwritten, no degree rule is extended, and no exact current subsection is inferred. This is a1906 snapshot attestation, not a back-projected section at an earlier Tokyo Academy election. Ito Keisuke and the older 36-person unresolved group retain their prior scope state.

Japan retains 482 stable identities, seven Section I exclusions and 475 nonexcluded science-or-unresolved candidates. Its 528 birth claims for 433 people and 368 day statuses remain unchanged: 215 institution/university/organization supported, 150 edited-reference-only and three other attributed-secondary-only. All 46 inherited birth holds remain, as do all four earlier exact calendar outcomes. There are 107 nonexcluded cases without a day status; the combined queue falls by five because five of the newly scoped identities already had day-level evidence. These are working restored-universe counts, not a frozen national denominator.

## Actual search and review coverage

France's 82 fixed people all have individual targeted queries. They close the 89-person historical-query-coverage-unknown membership-gap subset down to seven inherited chronology-held cases that were deliberately not queried in this round. Unknown historical coverage does not mean never searched. The 68 newly queried people still lacking strict membership are parked with known query history, not relabeled unsearched. Earlier searched-and-parked groups remain separate.

All 47 selected Japanese unresolved identities received local scope triage. Five received new individual scope queries;12 had new scope-source body review. Fifteen people have completed new source-route dispositions, including queries or body reviews. The other 32 received local review only. There were zero birthday searches, zero new birth body claims, and zero new DOB-processing IDs. Source/scope activity is not counted as birthday processing.

Each French batch has an external independent QA report in `source_audits`; the ring reviews A→B, B→C and C→A. Japan's source proposals and the Dassault source pair each have separate independent QA. Frozen collector handoff files may still say their own approval was pending. The externally bound final reports, root approval files and integration audits record final approval without rewriting the reviewed source batches.

## Replay architecture and evidence gates

v10 first reconstructs the complete approved v9 structured ledger with immutable v9 code, then passes that ledger to the original DOB reducer with all effective current hold statuses/reasons and the original NDL authority dictionaries. It does not reconstruct from V4's older overlays. This retains the approved Terao original-V2 routing outcome without reintroducing that old hold or copying a previous selected date over new contradictions. A synthetic new comparable contradiction still produces a conflict. Prior source flags and all 528 inherited claims remain unchanged.

A successor can call `V10.final_japan()` to reconstruct the complete final state, including the ten scope decisions. A direct three-argument `V10.japan(...)` call omits the optional scope actions and is reserved for birth-baseline tests; it is not the final v10 scope state.

The exact attributed-university-publication reproduction tier stays in other-secondary through the inherited v9 classifier. It is not promoted to institution-hosted or dictionary evidence. New scope actions require an exact identity/source/hash/printed-name/edition allowlist, currently unresolved state, root approval, actual final proposal/worker-manifest/QA hashes and per-person visual/identity/year-overlap checks. They may alter only the two scope classification fields plus new v10 provenance, followed by scope/queue recounting. Birth status, date, source tiers, membership dates and NDL identity evidence do not change.

The French DOB quarantine has a separate exact one-person gate. Its source-pair and QA hashes, old accepted value and observed competing dates must all match. It cannot choose a new date or alter another identity. Membership approval still requires a same-body Academy/Institut-issued ordinary-member event with an actual election/start day or year. Author titles, generic section seats, correspondence/foreign roles, as-of bounds and relative-year arithmetic cannot substitute. Existing Gravier/Chardonnet typing holds remain.

## Offline reproduction

```sh
python3 studies/academy_fr_jp_completion_v10/scripts/continue.py prepare --output-dir /tmp/academy-v10-inputs
python3 studies/academy_fr_jp_completion_v10/scripts/continue.py assemble --output-dir /tmp/academy-v10-outputs
python3 -m unittest discover -s studies/academy_fr_jp_completion_v10/tests -v
python3 studies/academy_fr_jp_completion_v10/scripts/continue.py verify
```

Use fresh output directories. Preparation writes 11 pinned inputs, including `japan_section_decisions.json` and `france_dob_conflict_decisions.json`. Assembly writes eight deterministic country outputs. Verification checks the complete metadata inventory, every predecessor pin and an exact byte replay. Private raw PDFs/HTML/images remain outside this deliverable; only hashes, locators and short evidence metadata are included.
