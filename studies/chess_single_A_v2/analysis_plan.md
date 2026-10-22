# Chess single-player A v2: expanded-cohort analysis plan

Prepared: 2026-10-21. Protocol ID: `chess-single-A-v2`.

**Status: modelling REVIEW DRAFT; fitting is disabled.** The acquisition rules
are in `acquisition_protocol.md` and are locked by a separately recorded commit
before live expansion. Data hashes, analysis implementation and dependency
versions must be fixed in a later analysis-lock commit before fitting. This
document does not claim that either lock already exists.

This v2 replaces the unexecuted `chess_single_A_v1` modelling draft after the user
requested expansion before fitting. Preserve v1 and all original frozen cohorts;
no v1 predictive model or analysis-lock tag was created.

## 1. Question and previous access

Among the selected Northern-Hemisphere male chess cohorts, can a model using only
the six position-specific Year/Month/Day stem/branch identities predict snapshot
standard Elo better than a model using ordinary age and season information?
How do prespecified 500-, 800- and 1,000-person training subsets perform on the
same reconstructed 2023 NEW cohort?

The 1994/2013 and 2023 BaZi/Elo results have previously been examined in other
analyses. See `POSTREVEAL_LOG_CHESS_1994_2013_V2.md` and
`VALIDATION_PLAN_CHESS_2023_V2.md`. This records a new modelling procedure on an
expanded cohort; it is not outcome-naive preregistration or a newly blind test.
A Git commit/tag or later registration cannot remove previous outcome access.

A is a raw-symbol representation study. No Ten-God, Five-Phase, hidden-stem,
strength, stem-combination or branch-interaction labels are supplied. A separate
B study requires its own feature specification and analysis record.

## 2. Acquisition, cohorts and identity

Follow `acquisition_protocol.md` without using model performance to revise the
cohort. Obtain the full official active January-2013 and January-2023 standard
rating populations, reuse frozen annotations with provenance, and apply the
existing exact-DOB, historical birth-year agreement, temporal sanity and confirmed
northern birthplace rules. No GM-title filter or southern month inversion is
introduced. Unresolved identity/DOB conflicts and source failures are audited;
they are not repaired or excluded according to a model result.

New DOB claims require an explicit Gregorian calendar-model check. Legacy frozen
dates inherit the earlier pipeline's Gregorian interpretation, whose query did
not retain calendar-model metadata; record `legacy_calendar_not_reverified`.
Their calendars are not presented as newly verified, and unknown/non-Gregorian
new claims do not silently receive a Gregorian interpretation.

Planned data roles:

- Development pool: January-2013 men, Top1,000 eligible plus all eligible cutoff
  Elo ties. Its actual size can exceed 1,000.
- Primary evaluation: January-2023 NEW, at least 1,000 eligible unseen men plus
  eligible cutoff ties. Exclude the entire expanded 2013 pool and the union of
  all four old 1994/2013 M/F frozen north-v3 cohorts using their identity bridges.
- Supplementary diagnostic: expanded January-2023 FULL, Top1,000 eligible men
  plus cutoff ties before seen/unseen exclusion, derived from the same candidate
  audit. It is not an independent replication.
- Supplementary evaluation: the unchanged, previously explored 2023 M_FULL501
  file, if retained in the final manifest. Its role is fixed here; any input
  failure is reported rather than replaced by a more favorable cohort.

Canonical identity is normalized decimal `identity_bridge_modern_fide_id` when
available, otherwise normalized decimal `fide_id`. Require one row per canonical
person, consistent DOB across snapshots, and development-pool/NEW overlap zero.
Report all other overlaps after acquisition, including expanded development/FULL
and NEW/FULL for both expanded and legacy FULL definitions, and overlap of the
two FULL files. FULL includes repeated development people and can overlap NEW.
Repeated snapshots are not additional independent training people.

Save final files, exact SHA256 values, source/archive fingerprints, source-code
commit, selected IDs and actual counts in `data_manifest.json` before analysis
lock. The old v1 manifest is not a manifest for these expanded data. Cohorts are
Top-k eligible people rather than the official ranking's first k rows; NEW scans
farther after exclusions. Conclusions are restricted to these selected cohorts,
not general chess talent, entry into professional chess or causal astrology.

## 3. Training subsets and the meaning of sample size

The **primary training subset is exactly 1,000 people**. Order all canonical IDs
in the expanded 2013 pool by ascending SHA256 hex digest of the UTF-8 string
`20261024` followed by one newline and the canonical ID. Use canonical ID as a
hash-tie breaker. Take the first 500, 800 and 1,000 IDs as nested random subsets.
Save these exact ID lists and hashes before fitting. There is one prespecified
draw; do not try additional seeds or select the draw with the best performance.
The expanded pool's remaining cutoff-tied members still belong to the pool
excluded from 2023 NEW.

Random500 and Random800 are secondary training-scale comparisons. Because their
members are drawn from one fixed eligible population, they more directly address
training size than the old Top500-versus-expanded-Top1000 contrast. A single draw
does not estimate all possible training-subset variation, and a monotonic
improvement is not assumed.

Also fit three prespecified **ranked sensitivity subsets**: the top 500, top 800
and top 1,000 eligible 2013 people, including every pool member tied at each
threshold's rating. Record their actual counts. These contrasts change both
sample size and Elo/population range; do not label their difference a pure
sample-size effect. Do not silently call the previous 501-person cohort a random
500-person subset. If two prespecified subsets have identical canonical ID sets,
fit once and retain both result labels.

Every subset uses the same fixed 2023 NEW evaluation people. None of the NEW
people can be used to select a size, seed, family, hyperparameter or ranked
threshold. The whole expanded 2013 pool is excluded from NEW for every size,
including people absent from a particular random subset.

## 4. Target and representations

Target: numeric standard Elo in `rating` at the row's `snapshot`, not rank,
Elo-z, career maximum or future rating change.

Raw A input order is year_stem, year_branch, month_stem, month_branch, day_stem,
day_branch. Split stored year/month/day pillars to harmonize schemas; existing
explicit columns must agree. Use six separate fixed-vocabulary one-hot groups,
10 stems and 12 branches per corresponding position, giving 66 indicators.
No ordinal symbol values, learned relabeling, pretrained embeddings, person ID,
name, title, federation, rank, games or earlier-study scores are predictors.

Date control has seven features: age, age squared, age cubed and first/second
annual sine/cosine harmonics of birth day-of-year. Age is days from Gregorian DOB
to the snapshot month's first day divided by 365.2425. Season phase is
`2*pi*(day_of_year-1)/(366 if the birth year is leap else 365)`. Do not drop leap
days. Exact definitions and vocabularies are in `config.json`.

All fitted transforms and input/target scaling are fitted on the relevant
training fold only. Comparing pure A with date control compares representations;
it does not establish incremental information conditional on a sufficiently
flexible date predictor. A date-versus-date-plus-six claim requires a separately
prespecified analysis.

## 5. Algorithms and selection

Retain the five v1 families and exact finite grids in `config.json`: additive
Ridge; generic degree-two pairwise expansion plus Ridge; RBF kernel ridge;
shallow gradient boosting; small MLP. Raw A and date control get the same family
menu and logical search budget. Pairwise expansion retains main effects and all
distinct input-column products, without choosing traditional combinations.

Average MLP predictions across the three fixed seeds; do not choose a seed.
Select configurations by pooled per-person held-out MAE in original Elo units.
Ties within 1e-12 use the first listed family/configuration in the fixed order.
A finite fit reaching an iteration limit is retained and its warning reported;
do not expand the iteration budget. A numerical exception/nonfinite prediction
invalidates the configuration for that inner search. Stop if all configurations
for a representation are invalid. Do not add a family, seed, grid value or manual
rule after viewing external results.

## 6. Internal development and final fitting

Use the primary Random1000 subset for shuffled 5-fold outer CV, after
lexicographic canonical-ID sorting, seed 20261021. Each outer model has 800
training and 200 held-out people. Within each outer training set use shuffled
4-fold CV, seed 20261022, to select family/hyperparameters separately for raw A
and date control. Save one outer held-out prediction per development person.

An internal learning curve uses exact training sizes 400, 600 and 800 from each
outer training fold and the same outer held-out people. Order training IDs by
the SHA256 rule above with seed `20261024 + zero_based_outer_fold_index`; nested
prefixes define each size. Repeat the fixed inner selection inside each prefix.
An insufficient fold size is an input/configuration failure, not permission to
relabel a smaller sample as 800. This curve uses only 2013. It provides **no
internal CV estimate for a model trained on 1,000 people**.

After development, run the same 4-fold inner search independently within each of
the six final training subsets: Random500/800/1000 and Ranked500/800/1000 with
ties. Refit the selected raw A and date-control pipeline on the entire respective
subset. Retain each family's independently tuned pipeline for complete secondary
reporting, plus that subset's training-median Elo benchmark. The primary pair is
the two selected pipelines fitted on exactly Random1000. Do not promote a
secondary size or family to primary after external evaluation.

Before any new external model scores are calculated, save all selected
configurations, model objects, training-ID hashes, environment versions, seeds,
development predictions, convergence/invalid-fit logs and file checksums. Then
evaluate every prespecified model/size together on the fixed external cohort(s)
and produce one complete report. Previously explored 2023 outcomes remain
acknowledged; this barrier prevents new score-driven changes, not prior access.

## 7. Primary endpoint and uncertainty

Primary directional hypothesis: the Random1000 raw A selection procedure has
lower 2023 NEW MAE than the Random1000 date-control selection procedure.

Primary endpoint: `delta_mae = MAE(date_control) - MAE(raw_A)`, in Elo points.
Positive values favor A. Report the paired per-person absolute-error differences,
their mean, and a 95% paired person-level percentile bootstrap interval using
10,000 resamples, seed 20261023. This interval conditions on the fixed fitted
models and does not include all model-development or subset-selection
uncertainty. Report internal development stability separately.

No minimum meaningful gain is agreed: `minimum_meaningful_gain_elo` remains null.
Do not claim equivalence, sufficient power for an unspecified effect or proof of
no association. No p-value is a primary endpoint. Zero, negative and uncertain
results are valid reportable outcomes.

## 8. Complete secondary reporting

Report every prespecified size/family's NEW MAE, RMSE and Spearman correlation
(undefined for constant predictions), date-control contrast and training-median
benchmark. Report the same supplementary expanded-FULL and legacy-FULL501 results
with observed overlaps and known previous access. Keep their labels separate.
Do not substitute favorable FULL or individual family results for the primary
NEW result.

For the selected raw A pipeline and selected date-control pipeline separately,
report paired external MAE changes for Random800 versus Random500, Random1000
versus Random800, and Random1000 versus Random500. Define improvement as the
smaller model's per-person absolute error minus the larger model's error.
Use the same descriptive paired bootstrap procedure; intervals do not have
simultaneous coverage and support no separate formal significance claims.
Present ranked-subset results as sensitivity to jointly changing training size
and population range. Report all results regardless of sign; no external winner
selects the final sample size. Formal additional tests require a labeled
amendment and appropriate multiplicity handling.

## 9. Freeze and execution order

1. Commit-lock acquisition rules/source probe, then record the collector commit.
2. Collect complete cohorts under those rules and audit sources, identities,
   exclusions, boundary ties, overlaps and final fingerprints. Retain checkpoints
   for failures; do not silently lower targets or alter eligibility.
3. Finalize this modelling plan, exact manifests/subset IDs, implementation,
   dependencies and tests. Record an immutable analysis-lock commit/tag and the
   known prior outcome access. A Git tag is not third-party registration.
4. Run 2013 development and fit all prespecified final models; save artifacts.
5. Calculate and jointly report all fixed external scores without model changes.

There is no automatic expansion beyond the planned pool or the planned NEW
target. Any future sample/source/feature/model change requires a versioned
amendment retaining the full earlier result, not collecting until a desired
effect appears. This draft permits acquisition and audits only: no predictive
fitting is implemented or launched here, and the modelling lock is not created.
