# France Académie des sciences: 2019/2020/2022/2023 election PDF source pilot v2

## Scope and freeze context

**Before unblinding**: primary study institution is the Paris Académie des sciences, full/ordinary members elected through 2025, with precise DOB evidence handled separately and the Nobel birth-year support fixed at 1835–1985. This is a **partial first-party election-source layer**, NOT the full historical institutional member roster or a DOB freeze. Do not calculate or inspect any BaZi variables.

This pilot is a narrow follow-up to the pre-existing 66 first-party electees (2010/2011, 2013, 2014, 2017) and 36 government-approved 2024/2025 names. No prior 562 CTHS biographies were re-fetched.

## First-party PDF evidence, checked 2026-10-18 UTC

| Academy selection batch | Candidate elected persons | Source link | Confirmed original SHA256 |
|---|---:|---|---|
| 2019 | 18 | https://www.academie-sciences.fr/pdf/communique/elections_2019.pdf | adaed87b57a02d37dcd718a3624bb1e7843d6a4974c0dc7cbb7b2b337fa5555f |
| 2020 | 4 | https://www.academie-sciences.fr/pdf/communique/elections_2020.pdf | 212041764f3013eaa422e3f255eeb248e262cccf64c23d0a65785d5d23763137 |
| 2022 | 18 | https://www.academie-sciences.fr/pdf/communique/221219_elections_nouveaux_membres.pdf | 64587bf10c717346a8d12b3cbaafeffa8098bb6038b3421ae87b5884e8fb3980 |
| 2023 | 18 | https://www.academie-sciences.fr/pdf/communique/231212_elections_nouveaux_membres.pdf | 9c332c5bb22239100379962913248412dfc1b57256f3bb1cb890c97f4db06966 |
| **Total** | **58** | Four separate original Academy first-party PDFs | Four verified source snapshots |

The 19 December 2019 document confirms 18 already elected and a planned second round of four targeted posts; the 19 March 2020 separate announcement specifically declares election of **four new members**. **Do not change 2020 election year to 2019** on account of shared election campaign. The document issue dates are **announcement dates**, NOT independently certified election-ballot dates; no exact-ballot-day flag is filled.

The 2022 and 2023 PDF announcements contain 18 new members each and indicate a future presidential decree ratification, which is not automatically considered independently verified by reading the Academy announcement. The 2021 selection of 16 *associés étrangers* is **not** a primary full-member election; a negative-control row is retained but completely excluded from eligible 58-person outputs.

All four verified notices give name, career/affiliation and selected source sections or targeted positions, but **none provides a person-level exact DOB or birth year**. Do not infer DOB from electee age limit (e.g. 50% under age 55) or from biographies in the same PDF. No exact DOB is accepted from these four election PDFs.

## Machine-verifiable source replay

Input hand-read golden list: `data/france_academy_elections_2019_2023_pilot_v2/golden_58_official_member_names_v2.csv`

Original source inventory: `data/france_academy_elections_2019_2023_pilot_v2/source_inventory_v2.csv`

Script: `scripts/france_academy_elections_2019_2023_source_pilot_v2.py`

Audited outputs: `data/france_academy_elections_2019_2023_pilot_v2/source_validation_v2/` (58 person matches, four source hashes, summary, empty mismatched-name queue).

All **58/58 names matched exact expected PDF pages** after strictly controlled source glyph/order handling. The PyMuPDF text extraction interleaves Nathalie Palanque-Delabrouille's split surname with adjacent right-column biographical wording on the original 2020 PDF p.1. The sole exception uses a bounded, person-specific *Cosmologie expérimentale* header and surname fragments on the verified page, with flag `PDF_INTERLEAVED_TWO_COLUMN_NAME_VISUAL_QA`. This is NOT a general fuzzy matcher and does not apply to any other person.

The source site was accessible from the pilot GitHub runner. Full source bytes were cached only in the ephemeral pilot runner and never committed to the public research repository. The repository contains URLs/hashes/selection and extraction outcomes.

Successful four-document run: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39093543754

## Already selected first-party election source union

We combined three **source sets** offline, without crawling:
- 66 persons from Academy PDFs for 2010–2011, 2013, 2014 and 2017;
- 58 persons from four Academy PDFs for 2019, 2020, 2022 and 2023;
- 36 people elected in 2024 and 2025, with subsequent French government presidential-decree approval documented and retained separately.

Result: **160 selected first-party person-election records**, **160 distinct normalized name-token identities**, **0 exact-name collisions**. Source-document DOB precision is **21 day-precision candidate claims**, **10 year-only claims**, **129 where that selected official election source states no DOB**. A birthdate missing from an election press notice is NOT missing from the person's biography in general.

The single-person name-uniqueness check does not replace historical identity disambiguation. This 160 sample is *selected announcement/approval years*, not continuous complete membership for 1835–2025 and not the primary study denominator. The years absent from the selected election source layers (for instance 2012, 2015, 2016, 2018, 2021) are **not evidence of zero elections or zero members**. Only historical official directories plus systematic all-elections confirmation can settle scope.

Union CSV, audit and possible name-collision queue:
`data/france_academy_firstparty_elected_union_v1/`.
Offline script: `scripts/france_academy_firstparty_election_union_v1.py`
Action: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39093704373

## Windows local rerun (optional, source files were already audited on GitHub)

The requested **local-first** design was implemented in the PDF source pilot. It has bounded `--limit`, input fixture assertions, `--resume` for previously verified source caches, and strictly network-free `--offline` for repeatability. Downloads are SHA256-indexed with per-source metadata and finite request retries. Python 3.10+.

From the user's existing project clone root, using *individual single-line PowerShell commands*:

`git pull --ff-only`

`python -m pip install requests==2.32.3 pymupdf==1.26.5`

`python .\scripts\france_academy_elections_2019_2023_source_pilot_v2.py --fixture-check`

`python .\scripts\france_academy_elections_2019_2023_source_pilot_v2.py --fetch --limit 4 --resume`

`python .\scripts\france_academy_elections_2019_2023_source_pilot_v2.py --offline --limit 4`

Local output directory is ignored by git: `local_runs/france_academy_elections_2019_2023_v2/`. You need only share `summary.json`, `source_fetch_audit_v2.csv`, and `unmatched_names_v2.csv` on failure, never large raw PDFs or verbose logs.

**Do not re-download this 58-source cohort merely for conversation continuity.** The four GitHub source-validation CSVs and immutable SHA-256 claims are sufficient. The next actual collection should be a pre-specified source class (historical first-party directories and new earlier election years), with 10–30 record pilot, and only then large Windows-local collection.

## Unresolved scientific gates

Original historical ordinary-member status including promotions from correspondents and foreign associates; year-by-year election completeness and deceased member ascertainment; source-independent DOB corroboration and conflicts; calendar convention; coverage/missingness by era/section; and a global cross-tier cohort+analysis freeze. No BaZi-variable calculation or publication before those gates.
