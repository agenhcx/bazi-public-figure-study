# Chess 2023 Prospective Validation Plan v2

## Freeze rule

This plan must be committed and tagged before ANY 2023 BaZi pillar or Day
Master is calculated.

## Snapshot

Use January 2023 FIDE STANDARD ratings.

Population eligibility remains aligned with the previous chess study:

- active players only;
- no title requirement;
- exact clean Gregorian DOB required;
- DOB must not be after 2023-01-01;
- confirmed Northern-Hemisphere birthplace required;
- unknown / ambiguous hemisphere excluded;
- Southern Hemisphere excluded;
- no month-season inversion;
- rank by standard Elo descending;
- retain all eligible ties at the relevant cutoff.

## Three pre-specified cohort views

### A. FULL

This is the primary 2023 cross-sectional elite population.

- 2023_M_FULL: first 500 eligible men + all eligible cutoff ties.
- 2023_F_FULL: first 200 eligible women + all eligible cutoff ties.

FULL answers:

> What does the actual January-2023 elite population look like?

Players previously seen in 1994/2013 remain included because they genuinely
belong to the 2023 elite population.

### B. NEW_WITHIN_FULL

Subset FULL by removing every player whose FIDE ID occurred in any frozen
1994/2013 primary cohort.

Do not refill.

This is a diagnostic for whether a FULL result is driven mainly by players
already observed in the discovery snapshots.

### C. NEW_TARGET

Construct a non-overlapping validation cohort by scanning farther down the
January-2023 ranking while skipping every FIDE ID that appeared in any frozen
1994/2013 primary cohort.

Continue until reaching:

- 500 eligible new men + cutoff ties;
- 200 eligible new women + cutoff ties.

The resulting Elo cutoff is NOT fixed in advance.

The cutoff must be reported before BaZi reveal and accepted as produced by the
frozen rule. It must not be changed after seeing BaZi results.

NEW_TARGET answers a different question from FULL:

> Does the pattern replicate in a comparably sized set of previously unseen
> 2023 ranked players?

Because NEW_TARGET may extend below the FULL elite threshold, it must not be
silently substituted for FULL when describing the actual Top500/Top200.

## H1 — Prospective Day-Stem selection pattern

Frozen directional pattern:

- 乙 > 甲
- 丙 > 丁
- 戊 > 己
- 辛 > 庚
- 壬 > 癸

Define:

    predicted_set = {乙, 丙, 戊, 辛, 壬}
    opposite_set  = {甲, 丁, 己, 庚, 癸}

For each player:

    stem_direction_score = +1 for predicted_set
                           -1 for opposite_set

Primary selection statistic:
mean stem_direction_score versus same-birth-year calendar null.

Report:
- FULL pooled-sex, male, female;
- NEW_TARGET pooled-sex, male, female;
- NEW_WITHIN_FULL diagnostic.

The five individual stem pairs are secondary diagnostics and must all be
reported, not selectively highlighted.

## H2 — Prospective Shangguan selection replication

Candidate from 2013M:

    six-position Shangguan exposure is higher than same-birth-year calendar
    expectation.

Primary test:
- 2023_M_FULL total shangguan_count_6pos > calendar null.

Independent validation:
- 2023_M_NEW_TARGET total shangguan_count_6pos > calendar null.

Female cohorts are secondary generalization checks.

Six positions remain exactly:

1. year stem
2. year branch main qi
3. month stem
4. month branch main qi
5. day stem
6. day branch main qi

No hour.
No secondary hidden stems.
No 三合 / 三会 / 六合 transformations.

## H3 — Prospective Day-Master performance replication

Performance metric:
within-2023-sex standardized Elo (Elo-z).

### H3a primary coarse contrast

Metal Day Masters have higher mean Elo-z than Earth Day Masters.

Direction:
    mean_z(Metal) > mean_z(Earth)

Report separately for male and female, plus sex-standardized pooled result.

### H3b primary stem contrast

Geng (庚) has higher mean Elo-z than Wu (戊).

Direction:
    mean_z(庚) > mean_z(戊)

This contrast was directionally consistent in all four discovery strata and is
therefore frozen prospectively here.

### H3c secondary refinement

Report:
- 庚 vs 辛;
- 戊 vs 己;
- all five element group means;
- all ten stem group means;
- omnibus five-element and ten-stem tests.

Do not redefine the primary contrast after reveal.

## H4 — Shangguan/Pianyin performance negative benchmark

Prior 1994/2013 data did not show a positive Elo relationship for Shangguan or
Pianyin count.

For 2023 report the same Spearman associations as replication diagnostics.
No positive effect is assumed.

## Multiplicity and interpretation

The 2023 validation families are conceptually distinct:

1. Day-Stem selection direction;
2. Shangguan selection enrichment;
3. Day-Master performance contrast.

Results must be reported separately.

No failed hypothesis may be rescued by adding hidden stems, combinations,
transformations, birth-hour assumptions, or a different cohort definition
after reveal.

FULL and NEW_TARGET must both be shown when available; do not choose whichever
looks more favorable.

