# France and Japan academy continuation v5

This bounded continuation starts from unchanged v4 commit `3181c9afa7545fa1ad8cbb3f4adc3f794b016440`. It adds reviewed source evidence while preserving the earlier claims, decisions, processing history and holds. Neither country is complete or frozen for analysis. Professor collection stays paused and Fields data stays preserved.

| Evidence measure | v4 | v5 |
|---|---:|---:|
| Japan people with body birth information | 363 | 422 |
| Japan day status without a known unresolved conflict | 310 | 359 |
| Institution/university/organization day support | 195 | 204 |
| Edited-reference-only day support | 114 | 154 |
| Financial reproduction-only day support | 1 | 1 |
| Nonexcluded Japan candidates without day status | 165 | 116 |
| Combined Japanese date/section queue | 177 | 128 |
| France strict ordinary membership | 290 | 315 |
| France identity, membership and DOB all accepted | 288 | 313 |

The Japanese fixed queues contain 89 candidates, all with actual processing dispositions. The batch adds 63 raw birth claims and 49 day-status gains; the full ledger has 502 distinct source claims. The universe stays at 482 IDs: 428 with broad Section II support, seven Section I exclusions and 47 unresolved sections. Source evidence and section evidence remain separate. The 475 nonexcluded candidates are not a frozen national eligible cohort.

Commercial edited references remain separate from institution, university and organization evidence. An institutional year or month does not promote a dictionary day into institution-supported day evidence. Literal January 1, original precision, old-calendar expressions and source-supplied date expressions remain explicit; no collector calendar conversion or default date filling occurs. Amemiya's verified November 15 versus November 5 disagreement stays held. Hirayama's historical calendar and differing year expressions remain a calendar hold, without treating unproven calendar equivalence as a comparable-date contradiction. All earlier Japanese holds remain in force.

One source has an explicit exception to original-byte capture: Suzuki Atsuto's university PDF gives 1946-10-03 in the complete web-extracted body, independently read by root. Direct PDF capture and screenshot returned 403. Its original source hash stays null; the derived text hash, exact member/URL allowlist and verification reference stay separate. The source is text-body verified, with no PDF visual verification claim. Every other new Japanese claim has an original captured-body hash.

France retains 877 candidate groups, 755 identity approvals and 744 DOB approvals. The fixed selection contains 120 candidates, with an explicit outcome for each: 96 were processed and 24 are honestly marked not searched. Processing includes batch text screening and source-only reviews; it does not mean 120 individual new searches. The A collector reports 28 targeted-search candidates, five source-only reviews and 27 cache-only outcomes. Exact status distributions and collector-reported search metrics are preserved in the summary. The B collector's 24 unsearched candidates are not counted as processed.

The fixed French queues add 24 strict ordinary memberships. One further existing candidate, Jean Brossel, is supported by an already captured source and adds one cross-source approval; it is outside the fixed 120 denominator and introduces no new roster identity or separate targeted search. The resulting totals are 315 strict memberships and 313 all-three groups. The remaining 564 all-three gaps are not a count of missing birthdays.

France strict positives require an observed Academy-original ordinary-full-member event matching the accepted year or day, including explicit ordinary nonresident membership. Correspondent, foreign-associate, dated role bounds and relative-year arithmetic cannot substitute for a literal ordinary event. Delépine's source explicitly gives ordinary nonresident membership since 1956; only that literal starting year is retained, with no invented election verb or day. All 24 inherited election chronology conflicts remain; Haller adds a further chronology hold. Louis de Broglie's inherited impossible source event is still held. Independent QA also caught a Gravier role assignment to the notice's author rather than its subject: the proposed strict approval was removed, the untyped 1922 event was retained and no new source conflict was manufactured from that correction. Membership-only work does not alter accepted identities or birth dates.

`source_batches/` contains root-approved public metadata and short transcriptions, with full copyrighted bodies and private review images excluded. `source_audits/` records independent source review, the Suzuki exception and integration invariants. Code review reports are tied to their recorded snapshot and scope; the Japanese core/403 review does not claim an identical hash for every later French processing change. The final root review and deterministic replay cover the integrated result.

`inputs/baseline_provenance.json` pins every v4 manifest entry and the five unchanged selection CSVs. Nine prepared input files retain cumulative evidence and separate v5 deltas. Empty-delta tests preserve the v4 counts and provenance; final replay compares all nine inputs and eight output files byte for byte. The eight tests also cover source tiers, inherited holds, wrong or derived election events, truthful unsearched outcomes and the exact-source capture exception.

From the repository root, with fresh replay directories:

```bash
python3 -m unittest discover -s studies/academy_fr_jp_completion_v5/tests -v
python3 studies/academy_fr_jp_completion_v5/scripts/continue.py prepare --output-dir /tmp/academy-v5-inputs
python3 studies/academy_fr_jp_completion_v5/scripts/continue.py assemble --output-dir /tmp/academy-v5-outputs
diff -r studies/academy_fr_jp_completion_v5/outputs /tmp/academy-v5-outputs
python3 studies/academy_fr_jp_completion_v5/scripts/continue.py verify
```

The workflow also compares all nine prepared inputs and preserves all ancestor inventories. No final cohort approval, BaZi variable or outcome analysis was produced.
