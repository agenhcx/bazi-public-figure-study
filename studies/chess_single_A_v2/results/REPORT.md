# Chess single-player A v2: complete fixed-model evaluation

Primary comparison: Random1000 trained on January-2013, evaluated on the rebuilt
500-person January-2023 NEW cohort. Lower MAE is better.

**Primary delta MAE (date control minus raw six symbols): -2.239 Elo,
95% paired bootstrap interval [-3.857, -0.638].**
Positive delta favors raw A. The interval conditions on these fixed fitted models.
No minimum meaningful gain was specified, and no equivalence or no-association
claim follows from a zero-crossing interval. No primary p-value is reported.

## Selected procedures and training-size comparison

Selection uses only 2013 inner cross-validation. External scores do not choose a
family, size, seed, or ranked threshold. All fixed sizes are shown together.

| Training subset | Actual train n | Raw selected family | Date selected family | Raw MAE | Date MAE | Median MAE | Date minus raw MAE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| random_500 | 500 | rbf_kernel_ridge | ridge | 105.860 | 104.533 | 98.322 | -1.328 |
| random_800 | 800 | rbf_kernel_ridge | ridge | 107.592 | 105.731 | 99.664 | -1.861 |
| random_1000 | 1000 | shallow_gradient_boosting | ridge | 107.174 | 104.936 | 98.588 | -2.239 |
| ranked_500_with_ties | 501 | rbf_kernel_ridge | pairwise_ridge | 149.233 | 147.572 | 135.772 | -1.661 |
| ranked_800_with_ties | 801 | rbf_kernel_ridge | ridge | 120.496 | 118.004 | 109.088 | -2.491 |
| ranked_1000_with_ties | 1000 | shallow_gradient_boosting | ridge | 107.174 | 104.936 | 98.588 | -2.239 |

Random500/800/1000 are one fixed nested draw from the same population. Ranked
subsets include boundary ties and jointly change training size and Elo range.
Ranked1000 reuses the identical fitted Random1000 models, retaining both labels.

| Representation | Training n contrast | MAE improvement from more people | 95% descriptive interval |
| --- | --- | --- | --- |
| raw_A | 500 to 800 | -1.732 | [-1.927, -1.531] |
| raw_A | 800 to 1000 | 0.418 | [-0.201, 1.058] |
| raw_A | 500 to 1000 | -1.314 | [-1.921, -0.681] |
| date_control | 500 to 800 | -1.198 | [-1.875, -0.481] |
| date_control | 800 to 1000 | 0.795 | [0.692, 0.899] |
| date_control | 500 to 1000 | -0.403 | [-1.038, 0.262] |

These secondary intervals have no simultaneous-coverage or separate formal
significance claim and do not cover all variation over possible training draws.

## All five families on the common NEW cohort

Every family was independently tuned using the corresponding 2013 training
subset. Invalid families, if any, remain explicitly identified.

| Training subset | Family | Raw MAE | Date MAE | Date minus raw MAE | Raw RMSE | Date RMSE | Raw status | Date status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_500 | ridge | 106.282 | 104.533 | -1.749 | 123.899 | 121.035 | complete | complete |
| random_500 | pairwise_ridge | 108.403 | 104.224 | -4.179 | 127.012 | 120.656 | complete | complete |
| random_500 | rbf_kernel_ridge | 105.860 | 104.795 | -1.066 | 123.383 | 121.225 | complete | complete |
| random_500 | shallow_gradient_boosting | 106.080 | 105.032 | -1.047 | 123.659 | 121.635 | complete | complete |
| random_500 | small_mlp | 111.839 | 104.629 | -7.210 | 130.363 | 121.053 | complete | complete |
| random_800 | ridge | 107.990 | 105.731 | -2.260 | 125.675 | 122.207 | complete | complete |
| random_800 | pairwise_ridge | 108.364 | 106.957 | -1.407 | 126.980 | 124.832 | complete | complete |
| random_800 | rbf_kernel_ridge | 107.592 | 106.516 | -1.076 | 125.234 | 123.653 | complete | complete |
| random_800 | shallow_gradient_boosting | 107.622 | 106.807 | -0.815 | 125.283 | 123.377 | complete | complete |
| random_800 | small_mlp | 112.133 | 106.097 | -6.036 | 131.509 | 122.645 | complete | complete |
| random_1000 | ridge | 107.337 | 104.936 | -2.402 | 124.965 | 121.360 | complete | complete |
| random_1000 | pairwise_ridge | 108.743 | 105.621 | -3.122 | 128.036 | 122.891 | complete | complete |
| random_1000 | rbf_kernel_ridge | 106.780 | 105.149 | -1.631 | 124.383 | 121.767 | complete | complete |
| random_1000 | shallow_gradient_boosting | 107.174 | 106.156 | -1.018 | 124.654 | 122.709 | complete | complete |
| random_1000 | small_mlp | 110.098 | 105.288 | -4.810 | 129.537 | 121.622 | complete | complete |
| ranked_500_with_ties | ridge | 149.743 | 147.748 | -1.995 | 168.209 | 164.107 | complete | complete |
| ranked_500_with_ties | pairwise_ridge | 149.781 | 147.572 | -2.209 | 169.556 | 164.364 | complete | complete |
| ranked_500_with_ties | rbf_kernel_ridge | 149.233 | 148.663 | -0.570 | 167.589 | 165.478 | complete | complete |
| ranked_500_with_ties | shallow_gradient_boosting | 149.250 | 148.207 | -1.044 | 167.598 | 165.147 | complete | complete |
| ranked_500_with_ties | small_mlp | 152.144 | 147.801 | -4.343 | 172.917 | 164.195 | complete | complete |
| ranked_800_with_ties | ridge | 120.811 | 118.004 | -2.807 | 138.870 | 134.430 | complete | complete |
| ranked_800_with_ties | pairwise_ridge | 118.704 | 119.320 | 0.616 | 138.482 | 135.845 | complete | complete |
| ranked_800_with_ties | rbf_kernel_ridge | 120.496 | 119.794 | -0.701 | 138.620 | 136.125 | complete | complete |
| ranked_800_with_ties | shallow_gradient_boosting | 120.531 | 119.344 | -1.187 | 138.598 | 136.141 | complete | complete |
| ranked_800_with_ties | small_mlp | 124.716 | 118.717 | -5.999 | 143.968 | 135.042 | complete | complete |
| ranked_1000_with_ties | ridge | 107.337 | 104.936 | -2.402 | 124.965 | 121.360 | complete | complete |
| ranked_1000_with_ties | pairwise_ridge | 108.743 | 105.621 | -3.122 | 128.036 | 122.891 | complete | complete |
| ranked_1000_with_ties | rbf_kernel_ridge | 106.780 | 105.149 | -1.631 | 124.383 | 121.767 | complete | complete |
| ranked_1000_with_ties | shallow_gradient_boosting | 107.174 | 106.156 | -1.018 | 124.654 | 122.709 | complete | complete |
| ranked_1000_with_ties | small_mlp | 110.098 | 105.288 | -4.810 | 129.537 | 121.622 | complete | complete |

Complete RMSE and Spearman correlations for every model/cohort are in
`external_metrics.csv`; constant-prediction correlations are undefined.

## Internal development

| People used to train each outer model | Representation | Pooled held-out MAE | RMSE | Spearman |
| --- | --- | --- | --- | --- |
| 400 | raw_A | 58.737 | 74.328 | -0.055 |
| 400 | date_control | 57.501 | 72.845 | 0.160 |
| 400 | benchmark | 57.490 | 75.820 | -0.025 |
| 600 | raw_A | 59.212 | 74.500 | -0.049 |
| 600 | date_control | 57.182 | 72.367 | 0.184 |
| 600 | benchmark | 57.532 | 75.595 | -0.069 |
| 800 | raw_A | 59.259 | 74.360 | -0.092 |
| 800 | date_control | 57.374 | 72.349 | 0.167 |
| 800 | benchmark | 57.434 | 75.391 | -0.099 |

Each row aggregates five fixed outer held-out folds with one prediction per
2013 person. The 800-training-size row is the primary nested-CV development
estimate. There is no internal-CV estimate for a model trained on 1,000 people.

## Supplementary, overlapping evaluation cohorts

| Cohort | Training subset | Evaluation n | Raw selected MAE | Date selected MAE | Date minus raw MAE | Median MAE |
| --- | --- | --- | --- | --- | --- | --- |
| supplementary_full | random_500 | 1001 | 66.808 | 64.698 | -2.110 | 65.357 |
| supplementary_full | random_800 | 1001 | 66.889 | 64.028 | -2.861 | 65.742 |
| supplementary_full | random_1000 | 1001 | 68.038 | 63.734 | -4.304 | 65.431 |
| supplementary_full | ranked_500_with_ties | 1001 | 88.769 | 89.400 | 0.631 | 84.485 |
| supplementary_full | ranked_800_with_ties | 1001 | 73.331 | 69.846 | -3.485 | 69.365 |
| supplementary_full | ranked_1000_with_ties | 1001 | 68.038 | 63.734 | -4.304 | 65.431 |
| legacy_full | random_500 | 501 | 57.635 | 59.086 | 1.451 | 67.336 |
| legacy_full | random_800 | 501 | 55.420 | 57.496 | 2.076 | 65.611 |
| legacy_full | random_1000 | 501 | 58.289 | 58.087 | -0.203 | 66.984 |
| legacy_full | ranked_500_with_ties | 501 | 46.278 | 51.330 | 5.053 | 50.164 |
| legacy_full | ranked_800_with_ties | 501 | 49.346 | 51.188 | 1.843 | 56.880 |
| legacy_full | ranked_1000_with_ties | 501 | 58.289 | 58.087 | -0.203 | 66.984 |

Expanded FULL and legacy FULL include repeated development people and overlap
NEW. They are supplementary diagnostics, not independent replications. Their
individual-family results are also included in `external_metrics.csv`.

| Cohort | People | Minimum snapshot Elo | Maximum snapshot Elo |
| --- | --- | --- | --- |
| development | 1000 | 2444 | 2861 |
| primary_new | 500 | 2334 | 2785 |
| supplementary_full | 1001 | 2412 | 2859 |
| legacy_full | 501 | 2513 | 2859 |

| First cohort | Second cohort | Shared people |
| --- | --- | --- |
| development | primary_new | 0 |
| development | supplementary_full | 673 |
| development | legacy_full | 357 |
| primary_new | supplementary_full | 308 |
| primary_new | legacy_full | 139 |
| supplementary_full | legacy_full | 501 |

## Audit and interpretation limits

- All 20 training tasks and every model/checkpoint hash were sealed before
  external evaluation, then reverified before any new external predictions or
  scores were calculated.
- Finite convergence-limit fits are retained as specified. Warning records:
  1315; invalid inner-search candidates: 0. Detailed logs
  and selected configurations are in the sealed training artifacts.
- Raw A versus the age/season date control compares two representations. It
  does not establish incremental information conditional on an unrestricted
  date predictor, nor a causal astrological mechanism.
- Only active, exact-DOB, confirmed-northern male players meeting the fixed
  ranking and exclusion rules are represented. NEW has a different rating
  range after excluding the enlarged development pool. General-population
  talent, professional selection, and other populations are not evaluated.
- Historical 2013/2023 BaZi and Elo outcomes were previously explored. The
  acquisition amendment corrected the extra NEW1000 target to NEW500 before
  predictive fitting. This is not a newly blind preregistration.
- A finite model menu cannot prove the absence of every possible relationship.
  Test-person bootstrap uncertainty excludes all training/process uncertainty.

## Provenance

| Item | SHA256 |
| --- | --- |
| config_sha256 | d78010beb87ac8d8c274c56103c0b5f3c9bc8d3053ba421d38694dc9491c374f |
| data_manifest_sha256 | 77184cde285f8499b06863703e570930f4e3ea4f23a15d2f33048e938a129802 |
| analysis_lock_sha256 | 4ee147676368294e93630d9e801333f5498059a7ae615d8abc532aee40c7277c |
| fitted_models_seal_sha256 | b7b31cab6b7bd4099570638f3fe443a41a17cec10efeedea8d519604c0420656 |
| evaluation_script_sha256 | 26a8bd0b129679bdf684b6dde928f22ac2168b5f6c8ac70785d4f1afbca20d8b |

Predictions are saved in `external_predictions.csv.gz`; primary paired losses
are separately available in `primary_paired_losses.csv`. No model or parameter
was changed in response to these external results.
