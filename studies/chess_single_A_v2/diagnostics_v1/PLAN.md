# A1 training-sufficiency diagnostics, version 1

This is a bounded, post-result diagnostic of the completed raw-six-symbol A1
analysis. It is not a new blind preregistration or a replacement for its results.
The 2013 internal and 2023 external results have already been seen. The original
analysis lock, configuration, source data, fitted models, and reported results
remain unchanged. No diagnostic selects a new model from 2023 performance.

## Fixed inputs and execution

- Original analysis commit: `83e2e82f57b37cf5ed5308ea6218ba317b032180`.
- Original joint-results commit: `488539eaac33b863eaa0505ee152ac47df53dce0`.
- Original analysis-lock SHA256:
  `4ee147676368294e93630d9e801333f5498059a7ae615d8abc532aee40c7277c`.
- Original fitted-model-seal SHA256:
  `b7b31cab6b7bd4099570638f3fe443a41a17cec10efeedea8d519604c0420656`.
- Durable checkpoint bundle: `results/training_checkpoint_bundle.zip`,
  8,351,666 bytes, SHA256
  `445c2b7cbe79ad31c8eec8e414d1c765da615bc84cfaf87d2e4a5428231f5c2f`.
- Use the original pinned Python 3.11.17/dependency environment and one numerical
  thread. Verify original locked file hashes before diagnostics.
- This plan, diagnostic implementation, tests, and workflow are bound in a
  separate `diagnostic_lock.json` and immutable tag
  `chess-single-a-diagnostics-lock-v1` before new research-data fitting.
- Only the 1,000-person 2013 development frame is loaded for predictions or
  fitting. Hash verification can read the original locked external-file bytes;
  no external frame, prediction, metric, or outcome is used in these diagnostics.

## 1. Audit existing fits without refitting

Verify the sealed ledger and all recorded file/model hashes. For every saved
unique model object, align the original training IDs and compute training MAE
and RMSE. Compare with its saved candidate's inner out-of-fold predictions;
include fold-training-median out-of-fold and training-median benchmarks.
For saved development selections, also retain the original outer-held-out
metrics, including pooled 400/600/800-person training-size results.

Report warning records separately from the number and fraction of fitting
entries with at least one convergence warning. Three initialization warnings
from one MLP ensemble are not three failed model configurations. Record refit
warnings and selected-procedure status separately. Candidate failures remain
failures and are not silently rescued.

Inner scores already participated in candidate selection; gaps are descriptive
diagnostics, not fresh unbiased estimates of prediction performance. Lower
training error alone does not imply useful prediction.

## 2. Paired MLP optimization-budget diagnostic

Use the five original `dev_f0_n800` through `dev_f4_n800` splits. Within each
fold and representation (`raw_A` and `date_control`), take the MLP family winner
from that fold's original inner search. Do not reselect candidates or seeds.
Retain each candidate's architecture, regularization, preprocessing, target
scaling, and all three seeds (20261021/22/23), averaging every seed.

Refit the same candidate in two fixed conditions:

| Condition | max_iter | max_fun |
| --- | ---: | ---: |
| Original | 1,000 | 20,000 |
| Extended | 5,000 | 100,000 |

Record each seed's final objective, iterations and convergence warnings, plus
ensemble training and outer-held-out MAE/RMSE. Preserve predictions and fitted
diagnostic objects. Pool the five disjoint held-out folds to 1,000 predictions
for each representation and condition. Compare with the original fold median.
Report original-minus-extended MAE/RMSE descriptively; positive values favor
the extended budget. Do not select a budget based on these outer scores, and
do not add a primary p-value or confidence claim.

The MLP minimizes squared error plus L2, whereas A1's primary evaluation is MAE.
An improved objective need not improve MAE. A limit warning is evidence of an
optimization stopping condition, not proof that it caused prediction failure.
These outer folds have already been examined and are development diagnostics.
This paired budget check concerns only the originally selected within-family
MLP candidates. It does not test whether originally unselected candidates would
become preferable after longer optimization, and it does not establish that the
broader model search was exhaustive.

## 3. Fixed synthetic recovery controls

Use the same 66-column raw representation and lexicographically sorted 1,000
development IDs, with the original shuffled five-fold split (800 training,
200 held out; seed 20261021). Actual Elo is not a synthetic target and is not
used to define signals or choose any representative estimator.

Seed 20261025 defines one independent Gaussian category score for each of the
six fixed-vocabulary positions. Define three functions:

- `additive`: the sum of all six position scores;
- `pairwise`: year-stem score times day-stem score;
- `third_order`: year-stem times month-stem times day-stem scores.

Center and standardize each function on the fixed 1,000-row covariate design
to define its signal unit, before fitting any estimator. This is a definition
of a synthetic outcome on a fixed design, not a learned preprocessing step for
real Elo. Calendar constraints can correlate these constructed functions with
lower-order terms; no orthogonal or exclusively high-order signal is claimed.

For each function use strengths 0.5 and 2, and two fixed noise replicates
(seeds 20261026 and 20261027). Generate independent standard normal noise and
set `y = 2500 + 50 * (strength * standardized_signal + noise)`. Also run a
single zero-signal condition, with the same two noise replicates. There are
14 scenario/replicate combinations in total, not 14 independent discoveries.

Use these five fixed representative candidates, without hyperparameter search:

| Family | Fixed candidate parameters |
| --- | --- |
| Ridge | alpha 10 |
| Pairwise Ridge | alpha 100 |
| RBF kernel ridge | alpha 1, gamma 0.01 |
| Shallow gradient boosting | depth 2, 100 trees, minimum leaf 10 |
| Small MLP | width 16, alpha 1; original optimization budget and all 3 seeds |

All other parameters and fold-local transformations retain their original
values. Include each fold's training-median benchmark. Preserve design weights,
synthetic targets, per-person held-out predictions, failures and warnings.
Report pooled MAE/RMSE and improvement relative to the median for every fixed
case; no post-hoc successful-type selection, model-family expansion or new
formal significance claim. The exact initial budget is 350 pipeline/ensemble
fits (including 70 MLP ensembles with three seed fits each), corresponding to
490 underlying estimator fits, plus median predictions.

These controls test recovery only for the specified types, strengths, noise,
covariate design, and fixed estimators. Success is not evidence for a real
astrological signal. Failure does not prove all other real functions are
undetectable. The zero-signal controls can show chance fluctuations.

## Stopping and interpretation

Run this finite audit, ten paired representation/fold MLP comparisons, and
four synthetic-control jobs once. Preserve diagnostics of numerical failures;
do not expand models, strengths, budgets, seeds, or endpoints after seeing the
results. An infrastructure retry uses identical code and parameters and is
recorded as such. Any implementation correction is documented before rerun.

The report answers whether A1 shows optimization limits, training/validation
gaps, and recovery of the selected synthetic signals. It cannot decide that
all six-symbol relationships are absent, that adding the hour must help, or
that a more complex model will improve. Future model development requires a
separate version; final predictive confirmation requires a predeclared sample
not used for that development. A1's 2023 NEW cohort remains previously seen.
