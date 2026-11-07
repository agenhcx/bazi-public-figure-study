# France/Japan continuation v8 — 2026-10-29

This collection-only continuation starts from immutable v7 commit `37adc745748718db64fb85bc81c44bc07356b157`. It preserves all earlier evidence, section decisions, public identity keys and source-calendar expressions. No analysis cohort is frozen and no BaZi variables are computed. Professor collection remains paused; the Fields ledger remains parked.

## Fixed selection and bounded searches

The fixed queues contain 26 French candidates whose prior v5 processing was explicitly cache-only and 21 Japanese calendar-held candidates whose v7 review did not include a fresh targeted search. Selection is not itself evidence that a new query or source review was completed. The final processing summary records each person's actual disposition and the collectors' numeric activity separately. Any cross-source acceptance is counted outside these fixed queues.

## Reviewed results

All 47 fixed candidates received a new targeted search: 26 in France and 21 in Japan. France gains five strict ordinary memberships within its fixed queue and one extra cross-source approval for Jean-Louis Faure, counted separately. Strict membership approvals rise375→381 and all-three approvals373→379; birth approvals remain744. There are498 all-three gaps, not498 missing birthdays. Seven new membership decisions include one held as-of event; all25 inherited chronology holds remain.

Japan gains two source claims,525→527, with body evidence still covering433 people. The exact NNAC conference source supplies Adachi Buntaro's old/new date pair, releasing one inherited automatic calendar route to1865-08-01. The source does not literally name the modern calendar and is conference teaching material, not a peer-reviewed paper; unrelated chronology errors are disclosed in its claim. Root and independent review approved only the exact member/source/date. Day statuses rise366→367:215 institution/university/organization-supported,150 edited-reference-only and two other attributed-secondary-only. Nonexcluded cases without a day status fall109→108, and the combined date/section queue121→120. Nakamura Kiyoo gains a different old-calendar day expression; both old expressions stay noncomparable and the calendar hold remains.

The former26 cache-only French priorities have now all been individually queried;21 remain membership gaps and are parked. The earlier151-person subset with unknown historical person-level search coverage now has150 current gaps after the extra Faure approval. Unknown coverage does not mean never searched. The pinned coverage-closure audit records the exact identities and limits.

Each lane's final claim/decision and worker manifest hashes are bound by an external independent QA report in `source_audits`. Frozen worker summaries may still say their own handoff QA was pending; the external final QA reports and integration audit record the completed review without rewriting the reviewed worker files.

## Baseline and evidence rules

The v7 baseline has 877 French candidates, 755 identity approvals, 744 day-level birth approvals, 375 strict ordinary-membership approvals and 373 people with all three dimensions. All 25 inherited election chronology holds stay held.

Japan retains 482 stable identities: 428 broadly supported Section II, seven known Section I exclusions and 47 section-unresolved candidates. This is a working restored universe, not a frozen national denominator. The v7 baseline has 525 birth claims for 433 people and 366 day statuses without a known unresolved conflict: 214 supported by an institution, university or organization, 150 with edited-reference-only day evidence and two with other attributed-secondary-only day evidence. There are 109 nonexcluded candidates without an accepted day status; these include partial dates and unresolved calendar/conflict cases.

All source bodies require a same-person career bridge. New French membership approvals require an Academy/Institut original, an ordinary-member subtype and a directly stated election or membership-start date/year. Correspondent/foreign events, presidency, as-of bounds, author titles and derived arithmetic are insufficient. Existing identity/DOB approvals and chronology conflicts are not adjudicated in this batch.

A Japanese four-digit birth year does not establish a Western month/day before 1873. No collector calendar conversion, date padding or majority adjudication is performed. The exact two source-supplied calendar pairs approved in v7 are inherited with all original claims unchanged. Every other inherited hold is retained unless an exact root-approved, independently reviewed routing decision is added and pinned. Private raw source captures remain outside this deliverable; public metadata contains hashes, locators and short excerpts only.

## Offline reproduction

```sh
python3 studies/academy_fr_jp_completion_v8/scripts/continue.py prepare --output-dir /tmp/academy-v8-prepared
python3 studies/academy_fr_jp_completion_v8/scripts/continue.py assemble --output-dir /tmp/academy-v8-replay
python3 -m unittest discover -s studies/academy_fr_jp_completion_v8/tests -v
python3 studies/academy_fr_jp_completion_v8/scripts/continue.py verify
```

Use fresh output directories. Preparation checks all predecessor pins and reconstructs nine public inputs from reviewed worker batches. Assembly writes eight deterministic outputs. Verification checks every deliverable hash, prevents redistribution of private/raw captures and compares the outputs byte for byte with a fresh offline replay. No network retrieval is performed by these commands.
