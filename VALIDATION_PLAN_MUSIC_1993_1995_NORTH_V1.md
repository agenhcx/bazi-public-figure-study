# Validation Plan — Music × BaZi, 1993–1995 (North-primary) — V1

**Status:** to be frozen before inspecting 1993–1995 Music × BaZi outcomes.

## 1. Confirmatory cohort
- Gregorian birth years: **1993, 1994, 1995**
- Pooled analysis across all three years.
- No stopping or hypothesis revision after inspecting 1993 or 1994 separately.
- Per-year estimates are descriptive only.

## 2. Primary hemisphere rule
Primary analysis uses Northern-Hemisphere births only:
- Wikidata person QID → P19 birthplace
- P19 place → P625 coordinate
- north = latitude > 0
- south, equator, and unknown-coordinate cases excluded from the primary sample
- `known` and `full` are sensitivity analyses only

## 3. Date / BaZi conventions
- Gregorian civil date is the temporal unit available.
- Y/M/D pillars evaluated at 12:00 civil clock time.
- Dates whose year or month pillar differs between 00:30 and 22:30 are excluded as transition-ambiguous.
- Month-order Ten God uses the month branch's main hidden stem / 本气.
- No birth-hour imputation is used.

## 4. Outcome
Primary outcome: **Music** broad category from the existing frozen Wikidata P106 classification pipeline.

Missing P106 is retained as non-Music under the existing project convention, but:
- P106 coverage must be reported before association results are inspected.
- If coverage is <95% in any annual cohort, pause before outcome analysis and document the issue.

## 5. H1 — Primary hypothesis
### Earth-Day-Master matching-main-qi tomb-month structure is positively associated with Music.

Feature = 1 for exactly:
- 戊日主 + 辰月
- 戊日主 + 戌月
- 己日主 + 丑月
- 己日主 + 未月

Else 0.

Primary grouped-binomial daily model:

`Music/non-Music counts ~ H1 + C(gregorian_year) + C(gregorian_month) + C(weekday) + C(day_stem) + C(month_branch)`

- HC0 robust covariance
- one-sided positive test
- alpha = 0.05
- pooled 1993–1995 is confirmatory

Supportive descriptive check:
- report exact-combination ORs for 戊辰 / 戊戌 / 己丑 / 己未
- report how many of the 4 are >1
- exact-combination p-values are not confirmatory

## 6. H2 — Secondary hypothesis
### Non-Fire month-order 伤官 is positively associated with Music.

Feature = 1 for exactly:
- 甲午
- 乙巳
- 戊酉
- 己申
- 庚子
- 辛亥
- 壬卯
- 癸寅

Equivalent operational definition:
- month-branch main hidden stem is 伤官 relative to Day Stem
- Day Master element is not Fire

Model:

`Music/non-Music counts ~ H2 + C(gregorian_year) + C(gregorian_month) + C(weekday) + C(day_stem) + C(month_branch)`

- HC0 robust covariance
- one-sided positive test
- single frozen secondary hypothesis; report raw directional p
- pooled 1993–1995 is the inferential unit

Supportive descriptive check:
- report exact-combination ORs for the 8 frozen combinations
- report how many of the 8 are >1
- exact-combination p-values are not confirmatory

## 7. Sensitivity analyses
After the north-primary analysis:
1. known-coordinate sample
2. full sample

The same frozen definitions and models must be used. Sensitivity results cannot replace the north-primary result.

## 8. Excluded confirmatory branches
The following are NOT confirmatory hypotheses for 1993–1995:
- creator-coded vs other Music
- solo-vs-band status
- 杂气透干
- individual exact-combination significance
- any newly noticed Ten-God or Five-Element feature

## 9. Interpretation rules
- If H1/H2 point in the opposite direction, call that non-replication.
- If direction is positive but p does not meet the frozen threshold, call it directionally consistent but unsupported.
- Do not create new confirmatory hypotheses from 1993–1995 after outcome reveal.
