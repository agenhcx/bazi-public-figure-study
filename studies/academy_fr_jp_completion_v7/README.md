# France and Japan academy continuation v7

This bounded continuation starts from unchanged v6 commit `4187d923880b6c78259c703904f0d46cfd35d934`. Ancestor evidence, decisions, processing history and unresolved holds remain available. Neither country is complete or frozen for analysis; professor collection stays paused and Fields data stays preserved.

The batch adds seven Japanese source-body claims and 15 strict French memberships. Japan gains three day statuses, including two exact root-approved releases of calendar routing holds based on dates paired by the sources themselves. Actual completed processing is 36 of 60 Japanese selections and all 78 French selections. The other 24 Japanese selections retain explicit `not_searched` dispositions. Jean Laval's separately approved French cross-source case is outside the fixed 78 and does not imply another targeted search.

| Evidence measure | v6 | v7 |
|---|---:|---:|
| Japan people with body birth information | 430 | 433 |
| Japan distinct body birth claims | 518 | 525 |
| Japan day status without a known unresolved conflict | 363 | 366 |
| Institution/university/organization day support | 212 | 214 |
| Edited-reference-only day support | 150 | 150 |
| Other attributed-secondary-only day support | 1 | 2 |
| Nonexcluded Japan candidates without day status | 112 | 109 |
| Combined Japanese date/section queue | 124 | 121 |
| France strict ordinary membership | 360 | 375 |
| France identity, membership and DOB all accepted | 358 | 373 |

The two other-secondary-only days consist of one inherited financial-filing reproduction and one newly captured, attributed HLA journal preview reproduced on ResearchGate. The new preview remains separate from both institutional evidence and edited biographical references. All 363 previously selected Japanese day expressions remain unchanged. All inherited claims retain every field; 48 baseline holds remain held and only the two approved calendar-routing cases are released.

The four immutable selection queues contain 60 Japan candidates (29 date routes and 31 calendar routes) and 78 French membership gaps (39 in each batch). The French queue was chosen from 25 previously unsearched and 53 prior cache-only cases, excluding inherited chronology conflicts and the false same-name case. Every selected identity needs an explicit disposition. A `not_searched` outcome is allowed and does not count as completed processing. Claims never substitute for a processing disposition. Cache scans, targeted queries, fixed outcome coverage and actual completed dispositions are reported separately. Any additional cross-source identity requires an exact root-approved ID allowlist and remains outside the fixed 60/78 denominators.

The Japan baseline has 482 stable IDs: 428 with broad Section II support, seven Section I exclusions and 47 unresolved sections. It contains 518 distinct body birth claims for 430 people and 363 day statuses without a known unresolved conflict: 212 institution, university or organization supported; 150 edited-reference-only; and one financial-reproduction-only. The remaining nonexcluded date gaps number 112; the combined date/section queue has 124 candidates. v7 makes no section decisions.

Japanese source tiers remain separate. Institutional year/month evidence cannot promote a dictionary day. Literal January 1, original precision and calendar expressions remain explicit. Comparable body-date conflicts are held regardless of source counts or source tiers. An alternate unconverted calendar expression cannot silently erase an existing supported modern date. A new comparable disagreement may produce a conflict hold; an old selected day that remains accepted must retain its exact prior value.

All 50 actual baseline Japanese holds are retained by default, including automatic calendar/date routing holds that were absent from v6's 20 explicit continuation overlays. v7 makes those effective holds explicit in the cumulative hold input, with baseline identity and status provenance where newly materialized. Before a new source can affect an automatically held identity, its inherited hold is supplied to the assembler. A new modern-looking body claim alone cannot release that hold.

`inputs/calendar_routing_decisions.json` is a separate root-reviewed input for two exact source-supplied calendar pairs: Miyairi's 1865-06-08 and Yamasaki's 1870-04-10. Applying either decision additionally requires independent Dates QA, the exact new source SHA256 and day components, a body-supported comparable claim explicitly marked as a source-supplied pair, no old comparable claim and no new comparable disagreement. Missing or mismatched evidence preserves the inherited hold. All older noncomparable expressions remain unchanged in the ledger. The resulting changes are separately counted as approved calendar-routing releases. v7 performs no collector calendar conversions, date padding, generic hold release, majority date adjudication, final cohort approval or BaZi computation.

The inherited Suzuki and Yanagida exceptions retain their original null source-byte hashes, derived-text hashes and prior exact approval records. Any new failed original-byte capture requires a separate exact root approval for member ID, source URL, derived-body hash, original HTTP failure status, actual-body reference and root verification reference. A hash of extracted text is never represented as an original-byte hash. New source tiers also require root review.

The French baseline has 877 candidate groups, 755 identity approvals, 744 DOB approvals, 360 strict ordinary memberships and 358 all-three approvals. All 25 inherited chronology holds remain held, including the impossible Louis source event; Gravier's separate unresolved membership case is unchanged. A strict positive requires the same Academy-original evidence item to support an ordinary full-member role and a literal observed day, year or explicit membership-start year. The exact official `comptes-rendus.academie-sciences.fr` journal host is included; arbitrary subdomains are not automatically approved. Correspondent/foreign roles, derived or relative-year arithmetic, as-of bounds and a notice author's title cannot substitute. Human source review checks the literal role/date attribution; a short quote need not reproduce every date component. Membership evidence cannot change identity or DOB approvals. The v3/v4/v5/v6 review columns and the entire predecessor decision ledger are retained alongside v7 review fields.

`source_batches/` contains only root-approved public JSON/CSV/README metadata and short transcriptions. Full copyrighted bodies, source images and production helpers are excluded. `source_audits/` records review scope and integration invariants. `inputs/baseline_provenance.json` pins every v6 inventory entry, its manifest and the four unchanged selection CSVs. Nine prepared inputs retain cumulative evidence and separate v7 deltas; eight outputs replay byte-for-byte.

From the repository root, with fresh replay directories:

```bash
python3 -m unittest discover -s studies/academy_fr_jp_completion_v7/tests -v
python3 studies/academy_fr_jp_completion_v7/scripts/continue.py prepare --output-dir /tmp/academy-v7-inputs
python3 studies/academy_fr_jp_completion_v7/scripts/continue.py assemble --output-dir /tmp/academy-v7-outputs
diff -r studies/academy_fr_jp_completion_v7/outputs /tmp/academy-v7-outputs
python3 studies/academy_fr_jp_completion_v7/scripts/continue.py verify
```

The nine tests cover complete evidence/provenance inheritance, source-tier separation and minority date conflicts, explicit and automatic hold retention, historical alternatives, exact approved routing-release guards, precision/identity/capture rejection, exact null-hash approval, French role/date/source attribution, fixed scope and truthful unsearched outcomes. Current evidence counts and processing dispositions are in `outputs/summary.json`; deterministic replay and inherited evidence checks are in `source_audits/integration_invariants.json`.
