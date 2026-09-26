# Discovery Log — Music × BaZi, 1986–1989 (North-primary) — V2

**Status:** exploratory / discovery log  
**Purpose:** freeze the current analysis conventions and record what has already been observed **before inspecting 1990–1992 Music × BaZi validation results**.

## 1. Cohort roles

- **Discovery cohort:** Gregorian birth years **1986–1989**.
- **Untouched validation cohort:** **1990–1992**.
- 1990–1992 may already have been crawled / enriched with metadata, but their Music × BaZi association results must not be inspected before the validation plan is frozen.

## 2. Primary hemisphere rule

Primary analyses use **Northern-Hemisphere births only**:

- Wikidata person QID → **P19** place of birth.
- P19 birthplace entity → **P625** coordinate.
- **north = latitude > 0**.
- Southern-Hemisphere births are excluded from the primary sample.
- Missing P19/P625 coordinates are **not** treated as north and are excluded from the primary sample.
- `known` and `full` samples are sensitivity analyses only.

## 3. Calendar / BaZi conventions

- Gregorian civil birth date is the available temporal unit.
- BaZi Y/M/D pillars are evaluated at **12:00 civil clock time**.
- Dates for which the **year or month pillar changes within the same civil date** are flagged as transition-ambiguous and excluded when exact birth time is unknown.
- Month-order Ten God (月令十神) is operationalized using the **main hidden stem / 本气** of the month branch.
- For overall Five-Element composition, each person contributes six equally weighted Y/M/D components:
  1. year stem
  2. year-branch main qi
  3. month stem
  4. month-branch main qi
  5. day stem
  6. day-branch main qi
- No hidden-stem fractional weighting is used in the primary exploratory analysis.

## 4. Outcome definition

- Primary occupational outcome: **Music** broad category from the existing frozen Wikidata P106 classification pipeline.
- Category mappings are treated consistently across years.

## 5. Statistical conventions

- Calendar/date structure is treated explicitly; people sharing the same civil date are not treated as independent BaZi predictor realizations.
- Expected distributions are matched to the observed Gregorian birth-year composition rather than assuming:
  - 10% per heavenly stem,
  - 20% per Five Element,
  - or independent 6-component element slots.
- Multiple-testing correction is retained where applicable.
- Nominal p-values are not interpreted as confirmatory significance when the corrected result is null.

## 6. Current exploratory Ten-God findings — north-primary, pooled 1986–1989

The clearest positive direction is **month-order 伤官**:

- 月令伤官: OR ≈ **1.101**, one-sided p ≈ **0.0403**, but all-20 BH q ≈ **0.487**.

Other positive-direction exploratory estimates include:

- 月令比肩: OR ≈ **1.089**
- 月干正财: OR ≈ **1.076**
- 月干七杀: OR ≈ **1.072**
- 月令正印: OR ≈ **1.064**
- 月干偏印: OR ≈ **1.063**

Negative-direction exploratory estimates include:

- 月干正官: OR ≈ **0.856**
- 月令劫财: OR ≈ **0.898**
- 月令正财: OR ≈ **0.917**
- 月干伤官: OR ≈ **0.946**
- 月令偏财: OR ≈ **0.954**
- 月令食神: OR ≈ **0.956**
- 月干劫财: OR ≈ **0.963**

**Important:** none of the 20 Ten-God tests survives the all-20 multiple-testing correction.

Thus the current descriptive statement is:

> **Month-order 伤官 shows the most interesting positive direction, while the broader 20-variable pattern is mixed rather than uniformly negative.**

In particular, “伤官 positive” means specifically **月令伤官**. **月干伤官 is negative** in the pooled north-primary result.

## 7. Day-Master findings — north-primary, 1986–1989

- 10-Day-Master distribution: no meaningful global deviation from the matched-calendar null.
- 5 Day-Master elements: no meaningful global deviation from the matched-calendar null.
- Individual stem differences are small and do not survive correction.

Interpretation: the Music signal, if any, does **not** appear to be strongly expressed through Day Master alone.

## 8. Overall Y/M/D Five-Element findings — north-primary, 1986–1989

Using the six-component main-qi definition:

- 木: enrichment ≈ **1.013**
- 金: enrichment ≈ **1.010**
- 火: enrichment ≈ **1.007**
- 土: enrichment ≈ **0.995**
- 水: enrichment ≈ **0.965**

The strongest deviation is **lower Water**, with nominal two-sided p ≈ **0.049**, but Holm-adjusted p ≈ **0.245**.

The global Five-Element composition test is not significant.

Therefore lower Water is an **exploratory hint only**.

## 9. Frozen validation hypotheses for 1990–1992

### Primary hypothesis

**H1 — 月令伤官 positive**

Among north-primary public figures born in 1990–1992, `month_order_tengod == 伤官` is positively associated with Music occupation.

- Direction: positive.
- Primary inferential model: pooled 1990–1992 grouped-binomial date-level GLM.
- Covariates: Gregorian year fixed effect + Gregorian month + weekday.
- Test: one-sided positive coefficient test.
- H1 is the sole primary hypothesis and is not multiplicity-adjusted against secondary hypotheses.

### Secondary hypothesis family

**S1 — overall Water lower**

Among north-primary Music public figures born in 1990–1992, the total Water contribution across the six-component Y/M/D main-qi composition is lower than the matched-calendar expectation.

- Six components per person:
  year stem + year-branch main qi + month stem + month-branch main qi + day stem + day-branch main qi.
- Direction: lower Water.
- Test: lower-tail matched-calendar Monte Carlo test, preserving whole-date six-component vectors and the observed birth-year composition.

**S2 — 月令劫财 negative**

Among north-primary public figures born in 1990–1992, `month_order_tengod == 劫财` is negatively associated with Music occupation.

- Direction: negative.
- Model: same pooled grouped-binomial date-level GLM as H1.
- Test: one-sided negative coefficient test.

**S3 — 月令比肩 positive**

Among north-primary public figures born in 1990–1992, `month_order_tengod == 比肩` is positively associated with Music occupation.

- Direction: positive.
- Model: same pooled grouped-binomial date-level GLM as H1.
- Test: one-sided positive coefficient test.

### Secondary multiplicity rule

The three secondary p-values **S1–S3** will be adjusted jointly using **Benjamini–Hochberg FDR** across exactly these three tests.

No other Ten-God, Day-Master, or Five-Element category will be promoted to a confirmatory hypothesis after 1990–1992 inspection.

## 10. Validation cohort / stopping rule

- Confirmatory sample is the **pooled 1990 + 1991 + 1992 north-primary cohort**.
- No stopping or hypothesis revision after inspecting 1990 or 1991 separately.
- Per-year estimates may be reported as secondary descriptive diagnostics only.
- The pooled 1990–1992 result is the confirmatory target.

## 11. Interpretation guardrails

- 1986–1989 are discovery-only.
- H1 and S1–S3 were selected after inspection of 1986–1989 and must be evaluated only on the untouched 1990–1992 validation cohort.
- `full` and `known` hemisphere variants are sensitivity analyses, not substitutes for the frozen north-primary analysis.
- If 1990–1992 do not reproduce the directions, the hypotheses are considered unsupported in validation.
