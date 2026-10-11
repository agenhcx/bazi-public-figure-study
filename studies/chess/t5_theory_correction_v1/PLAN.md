# T5 Theory-Aligned Correction V1

Status: post-reveal exploratory correction. This analysis does **not** replace or retroactively redefine the frozen T5/T5G analysis.

## Reason for correction

The frozen conditional-structure analysis treated T5 (Direct Officer among Hurting-Officer-positive charts) as an enrichment test. The traditional proposition motivating 傷官見官 is more naturally translated as a depletion hypothesis. Because all relevant Chess cohorts have already been revealed, the corrected directional analysis is exploratory.

## Cohorts

Male cohorts only, unchanged from prior analyses:

1. 2013_M_DISCOVERY: chess_north_v3/primary_north_top_2013_M.csv
2. 2023_M_FULL: chess_2023_cohorts_v1/primary_2023_M_FULL.csv
3. 2023_M_NEW_TARGET: chess_2023_cohorts_v1/validation_2023_M_NEW_TARGET.csv

## Representation

M0 only for the correction headline:
Year Stem, Year-Branch main qi, Month Stem, Month-Branch main qi, Day Stem, Day-Branch main qi.
The Day Stem is self-related and therefore cannot itself be Hurting Officer or Direct Officer.

Binary anchors:
- HO+ = at least one Hurting Officer in the six positions.
- DO+ = at least one Direct Officer in the six positions.
- Geng = Day Stem 庚.

## T5 corrected directional test

For each observed HO+ player, preserve birth year. Within that Gregorian year, restrict the calendar null to dates that are also HO+. The player's null Direct-Officer probability is the fraction of such dates that are DO+.

Primary descriptive statistic:
P(DO+ | observed HO+).

Directional exploratory hypothesis:
P(DO+ | HO+) is lower than its exact-birth-year conditional calendar expectation.

Monte Carlo:
200,000 simulations, fixed reproducible seed 20261010.
Report lower-tail, upper-tail, two-sided p values, observed rate, null mean, ratio, Z.

## Geng-specific diagnostic

For observed Geng+HO players, use same-year dates satisfying Geng+HO as the conditional null.
For observed non-Geng+HO players, use same-year dates satisfying non-Geng+HO as the conditional null.

Define null-centered deviations:
d_G = observed_Geng_rate - expected_Geng_rate
d_N = observed_nonGeng_rate - expected_nonGeng_rate

Exception interaction:
I = d_G - d_N.

A positive I means Geng attenuates or reverses any general HO-DO depletion relative to non-Geng; a negative I means Geng is at least as depleted, or more depleted.

This interaction is exploratory and is not a preregistered confirmatory test.

## Guardrails

- Do not reinterpret any nominal p value as preregistered evidence.
- Do not alter cohort membership or calendar engine.
- Report all three cohorts regardless of direction.
- If the reconstructed conditional null does not approximately reproduce the archived 2023_M_NEW_TARGET T5 expectations (T5 expected about 0.3621; T5G expected about 0.3264), treat the run as a pipeline mismatch and do not interpret it.
