# Chess BaZi Study — Preregistration Amendment v3
## Temporal DOB Sanity Patch

**Status:** committed before any chess BaZi calculation/reveal.

The v2 Northern-Hemisphere population rule remains unchanged.
This amendment adds one hard data-integrity condition:

> A player's exact DOB must be on or before the historical snapshot date.

Any DOB later than the snapshot is treated as an identity/DOB data error,
not as a valid observation. Such rows are excluded before BaZi calculation.

After exclusion, the cohort is reselected as Top500 men / Top200 women
plus all valid Elo cutoff ties using only the already-frozen v2 population.

If the v2 files do not contain enough valid rows to satisfy the target,
the sanitizer aborts instead of silently changing the population rule.

No BaZi values were inspected before adding this rule.

## Frozen v3 cohorts

- 1994_M: n=501, cutoff Elo=2435, age range=14.07–71.90
- 1994_F: n=201, cutoff Elo=2135, age range=13.69–65.03
- 2013_M: n=501, cutoff Elo=2529, age range=16.26–67.37
- 2013_F: n=200, cutoff Elo=2272, age range=14.26–71.67

The original `chess-preregister-v1` and
`chess-preregister-v2-hemisphere` tags remain unchanged for provenance.

**No chess BaZi values were used to construct this amendment.**
