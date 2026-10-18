# France Academy 1666–2016 Leridon master historical data — acquisition priority v1

Source-research checkpoint 2026-10-18 UTC. This is NOT the final French institutional roster and NO BaZi variables were computed.

## Verified scholarly source and evidence

Henri Leridon, "Démographie de l'Académie des sciences (Institut de France) de 1666 à 2017, et perspectives", Archives Internationales d'Histoire des Sciences 72(188) (2022), DOI: 10.1484/J.ARIHS.5.129761.

A 41-page accepted manuscript was downloaded directly from the public HAL open archive: https://hal.science/hal-03763832v1/file/Leridon_Demographie-Academie-des-Sciences_version-AA_01-2022.pdf . SHA256: 04ac1259f3488a0b88f9fbb4befd238df2f298821a65bf59e7dd7f1ec8f6b752. INED's other download endpoint did not respond to GitHub's runner. Only methodology snippets and the SHA were saved; no full copy is stored in the research repository.

Source paper's PDF p.34–38 (zero-indexed; appendix):
- 2002–2004 manual Excel study: 1,039 strict academy Members, defined as pensionnaires, resident/nonresident Membres, académiciens and académiciens libres, excluding Cadas. This sample is NOT a complete 2016 member count.
- 2018–2020 expanded digitization: N=3,218 biographical entries dating from 1666 through 2016, of which the author says 1,804 correspondants and 1,205 Members. These are author-reported category counts; do not infer that the two numbers exhaust all member categories or statuses.
- The initial 2016 electronic biographical Index was a provisional Word transcription. Manuscript authors found differences from the printed 2016 edition, including names, dates and omissions, and corrected a derived data file.
- In 2022 the author wrote that a complete digitized individual-level file would soon be available on the Academy Archives portal. This is an intention IN THE PAPER, not proof the file was accessible to this session.

## Explicit original database fields (source appendix, PDF pp.37–38)

| Source field | Author's meaning | Analysis safety |
|---|---|---|
| NOM | personal name, birth information | exact identity must be adjudicated |
| ENTREE | first Academy position including rank, date and section | not necessarily first ordinary/full membership election |
| SUITE | later ranks and dates, including transitions | important for correspondent/foreign to ordinary promotions |
| DECES | death date/details | some old death dates were IMPLICITLY IMPUTED, never treat as archival fact |
| DatNais | full birth-date field, 00/00/0000 used for unknown | 85 entries incomplete; do not assume all others date-source certified |
| DatEntree | full date of FIRST Academy entry | distinct from full-member election date |
| PaysNais | birthplace country | independent quality checks needed |
| Etranger | nationality/foreign flag | nationality is NOT proof of the Academy foreign-associate membership category |
| Femme | sex flag | descriptive only, not cohort inclusion |

The author reports 83 unknown years of birth after archival checks, while the DatNais field labels 85 incomplete full dates. These different measures should not be silently equated. The author also reports 40 unknown death dates and an analysis-specific convention imputing death year as first Academy entry year plus 25. Retain imputation flags and NEVER treat those death dates as actual dates.

Key insight: membership status must be evaluated across ALL career transitions, not from ENTREE or Wikidata P463/CTHS one-word classifications. The full-file DOB/election/date coverage could be much better than the current CTHS source-pool, but is NOT accepted until the underlying file is acquired and checked.

## Original individual-level source NOT YET OBTAINED

Potential exact official archive item, title "Fichier des membres de l'Académie issu de l'index biographique, par Henri Leridon":

https://archives.academie-sciences.fr/n/fichier-des-membres-de-l-academie-issu-de-l-index-biographique-par-henri-leridon/n:155

This archive record and https://archives.academie-sciences.fr/ currently return Anubis ACCESS DENIED to automated requests. Do not evade this restriction. A person may try the official archive's normal interactive website or request an authorized copy or further information through https://www.academie-sciences.fr/nos-archives-le-patrimoine-scientifique-de-lacademie . The actual distribution status/format/license of the machine-readable 3218-row master remain unknown.

Independently, the Academy's own 2021 printed archive inventory cites the physical "Index biographique de 1666 à 2016" at https://www.academie-sciences.fr/pdf/dossiers/fonds_pdf/medaillons.pdf . A printed index exists; this audit has not obtained its original 2016 pages.

Legacy BnF 1989 member-only and 1979/1994 index volumes are fallback sources only; the 1994 Gallica OCR/IIIF endpoints gave HTTP403 from a runner. CTHS raw 562 archived HTML files must not be downloaded again.

## Integration and prospective freeze

Do not append all 160 already checked modern elected names to a 2016 master: 48 were elected in 2010–2014, already within the 2016 master window, and can be used as a source validation holdout. There are 112 currently source-identified new member-elections in years 2017–2025 (2017 18; 2019 18; 2020 4; 2022 18; 2023 18; 2024 18; 2025 18). Years 2018 and 2021 remain UNKNOWN for separate ordinary elections, not zero by assumption. Some new promotions of pre-2017 correspondents might also be absent without later updates.

Keep the entire historical institutional roster and all membership events before filtering candidate research birth years 1835–1985. Only after the historic original index/Excel has been lawfully obtained and the exact schema observed should a source-specific bulk parser be written. Prefer source access and 20 checked individuals to another large blind scrape.

## CTHS 2016 index citation addendum

The 562 existing source pages were replayed OFFLINE from the archived SHA-pinned tarball to check for source citations to the *2016* printed index (an edition missed by the previous 1979/1989/1993-only audit). **One** source citation was found: Mikhaïl Gromov (CTHS ID 125186), not previously in the 130 historical volume citation queue. This is a bibliographical lead, NOT direct evidence from the printed index itself.

Files: scripts/france_academy_cths_2016_index_citation_addendum_v1.py and data/france_academy_leridon_historical_master_source_pilot_v1/cths_2016_index_citation_summary_v1.json. 562 checked; 0 new DOBs/statuses accepted and 0 BaZi outputs.

Other evidence manifests:
- data/france_academy_leridon_historical_master_source_pilot_v1/summary.json (two manuscript host access results).
- data/france_academy_leridon_historical_master_source_pilot_v1/appendix_methodology_summary.json (methodological evidence page anchors).
- data/france_academy_leridon_historical_master_source_pilot_v1/original_master_and_fallback_source_access_manifest_v1.csv (status of seven acquisition routes).

Global hierarchy preregistration and anti-unblinding freeze remain unchanged.
