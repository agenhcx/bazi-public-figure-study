# NAS Science-Core Analysis Preregistration v1

## Purpose and timing

This document is frozen **before any BaZi variables are computed for the NAS science-core cohort**. Its purpose is to lock the data version, transformation rules, missingness handling, and the previously stated directional hypotheses before looking at NAS BaZi outcomes.

This document does **not** turn the NAS cohort into a standalone discovery set. NAS is the academy tier of the broader professor → academy → Nobel hierarchy study. Cross-tier inferential details will be finalized in a separate preregistration before the professor cohort is analyzed.

## Frozen NAS input

- Cohort definition: NAS science-core regular Member/Emeritus roster, primary sections 12–16, 21–29, and 41–44, elections through 2025.
- Total cohort: **3,051**.
- Exact DOB available: **2,238 / 3,051 = 73.353%**.
- Missing exact DOB: **813**.
- Deceased: **1,360 / 1,360 = 100% exact DOB coverage**.
- Living: **878 / 1,691 = 51.922% exact DOB coverage**.
- Frozen source checkpoint: `nas_science_core_dob_crosswalk_v16.csv`.
- Frozen CSV SHA256: `f577b22bf646b4b5355a133cc265d4d9ccf253f501bac98b6afddce874fc4561`.
- GitHub Actions source artifact: run `37860554354`, artifact `11586500739`.
- No birth-time data are used.
- At the time of this preregistration: **bazi_variables_computed = 0**.

Any later DOB correction must be a new, versioned provenance amendment. It must not silently modify v16.

## Missingness facts known before BaZi computation

Missingness is strongly associated with recency and living status, so raw complete-case NAS results must not be treated as if DOB availability were random.

Exact-DOB coverage by election decade:

| Election decade | Exact / total | Coverage |
| --- | ---: | ---: |
| 1960s | 236 / 237 | 99.58% |
| 1970s | 425 / 430 | 98.84% |
| 1980s | 362 / 384 | 94.27% |
| 1990s | 305 / 380 | 80.26% |
| 2000s | 281 / 436 | 64.45% |
| 2010s | 246 / 504 | 48.81% |
| 2020s | 123 / 420 | 29.29% |

Among living members, exact-DOB coverage is **75.30% for pre-2000 elections** and **44.27% for 2000+ elections**.

Section-level coverage also varies materially. Therefore section and election era are pre-specified missingness covariates.

## Date-to-BaZi transformation rules

Only exact Gregorian birth dates are transformed. Exact DOB is never imputed from a birth year, age, approximate date, or weak web source.

Because birth time is unavailable, only the six date-known characters are derived:

- year stem
- year branch
- month stem
- month branch
- day stem
- day branch

No hour pillar is inferred or approximated.

A single fixed calendar algorithm/version must be recorded in the analysis output. The year/month pillar convention must use solar-term boundaries rather than lunar-month boundaries.

Because exact birth time and often birthplace/time zone are unavailable, solar-term boundary cases are a known ambiguity. The primary date-level assignment may use the fixed implementation's civil-date convention, but every analysis involving year or month pillars must include a sensitivity analysis excluding DOBs within **±1 civil day** of Li Chun or the relevant monthly Jie transition.

## Pre-specified BaZi variables

The day stem is the Day Master.

### Primary representation

1. **Month-order main-qi Ten God**: the Ten God relation between the Day Master and the main qi of the month branch.
2. **Five informative date-known positions excluding the deterministic Day Master itself**:
   - year stem
   - month stem
   - year-branch main qi
   - month-branch main qi
   - day-branch main qi
3. For each of the Ten Gods, compute:
   - count among those five positions, range 0–5
   - binary presence/absence
4. Day Master classifications:
   - 10 Heavenly Stems
   - five-element Day Master
   - yin/yang Day Master

Hidden-stem expansions are not part of the primary analysis. If used later, they must be explicitly labeled secondary/exploratory.

## Locked directional hypotheses for the broader hierarchy study

These hypotheses pre-date inspection of NAS BaZi outcomes.

- **H1: 伤官 / 偏印 tier gradient.** Their prevalence or five-position burden is expected to increase from professor → academy → Nobel.
- **H2: 正官 / 正印 reverse gradient.** Their prevalence or five-position burden is expected to be relatively higher in the professor tier and lower at the academy/Nobel tiers.
- **H3: cohort trend.** 伤官 / 偏印 signals are expected to weaken in more recent birth cohorts.
- **H4: metal-Day-Master pattern.** Any increase of 金日主, especially 庚金, at higher tiers is exploratory unless separately frozen before the corresponding cross-tier test.

NAS-only feature frequencies are descriptive/bridge results and must not be used to invent new confirmatory hypotheses for the professor or Nobel cohorts.

## Missingness handling

Primary NAS summaries use the 2,238 exact-DOB complete cases, but every reported result must show the corresponding coverage context.

Required sensitivity views:

1. all exact-DOB NAS members;
2. deceased-only NAS members, for which DOB coverage is complete;
3. living-only NAS members;
4. election-decade-stratified summaries;
5. section-stratified summaries;
6. solar-term-boundary exclusion sensitivity.

A secondary inverse-probability-weighting sensitivity may be used for living members only. If used, DOB availability is modeled **without BaZi variables** using election decade and NAS section as predictors. Weights must be computed before inspecting weighted BaZi effects and must be capped at a pre-declared percentile to prevent extreme influence.

No exact DOB is imputed for the 813 unresolved members.

## Cross-tier analysis guardrails

Raw pooled NAS-vs-Nobel or professor-vs-NAS percentages are not sufficient because the groups differ by birth cohort and NAS DOB missingness is strongly era-dependent.

Before any confirmatory professor → academy → Nobel comparison:

- professor cohort collection must be frozen;
- cohort-specific DOB coverage must be reported;
- birth-cohort adjustment or matching must be specified before outcome inspection;
- the four primary Ten-God directions above must not be changed based on NAS descriptive results;
- multiple-testing correction must be fixed in the cross-tier preregistration.

## Stop rule for NAS DOB acquisition

Systematic exact-DOB acquisition stops at v16. New DOBs may be added only when a genuinely new high-authority source is found or when a small manually audited correction set resolves a documented provenance issue.

Weak-source filling to increase coverage is prohibited.

## Reproducibility

Every downstream NAS BaZi output must record:

- input v16 SHA256;
- transformation script commit SHA;
- calendar library/version;
- boundary-case policy;
- row counts before/after each exclusion;
- `bazi_variables_computed` state transition;
- hashes of final analysis-ready files.
