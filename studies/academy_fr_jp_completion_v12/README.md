# France/Japan continuation v12 — 2026-10-30

This collection continuation starts from immutable v11 commit `070239774f4fff72daea231e836796ef3ae8fc62`. It preserves all predecessor files, original claims and earlier decisions. Professor collection remains paused and Fields data remain parked. No analysis cohort is frozen, no BaZi variables are computed, and nobody is contacted.

| French working ledger | v11 | v12 |
|---|---:|---:|
| Identity approved | 755 | 780 |
| Exact DOB approved | 743 | 768 |
| Strict ordinary membership | 604 | 638 |
| Identity, DOB and membership all supported | 601 | 635 |
| Remaining multidimensional gaps | 276 | 242 |

The 52 fixed French cases comprise 26 expanded-notice membership reviews and 26 separate individual identity/DOB reviews. Batch A adds nine strict memberships and retains 17 role/start holds. Batch B adds 25 individually approved identity/DOB cases and their separately supported ordinary memberships; one father/son source conflict remains entirely held. The 34 membership gains retain 15 year-precision starts and 19 directly observed days. Douvillé is 1907-04-29; Glangeaud is 1968 at year precision.

The 25 new DOB approvals adjudicate unchanged singleton dates already present in the raw ledger. They are not 25 newly discovered raw birthdays. Original day-claim sets, source-origin/firstparty flags, legacy identifiers and candidate groups are unchanged. Every earlier approved identity/DOB and all 604 earlier strict membership rows remain intact, as do the 25 election chronology holds and four exact-DOB conflicts. Dassault's13/18January1882 conflict still selects neither date.

## Expanded CTHS notice components

Batch A makes 26 observed expanded-biography GETs, all 200, and reuses the 26 captured parent notices. All 52 originals are rehashed and read. The parent notice supplies the exact institutional writer/co-writer credit and identity/DOB; its actual subject-specific expansion handler links the separately captured biography. The code validates exact q/id/dep/target continuity, both original hashes/statuses/times/bytes, preview/career continuity and component-specific ordinary-role/start locators. The combined bundle is one authorial notice, not two independent sources. Cached parent and fresh fragment times remain distinct.

This is explicitly a two-response method. The old same-HTTP-body flag must be false. It does not create blanket CTHS authority, transfer another person's byline, or accept generic membership of a different academy. Exact Academy and Institut credits retain distinct provenance. All nine positive source pairs and literal events have separate root approval and independent C QA, bound to final decision and worker-manifest hashes. Unresolved foreign/correspondent controls and ambiguous intervals are retained.

## Individual case adjudication

Batch B makes three PDF GETs and reopens six archived target CTHS bodies offline, with no search queries. Its first 20 candidates had prior primary-source claims; the other six had unaccepted cached-notice leads. The source review reads actual subject names, exact birth expressions, career bridges and separately typed ordinary membership starts. A normalized scan of all 877 groups checks uniqueness and known alias/profile collisions. Historical claims and flags alone do not approve a person.

The separate case API permits only exact root/independent-QA approved old-zero identity/DOB fields. A birthday must equal the one unchanged prior raw date and have no prior exact conflict; no date is invented or chosen by source votes. It applies identity/DOB adjudication before the independent ordinary-membership validator. The 25 approved before/after values, original source hashes, proposal and conditional-membership file hashes, and final independent QA are pinned. The separate `france_case_adjudications.csv` records this history without rewriting old claim provenance. Archived captures with unknown original retrieval time retain null and explicit archive/member provenance plus the actual reopening time.

Father CTHS_102829 remains unapproved in all three dimensions. His dedicated notice gives 1862-11-23; the preserved son's notice identifies the same father with 1867–1947. This contrary year is recorded in machine-readable v12 birthday-review status, source hashes and observed-year metadata, plus a bounded identity/source control. The case gate blocks promotion while this control is unresolved, even if an approval map were mistakenly broadened. It is not an invented 1867 day or an extra exact-date vote. Neither father nor son raw dates change, and every old field of the son's accepted record remains intact.

## Japan and verification

All 34 unresolved Japanese scope cases receive local chronology triage. Two bulk queries and one actual Academy newsletter-index capture show that this contemporary route starts in 2008, after the latest recorded retirement in 2007. The route stops there; retrospective evidence is not ruled out. There are zero individual queries, person-body reviews, DOB searches, birth claims or section proposals. No Japanese scope or DOB field changes.

Japan retains 482 identities,438 Section II,10 Section I and 34 unresolved;528 claims for 433 people;368 day statuses split 215 institutional/university/organization,150 edited reference only and three other attributed secondary. All 46 holds and four older calendar outcomes remain. There are472 nonexcluded cases,104 without day status,360 Section II plus day, and 112 in the combined queue. These are restored working-ledger counts, not a national completion claim.

The replay uses `V11.final_japan()` and the complete final French master/history. A successor should call `V12.final_japan()` for the complete v12 state. Every old Japan field/claim and every untouched French field remains; new comparable contradictions still reach the reducer. Selection size, actual source processing, HTTP requests and individual search queries are reported separately. Frozen collector files may retain pending-approval flags; external root approvals and independent reports record final acceptance without rewriting those handoffs.

```sh
python3 studies/academy_fr_jp_completion_v12/scripts/continue.py baseline
python3 studies/academy_fr_jp_completion_v12/scripts/continue.py prepare --output-dir /tmp/academy-v12-inputs
python3 studies/academy_fr_jp_completion_v12/scripts/continue.py assemble --output-dir /tmp/academy-v12-outputs
python3 -m unittest discover -s studies/academy_fr_jp_completion_v12/tests -v
python3 studies/academy_fr_jp_completion_v12/scripts/continue.py verify
```

Use fresh output directories. Preparation writes 12 deterministic inputs; assembly writes nine outputs. Nineteen guards cover inheritance, source origin, linked response/ID proof, role conflicts, exact approvals, singleton prior dates, unresolved identity collisions and truthful processing boundaries. Verification checks predecessor pins, the metadata inventory and byte-identical replay. Raw PDFs, HTML and images remain private; deliverables contain bounded evidence metadata, hashes and locators.
