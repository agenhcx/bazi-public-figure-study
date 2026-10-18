# France Academy original Comptes rendus: 211-volume source inventory, independent 12-volume holdout and original facsimile spot-check v1

**Source-research checkpoint:** 2026-10-18 UTC, all output strictly **before** original member-roster and multi-academy global research cohort freezes. Original Academy published election documentation exists, but this work does **not** assert an exhaustive 1666–2025 member census, does not compute BaZi or change any frozen dates/memberships.

## 1. Source frame: official Academy archives versus Wikisource

The French Academy's own journal page lists year-specific original printed `Comptes rendus` volumes from 1835 onward and provides retrospective multi-decade indexes. Its public URL is:

https://comptes-rendus.academie-sciences.fr/page/consulter-les-anciens-numeros-1835-1996_fr/

Our deterministic, historical year–volume mapping, crosswalked to Wikisource's public category `Catégorie:Index - Comptes rendus hebdomadaires des séances de l’Académie des sciences`, produced the exact **211 volumes numbered 1 through 211**, 1835–1940 inclusive (106 publication years). Each of the 211 entries matches the Academy's official annual-archive entry and contains a public original-archive link: **209 separate volume links**, plus **two 1939 volumes, 208 and 209**, which share one official linked source in the Academy's annual row. This is **volume/link metadata**, not inspected original full scans.

Wikisource links are to original scanned `Livre:` items; however, a scanned `Livre:` existing does **not** imply a transcribed `Table des matières`, an available individual event page, or a complete historical roster.

## 2. Deliberately separated discovery and holdout coverage

To avoid extrapolating from our five selected 1919/1924/1926/1931/1934 *Comptes rendus* pilot volumes, the first historical availability audit covered 11 purposively spread-out volumes; a separate 12-volume holdout covered **nonoverlapping** volume identifiers.

| Sample | Volumes tested | Public Table des matières HTTP200 | HTTP404 | Recognized election heading | Source index event candidates |
|---|---:|---:|---:|---:|---:|
| Discovery | 11 | 9 | 2 | 6 | 40 |
| Holdout | 12 | 6 | 6 | 2 | 8 |
| **Total** | **23** | **15** | **8** | **8** | **48** |

The exact volume-level outcomes, avoiding any silent missingness imputation, are:

| Group | Volume/year | Table result | Candidate indexed election events |
|---|---|---|---:|
| Discovery | 1 / 1835 | 200, election heading | 1 |
| Discovery | 20 / 1845 | 404 | unknown |
| Discovery | 54 / 1862 | 200, no election heading recognized | 0 *parsed* |
| Discovery | 91 / 1880 | 200, nominations heading | 4 |
| Discovery | 121 / 1895 | 200, no heading recognized | 0 *parsed* |
| Discovery | 136 / 1903 | 200, no heading recognized | 0 *parsed* |
| Discovery | 158 / 1914 | 200, election heading | 8 |
| Discovery | 168 / 1919 | 200, election heading | 13 |
| Discovery | 182 / 1926 | 200, election heading | 8 |
| Discovery | 198 / 1934 | 200, election heading | 6 |
| Discovery | 211 / 1940 | 404 | unknown |
| Holdout | 2 / 1836 | 404 | unknown |
| Holdout | 21 / 1845 | 404 | unknown |
| Holdout | 55 / 1862 | 200, no heading recognized | 0 *parsed* |
| Holdout | 92 / 1881 | 404 | unknown |
| Holdout | 120 / 1895 | 200, no heading recognized | 0 *parsed* |
| Holdout | 122 / 1896 | 404 | unknown |
| Holdout | 137 / 1903 | 404 | unknown |
| Holdout | 159 / 1914 | 200, no heading recognized | 0 *parsed* |
| Holdout | 169 / 1919 | 200, election heading | 5 |
| Holdout | 183 / 1926 | 200, no heading recognized | 0 *parsed* |
| Holdout | 199 / 1934 | 200, election heading | 3 |
| Holdout | 210 / 1940 | 404 | unknown |

**Important**: A 404 on a *Table des matières* subpage is not a 404 on the underlying `Livre:` scan or the official Academy original. An index without a detected election heading might be incompletely transcribed, use a different editorial heading, or genuinely lack such election events in that *half-year volume*; our parser cannot adjudicate absence. Thus `0 parsed` never authorizes a historical `0 elections that year` claim. 48 are indexed event *candidate rows*, not 48 unique full academicians, nor a random draw permitting an estimated membership percentage. Of 211 inventoried volumes, **188 table-of-contents subpages remain entirely unprobed**.

Separate successful CI source runs:
- 11-volume discovery + 211 official-to-Wikisource link inventory: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39117999447
- 12-volume nonoverlapping holdout and correct sequential GitHub checkpoint: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39118293116
- initial holdout **data processing succeeded** but concurrent workflow commits prevented the final GitHub push; failure recorded at https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39118167776 . Re-run included a fetch/rebase before push.

## 3. Corrected historical parser and prevention of false zero counts

The modern index table markup uses HTML `<tr>`/`<td>` rows. **The 1835 original Wikisource table of contents instead used `div.tableItem`, `div.ws-titrex` and `div.ws-titpge`, often outside the `.mw-parser-output` container.** Earlier pilot scanners incorrectly returned 0 election-event candidates in this older part of the publication series.

Separately, pre-1914 indexes may use headings `Élections`, `Nominations de membres et de correspondants`, or other editorial forms rather than only later `Élections de membres et de correspondants`. The correction:
- correctly restores the 1835 `Élections` record for **Élie de Beaumont** (printed p.515);
- finds 1880 `Nominations` corresponding elections for Brioschi (p.903), Abria (p.960), Sella and Warren de la Rue (both p.1044);
- preserves the already-audited 1926 `FULL_SECTION_MEMBER` vs `CORRESPONDENT` classifications;
- excludes candidate nominations, predecessor names after `en remplacement de`, prize panels, government decrees and elections of Academy administrative officers from automatically becoming *new* Academy full-member admissions.

Legacy parser and source audit: `scripts/france_academy_wikisource_legacy_election_headings_v1.py`, `data/france_academy_wikisource_legacy_heading_pilot_v1/summary.json`. Synthetic and live source run https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39118186355 and later v1_3 rerun. Exactly **13** transcribed event candidates in its four source volumes (1835 v1 1, 1862 v54 0 parsed, 1880 v91 4, 1926 v182 8), including **6 full-like** and **7 corresponding/foreign** candidates. The original 1835 name did not strictly match the existing *562 CTHS priority DOB biographies*; this subset is not complete and the absence is not a denial of his election.

## 4. First direct original facsimile check: 1835, original printed p.515

**Source:** `Comptes rendus hebdomadaires des séances de l’Académie des sciences`, Tome 1 (1835), **page 515**, original image displayed from the original scanned DjVu through Wikisource's Page namespace:

https://fr.wikisource.org/wiki/Page%3AComptes_rendus_hebdomadaires_des_s%C3%A9ances_de_l%E2%80%99Acad%C3%A9mie_des_sciences%2C_tome_001%2C_1835.djvu/515

The original page facsimile was **directly visually examined**, not merely the transcription. It states Academy vote within the session dated **21 December 1835**, section of mineralogy and geology, 51 voting members, **45 votes for Élie de Beaumont**, and then expressly states his appointment will be submitted for **royal approval**. The index's printed page number, person and event are consistent with the original-page content. We have NOT obtained a separate original royal-approval decree, so do not mark final legal approval or effective full membership as directly verified.

The exact event source was separately transcribed at:

https://fr.wikisource.org/wiki/Comptes_rendus_de_l%E2%80%99Acad%C3%A9mie_des_sciences/Tome_1%2C_1835/21_d%C3%A9cembre

The facsimile image was viewed but **not downloaded or byte-hashed**. Its original source URL and explicit absent image hash are recorded, avoiding a fabricated SHA-256, in `data/france_academy_comptes_rendus_211_volume_inventory_v1/original_page_facsimile_qc_v1.json`. This is a ONE-PAGE positive audit, not a measured overall transcript accuracy rate. An original page visual audit was *not* completed for other candidate events yet.

**Event state model** for early years must distinguish:
1. candidature/proposition (candidate not elected);
2. Academy internal election ballot or nominating vote;
3. royal/government approval or promulgation, separately attested;
4. resulting membership type/effective date, after reconciling any later transitions.

Avoid treating four historical records about the same person as four new independent members.

## 5. Artifacts and next collection stage

Source-only scripts:
- `scripts/france_academy_comptes_rendus_211_volume_inventory_v1.py` (Python>=3.10, BeautifulSoup, optional cache, `--fixture-check`, `--offline`, `--dry-run`, volume list `--sample-volumes`, `--max-table-probes`).
- `scripts/france_academy_wikisource_legacy_election_headings_v1.py` (supports modern tables plus pre-1850 `div.tableItem`, and separate corresponding/full classes).

Deterministic metadata (no republished scans or large source HTML):
- `data/france_academy_comptes_rendus_211_volume_inventory_v1/academy_original_wikisource_211_volume_inventory_v1.csv` and `summary.json`: all 211 linked book entries, **only** 11 subpage probes flagged.
- `data/france_academy_comptes_rendus_211_volume_holdout_v1/academy_original_wikisource_211_volume_inventory_v1.csv` and `summary.json`: same 211 links but **only** 12 different subpage probes flagged.
- `data/france_academy_wikisource_legacy_heading_pilot_v1/historical_nominations_elections_candidates_v1.csv`, `summary.json`: early terminology source event candidates.
- `data/france_academy_comptes_rendus_211_volume_inventory_v1/original_page_facsimile_qc_v1.json`: 1 source page visually checked, flags royal approval *not* directly established.

**Next research direction:** build a resumable local public-source table-subpage collector only after an access/availability inventory, with separate status gates for `BOOK_EXISTS`, `TABLE_HTML_READABLE`, `ELECTION_LINE_PARSED`, `ORIGINAL_EVENT_SCAN_VERIFIED`, `CLASS_AND_APPROVAL_ADJUDICATED`, and final `STUDY_MEMBER_ACCEPTED`. Respect rate limits and use an explicitly bounded number of remote requests per batch. For failed page URLs, attempt lawful official-source originals or a human-operated browser, not access-control evasion. The Academy's 1666–1834 early centuries and 1941–2025 remain outside this 1835–1940 book inventory; this route on its own cannot establish a complete historical denominator.

**Research safeguards:** All previous 562 CTHS raw HTML snapshots, 529 syntactically exact source DOB claims, 160 noncontinuous first-party modern election candidates, and the Jean Roche / Robert de Vernejoul disputed birth dates remain unchanged. `accepted_full_memberships=0`, `accepted_exact_dobs=0`, `bazi_variables_computed=0` for this audit. No image generation, DOB-based hypothesis change, cohort unblinding, or data request emails.
