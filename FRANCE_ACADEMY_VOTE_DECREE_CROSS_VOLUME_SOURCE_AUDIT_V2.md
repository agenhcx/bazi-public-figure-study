# French Academy 1924–1934 historical election versus government approval: source-only link pilot v1/v2_1

**Date:** 2026-10-18 UTC. This is a structured historical *source evidence* study, NOT approval of 17 original membership documents, NOT a complete historical institutional roster, NOT approval of birth dates, and NOT unblinded BaZi analysis.

## Exact public source and observed procedure

We read French Wikisource's public **Table des matières transcriptions** of the original Académie des sciences publication *Comptes rendus hebdomadaires des séances de l’Académie des sciences*, specifically:

- Tome **179**, 1924 (one half-year) for initial vote/decree event demonstration;
- Tomes **182–183**, 1926 (both half-years) for cross-volume historical election → government decree reference;
- Tomes **198–199**, 1934 (both half-years) for corresponding cross-volume validation.

Each publicly fetched index HTML has a SHA-256 pinned in the output. No original printed vote report or government decree full page was directly opened in this pilot. The raw HTML and DjVu scans are not redistributed. The latest historical source indexes remain CANDIDATE transcription evidence, not signed law enactments.

Source URLs:
- https://fr.wikisource.org/wiki/Comptes_rendus_de_l’Académie_des_sciences/Tome_179,_1924/Table_des_matières
- https://fr.wikisource.org/wiki/Comptes_rendus_de_l’Académie_des_sciences/Tome_182,_1926/Table_des_matières
- https://fr.wikisource.org/wiki/Comptes_rendus_de_l’Académie_des_sciences/Tome_183,_1926/Table_des_matières
- https://fr.wikisource.org/wiki/Comptes_rendus_de_l’Académie_des_sciences/Tome_198,_1934/Table_des_matières
- https://fr.wikisource.org/wiki/Comptes_rendus_de_l’Académie_des_sciences/Tome_199,_1934/Table_des_matières

## Pilot 1: 3 individual half-year volumes, 1924/1926/1934

Script `scripts/france_academy_vote_decree_index_link_v1.py` matches Academy election **index** lines in the SAME volume with its `Décrets` index lines, using exact normalized full names. Original public CI: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39121860000 .

- **17 candidate election events** across selected volumes 179/1924, 182/1926, 198/1934.
- **10** exact name matches to government decree approval **index** entries in the same half-year volume.
- **7** without a *same-volume* matching approval index entry: UNKNOWN until the next source checked. Do not interpret nonmatching as proof of no approval.
- Decree notice index typically uses `Approuvant l’élection de M. [name]` or context-dependent `Id. de M. [name]`; one `Id.` is resolved only when it follows an explicit relevant approving-election entry in the same `Décrets` section.
- Election categories `FULL_SECTION_MEMBER`, `FULL_NONRESIDENT_MEMBER`, `FULL_ACADEMICIAN_LIBRE` and `CORRESPONDENT` preserved; decrees are not new elections.

This alone already shows election reporting and subsequent government approval can have DIFFERENT page locations.

## Pilot 2: two consecutive-volume windows, 1926 and 1934

Script `scripts/france_academy_cross_volume_vote_decree_link_v2.py` reads two half-year volumes each for 1926 and 1934. It also recognizes late-1934 index format `— décrets. — Approuvant... `, and the singular `Décret` in 1926. It removes a false duplicate arising from the original parser retaining `parmi les membres non résidants` as though it were part of Pierre Weiss's name. A source page is independent and individually SHA256-pinned for each half-year.

**Live, successful CI**: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39122229395 .

Actual results in **four** half-year volumes:

| Source observation | Result |
|---|---:|
| Individual election **event** candidates | **17** |
| Full-like election event candidates (regular/nonresident/libre) | **13** |
| Correspondent-only election event candidates | **4** |
| Same-volume vote→approval-index links | **11** |
| Next-volume vote→approval-index links | **2** |
| Total vote→approval-index link candidates | **13** |
| No approval **index** match in this/next volume | **4**, all correspondent-only |
| Approving decree-index references parsed | **13** |
| Orphan/duplicate approval-index references after parsing QA | **0** |
| Original printed decree event pages opened | **0** |
| Legally adjudicated government approvals/effective dates | **0** |
| Study member/date accepted | **0 / 0** |

Important: **13/13 full-like election event candidates linked to a decree INDEX reference** in these two specific historical years. This does not establish a universal French member process. The four corresponding election events lacked a matching decree index within the bounded pair; this is an observation about limited transcriptions, not proof correspondents were not approved or not elected. Sample choice is purposeful and should not be used as a population rate estimate.

### Crucial cross-volume examples

| Elected person | Election entry (Tome/page) | Approval notice in immediately following Tome/page |
|---|---|---|
| **Pierre Weiss** | **182 (1926), p.1511**, `membre non résidant` | **183 (1926), p.5**, singular `Décret`, approving election as nonresident |
| **Paul Langevin** | **198 (1934), p.2220**, physics full-section member | **199 (1934), p.5**, lower-case `décrets`, approval notice |

Both are **same-year, next-half-volume** records. Their original printed page number resets to 5 in the following volume. The exact 1926/1934 approval administrative dates and any separate governmental published decree were **not** verified. Never equate the notice's publication/page with an official approval date or the Academy election date.

### Same-volume example claims

| Year | Name | Election index page | Approval index page |
|---|---|---:|---:|
| 1924 | Georges Claude | 1237 | 1297 |
| 1926 | Camille Matignon | 303 | 421 |
| 1926 | Georges Perrier | 506 | 549 |
| 1926 | Jean Charcot | 747 | 817 |
| 1926 | Victor Grignard | 1366 | 1497 |
| 1934 | Antonin Gosset | 312 | 409 |
| 1934 | Gaston Julia | 873 | 997 |
| 1934 | Émile Schribaux | 1104 | 1281 |
| 1934 | Gustave Moussu | 1730 | 1821 |
| 1934 | Jean-Louis Faure | 2048 | 2129 |

Approval documents have NOT been opened merely by extracting these index references. In later phases, selection event, ratification notification, exact ratification date, and effective regular-member date must be separately documented.

## Source files and scientific safeguards

- `scripts/france_academy_vote_decree_index_link_v1.py`
- `scripts/france_academy_cross_volume_vote_decree_link_v2.py`
- `data/france_academy_vote_decree_index_link_pilot_v1/vote_decree_link_candidates_v1.csv`, `summary.json`
- `data/france_academy_cross_volume_vote_decree_pilot_v2/cross_volume_vote_decree_event_chains_v2.csv`: independent election volume and decree volume, page, SHA256, identity key basis, source tier, and **no imputed decree date**.
- `data/france_academy_cross_volume_vote_decree_pilot_v2/summary.json` and `unmatched_decree_index_manual_v2.csv`.

The original Academy member roster is still incomplete for 1666–2025; the CTHS 562 profile candidate set and 211 Wiki-volume bibliography are independent earlier source frames that are not modified here. Later pre-1920 source language may differ; the parser has been deliberately scoped to explicit approval index grammar, with an explicit unknown state rather than inventing administrative acts.

`study_member_acceptance=0`, `study_exact_birthdate_acceptance=0`, `bazi_variables_computed=0`; no prerequisite global study freeze or prior BaZi statistical cohort is altered.

**Next:** Audit a tiny purposively chosen number of original printed election **and** approving decree notice pages, then inventory status for the remaining 188 unprobed table-of-contents subpages in bounded local batches. That is a source validation step, not yet global full membership acceptance.
