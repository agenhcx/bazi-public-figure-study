# A1 training-sufficiency diagnostics: complete joint report

This is a fixed, post-result diagnostic, not a new blind predictive test. It uses
only 2013 development data for interpreted outcomes, fits and predictions. The
2013 and 2023 A1 results were already seen; no 2023 model predictions or scores
were calculated here. The original A1 files and results are unchanged.

The full-1000 raw MLP has training MAE **25.167 Elo** versus its
saved inner-OOF MAE **66.081**, while the corresponding
fold-training-median OOF MAE is **57.498**. This is
consistent with fitting training patterns that do not improve held-out
prediction; it does not support attributing every A1 failure solely to too few
optimization iterations. The paired budget and recovery results below further
describe that limitation without selecting a new winning procedure.

## Existing fitted models: training and saved inner OOF errors

| Family | Raw train MAE | Raw inner-OOF MAE | Date train MAE | Date inner-OOF MAE |
| --- | --- | --- | --- | --- |
| training_median | 57.379 | 57.498 | 57.379 | 57.498 |
| ridge | 57.362 | 59.216 | 56.478 | 57.310 |
| pairwise_ridge | 34.492 | 63.540 | 56.128 | 57.684 |
| rbf_kernel_ridge | 53.344 | 58.756 | 56.634 | 57.987 |
| shallow_gradient_boosting | 57.308 | 58.556 | 56.659 | 57.690 |
| small_mlp | 25.167 | 66.081 | 56.409 | 57.598 |

These are the independently selected family candidates for final Random1000.
The benchmark uses the median fitted within each inner training fold for OOF
prediction. Inner OOF already selected candidates; it is not a fresh unbiased
confirmation. Full refit training has 1,000 people but each inner fit has 750,
so the displayed gap is not a pure comparison at an identical training size.
All model/candidate/fold details are preserved in the audit worker outputs.

## Original convergence-warning audit

The audit verified 20 original task manifests, all recorded file
hashes and 80 unique saved model objects.
There were 1315 warning records, and
552 of 5360
fitting entries had at least one convergence warning. A three-seed MLP fitting
entry can generate several warning records. The ten final selected-procedure
refits emitted 0 warnings.

| Representation | Family | Inner fits with convergence warning | Total inner fits | Fraction |
| --- | --- | --- | --- | --- |
| date_control | pairwise_ridge | 0 | 400 | 0.000 |
| date_control | rbf_kernel_ridge | 0 | 720 | 0.000 |
| date_control | ridge | 0 | 400 | 0.000 |
| date_control | shallow_gradient_boosting | 0 | 640 | 0.000 |
| date_control | small_mlp | 178 | 480 | 0.371 |
| raw_A | pairwise_ridge | 0 | 400 | 0.000 |
| raw_A | rbf_kernel_ridge | 0 | 720 | 0.000 |
| raw_A | ridge | 0 | 400 | 0.000 |
| raw_A | shallow_gradient_boosting | 0 | 640 | 0.000 |
| raw_A | small_mlp | 370 | 480 | 0.771 |

## Fixed-candidate MLP optimization-budget comparison

Each of five original 800/200 development splits uses its own original MLP
family winner, with the same three initializations and preprocessing. Only the
iteration/function-call caps differ: original 1,000/20,000 versus extended
5,000/100,000. No candidate, seed or budget is selected from these results.

| Representation | Budget | Training MAE | Held-out MAE | Held-out RMSE | Seed fits with convergence warning / 15 |
| --- | --- | --- | --- | --- | --- |
| raw_A | original | 18.806 | 67.913 | 85.468 | 5.000 |
| raw_A | extended | 18.741 | 68.209 | 85.561 | 0.000 |
| raw_A | median | 57.373 | 57.434 | 75.391 | — |
| date_control | original | 56.328 | 57.522 | 72.666 | 0.000 |
| date_control | extended | 56.328 | 57.522 | 72.666 | 0.000 |
| date_control | median | 57.373 | 57.434 | 75.391 | — |

Held-out rows pool 1,000 distinct people per representation, one prediction per
person. Training MAE aggregates 4,000 fold-training predictions, with repeated
people across the five fits; it is not a 4,000-person sample.

| Representation | Training MAE improvement | Held-out MAE improvement | Held-out RMSE improvement | Mean seed objective improvement |
| --- | --- | --- | --- | --- |
| raw_A | 0.064 | -0.297 | -0.094 | 0.001 |
| date_control | 0.000 | 0.000 | 0.000 | 0.000 |

Positive improvement is original minus extended and favors the extended budget.
All differences are descriptive; no new p-value or confidence claim is made.
MLP optimizes squared error plus L2, so optimization-objective improvement need
not improve MAE. These folds have already been examined. Checking only the
original MLP family winners does not exclude an unselected candidate improving
under a larger budget, or another architecture working better.

## Fixed synthetic recovery controls

Targets are entirely synthetic: 2500 + 50 × (strength × standardized signal +
independent standard-normal noise). The 66 raw columns define additive,
pairwise and third-order functions with prespecified random category scores.
Zero-signal controls use noise only. Each condition has two fixed noise
replicates and five 800/200 folds. Each of five representative estimators is
fixed before fitting; there is no hyperparameter search. Actual Elo is not used
to create these targets or choose a representative candidate.

The table shows **mean MAE gain over the fold-training-median benchmark across
the two fixed noise replicates**; positive values favor the model. Every
replicate/model result, including failures, is in `synthetic_pooled_metrics.csv`.

| Signal | Strength | Ridge gain | Pairwise Ridge gain | RBF gain | Boosting gain | MLP gain |
| --- | --- | --- | --- | --- | --- | --- |
| null | 0.000 | -2.438 | -22.144 | -2.668 | -1.007 | -10.017 |
| additive | 0.500 | 3.188 | -16.485 | 2.717 | 2.162 | -4.608 |
| additive | 2.000 | 49.326 | 29.197 | 46.145 | 24.078 | 41.682 |
| pairwise | 0.500 | 0.121 | -17.878 | 0.510 | 2.060 | -6.374 |
| pairwise | 2.000 | 19.250 | 16.541 | 23.821 | 24.563 | 29.219 |
| third_order | 0.500 | -2.316 | -22.861 | -2.109 | -0.952 | -9.785 |
| third_order | 2.000 | -4.513 | -23.612 | 0.612 | -0.709 | 8.914 |

| Signal | Fit attempts | Failed fits | Fits with convergence warning | Warning records |
| --- | --- | --- | --- | --- |
| additive | 100 | 0 | 20 | 60 |
| null | 50 | 0 | 10 | 30 |
| pairwise | 100 | 0 | 20 | 60 |
| third_order | 100 | 0 | 20 | 60 |

Recovery concerns only these functions, strengths, noise and fixed covariate
design. Calendar dependencies can correlate the constructed interaction
signals with lower-order features; exclusively high-order effects are not
claimed. Success is not evidence for a real BaZi–Elo relation; failure cannot
rule out every other function. Two noise replicates do not establish a
universal detection threshold, and zero-signal gains can fluctuate by chance.

## Interpretation and next decision

This finite diagnostic checks optimization limits, training/validation gaps and
recovery of selected known signals. Lower training error alone does not show
better prediction. It cannot prove six symbols contain no information, that an
hour pillar must help, or that a larger model will improve. No A1 conclusion is
replaced by these post-result diagnostics. Further development should be a
separate version with a fixed budget, and final predictive confirmation needs
a predeclared evaluation sample not used for development. The old 2023 NEW
cohort remains previously seen.

The report's machine-readable summary records diagnostic code, plan, lock,
worker input and output SHA256 hashes. All ten workers are required, all
available predictions are realigned and numerical metrics are recomputed
before this report is created.
