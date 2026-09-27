# Chess BaZi Study — Preregistration Amendment v2
## Northern-Hemisphere Primary Cohorts

**Status:** written and committed before the first chess BaZi calculation/reveal.

This amendment does not delete or rewrite `chess-preregister-v1`.
The v1 frozen cohorts remain available as sensitivity analyses.

## Reason for amendment

The purpose of the hemisphere restriction is to avoid a methodological dispute
over whether Southern-Hemisphere births should use a season/month inversion.

No such inversion is applied in this study.

Instead, the v2 primary analysis is restricted to players with a confirmed
Northern-Hemisphere birthplace.

This rule was frozen before calculating any chess BaZi variables.

## Hemisphere definition

Hemisphere is determined by **birthplace latitude**, not federation,
citizenship, residence, or chess federation.

Data path:

- FIDE ID -> Wikidata `P1440`
- person -> place of birth `P19`
- birthplace -> coordinates `P625`

Classification:

- latitude > 0: North
- latitude < 0: South
- latitude = 0: Equator
- missing/ambiguous identity, birthplace, or coordinates: Unknown

Only confirmed North is eligible for the v2 primary cohorts.

South, Equator, and Unknown are skipped. They are not relabeled.

## Population construction

For each historical snapshot and sex, players are ranked by classical Elo.

The scanner proceeds downward through the FULL active population and includes
only players satisfying BOTH:

1. clean exact Gregorian DOB;
2. confirmed Northern-Hemisphere birthplace.

It continues until at least:

- 500 men;
- 200 women

have been obtained, and then includes every additional eligible player tied at
the resulting Elo cutoff.

No GM-title requirement is imposed.

### Frozen v2 cohorts

- 1994 men: **502**, cutoff Elo **2435**
- 1994 women: **201**, cutoff Elo **2135**
- 2013 men: **501**, cutoff Elo **2529**
- 2013 women: **200**, cutoff Elo **2272**

## 1994 historical identity rule

Raw January-1994 `Player_ID` values are not assumed to equal modern FIDE IDs.

Identity bridge:

January-1994 row -> exact OlimpBase player profile -> `Most recent ID` ->
Wikidata.

Kasparov and Short remain restored before ranking because their 1994 official
FIDE-list absence resulted from the FIDE/PCA split rather than chess strength.

## Exact-DOB rule

### 1994

- OlimpBase profile and Wikidata exact DOB agree: eligible.
- Exact OlimpBase profile DOB with no unique conflicting Wikidata exact DOB:
  eligible.
- No profile exact DOB but one unique day-level Wikidata DOB through the
  identity-bridged modern FIDE ID: eligible.
- Explicit profile DOB conflict: excluded.
- Profile vs Wikidata exact-date disagreement: excluded.
- Multiple identities/exact dates or missing exact DOB: excluded.

### 2013

Exactly one identity-matched day-level Wikidata DOB is required, and its year
must agree with the official 2013 FIDE birth year when that year is available.

## Primary analysis

The v2 Northern-Hemisphere cohorts are the primary population for the
preregistered chess hypotheses.

The previously frozen `chess-preregister-v1` cohorts are retained as
sensitivity analyses.

No month/season inversion is performed for any player.

## Performance endpoint

The primary continuous performance endpoint remains:

`elo_z_within_snapshot_sex`

computed inside each frozen snapshot x sex cohort.

## Hypotheses

The substantive hypotheses remain those frozen in v1. This amendment changes
the population rule for the primary analysis; it does not add a BaZi-derived
hypothesis.

The principal headline tests remain:

1. temporal Day-Master element gradient, including the predefined Metal/Earth
   comparison;
2. 1994 vs 2013 Day-Master element distribution;
3. predefined measurable three-pillar 伤官 / 偏印 exposure analyses;
4. preregistered performance analyses.

## Reveal rule

After this amendment is committed/tagged:

- v2 north-only cohort membership is immutable for primary analysis;
- BaZi is calculated from `exact_dob_frozen`;
- any newly noticed BaZi pattern is exploratory;
- South/Unknown players cannot be selectively restored after seeing results.

**No chess BaZi values were used to construct this amendment.**
