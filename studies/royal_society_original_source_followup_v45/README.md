# Royal Society original-source follow-up V45

Six prospectively selected original-source leads were reviewed after the V44 canonical first-pass closeout. Five source works were requested; one possible catalogue republication was held before retrieval. **No new birthplace or hemisphere assignment qualified. The V44 master, pipeline, schema and CSV outputs remain unchanged.** This folder is a source-evidence supplement, not a new master-data version.

| Record | Original-source result | Decision |
| --- | --- | --- |
| NA4193 Kenneth Dawson Bagshawe | RCP entry confirms name and exact DOB; obituary pending; no birthplace. | Hold |
| NA4301 Cecil Edwin Henry Bawn | Prior acquisition/work identity of the alternate catalogue frontend remains unresolved. No request made. | Hold before request |
| NA4155 Leonard George Goodwin | Original ODNB public extract confirms full identity/exact DOB and Wood Green, London birth address; no birth whole-region. | Hold geography; existing place/grade unchanged |
| NA6868 Roger Philip Ekins | Actual RS profile has no Philip, DOB or birthplace. | Hold |
| NA1998 Basil Kassanis | Local-history personal article returned a verification challenge. | Hold; work closed |
| NA4490 Anthony Ledwith | Single title locator found actual Chemistry World URL; first open failed with tool-reported 405. | Hold; work closed |

The source-only Ekins death-day contrast (27 July in the profile versus 26 July in the retained memoir title) is preserved without a correct-date verdict or native DOB/endpoint-year repair. It is not added to the active DOB inventory.

The authoritative data remain at `studies/royal_society_birthplace_completion_v44`, commit `cc23cc8d35eb2bfffcbbf041310dd049b308e5ca`. The fixed master has 4,983 membership records. Within native DOB 1835–1985 inclusive, 2,644 records comprise 2,305 North, 182 South and 157 unknown; the unknown records split into 103 blank birthplaces and 54 stored-place geography holds. These are membership-record counts, not a deduplicated scientist count.

## Admission and preservation

The six-record scope was frozen before new source requests. Blank birthplace records reuse the inherited V15–V29 original-biography admission rules; existing-place geography records reuse V30–V35. They require complete native identity, an explicitly stated compatible birth-date precision, coherent career and compatible lifespan. They do not impose the separate V36 canonical exact-day gate. Hemisphere classification requires direct, sufficient whole-region birth evidence. No dateless, age-inferred, omitted-middle or source-grade exception was introduced.

Previously unusable works stay closed. New held observations and retrieval intent are retained without changing native identity, DOB, original source grades, raw places, cohort membership, prior claims or any of the nine issue inventories. The historical V44 Q4924984 same-work request deviation remains documented and is not cleared by this stage.

## Files and validation

`scope.json` fixes strategy, candidates, budgets and authority hashes. `audit/native_scope_*.json` preserve complete target objects. `audit/v45_sources_*.json` and `audit/v45_intent_*.json` are the sparse acquisition reports and prospective exact request ledgers. The report filenames keep their original workspace names; the workspace `v45_original_scope.json` is byte-identical to packaged `scope.json`, and `v45_scope_*.json` to `audit/native_scope_*.json`.

`audit/parent_adjudication.json` records all six decisions. `audit/source_qa.json` contains independent source review; `audit/baseline_integrity_final.json` verifies frozen data, code, schema and inventory bytes without importing historical replay code or running a production CLI. No new master wrapper or CSV columns were created because this stage adopted no facts. The baseline checker can be run from a repository checkout with `python -B studies/royal_society_original_source_followup_v45/audit/check_baseline_integrity.py`; `--repo-root` and `--output` are optional. `summary.json` gives the current counts. `MANIFEST.sha256` authenticates the distributed files.

This bounded source stage is complete. Birthplace coverage, source exhaustion and final analysis-cohort freeze are not claimed. No BaZi features, statistical outcomes or new research hypotheses were evaluated.
