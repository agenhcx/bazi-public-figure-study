# Chess single-player A: pre-fit analysis plan v1

**Status: REVIEW DRAFT; not frozen, not registered, and no predictive model fitted.**

Protocol ID: chess-single-A-v1
Prepared: 2026-10-21
Proposed Git tag after review: `chess-single-a-analysis-lock-v1`
Source repository: https://github.com/agenhcx/bazi-public-figure-study
Source data commit: `20f743ef8eda060d34121530323893dffc938aa6`

## 1. Question, scope, and previous access

Among the already selected Northern-Hemisphere male chess cohorts, can a model
using only the six position-specific Year/Month/Day stem/branch identities predict
January-snapshot standard Elo better than a model using ordinary age and season
information?

This is a new analysis of previously explored data. The 1994/2013 BaZi and Elo
results, and the 2023 BaZi and Elo results, have already been examined in earlier
studies. See `POSTREVEAL_LOG_CHESS_1994_2013_V2.md` and
`VALIDATION_PLAN_CHESS_2023_V2.md`. This plan is a prospective record of the
new modelling procedure, NOT a claim of outcome-naive preregistration or a new
blind test. Neither the Git tag nor later registration can erase previous access.

A is a raw-symbol representation study. There are no Ten-God, Five-Phase,
hidden-stem, strength, stem-combination or branch-interaction labels. A separate
B study requires its own feature definitions and analysis record.

## 2. Fixed data and independent units

Use the exact three existing files specified in `data_manifest.json`:

- Development: January 2013 men, 501 people.
- Primary external evaluation: January 2023 M_NEW_TARGET, 501 people.
- Secondary external evaluation: January 2023 M_FULL, 501 people.

Canonical identity is `identity_bridge_modern_fide_id` when available, otherwise
`fide_id`. Each file must have one row per canonical person. No exclusion,
replacement, rating cutoff change, pooling with women, or addition of 1994 data
is permitted in v1. Input defects stop the run and require a documented amendment;
they are not silently repaired.

Expected identity overlaps: development/NEW_TARGET = 0;
development/FULL = 283; NEW_TARGET/FULL = 209. FULL and NEW_TARGET are not two
independent replications. Repeated people across snapshots are not additional
independent training people.

The original cohort eligibility and tie rules remain unchanged. The NEW_TARGET
rating range differs from the original Top500 range by construction. Conclusions
are restricted to these selected cohorts, not general-population chess talent,
becoming a professional, or a causal astrological mechanism.

## 3. Target and inputs

Target: numeric standard Elo in `rating` at the row's `snapshot`, not rank,
Elo-z, career maximum, or future performance changes.

Raw A input order:
year_stem, year_branch, month_stem, month_branch, day_stem, day_branch.

Split the stored year/month/day pillars to harmonize schemas; existing explicit
columns must agree. Use six separate one-hot groups with the fixed ten-stem and
twelve-branch vocabularies: 66 indicator columns before model transformations.
No alphabetical ordinal values, data-driven relabeling, or pretrained embeddings.
No person ID, name, title, federation, rank, games, Elo-z or earlier-study scores
as predictive inputs.

Date-control input: age in years at the first day of each snapshot month,
age squared, age cubed, and first/second annual sine/cosine harmonics of birth
day-of-year, using the actual length of the birth year. Leap years are not dropped.
The exact feature definitions are recorded in `config.json`.

All fitted transforms, input scaling and optional target scaling are fitted on
the relevant training fold only.

**Interpretation boundary:** comparing pure A against a date-only predictor
compares two representations. It does not establish incremental information
after conditioning on a sufficiently flexible date predictor. Such a claim
requires a separately prespecified date-versus-date-plus-six analysis.

## 4. Candidate algorithms and fixed search budget

Use the five algorithm families and the exact finite grids in `config.json`.
Run the same family menu and logical configuration budget for raw A and the date
control; do not give A a rich search and the control only one simple equation.

1. Ridge.
2. Generic degree-two interaction expansion plus Ridge.
3. RBF kernel ridge.
4. Shallow gradient-boosting regression trees.
5. Small MLP.

Generic pair interactions enumerate all distinct input-column products; they do
not select traditional combinations. MLP predictions average the three specified
initializations; seeds are not competing candidates. No CNN, pretrained model,
new family, added seed, wider grid, or manual rule is added after scoring.

A finite prediction from a fit that reaches the iteration limit is retained,
with convergence warnings reported. Numerical exceptions/nonfinite predictions
invalidate that configuration on that inner search; do not alter settings to
rescue it. Stop if a representation has no valid configuration. Ties use the
fixed family/configuration order, never external performance.

## 5. Development and selection

Use shuffled 5-fold outer CV on 2013 canonical IDs in lexicographic order,
seed 20261021. Within each outer training set, use shuffled 4-fold CV,
seed 20261022, to select family and hyperparameters by the mean per-player
out-of-fold MAE. Generate exactly one outer held-out prediction per person.
No test-fold-informed preprocessing or target transformations.

After reporting nested-CV predictions, repeat the same 4-fold inner search on all
501 development people and refit the selected raw A and selected date-control
pipelines on all 501. These become the two fixed primary predictors. The training
median Elo is an additional untuned descriptive benchmark.

The five families' individually selected configurations may be retained for
secondary reporting, but must be selected using 2013 only.

## 6. Primary hypothesis, endpoint, and uncertainty

Primary directional hypothesis:
the fixed raw A selection procedure has lower external MAE than the fixed
date-control selection procedure on M_NEW_TARGET.

Primary endpoint:
`delta_mae = MAE(date_control) - MAE(raw_A)`, in Elo points.
Positive values favor A; zero or negative values are valid outcomes.

Report the paired per-person absolute-error differences, their mean, and a
95% percentile bootstrap interval, with 10,000 person-level paired resamples,
seed 20261023. The interval conditions on the final fitted models and does not
include all model-development uncertainty. Report the development outer-CV
stability separately. This is retrospective external evidence, not an
outcome-naive confirmatory test.

No minimum meaningful gain has been agreed; `minimum_meaningful_gain_elo`
remains null. Therefore do not claim an equivalence test, adequate power for an
unspecified effect, or proof of no association. No p-value is a primary endpoint.

Secondary results: RMSE, Spearman correlation (undefined for a constant
predictor), FULL performance, training-median performance, and all five families'
results. Report all prespecified secondary results without separate significance
claims or substituting a favorable secondary result for the primary one.
Any later formal multiple-hypothesis tests require a labeled amendment.

## 7. Learning curves and expansion

v1 is fixed at 501 development people. Learning curves use only 2013 data and
the same outer folds, with training subsets of 100, 200, 300 and 400 people.
Subsets are nested by a seeded permutation within each outer training fold
(seed 20261024 plus outer-fold index). Repeat the fixed inner selection inside
each subset. No 2023 scores guide sample size.

Learning curves are diagnostics, not an automatic extension trigger. There is
no v1 adaptive sampling rule. In particular, an unfavorable result or a
p-value/interval threshold does not trigger expansion until success.

Any expansion to 1000 is a separately versioned v2, with its population, reason,
data access history and validation plan recorded before fitting that version.
Recheck overlap against the expanded development cohort. Previously examined
2023 results cannot be relabeled as new blind evidence in v2.

## 8. Execution order and freeze record

1. Review this plan, config, manifest and input audit.
2. Commit the final reviewed plan and code; record the immutable commit SHA and
   create the proposed analysis-lock tag. Record that Git versioning is not
   third-party registration. An optional OSF registration must disclose prior data access.
3. Run development/learning-curve work using 2013 only.
4. Save selected configurations, model objects, environment versions, seeds,
   nested predictions and checksums before opening the new 2023 model scores.
5. Produce the one-time external report with every prespecified result.

This draft includes only an input-audit workflow. It does not implement or launch
model fitting, create the lock tag, merge to main, or register a study on OSF.

