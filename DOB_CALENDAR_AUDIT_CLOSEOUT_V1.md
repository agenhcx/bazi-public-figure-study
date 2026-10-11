# DOB / Calendar Audit Closeout v1

## Scope

This closeout freezes the **calendar-model / absolute-date normalization layer** for the primary Professor -> Academy -> Nobel hierarchy study **before any BaZi variable computation or inspection**.

It does **not** declare all cohort-level DOB provenance collection complete. Each cohort still remains subject to its own provenance/final-DOB freeze rules. In particular, a candidate-stage DOB row is not promoted to final merely because its calendar normalization is internally consistent.

Primary hierarchy birth-year support was preregistered as the min/max known birth year of the frozen 658-person Nobel science cohort:

- **1835 <= birth_year <= 1985**

Full historical academy rosters remain archived and unchanged; rows outside this window are excluded only from the primary hierarchy comparison.

## Final primary DOB coordinate

All downstream hierarchy analysis must use a **proleptic Gregorian absolute-date coordinate**.

The canonical analysis overlay is produced by:

- `scripts/apply_canonical_gregorian_dob_overlay_v1.py`
- registry: `data/dob_absolute_date_adjudication_v1/canonical_gregorian_dob_registry_v1.csv`

Frozen source datasets are never overwritten.

## Final counts

The completed primary overlay contains:

- total rows: **7,946**
- calendar-eligible rows: **7,944**
- rows changed by adjudication: **6**
- pending calendar-semantics rows: **2**
- frozen inputs modified: **0**
- BaZi variables computed: **0**

By dataset:

| Dataset | Rows | Changed | Pending | Calendar-eligible |
|---|---:|---:|---:|---:|
| Leopoldina candidate | 2,407 | 0 | 0 | 2,407 |
| NAS science-core | 2,240 | 1 | 2 | 2,238 |
| Nobel science exact-DOB | 655 | 3 | 0 | 655 |
| Royal Society | 2,644 | 2 | 0 | 2,644 |

## Confirmed person-level adjudications

Canonical Gregorian overlay corrections:

- Ivan Petrovich Pavlov -> **1849-09-26**
- Nikolay Nikolaevich Semenov -> **1896-04-15**
- Pyotr/Piotr Leonidovich Kapitsa -> **1894-07-08**
  - applies to both Nobel and Royal Society rows
- George B. Kistiakowsky -> **1900-12-01**
- Boris Petrovich Uvarov -> **1886-11-03**

Confirmed no-change:

- Ilya Ilyich Mechnikov -> **1845-05-15**

Pending manual calendar semantics; not calendar-eligible for automatic downstream BaZi analysis:

- Katherine Esau
- Gregory Breit

## Frozen audit provenance

Primary calendar audit input:

- `data/dob_calendar_model_audit_primary_with_nobel_v1_1/calendar_model_audit_rows_v1.csv`
- SHA256: `7b105c02082ac0e887043d9651a5eb08a4de24712e26eaeb8c613e817d4e0987`

Adjudication registry:

- `data/dob_absolute_date_adjudication_v1/canonical_gregorian_dob_registry_v1.csv`
- SHA256: `847c24696bce48810cf865de531daf60bc4dcdea51fae6381f577b42b9730188`

Locally generated overlay summary reviewed for this closeout:

- SHA256: `4dd90ecdcda6346359af6aa6fe1a371709a204c57d619e5b92d007e658ce714e`
- bytes: 1,281

## Interpretation of generic review rows

The broader calendar audit contained many `review_rows`, mostly from:

- missing Wikidata QID bridge;
- current Wikidata lacking exact-day P569;
- multiple exact P569 claims.

These states are **not themselves evidence that the frozen DOB is wrong**. Calendar-specific manual adjudication was limited to cases where historical-calendar semantics or conflicting exact dates could affect the absolute day.

## Closeout rule

From this point forward:

1. Do not alter the frozen source DOB snapshots.
2. Apply the canonical Gregorian overlay by QID.
3. Exclude rows with `analysis_eligible_calendar=0` unless a later versioned adjudication resolves them.
4. Any further DOB correction requires a new versioned amendment with source evidence.
5. Do not retroactively change this v1 closeout after BaZi unblinding; later corrections must be logged as amendments.

**The calendar-model / absolute-date adjudication layer is considered closed for the primary hierarchy study v1. Cohort-level DOB provenance collection must still be completed and frozen before any BaZi unblinding.**
