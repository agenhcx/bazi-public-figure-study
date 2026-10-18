# French Academy: fix 1856 historical nominations, link imperial decrees, and ingest source-verified TOC shard 0

Checkpoint: **2026-10-18 UTC**. PUBLIC SOURCE RECONSTRUCTION ONLY. The starting 1835–1940 source frame is 211 original half-year `Comptes rendus` volumes. **Source index events are not accepted full-member subjects.** User's larger research birthyear support remains 1835–1985. No original accepted cohort, DOB assertion, frozen 562 CTHS biographies or BaZi outcomes changed.

## 1. Definitive diagnosis of the 1856 parser false zero

The existing 211-volume source availability audit reported Tome **43 (1856)** as HTML200, recognized an election-related heading but extracted **0 names**. Direct public inspection showed the heading is *NOMINATIONS de Membres et de Correspondants de l'Académie*, and the original row predicates are **`est nommé`**, not `est élu`; hence the modern-election parser's 0 meant *parser omission*.

The 1856 Tome **42** was also found to contain actual historical appointments but initially returned 0 to the old parser. Its Wikisource HTML has **both** a partial legacy `div.tableItem` structure and conventional `<tr>` source table (a mixed format). The old branch selected one HTML structure exclusively, discarding the real appointment rows. We therefore:

- Parse both HTML structures independently and then deduplicate identical person+role+page/action references; preserve earlier modern `est élu` and 1926 continued-page regression checks.
- Recognize `NOMINATIONS de Membres et de Correspondants`, standalone `Nominations` when the explicit source clause says `est nommé Correspondant`, and the 19th-century `est nommé` action.
- Preserve the source's **original action** separately from the historically interpreted provisional class. For example `M. Hermite est nommé à la place vacante dans la Section de Géométrie` becomes **`FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION`** (member-like source candidate, NOT a legally or finally confirmed regular member).
- Mark explicit `Membre` assignments as `FULL_SECTION_MEMBER`, correspondents as `CORRESPONDENT`, and not confuse candidate nomination or predecessor replacement text with new election events.
- Keep both references for source rows like **`510 et 618`** or **`725 et 798`** in `source_printed_page_references` on a **single appointment event**, not two independently elected members.

Source: https://fr.wikisource.org/wiki/Comptes_rendus_de_l’Académie_des_sciences/Tome_42,_1856/Table_des_matières and https://fr.wikisource.org/wiki/Comptes_rendus_de_l’Académie_des_sciences/Tome_43,_1856/Table_des_matières .

**Actual bounded 1856 re-ingestion** via `scripts/france_academy_wikisource_legacy_election_headings_v1.py`:

| Original volume/year | Full-like appointment events | Correspondent appointment events | Total |
|---|---:|---:|---:|
| Tome 42, 1856 Jan–Jun | 3 | 4 | **7** |
| Tome 43, 1856 Jul–Dec | 1 (Hermite contextual) | 1 (W. Hooker) | **2** |
| **Combined** | **4** | **5** | **9** |

Tome 42 print pages include Jobert de Lamballe 578, Bertrand 786, Claude Gay 931, correspondent Guyon 378, Ostrogradski 416, Wrangell 510/618 and Gerhardt 725/798. Tome 43 includes Hermite 85 and W. Hooker 1143. Short source name forms remain as printed: e.g. `Bertrand`, `Gay (Claude)`, `W. Hooker`. Do not treat such source abbreviations as exact Wikidata or CTHS identity reconciliations. The source date is publication semester/year, **not an independently established member effective date**.

## 2. Imperial decree indexes are a separate stage

The **same 1856 volumes** also show government decree approval listings:
- Tome 42 has three indexed imperial decree confirmations, pp. **605** (Jobert de Lamballe), **813** (`J. Bertrand`) and **1021** (`Cl. Gay`).
- Tome 43 includes an imperial decree confirming `M. Hermite`'s nomination, p. **169**, distinct from Academy appointment p. **85**.

Source-only code: `scripts/france_academy_1856_imperial_decree_index_v1.py`, parse `Décrets impériaux` heading (including accents, collective heading with `De M.` continuation rows, and explicit `Décret confirmant la nomination`). It does not misread other imperial decrees about grants or awards as new academicians.

Observed 1856 source claims: **9 nomination events, 4 indexed decree confirmations, 2 strict normalized printed-name joins, 2 decree name forms requiring manual alias adjudication** (`J. Bertrand` versus `Bertrand`; `Cl. Gay` versus `Gay (Claude)`). The exact-name links include Hermite and Jobert de Lamballe. Name abbreviations must NOT be resolved by automatic surname-only matching. Correspondent nominations without a decree in these indexes remain "not found in THIS index," not rejected nominations.

No original appointment ceremony report or original decree document page was directly opened in this run; all these are Wikisource TOC **transcription claims**. Nothing proves precise final administrative effective dates from the index alone. The first-party original scanned 1835 election report inspected in PR#94 is a separate historical source case, not proof for 1856.

## 3. First fixed 172-source-plan batch, shard 00 (16 volumes)

Original frozen plan: `data/france_academy_unprobed_16_volume_batch_v1/remaining_172_toc_shard_plan_v1.csv`, **11 shards** chosen before requesting any new source. The user did not need to download any large archives: bounded Github Actions source requests used the same rate-limited code, original source links and SHA-256 provenance.

**First 16-volume batch result:** 12 Wikisource TOC HTML200, 4 TOC subpage HTTP404; **46 election/event index rows**, 11 readable source volumes with recognizable election headings. The new **person-event ledger** (`verified_transcribed_person_event_candidates_v1.csv`) was replayed from the *exact same cached HTML bytes* and checked SHA256 against `academy_original_wikisource_211_volume_inventory_v1.csv`; no second network pass per person.

The first shard's 46 source-index events include **13 section full-like events, 1 académicien libre event, 30 correspondent events and 2 foreign associate events**. Source name / member category / action-wording / year / printed page / source SHA are retained for every event. **4** of those events strictly match unique names in the already-frozen 562 CTHS priority biographies; neither absence from the 562 set nor a name match is final identity/membership evidence.

A notable source parser QA: **Sir Ernest Rutherford**'s 1927 election as a **foreign associate** is recorded in Tome **185**, original journal index page **1424**. The original name extractor required the French honorific `M.` and produced one nameless foreign event until a conservative `Sir/Lady/Lord/Mme/Mlle` variant was added and specifically regression-tested. This is NOT a regular full-member event and remains excluded from that provisional role category.

For all 46 entries: `original_member_election_page_opened=0`, `official_member_status_accepted=0`, `exact_dob_accepted=0`, `bazi_variables_computed=0`. HTTP404 returns are **NOT historical zero elections**.

## 4. Cumulative source coverage with explicit de-duplication

We have now audited four nonoverlapping previously sampled TOC source frames:

- 11 discovery volumes (9 readable, 2 TOC404, 40 indexed event candidates);
- 12 independent holdout volumes (6 readable, 6 TOC404, 8 candidates);
- 16 period-spread volumes (11 readable, 5 TOC404, 38 candidates);
- 16 frozen shard-00 volumes (12 readable, 4 TOC404, 46 candidates).

That gives 55 distinct sampled volumes and 132 index event candidates. Additionally, **Tome 42, 1856** was never in these 55 volumes and adds 1 readable TOC + 7 appointment events; **Tome 43** was already part of the original 16 period-spread sample but its falsely parsed 0 is corrected to **2** events. It is **not another new volume**.

Therefore the audited cumulative state is:

| Measure | Source-only observed tally |
|---|---:|
| Original books inventoried in Academy/Wikisource crosswalk | **211** |
| Unique TOC volume endpoints actually probed | **56** |
| Readable TOC HTML200 | **39** |
| TOC endpoints returning HTTP404 | **17** |
| Candidate election/nomination index EVENT rows | **141** |
| Never-probed TOC volumes still remaining | **155** |
| Original full-member population certified / DOBs admitted / BaZi variables | **0 / 0 / 0** |

The original **172-target prespecified shard plan is preserved unchanged** as an audit of decisions made before source collection. Tome42 was inspected out-of-order for the necessary 1856 grammar diagnosis; it must not be counted as a new volume again when its originally planned shard is eventually run. A separate reproducible **cumulative 56-volume deduplication overlay** is recorded by `scripts/france_academy_cumulative_56_source_probe_audit_v1.py`; the old source state showing Tome43 zero remains intact for historical reproducibility.

**Do not extrapolate 141 indexed events to 141 distinct academicians, or this purposeful source sample to national membership percentages.** Some are correspondents and foreign associates, some names are abbreviated, some persons may have multiple career transitions, and originals still need independent event-level confirmation.

## 5. Files and next actions

- `scripts/france_academy_wikisource_legacy_election_headings_v1.py`: historical `nommé` grammar and dual HTML layout fix; includes multi-page locator preservation.
- `scripts/france_academy_wikisource_election_rows_v1.py`: explicit foreign-honorific `Sir Ernest Rutherford` regression and cautious name extraction.
- `scripts/france_academy_1856_imperial_decree_index_v1.py`: imperial government approval claims (first/second half 1856), source-index only.
- `scripts/france_academy_offline_source_toc_event_ledger_v1.py`: exact SHA-verified per-person evidence from cached HTML, no network.
- `scripts/france_academy_run_remaining_172_toc_batch_v1.py`: local `--shard N --run` now creates individual person-event ledger in the same cached source pass; supports shard 10's final 12-volume size.
- `scripts/france_academy_cumulative_56_source_probe_audit_v1.py`: deterministic source overlay, replaces only erroneous derived metadata for old 1856 vol43; old immutable inputs untouched.
- Compact CSV and JSON evidence under `data/france_academy_1856_nomination_grammar_pilot_v1/`, `data/france_academy_1856_imperial_decree_index_v1/`, and `data/france_academy_remaining_172_toc_batch_v1/shard_00/`.

Next scientific-data priorities: spot-check the *original printed 1856 imperial decree* and Academy appointment pages; manually adjudicate abbreviated nomination names, then continue the next small batch from the original pre-registered shard list, still enforcing per-volume source availability and missingness. Note Tome42 is already inspected out-of-order: when shard 4 is run, deduplicate this exact source volume in cumulative results, or explicitly reuse its cached response if locally available.

Research safeguards remain unchanged: original CTHS 562 date claims, French Roche / Vernejoul DOB conflicts, historical member classes, 1835–1985 birth support, zero admitted new study subjects and NO BaZi model features or hypothesized discovery.
