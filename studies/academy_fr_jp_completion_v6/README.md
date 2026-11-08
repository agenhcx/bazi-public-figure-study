# France and Japan academy continuation v6

This bounded continuation starts from unchanged v5 commit `fe72fe259ee6aaf90f55c469ba7778a69588044d`. It preserves all ancestor evidence, holds and processing history. Neither country is complete or frozen for analysis; professor collection stays paused and Fields data stays preserved.

The batch adds 16 distinct source-body claims for Japan and 45 strict French memberships. Its actual processing coverage is 33 of 34 Japanese selections and 171 of 196 French selections; one Japanese and 25 French selections remain honestly marked `not_searched`. Five additional Japanese identities and two additional French identities come from root-approved cross-source reviews outside those fixed denominators, without separate targeted-search claims.

| Evidence measure | v5 | v6 |
|---|---:|---:|
| Japan people with body birth information | 422 | 430 |
| Japan distinct body birth claims | 502 | 518 |
| Japan day status without a known unresolved conflict | 359 | 363 |
| Institution/university/organization day support | 204 | 212 |
| Edited-reference-only day support | 154 | 150 |
| Financial reproduction-only day support | 1 | 1 |
| Nonexcluded Japan candidates without day status | 116 | 112 |
| Combined Japanese date/section queue | 128 | 124 |
| France strict ordinary membership | 315 | 360 |
| France identity, membership and DOB all accepted | 313 | 358 |

All 359 previously selected Japanese day expressions are unchanged. Four existing edited-reference-only days gain compatible JSCE organization support; the older edited sources remain in the ledger. Furuichi's explicit leap-month expression is retained as an unconverted, noncomparable alternative and does not invalidate the independently source-supplied modern date. Nakayama adds a calendar hold. All 49 inherited Japanese member holds and all 25 French chronology holds remain held.

Yanagida has the only new original-byte capture exception. The collector initially read the actual complete51-line university CV body; later original capture, reopening and screenshot attempts returned404. Root read and rehashed the separate derived transcript and corroborated DOB/career through official-URL indexed CV text. The original-source hash stays null, with the exact body reference, derived hash and root approval separately recorded. This source has no independently re-fetched original and no PDF visual-verification claim. The inherited Suzuki exception remains unchanged.

The five fixed queues contain 34 Japan candidates and 196 France candidates. Every selected identity requires an explicit processing disposition. A `not_searched` disposition is allowed and is not counted as completed processing; claims never substitute for processing records. Japanese and French cross-source candidates require a separate, root-approved allowlist and do not enter their fixed 34/196 denominators. Cross-source claims do not imply separate targeted processing.

The v5 Japanese baseline has 482 stable IDs: 428 with broad Section II support, seven Section I exclusions and 47 unresolved sections. It has 422 people with source-body birth information and 359 day statuses without a known unresolved conflict: 204 institution, university or organization supported; 154 edited-reference-only; and one financial-reproduction-only. The remaining nonexcluded date gaps number 116; the combined date/section queue has 128 candidates. No v6 section decisions are permitted.

Commercial edited references remain separate from institutional evidence. Institutional year/month evidence does not promote a dictionary day. Literal January 1, original precision and calendar expressions remain explicit. Comparable body-date conflicts are held regardless of source counts or tiers. No collector calendar conversion, date padding, final cohort approval or BaZi computation occurs. Exact root-approved source exceptions retain a null original hash, separate derived-text hash and verification reference; they do not permit generic failed-capture acceptance. The inherited Suzuki exception is preserved unchanged.

The French baseline has 877 candidate groups, 755 identity approvals, 744 DOB approvals, 315 strict ordinary memberships and 313 all-three approvals. Its 25 chronology holds remain held. A strict positive needs a matching Academy-original ordinary full-member event with a literal day or year. Correspondent/foreign roles, derived years, as-of bounds and a notice author's title cannot substitute. Membership evidence cannot alter identity or DOB approvals. v3/v4/v5 review columns and the full prior decision ledger are retained alongside v6 review fields.

`source_batches/` contains only root-approved public metadata and short transcriptions. Full copyrighted bodies, source images and production helpers are excluded. `source_audits/` records review scope and integration invariants. `inputs/baseline_provenance.json` pins every v5 inventory entry, its manifest, and the five unchanged selection CSVs. Nine prepared inputs retain cumulative evidence and separate v6 deltas.

From the repository root, with fresh replay directories:

```bash
python3 -m unittest discover -s studies/academy_fr_jp_completion_v6/tests -v
python3 studies/academy_fr_jp_completion_v6/scripts/continue.py prepare --output-dir /tmp/academy-v6-inputs
python3 studies/academy_fr_jp_completion_v6/scripts/continue.py assemble --output-dir /tmp/academy-v6-outputs
diff -r studies/academy_fr_jp_completion_v6/outputs /tmp/academy-v6-outputs
python3 studies/academy_fr_jp_completion_v6/scripts/continue.py verify
```

The eight tests cover empty-delta inheritance, source-tier separation, minority date conflicts, hold retention and historical alternatives, precision/identity/capture rejection, French role/date attribution, exact fixed scope, and truthful unsearched outcomes. Integration counts and deterministic replay checks are recorded in `outputs/summary.json` and `source_audits/integration_invariants.json`.
