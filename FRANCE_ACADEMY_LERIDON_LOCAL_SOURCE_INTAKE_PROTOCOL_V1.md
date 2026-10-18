# France Academy original 3218-person master: local intake gate v1

**Status: READY TO INSPECT REAL SOURCE, BUT REAL SOURCE NOT RECEIVED.**
The original workbook/Word/CSV issued by Académie des sciences / Henri Leridon is still missing. Do not fabricate an Excel, or describe synthetic tests as real-source validation.

## Data owner and source

- Exact historical archive item: https://archives.academie-sciences.fr/n/fichier-des-membres-de-l-academie-issu-de-l-index-biographique-par-henri-leridon/n:155
- Verified Academy official Archives contact: archives@academie-sciences.fr, https://www.academie-sciences.fr/nos-archives-le-patrimoine-scientifique-de-lacademie
- Primary manuscript: Leridon 2022, DOI 10.1484/J.ARIHS.5.129761, archived accepted manuscript https://hal.science/hal-03763832v1/file/Leridon_Demographie-Academie-des-Sciences_version-AA_01-2022.pdf . Appendix documents 3218 historical source entries through 2016; columns NOM, ENTREE, SUITE, DECES, DatNais, DatEntree, PaysNais, Etranger, Femme.
- Explicit file access inquiry **UNSENT**: FRANCE_ACADEMY_LERIDON_3218_OFFICIAL_DATA_REQUEST_DRAFT_V1.md

## Local schema-only import probe

Script: scripts/france_leridon_original_file_schema_probe_v1.py

Entirely offline and Python standard library (3.10+). Does **not** evaluate spreadsheet formulas, external references, macros, network requests, or BaZi features. XLSX is read-only through ZIP/XML with conservative memory/size limits. CSV/TSV is read with encoding and delimiter detection. DOCX is classified by structural paragraph/table counts and requires a separate person-record parser. Legacy XLS/DOC is detected but NOT decoded: leave the original unchanged and only convert to CSV with verified losslessness and data types after actual format is known.

### Procedure (each PowerShell command single line)

From the user's current repository clone:

    git pull --ff-only

Synthetic test only (already successful in GitHub Actions):

    python .\scripts\france_leridon_original_file_schema_probe_v1.py --fixture-check

After obtaining an authentic archive file, **not before**, run the actual source probe, replacing the sample path:

    python .\scripts\france_leridon_original_file_schema_probe_v1.py --source "C:\chenxi\bazi_project\scientists\external\leridon_original.xlsx"

The sample filename and extension above are **illustrative placeholders**, not a claim this specific archive file exists.

Only compact output: local_runs/france_academy_leridon_original_file_probe_v1/summary.json (ignored by Git). This includes original file SHA256, detected format, original field names/column positions, source row count (unverified provenance), missingness and date precision categories, role-term occurrences and other sheet names. It never exports person names, day-level dates, birth places, or full membership-history text. Share **only summary.json** for initial review.

### Critical data acceptance gates AFTER actual file arrives

1. Verify provenance: original 3218-person research file? File rights, version, source date/size/hash, content sheets and author/custodian statement. No row count assumed from mere article references.
2. Check schema: confirm actual field names and whether dates are strings, Excel serial numbers, missing sentinels, or mixed. **Never treat 00/00/0000, null or a raw Excel numeric serial as a verified day-level birthdate.**
3. Record duplicate identities and spellings without silently merging records. The 3218 sample may use one record per person, but this must be checked; article aggregate counts are not a signed data-integrity contract.
4. Historical membership timeline from ENTREE *plus* SUITE, not from the first role or nationality alone. French Academy 2004 strict-member definition and the 2018–2020 full-category definition differ.
5. Quarantine demographic-model imputation: the article mentions unknown/death-year imputations; never convert modeled dates to actual calendar events.
6. Sample original source against 20 known Academy historical people, including regular vs correspondant vs foreign and category changes. Preserve original printed source and external supporting documents.
7. After establishing legitimate historical 1666–2016 master coverage, reconcile 112 known elected members from 2017–2025, check unverified election years 2018 and 2021, and preserve all earlier promotion states. Only then study birthyear support 1835–1985 and conditional/missingness audit can be frozen.
8. **Do not compute or inspect BaZi variables before the global Nobel/professors/all-academies cohort freeze.**

## Smoke test

The synthetic fixture exercises:
- CSV-like 9-column Leridon schema (DATNAIS field) and counting missingness flags;
- a tiny XLSX with same headers using Office Open XML in a temporary file;
- exact day string, 00/00/0000 unknown, invalid calendar date, raw Excel date serial.

GitHub Actions synthetic source-only test:
https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39102280909

These tests demonstrate the schema probe runs correctly on synthetic input. **They are not validation of Leridon's 3218 real rows, which have not been obtained.**
