# Preregistration: 1988-1989 Pooled Replication Extension

## Timing and provenance

This protocol must be frozen before inspection of 1988 or 1989 Music outcomes.

Prior evidence:
- 1986: exploratory/discovery cohort; positive signals for H1/H2.
- 1987: first preregistered replication; primary hypotheses did not replicate.
- 1987 outcomes are already known and are NOT part of the future confirmatory sample.

Future confirmatory sample:
- Gregorian birth years 1988 and 1989.
- Both years will be analyzed regardless of the result of the first year.
- No hypothesis, exclusion rule, category definition, covariate, or test direction
  will be changed after viewing 1988 outcomes.

## Primary outcome
Music category, using the unchanged broad-category classifier already frozen in
the occupation pipeline.

## Primary hypotheses

H1:
YMD_DAY_HALF_TRINE has a positive association with Music.

H2:
P_HOUR_COMPLETES_DAY_SANHE has a positive association with Music.
The practically interpretable effect size is OR for exposure 0 -> 1/12.

H3:
YMD_STEM_COMBINE_AND_HALF_TRINE has a positive association with Music.

## Primary confirmatory sample and scope

Pool eligible dates from Gregorian 1988 and Gregorian 1989.

Exclude civil dates on which the BaZi year or month pillar changes during the
date, because exact birth time is unknown.

The primary analysis uses all remaining Gregorian dates from both years.
Year is included as a fixed-effect covariate.

Per-year 1988 and 1989 estimates are secondary replication/heterogeneity
summaries and do not replace the pooled primary test.

## Primary model

Grouped-binomial GLM at the date level:

Music count / non-Music count ~ feature + Gregorian year + Gregorian month + weekday

Use HC0 robust covariance.

For each H1/H2/H3:
- preregistered direction: positive coefficient
- report coefficient, OR, 95% two-sided CI, and one-sided positive p-value
- apply Benjamini-Hochberg FDR jointly across the three primary p-values

H2 effect-size reporting:
- report model OR(0->1)
- additionally report effective OR(0->1/12) = exp(beta / 12)

## Equivalence / meaningful-null analysis

To distinguish "not significant" from "evidence of a practically small effect",
also report an equivalence-oriented confidence-interval assessment using a
smallest effect size of interest of +/-10% in odds.

Practical-equivalence interval:
- OR lower bound = 1/1.10 = 0.9091
- OR upper bound = 1.10

For H1 and H3, evaluate the feature OR directly.

For H2, evaluate the effective OR for the practical 0->1/12 exposure change.

If the entire 90% CI lies inside [0.9091, 1.10], describe the result as
compatible with statistical equivalence under this preregistered margin.
Otherwise do not claim equivalence.

This equivalence analysis is secondary to the directional primary tests but is
frozen before viewing 1988/1989 outcomes.

## Secondary / exploratory analyses

Report, but do not use to redefine the primary conclusion:
- per-year 1988 and 1989 models
- feature x year interaction / heterogeneity
- P4_DAY_HALF_TRINE
- P4_FULL_SANHE_ANY
- P4_FULL_SANHE_INVOLVES_DAY
- P4_DAY_STEM_COMBINE
- P4_FULL_DAY_SANHE_AND_STEM_COMBINE
- descriptive exposure-level summaries

Any new pattern discovered after viewing 1988 or 1989 is exploratory and must
be tested only in a future untouched cohort.

## Unknown birth hour

Use equal weights over the 12 traditional double-hours (1/12 each) only as a
sensitivity/marginalization model. This is not a claim that empirical birth
hours are uniformly distributed.

Late-Zi (23:00) day-boundary conventions remain outside the primary model.

## Stopping rule

Analyze exactly both 1988 and 1989 under this protocol. Do not stop after 1988
based on significance or direction.
