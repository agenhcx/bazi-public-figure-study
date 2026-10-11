# Cross-study DOB Calendar-Model Audit Plan v1

## Purpose

Audit whether exact dates of birth used across the public-figure studies are represented on a consistent absolute-day coordinate before any downstream BaZi computation.

This audit was triggered by the Leopoldina provenance pass, where Wikidata JSON preserved Julian-calendar P569 values while RDF/QLever exposed the same instants as proleptic Gregorian dates. That interface difference created apparent 12/13-day DOB conflicts unless calendarmodel was handled explicitly.

## Locked audit rules

1. **Audit only; no automatic DOB rewriting.**
   - Existing frozen DOBs remain unchanged during this audit.
   - Any real correction requires a separately versioned DOB amendment.

2. **Identity links must be exact, not fuzzy.**
   - Existing Wikidata QIDs are used directly where available.
   - Exact external-ID bridges may be used:
     - Leopoldina member ID: P10299
     - Royal Society current Fellow ID: P2070
     - Royal Society past Fellow ID: P8612
     - US NAS member ID: P5380
   - No name-only fuzzy matching is allowed.

3. **Calendar model is read from raw Wikidata JSON P569 claims.**
   - Gregorian calendar model: Q1985727.
   - Julian calendar model: Q1985786.
   - Day-precision Julian values are converted to the equivalent **proleptic Gregorian absolute date** before comparison.

4. **Comparison statuses are descriptive QA states.**
   - `aligned_gregorian`
   - `aligned_after_julian_normalization`
   - `stored_raw_julian_needs_amendment`
   - `stored_date_not_in_current_p569`
   - `aligned_but_multiple_exact_p569_dates`
   - identity/no-exact-P569 review states

5. **Wikidata does not override a frozen source.**
   - A mismatch is a review flag, not an automatic correction.
   - Source-level adjudication remains governed by each cohort's frozen provenance rules.

6. **No BaZi variables may be computed or inspected during this audit.**

## Cohort order

Primary hierarchy cohorts:
1. Nobel science laureates
2. NAS science-core
3. Royal Society primary Fellows
4. Leopoldina science-core

Low-risk cross-study confirmation:
5. Chess 1994/2013 northern primary cohorts
6. Table tennis 1985-2008 training cohort
7. Music cohorts in a later adapter if needed

The first script version audits cohorts whose exact identity bridge and local canonical input are already available. If a frozen master is not present locally/repository-tracked, the script records that fact rather than guessing another file.

## Outputs

`data/dob_calendar_model_audit_v1/`

- `calendar_model_audit_rows_v1.csv`
- `p569_claims_exploded_v1.csv`
- `julian_claim_review_v1.csv`
- `date_or_identity_review_v1.csv`
- `dataset_summary_v1.csv`
- `royal_society_exact_id_bridge_v1.csv` when RS is included
- `summary.json`
- `cache/` for rebuildable API responses; ignored by Git

## Interpretation

The computational date coordinate for downstream cross-study work is the proleptic Gregorian absolute date. A Julian civil date and its Gregorian-normalized date are two labels for the same historical day; only the normalized absolute date should be used as the shared day coordinate.

This plan is fixed before inspection of cross-study audit results.
