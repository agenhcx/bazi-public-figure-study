# 1987 Replication Results Archive

## Status
This document archives the first preregistered replication outcome after the
1986 exploratory/discovery analysis.

The analysis plan was frozen before inspection of 1987 outcomes at Git tag:

- prereg-1987-v1
- commit: fb604cf14a5ab36ede87bedcc233224f9002a19f

## Data
- Gregorian birth year: 1987
- Dates: 365
- People: 16,420
- Music-category people: 1,105
- Pillar-transition ambiguous dates excluded: 10
- Dominant BaZi year pillar: 丁卯

## Preregistered primary hypotheses

H1: YMD_DAY_HALF_TRINE is positively associated with Music.

H2: P_HOUR_COMPLETES_DAY_SANHE is positively associated with Music.

H3: YMD_STEM_COMBINE_AND_HALF_TRINE is positively associated with Music.

Primary analysis: grouped-binomial GLM adjusted for Gregorian month and weekday,
one-sided positive coefficient tests, with BH-FDR across H1/H2/H3.

## Gregorian-1987 primary results

H1:
- Music rate: 6.68% vs 6.83%
- RR = 0.977
- adjusted OR = 0.977
- one-sided p = 0.6324
- global BH q = 0.691307

H2:
- model OR for exposure 0->1 = 0.660
- practical exposure range is 0->1/12
- effective OR for 0->1/12 ~= 0.966
- one-sided p = 0.691307
- global BH q = 0.691307

H3:
- Music rate: 6.12% vs 6.81%
- RR = 0.898
- adjusted OR = 0.947
- one-sided p = 0.62732
- global BH q = 0.691307

## Interpretation
The 1987 replication did not reproduce the positive 1986 discovery signal.
Effect estimates for H1 and H2 were approximately null/slightly negative; H3
was also negative in direction.

No hypothesis definition should be changed retroactively based on this outcome.
