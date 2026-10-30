# France/Japan continuation v11 — 2026-10-30

This collection continuation starts from immutable v10 commit `eb4c24192a2bf111e3b47bc02c57c8950e4ef89d`. Prior evidence and decisions remain unchanged. Professor collection remains paused and Fields data remain parked. No analysis cohort is frozen, no BaZi variables are computed, and nobody is contacted.

| Working ledger | v10 | v11 |
|---|---:|---:|
| France strict ordinary membership | 408 | 604 |
| France identity, birth and membership all supported | 405 | 601 |
| France accepted exact DOB | 743 | 743 |
| Japan broad Section II support | 438 | 438 |
| Japan Section I exclusions | 7 | 10 |
| Japan section unresolved | 37 | 34 |
| Japan day statuses without known unresolved conflict | 368 | 368 |
| Japan Section II plus day status | 360 | 360 |
| Japan combined date/section queue | 115 | 112 |

France adds196 strict memberships from307 fixed eligible membership gaps: A70, B67 and C59. The225 new decisions comprise196 approvals and29 holds;82 other cases receive parked dispositions. All755 identity approvals,743 accepted birthdays and25 inherited election chronology holds remain. The877 stable candidate groups now include601 all-three records and276 remaining multidimensional gaps. The Dassault13/18January1882 birthday conflict remains quarantined with neither day selected, alongside the older birthday conflicts.

The French batch makes307 direct CTHS URL attempts and retrieves306 successful HTML bodies; Debré's original request returns500. These are contribution-body audits, with zero new person search-engine queries in the three fixed batches. The failed retrieval is an explicit processed route outcome, not a successful body review. Separate bounded role-control lookups have their own activity metadata. Historical individual-query coverage is retained separately; body retrieval is not relabeled a new person query.

CTHS hosting alone cannot qualify a source. A positive requires the same actual HTML to identify the preserved person, a typed ordinary/free/nonresident Science506 membership, an unambiguous literal full-member start, and an exact institutional writer or co-writer credit in the bounded Rédacteur(s) block. Academy contributions and parent Institut de France contributions have distinct provenance flags; an Institut-only credit is not described as Academy authorship. A personal affiliation or a similarly named local academy cannot substitute for the institutional writer token. All196 positive bodies and their birth lines were independently reparsed, in addition to the A→B, B→C, C→A manual source QA.

A separate earlier correspondence phase can precede an explicit later full-member start. A presidency year, untyped interval, as-of bound or relative-year arithmetic cannot supply that start. Same-body or inherited explicit nonordinary evidence for the same event blocks acceptance. Exact Casimir and Chagas controls preserve their holds: Casimir has literal Academy foreign-associate evidence; Chagas's institutional interpretation uses the same-publication Paris/Germain bridge documented in its control report. Bronk's bounded lookup remains inconclusive and does not create a foreign-class claim. These controls do not claim complete detection of every membership-class ambiguity or infer lifetime exclusions.

Japan locally triages all37 unresolved scope cases. Two people receive individual scope queries (four queries), with five further bulk-source queries: nine queries and11 distinct URL attempts yield nine actual captures and two manifest404 responses. Six images receive visual review. Six people have completed new source-route outcomes;31 receive local triage only. There are zero birthday searches, zero new birth claims and zero DOB-processing IDs.

The1947 Academy directory digitized by NDL directly places 高柳賢三, 上野直昭 and 高橋誠一郎 in 第一部. Exact names and printed election dates match the three preserved unresolved identities. Root and independent QA approve only these three source/hash-bound Section I actions. The cover prints April1947, but later entries elsewhere prevent treating that month as a universal snapshot cutoff. These are1947 directory attestations; no section is projected back to an earlier election, no exact subsection is inferred, and no DOB or election date changes.

Japan retains482 stable identities,528 birth claims for433 people,368 day statuses and all46 birth holds. Day evidence stays split215 institution/university/organization,150 edited reference only and three other attributed secondary. All four earlier calendar outcomes remain. The472 nonexcluded candidates include104 without day status; this decrease from107 reflects the three Section I exclusions, not newly found birthdays. The combined queue is112. These are restored working-universe counts, not a national completion claim.

The replay starts with `V10.final_japan()`, preserving all ten v10 scope gains, actual NDL dictionaries and every old claim/field. Effective hold statuses and reasons enter the original reducer. Old selected dates are never copied over a new comparable contradiction. A successor should use `V11.final_japan()` for this complete final state. Frozen collector proposals may still record pending approval; the separate hash-bound root approvals and independent QA record final application without rewriting source handoffs.

```sh
python3 studies/academy_fr_jp_completion_v11/scripts/continue.py prepare --output-dir /tmp/academy-v11-inputs
python3 studies/academy_fr_jp_completion_v11/scripts/continue.py assemble --output-dir /tmp/academy-v11-outputs
python3 -m unittest discover -s studies/academy_fr_jp_completion_v11/tests -v
python3 studies/academy_fr_jp_completion_v11/scripts/continue.py verify
```

Use fresh output directories. Preparation writes11 deterministic inputs and assembly writes eight outputs. Sixteen tests cover baseline preservation, source origin, role conflicts, scope approval and conflict reduction. Verification checks all predecessor pins, the complete metadata inventory and byte-identical replay. Raw PDFs, HTML and images remain private; deliverables contain hashes, locators and bounded evidence metadata.
