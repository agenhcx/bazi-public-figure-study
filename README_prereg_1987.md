# 1987 BaZi–Music Replication Preregistration

## Status

This document freezes the primary hypotheses and analysis plan **before inspecting any 1987 Music-by-date outcome**.

- Discovery cohort: 1986
- First replication cohort: 1987
- Analysis script: `bazi_hour_marginal_analysis_v2_prereg.py`
- Primary outcome: Music occupation count among public figures for each Gregorian birth date
- Unit of analysis: calendar date (grouped binomial counts), not individual person

## Background from the 1986 discovery cohort

The 1986 exploratory analysis suggested a weak positive association between Music occupation and a Y/M/D structure in which the day branch forms a two-member San-He relation with the year or month branch. Other structures, including clash/punishment/harm and full San-He completion, did not show comparable evidence.

Because these patterns were noticed after inspecting 1986 data, 1986 is treated only as a discovery cohort. The following hypotheses are frozen for the untouched 1987 replication.

## Primary hypotheses

All three hypotheses are directional: the predicted association with Music is positive.

### H1 — Y/M/D day-branch half-trine

`YMD_DAY_HALF_TRINE = 1` when the day branch and either the year branch or month branch are two distinct members of the same San-He trio.

Prediction:

`Music rate(YMD_DAY_HALF_TRINE = 1) > Music rate(YMD_DAY_HALF_TRINE = 0)`

### H2 — Unknown hour can complete a day-involving full San-He

`P_HOUR_COMPLETES_DAY_SANHE` is calculated by enumerating the 12 traditional double-hours with equal weight 1/12 and measuring the probability that the unknown hour branch completes a full San-He trio involving the day branch that was not already complete in Y/M/D.

Prediction:

Higher `P_HOUR_COMPLETES_DAY_SANHE` is associated with a higher Music rate.

### H3 — Stem combine plus Y/M/D half-trine

`YMD_STEM_COMBINE_AND_HALF_TRINE = 1` when both conditions are met:

1. the day stem forms one of the five stem combinations with the year or month stem; and
2. `YMD_DAY_HALF_TRINE = 1`.

Prediction:

`Music rate(feature = 1) > Music rate(feature = 0)`.

## Primary statistical test

For each hypothesis, fit a grouped-binomial GLM with one row per calendar date:

`Music successes / total public figures ~ primary feature + Gregorian month + weekday`

The primary test is the **one-sided positive-coefficient p-value** for the primary feature.

The three primary p-values H1, H2, and H3 form **one multiplicity family** and are corrected together using Benjamini-Hochberg FDR at q = 0.05.

Effect sizes and 95% confidence intervals are reported regardless of significance.

## Secondary / robustness analyses

The following are secondary and will not be used to redefine the primary hypotheses after seeing 1987:

- `P4_DAY_HALF_TRINE`
- `P4_FULL_SANHE_ANY`
- `P4_FULL_SANHE_INVOLVES_DAY`
- `P4_DAY_STEM_COMBINE`
- `P4_FULL_DAY_SANHE_AND_STEM_COMBINE`
- permutation tests
- raw pooled risk ratios / Fisher tests
- Gregorian-year versus dominant BaZi-year scope comparisons

Any new pattern first noticed in 1987 is exploratory and must be tested in a later untouched cohort (for example 1988), not re-tested as a new primary hypothesis within 1987.

## Hour treatment

Exact birth time is unavailable for most public figures. The analysis does not impute a single hour. Instead, all 12 traditional double-hours are enumerated with equal prior weight 1/12.

Representative clock times are:

- 子 00:00
- 丑 02:00
- 寅 04:00
- 卯 06:00
- 辰 08:00
- 巳 10:00
- 午 12:00
- 未 14:00
- 申 16:00
- 酉 18:00
- 戌 20:00
- 亥 22:00

The late-Zi 23:00 day-boundary convention is not modeled in this version.

## Inclusion / exclusion rules

- Input dates must belong to Gregorian year 1987.
- Outcome counts come from the same Wikipedia/Wikidata pipeline used for 1986.
- Dates on which the year or month pillar changes during the civil date are excluded from the main analysis because exact birth time is unavailable.
- A secondary scope restricted to the dominant BaZi year pillar is also reported.
- No 1987 high-Music dates are to be inspected before the primary analysis is run.

## Interpretation rule

A replication is not defined merely as `p < 0.05` in one test. We will report direction, effect size, confidence interval, raw one-sided p-value, and BH-FDR q-value for all three primary hypotheses.

1987 will be considered supportive of a 1986 signal when the effect is in the preregistered positive direction; stronger evidence is present if the corresponding adjusted test is also statistically significant. Failure or reversal will be reported without changing the hypothesis definition within the 1987 cohort.

## Reproducibility

Before running the analysis on 1987 outcome data:

1. commit this file and `bazi_hour_marginal_analysis_v2_prereg.py` to Git;
2. push the commit to GitHub;
3. create and push tag `prereg-1987-v1`;
4. record the commit hash below.

Frozen version identifier: **Git tag `prereg-1987-v1`**. The exact commit can be recovered with `git rev-parse prereg-1987-v1^{commit}` after the tag is created.

