# Chess BaZi First-Reveal Analysis Plan v1

**Frozen before any chess BaZi calculation/reveal.**

Source cohort tag expected:
`chess-preregister-v3-date-sanity`

## Confirmatory analyses

### C1 — Day-Master five-element distribution
Report 木火土金水 counts and proportions for 1994 vs 2013, separately by sex
and pooled.

### C2 — Metal/Earth temporal gradient
Predefined direction:
- Metal Day Masters relatively more represented in 1994;
- Earth Day Masters relatively more represented in 2013.

Tests:
- Fisher exact test within sex;
- sex-stratified Mantel-Haenszel directional test.

### C3 — Three-pillar 伤官 / 偏印 exposure
Operationalization:
count occurrences across the six known stem/main-qi positions:
year stem, year branch main qi, month stem, month branch main qi,
day stem, day branch main qi.

Report:
- cohort distributions / means;
- Spearman association with `elo_z_within_snapshot_sex`;
- same-birth-year calendar-null enrichment summaries.

## Exploratory analyses fixed before first reveal

These are **not confirmatory hypotheses**.

### E1 — Water Day Master
Report Water-DM frequency and same-birth-year calendar-null comparison.

### E2 — WaterCount
Count Water among the six known stem/main-qi positions, range 0–6.

### E3 — MetalWaterCount
Count Metal + Water among those six positions, range 0–6.

These are exploratory operationalizations of the pre-existing "水主智 / 金水"
idea and must remain labeled exploratory regardless of result.

## Calendar null

For each player independently, sample a Gregorian date uniformly from the
same birth year. This preserves the exact empirical birth-year distribution.

Monte Carlo replicates: **5000**
Random seed: **20260927**

The null is used for selection/enrichment-style summaries, not to redefine
the historical-period C1/C2 tests.

## BaZi calculation

Engine: `sxtwl`

Known pillars only:
- year
- month
- day

No birth time is imputed.

No Southern-Hemisphere inversion is used because the source population is the
confirmed-Northern-Hemisphere v3 cohort.

## Multiple testing / interpretation

- C1/C2/C3 are reported as the frozen confirmatory family.
- E1/E2/E3 are reported separately as exploratory.
- Exploratory p-values are descriptive and are not promoted to confirmation.
- Newly noticed patterns after this first reveal remain exploratory.
