# France and Japan academy completion work, 2026-10-29

The user paused professor collection and prioritized finishing France and Japan. This round restores older reviewed data, adds actual source-body evidence, and publishes candidate-level gaps. Neither national cohort is frozen or complete. No BaZi or outcome analysis was performed.

## France

The recovered round 39 baseline has 877 candidate groups, not 877 established ordinary members. It is newer than the older Git source-discovery summaries. Baseline source-event counts must not substitute for this person-level ledger.

| Evidence dimension | Restored baseline | Current | Added this round |
|---|---:|---:|---:|
| Identity reviewed and accepted | 698 | 755 | 57 |
| Exact DOB reviewed and accepted | 688 | 744 | 56 |
| Strict ordinary-membership evidence accepted | 184 | 246 | 62 |
| All three dimensions accepted | 183 | 244 | 61 |

The new 57 cases have independently reviewed actual source bodies. Official Academy election lists also resolve 16 prior generic-profile membership holds. There remain 633 candidate groups without all three approvals; this is not 633 missing birthdays. The inherited 73 groups without a day-level source claim, old identity holds and exact-DOB conflicts remain explicit. Historical ordinary-member evidence is the main unresolved task.

Role support, stable election cutoff, and election-date conflict are separate columns:259 groups have role support and 256 have a stable cutoff. Conflicting election dates are retained and do not become accepted exact dates. The strict membership gate is unchanged. Reception in 2026 is not substituted for an explicit election in 2025.

Santy's official obituary states Correspondant. Santy is absent from the recovered 877 table; his external exclusion is therefore published separately without inventing an 878th row. Abragam's CEA corroboration remains separate from the unresolved ordinary/foreign membership classification. The three blocked French civil-record routes from the prior round were not repeated.

`france/inputs/` contains the pinned baseline, reviewed decisions and source provenance. `france/outputs/` contains the 877 master,244 all-three rows,633 remaining groups and external overlays. Original full texts and private PDF images are excluded. Replay verifies the recorded decisions and byte-identical outputs; it does not independently recreate human source interpretation.

## Japan

The restored 435 science-discovery rows omitted the old 40 mixed/blank-degree qualification cases and seven additional imperial-adjudication rows. Their union is 482 stable IDs. Seven are known Section I exclusions, leaving 475 science-or-unresolved candidates. Two Nishimura Hideo identities are retained separately with their distinct professions. Names are never used as global IDs.

| Restored qualification evidence | People |
|---|---:|
| Official current/detail Section II records | 139 |
| Imperial Section II adjudications, including one preserved historical conflict | 89 |
| Previously frozen broad science-degree rule | 199 |
| Direct Tier B Section II evidence | 1 |
| Original pre-1906 section evidence not recovered | 11 |
| Prior unresolved section cases | 36 |
| Section I exclusions | 7 |

Thus 428 have broad Section II support and 47 remain unresolved. These are evidence layers, not final eligible cohort sizes. Exact subsections are not inferred from degrees. Hiratsuka's directly stated subsection 6 is preserved. Matsumura Jinzo's historical Section I/II conflict remains visible. The old 137-versus 139 summary discrepancy is not silently rewritten: the restored row-level official flags contain 139 distinct IDs, while the origin of the older 137 summary remains undocumented.

Institutional body evidence now covers 157 people. After identity, source-caveat and calendar holds,120 have full day components without a known unresolved conflict, up from 4 in the previous seed. Of these,111 also have broad Section II support;119 have source birth years within 1835–1985. These are source-date components, not a declaration that every calendar is explicitly Gregorian or that final membership eligibility has been accepted.

Among 475 nonexcluded candidates,355 still lack this day-level status. Forty-seven also need section evidence; the combined action queue has 364 people because these gaps overlap. Three source-date conflicts, calendar holds, one explicit multiple-birthday caveat and seven identity-assignment holds remain distinct. A bounded unsuccessful search is separate from a person not yet institutionally processed.

The entire 435 and separate 40 were screened through the official NDL Authorities API. These results mostly contain birth years and name-only matches: they never fill a selected date. The rejected Katagiri association demonstrates why a unique name match alone is insufficient. The imperial-only seven were restored separately; no claim is made that all 482 underwent that API batch.

The Kyoto University archive's 1025-entry historical index yields 51 relevant source records after rejecting two wrong same-name pairs:37 western-calendar policy day dates,12 lunar day expressions, one month and one missing birth. Its published legend states that 1872-and-earlier lunar month/day values retain only a westernized year. They are never treated as converted Gregorian dates. A matching death/retirement date is supporting identity context, not a rule equating the two event types.

NDL portraits, learned societies, university biographies, Kyoto municipal biographies and a single UTokyo pathology history page provide additional body dates. Source-supplied dual expressions are retained without collector conversion. Yamagiwa's conflicting original-calendar days, Tamaru's ten-year source discrepancy and Okada's birthyear disagreement remain holds. Literal January 1 dates are preserved where the source actually states 1/1; no default dates are inserted.

Independent QA corrected one captured hash that belonged to an error page. The original transcription remains archived; the normalized hash is cleared and its correction is explicit. Web-extraction hashes are not represented as original HTML hashes.

## Replay

From the repository root, use fresh output directories:

```bash
python3 -m unittest discover -s studies/academy_fr_jp_completion_v2/tests -v
python3 studies/academy_fr_jp_completion_v2/scripts/normalize_japan.py --output-dir /tmp/academy-normalized
python3 studies/academy_fr_jp_completion_v2/scripts/build_japan.py --output-dir /tmp/academy-japan-v2
diff -r studies/academy_fr_jp_completion_v2/japan_outputs /tmp/academy-japan-v2
python3 -I studies/academy_fr_jp_completion_v2/france/assemble_france.py --output-dir /tmp/academy-france-v2
diff -r studies/academy_fr_jp_completion_v2/france/outputs /tmp/academy-france-v2
```

Compare the three normalization outputs with their corresponding files in `inputs/`. The workflow performs this comparison and verifies the complete study manifest. Collector scripts are archived as source-specific utilities; offline assembly uses pinned transcriptions and does not recrawl websites.

Professor and Fields datasets are preserved. Existing source hashes, source conflicts and global analysis gates are unchanged. Future work should take names directly from the gap tables, prioritizing available Academy election/obituary originals and new institutional birthday sources. Repeating inaccessible civil archives or year-only APIs will not complete those gaps.
