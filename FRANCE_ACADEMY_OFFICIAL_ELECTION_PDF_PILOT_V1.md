# France Académie des sciences — first-party election PDF source pilot v1

Collection-only pre-unblinding checkpoint. Source-review date: 2026-10-17 local / 2026-10-18 UTC.

## Purpose and research guardrails

Build an official **historical domestic/full-member election candidate source layer**, distinct from the 2,144 CTHS secondary biographical identities, the 529 original CTHS complete-birthday claims, the 562-source archive and 36 recent 2024/2025 presidential ratification records. Do not replace or recrawl those older sources.

All authoritatively named election groups stay in a historical master roster; downstream primary analysis will restrict to the frozen Nobel 1835–1985 birth-year support, *after* complete Academy membership and DOB source adjudication. No astrological features are generated or inspected in this pilot.

**Election date != government approval date != later receipt/ceremony date.** For example, the original 15 March 2011 communiqué says 9 members elected 30 November **2010** and 12 elected 15 March **2011**. The 2 May 2011 government decree approved all 21. These are two election cohorts, **not 21 2011 elections**.

## Four fetched official election source PDFs and candidate evidence

| Source ID | First-party event | Electees | Person-level DOB precision | Original file |
|---|---|---:|---|---|
| FR2011 | 2010-11-30 (9) and 2011-03-15 (12) | 21 | All 21 day/month/year claims, including one '1e' ordinal typo | https://verimag.univ-grenoble-alpes.fr/IMG/pdf/CP_12NvxMembres_Elus15mars2011.pdf (French Academy original press PDF, university mirror) |
| FR2013 | 2013-12-10 | 17 | No complete DOB field in 2013 elected-members brochure; *no guessing* | https://www.academie-sciences.fr/pdf/documentation/elus_2013/plaquette_nouveaux_elus.pdf |
| FR2014 | 2014-11-18 | 10 | Birth **year only**, not month/day | https://www.academie-sciences.fr/pdf/communique/election_191114.pdf |
| FR2017 | 2017-12-05 | 18 | No complete DOB field in election PDF | https://www.academie-sciences.fr/pdf/membre/election_051217.pdf |
| **Total** | | **66** | **21 day-level + 10 year-only + 35 with no DOB in selected source** | |

The 2014 communiqué names Bernard Meunier as incoming PRESIDENT and Sébastien Candel as incoming VICE-PRESIDENT; both were already members and are **NOT new 2014 electees**. The published list of ten newcomers is separated by the 'ONT ÉTÉ ÉLUS' heading. The script and golden fixture count only those 10. In the 2011 PDF, the 2010 and 2011 named election cohorts must be split by their original headings, not by calendar publication/decree.

### PDF text-layer problems and exact source replay

This source family has two independent issues:
- The 2011 original PDF prints 'Édouard Bard, né le **1e septembre 1962**' (printed p4, PDF page index3). Only the date *candidate* 1962-09-01 is inferred from the explicit first-of-month ordinal, with a separate `PDF_ORDINAL_1e_REQUIRES_REVIEW` flag. The source doesn't get silently edited.
- The 2013 booklet prints all 17 names correctly (visual printed p3), **but its PyMuPDF text extraction loses an initial capital glyph of eight surnames**: e.g. 'Laure aint-Raymond' for Laure Saint-Raymond, 'Barbara omanowicz', 'Odile isenstein', etc. The script rescues ONLY eight hard-coded person/damaged-text/printed-profile-page triples, each visually checked on printed p3. They are tagged `PDF_FONT_INITIAL_MISSING_VISUALLY_QA_RECOVERED`, never silently treated as verbatim machine text. Other future extraction defects stay unresolved.

The first-party document-based name/field check succeeded in GitHub Actions after those guardrails:
- 66/66 election identities matched.
- 20 exact-date fields directly parsed; 1 ordinal-repair candidate.
- 10 year-only DOB claims; 35 source-roster name/discipline-only.
- 8 first-party visual-index font-loss rescues.
- 0 inaccessible/bad-source PDFs; 0 unmatched people.
- NO independent DOB *second-source* corroboration is claimed here. First-party Academy PDF evidence is stronger than CTHS, but an exact date is still a source claim until the evidence-tier acceptance ledger and final cohort freeze.

## Foreign membership negative control

The historical presidential decree of 15 January 2010 concerns **foreign associates**, not the 2010 November domestic-member election: https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000021715817 .

The Academy's 2021 session electing **16 associés étrangers**, announced in January 2022, is also explicitly excluded from the domestic full-member source collector: https://www.academie-sciences.fr/en/node/1001 . The PDF negative-control manifest row has no primary elected-member output.

## Next first-party source discovery (not scraped here)

The file `data/france_academy_official_election_pdf_pilot_v1/next_source_route_inventory_v1.csv` lists 2019 (18), 2020 (4, same larger campaign), 2021 foreign-only negative control, 2022 (18), 2023 (18), and existing 2024/2025 election groups (18 each, already audited against subsequent government decrees; do not recrawl redundantly). Cross-year membership year and category are explicit fields, not inferred from the press release filename or reception date.

## Source-tested local Windows operation

Repository: `C:\chenxi\bazi_project\1986wiki`. Requires Python 3.10+ plus `requests==2.32.3` and `pymupdf==1.26.5`. From the repository root:

`git pull --ff-only`

`python -m pip install requests==2.32.3 pymupdf==1.26.5`

`python .\scripts\france_academy_official_pdf_source_pilot_v1.py --fixture-check`

`python .\scripts\france_academy_official_pdf_source_pilot_v1.py --fetch --limit 4 --resume`

`python .\scripts\france_academy_official_pdf_source_pilot_v1.py --offline --limit 4`

The last two commands save four PDF sources to gitignored `local_runs/france_academy_official_pdf_pilot_v1/cache/`; `--resume` reuses hashes and previous successful downloads, `--offline` does not make any HTTP requests. Each document has an independent URL + SHA256 + page count + type gate and each person row keeps page number, date precision, source status, first-party class candidate. No PDF bytes are committed to GitHub or pasted into chats; only compact source/identity CSV and summary are relevant.

**This script only handles the four whitelisted PDF layouts. It is not a generalized French archival scraper.** Before doing a larger Windows-local batch over 2019–2025 or older historical election notices, extend and test the source-type parser first, then enable the next bounded source manifest. Do not pretend the follow-up inventory was already downloaded or accepted.

## Source files

- `data/france_academy_official_election_pdf_pilot_v1/source_document_inventory_v1.csv`
- `data/france_academy_official_election_pdf_pilot_v1/official_election_name_DOB_transcription_v1.csv`
- `scripts/france_academy_official_pdf_source_pilot_v1.py`
- GitHub Actions four-document smoke: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39089889165

**Institutional full-member eligibility is not globally frozen; all BaZi variables remain blinded.**
