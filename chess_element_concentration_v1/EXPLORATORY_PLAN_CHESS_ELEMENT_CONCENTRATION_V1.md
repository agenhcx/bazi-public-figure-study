# Chess Elemental-Concentration Analysis Plan V1

## Evidence status

This hypothesis was conceived **after prior chess BaZi results had already been
revealed**. Therefore this analysis is explicitly:

> post-reveal exploratory, with the analysis plan frozen before the first
> calculation of elemental-concentration variables.

It is NOT described as a preregistered prospective replication and must not be
promoted to one after seeing the result.

## Motivation

A traditional-style BaZi idea sometimes expressed informally is that a more
concentrated elemental structure may be stronger or clearer than a highly mixed
five-element structure. This study does **not** equate the operational variables
below with formal 专旺格 / 从格 classifications, because exact birth hour is not
available and traditional格局 determination uses more than simple element counts.

The empirical construct is therefore called **elemental concentration/diversity**.

## Fixed BaZi representation

Known three pillars only:
- year stem
- year branch main qi
- month stem
- month branch main qi
- day stem
- day branch main qi

Exactly six positions.

No:
- birth hour
- hidden secondary stems
- 三合/三会/六合 transformation
- 格局 reclassification
- post-result weighting of positions

Branch main qi mapping is frozen as:
子癸 丑己 寅甲 卯乙 辰戊 巳丙 午丁 未己 申庚 酉辛 戌戊 亥壬.

## Frozen elemental metrics

### Primary metric
`distinct_elements_6pos`
Number of distinct five-element categories represented in the six known
stem/main-qi positions. Range 1–5.

### Secondary robustness metrics
- `dominant_element_share`: largest element count / 6
- `hhi_element_concentration`: sum over elements of p_i^2
- `element_entropy`: -sum p_i log(p_i)
- `all_five_present_6pos`: 1 if all five elements occur, else 0

These secondary metrics are correlated robustness descriptions, not independent
replications.

## H1 — within-elite performance

Primary directional hypothesis:

> Fewer distinct elements are associated with higher within-cohort Elo.

Primary inferential sample:
- 2023 NEW_TARGET pooled across M/F
- Elo endpoint is the already frozen sex-specific standardized Elo:
  `elo_z_within_2023_sex_cohort`
- pooled inference preserves sex strata during permutation
- statistic: Spearman rho
- direction: `rho(distinct_elements_6pos, Elo-z) < 0`

Secondary robustness directions:
- dominant_element_share: rho > 0
- HHI: rho > 0
- entropy: rho < 0
- all_five_present_6pos: rho < 0

The same metrics MUST also be reported, regardless of direction, for:
- 1994 M
- 1994 F
- 2013 M
- 2013 F
- 2023 M FULL
- 2023 F FULL
- 2023 M NEW_TARGET
- 2023 F NEW_TARGET

Direction consistency across these 8 strata is reported descriptively. No
favorable stratum may replace the frozen primary sample.

## H2 — occupational-selection enrichment

Primary directional hypothesis:

> The 2023 NEW_TARGET pooled cohort has fewer distinct elements than expected
> under a same-birth-year Gregorian-calendar null.

Null:
For each real player, birth year is fixed and Gregorian date is sampled uniformly
from all valid dates in that same year. The six-position BaZi representation is
then recalculated.

Primary:
- 2023 NEW_TARGET pooled
- observed mean `distinct_elements_6pos` < calendar-null mean

Secondary robustness directions:
- dominant_element_share > null
- HHI > null
- entropy < null
- all_five_present_6pos < null

Selection results are also reported for the 8 individual strata listed above.

## Frozen cohort provenance

1994/2013 cohorts must be loaded from Git tag:
`chess-preregister-v3-date-sanity`

2023 cohorts must be loaded from Git tag:
`chess-2023-cohorts-frozen-v1`

The script should read the frozen Git blobs rather than silently substitute a
current working-tree file.

Expected primary sizes:
- 1994 M = 501
- 1994 F = 201
- 2013 M = 501
- 2013 F = 200
- 2023 M FULL = 501
- 2023 F FULL = 202
- 2023 M NEW_TARGET = 501
- 2023 F NEW_TARGET = 200

Any size mismatch aborts before analysis.

## Statistical procedure

Performance:
- permutation Spearman test
- 50,000 permutations by default
- for pooled M/F tests, Elo-z is permuted within sex

Selection:
- same-birth-year calendar Monte Carlo
- 20,000 simulations by default
- observed means, null means, z scores, directional and two-sided empirical
  p-values reported

Seed:
`20260927`

## Interpretation rule

Because this is post-reveal exploratory:
- raw p-values are descriptive evidence, not a new prospective confirmation;
- a striking result becomes a candidate for a future independent-domain or
  future-cohort replication;
- null/heterogeneous results are retained and reported;
- no metric, cohort, direction, hidden stem definition, or weighting may be
  changed after reveal to rescue the hypothesis.
