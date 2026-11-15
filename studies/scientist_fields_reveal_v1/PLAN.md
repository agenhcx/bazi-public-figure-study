# Fields Medal: PI and SG enrichment, version 1

This plan interprets the user's correction “高于预期” as enrichment relative to a calendar expectation. It does not compare year/month pillars with residual hidden stems.

## Timing and scope

Freeze this plan, executable analysis and input hashes on a separate Git branch before computing Fields-specific feature aggregates. Previous academy and Nobel results, and selected individual birth dates, have already been seen. This is a new directional analysis locked before the Fields-specific aggregate, not a fully independent replication or a registration preceding all scientist data exposure.

Use the existing scientist northern-hemisphere data freeze V4 without roster, DOB or source edits. The frozen Fields parallel cohort has 57 unique people, exact Gregorian DOBs from 1897-07-03 to 1985-08-26. Strict S1+S2 and expanded S1+S2+S3 cohort files are byte-identical. Preserve the original roster cutoff and 1835–1985 birth window; no current roster updates. Eighteen members also appear in the previously revealed non-Nobel academy cohort. No member overlaps the frozen science Nobel cohort.

The original roster contains 64 recipients for awards in 1936–2022, with a 2025 cutoff. It retains the declined Perelman award, excludes the Wiles silver plaque and any 2026 expansion. The 64-to-57 exclusions are mutually exclusive: one month-only DOB, four southern-hemisphere people with exact DOB, and two northern-hemisphere people born in 1987 outside the birth window. No claim is made about the hemisphere of the month-only excluded person.

## Encoding

Reuse the exact calendar and hidden-model caches pinned in INPUT_PINS.json. Calendar convention and boundary-day flags remain those of the preceding scientist analyses; no new hour, timezone or month-boundary optimization. A day stem is the reference only. Main M0 uses five informative positions: year stem, year branch main qi, month stem, month branch main qi, day branch main qi. No hour pillar is imputed in the primary analysis.

Six primary endpoints in fixed order:

1. overall_PI: sum of PI occurrences over the five M0 positions.
2. overall_SG: sum of SG occurrences over the five M0 positions.
3. year_PI: one per person if either year stem or year branch main qi is PI.
4. year_SG: corresponding year-pillar SG presence.
5. month_PI: one per person if either month stem or month branch main qi is PI.
6. month_SG: corresponding month-pillar SG presence.

For overall counts, show occurrence sums, per-person means, and shares of 5N positions. For pillar presence, show people with at least one occurrence and percentage of N people. Two occurrences within a pillar count as one presence event. Do not assume 10% or 20% as these endpoints' null probability.

## Null model and inference

For each unique person, fix their observed Gregorian birth year and draw uniformly among every valid day in that year, independently across people. Enumerate the same year to obtain each person's exact expectation. Preserve the full chart within each sampled date and use the same replicate birthday draws across all six endpoints. Test the sum of each endpoint; because N is fixed, this gives the same tail as the displayed means/proportions.

Use NumPy PCG64, seed 2026111501, 99,999 Monte Carlo replicates. One-sided inclusive enrichment p = (1 + number of null sums >= observed sum)/(99,999 + 1). Integer primary endpoints need no floating tolerance. Apply Holm correction jointly to the six primary p-values, FWER 0.05. Give every endpoint regardless of direction or p-value. A non-significant result does not establish equivalence or absence of association. A significant enrichment in this selected observational sample would not establish a causal or predictive explanation of achievement.

## Prespecified descriptive sensitivities

These add no primary p-values and cannot rescue a failed primary hypothesis:

- M1 priority hidden-stem replacement, retaining five positions. For each branch, select the first exposed hidden stem in main/middle/residual priority order, using year/month visible stems only; otherwise retain main qi. Do not count the reference day stem as exposure. Report six observed and year-conditioned expected endpoints.
- Original eight cached PI/SG models: M0_5, M1_priority_5, M1_share_5, M1_any_5, M2_main_7, M3_priority_7, M3_share_7, M3_any_7. Report overall per-person counts and presence probabilities against each model's year-conditioned expectation. Seven-position models marginalize uniformly over 12 possible hour branches; do not choose a favorable hour. Share and any-hidden encodings are distinct models, not additional independent observations.
- Condition the main M0 expectation additionally on each person's birth month; enumerate all dates in their observed Gregorian year/month.
- Exclude people within one civil day of a cached jie boundary. For these retained people, leave the primary birth-year calendar null unchanged. This is an exclusion sensitivity, not a fully boundary-truncated null.
- Exclude the 18 people already in the previously revealed academy cohort. Report observed and expected endpoints for the remaining people; this is a smaller secondary group, not an independent confirmatory study.
- M0 and M1 distributions of all ten gods, and ten day stems, are descriptive only. No new tests, trends, country tests, post-hoc subdivisions or endpoint substitution.

## Quality checks and outputs

Before the Git lock, use synthetic charts and the full calendar universe only. Verify the Ten-God bijection, five-position totals, pillar OR logic, M0 PI/SG counts against the original calendar cache, M1 PI/SG against the hidden cache, inclusive tails, Holm implementation and 365/366 calendar support. Do not map Fields birth dates to features before the remote lock has been fetched and verified.

Execution requires a verified remote-lock receipt and code hash equality. Save all six results, source metadata, sensitivities, individual chart audit, lock receipt, code and hash manifest. Independently recompute observed and expected endpoints, verify Holm, and compare a fresh null simulation within Monte Carlo error. Retain failed checks if any; amend a lock transparently before running affected outcomes.
