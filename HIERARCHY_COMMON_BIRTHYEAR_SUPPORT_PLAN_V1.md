# Hierarchy Common Birth-Year Support Plan v1

## Purpose

Define the primary professor -> academy -> Nobel hierarchy comparison on a birth-year range supported by the frozen Nobel science cohort, rather than allowing centuries of historical academy membership to enter the primary comparison.

The complete historical academy rosters remain preserved as archive/master data. This rule only defines eligibility for the **primary hierarchy analysis cohort**.

## Pre-unblinding rule

This plan is frozen before any hierarchy BaZi variables are computed or inspected.

1. The birth-year support window is derived from the frozen Nobel science person-level roster:
   `data/nobel_science_enriched_v1/nobel_science_people.csv`.
2. The window uses **known birth year**, not exact-DOB availability.
   - This prevents exact-DOB missingness from changing the cohort-era definition.
   - Nobel laureates with known year but unresolved month/day still contribute to the support boundary.
3. Let:
   - `NOBEL_MIN_BIRTH_YEAR = min(known Nobel birth years)`
   - `NOBEL_MAX_BIRTH_YEAR = max(known Nobel birth years)`
4. Primary hierarchy eligibility for professor/academy/Nobel cohorts requires:
   `NOBEL_MIN_BIRTH_YEAR <= birth_year <= NOBEL_MAX_BIRTH_YEAR`.
5. Exact DOB remains required for downstream BaZi computation, but **not** for defining the birth-year window.
6. The full historical Royal Society / Leopoldina / NAS rosters remain unchanged. Rows outside the Nobel-supported window are excluded only from the primary hierarchy comparison.
7. Calendar-model/source adjudication effort for the primary study is prioritized to rows inside the Nobel-supported window. Older historical rows may remain in archival audit outputs without manual adjudication.
8. Within the eligible window, downstream hierarchy models must still account for birth-year/era structure (for example preregistered birth-year strata, decade strata, or weighting/matching). A min/max window alone is not treated as complete control for era confounding.
9. No BaZi variables are computed by the support-window script.

## Canonical outputs

`data/hierarchy_common_birthyear_support_v1/`

- `nobel_birthyear_support_summary.json`
- `nobel_birthyear_distribution.csv`
- `cohort_birthyear_eligibility_summary.csv`
- `manifest.json`

The exact numerical lower/upper bounds are written by the deterministic script from the frozen Nobel roster and are not manually chosen.
