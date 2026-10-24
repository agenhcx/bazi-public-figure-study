# Chess single-player B1: constrained five-phase representation

This plan is fixed after the A1 and training-sufficiency results were inspected, but before any B1 research-data fitting. It is an exploratory extension, not a new blind preregistration. The user requested five-phase generation/control, hidden stems with main > middle > residual, and a month-order multiplier >= 1. The original A1 files, outcomes, models, and diagnostics remain unchanged.

## Question and scope

Does adding a small, shared traditional structure improve held-out Elo prediction relative to the same raw-symbol Ridge procedure? Only the frozen 2013 Random1000 development set is used for tuning. Use one Ridge family rather than repeating all five A families or adding training-size searches. Compare B1, raw66 Ridge, date7 Ridge, and a training-median constant. Previously seen 2023 NEW500 is evaluated jointly only after every final model and all development outputs are sealed. No FULL-cohort scoring, outcome-guided data repairs, automatic grid expansion, or new significance/absence-of-effect claims.

## Frozen hidden-stem convention

Stem phases: 甲乙 wood, 丙丁 fire, 戊己 earth, 庚辛 metal, 壬癸 water. Phase order is wood, fire, earth, metal, water; generation is +1 modulo 5 and control is +2.

| Branch | Main | Middle | Residual |
|---|---|---|---|
| 子 | 癸 | — | — |
| 丑 | 己 | 癸 | 辛 |
| 寅 | 甲 | 丙 | 戊 |
| 卯 | 乙 | — | — |
| 辰 | 戊 | 乙 | 癸 |
| 巳 | 丙 | 戊 | 庚 |
| 午 | 丁 | 己 | — |
| 未 | 己 | 丁 | 乙 |
| 申 | 庚 | 壬 | 戊 |
| 酉 | 辛 | — | — |
| 戌 | 戊 | 辛 | 丁 |
| 亥 | 壬 | 甲 | — |

This is an explicit operational convention, continuing the project's [Chess C7 table](https://github.com/agenhcx/bazi-public-figure-study/blob/3d412f0b92875941f3e75aa89a750167faf08112/run_chess_c7_hiddenstem_hour_performance_sensitivity_v1.py) and [frozen plan](https://github.com/agenhcx/bazi-public-figure-study/blob/3d412f0b92875941f3e75aa89a750167faf08112/C7_HIDDENSTEM_HOUR_PERFORMANCE_SENSITIVITY_PLAN_V1.md). The old scripts used priority selection, not continuous qi weights. Assigning the second slot of 午 and 亥 to middle is a new explicit B1 definition. This table is not claimed to be the sole authoritative tradition: [lunar-python](https://github.com/6tail/lunar-python/blob/74c56657e02673d52f99d5afe8cfbd01b21cc1c7/lunar_python/util/LunarUtil.py) lists 巳 as 丙庚戊 and its [issue 28](https://github.com/6tail/lunar-python/issues/28) records disagreement. Do not silently substitute library array order.

## Feature mathematics

All players share main weight 1, middle m, and residual r=m*q. Search m in {0.25,0.5,0.75}, q in {0.25,0.5,0.75}, and month multiplier lambda in {1,1.5,2,3}. Thus 1>m>r>0 and lambda>=1 for every candidate. Fixing main to 1 defines a relative scale; these are finite discrete hyperparameter choices, not an unrestricted continuous fit.

For each branch, sum its present hidden stems using weights (1,m,r), then normalize those present weights to total 1. Missing roles contribute zero and no stem is fabricated. Each visible year/month/day stem contributes unit phase mass. Multiply only the month branch mixture by lambda; the month stem remains unit mass. Pool the three visible stems and three branch mixtures, then divide by total mass 5+lambda to obtain phase fractions f[0:5]. Weighting occurs before mixing and before any learned StandardScaler, so independent column scaling does not cancel the chosen parameters.

Append 20 columns to the exact raw66 position one-hot columns:

1. The five absolute phase fractions f.
2. Five day-master-centered fractions: same, I generate, I control, controls me, generates me (offsets 0,1,2,3,4 from the day-stem phase).
3. Five generation pair strengths f[i]*f[(i+1)%5].
4. Five control pair strengths f[i]*f[(i+2)%5].

These products encode paired presence, not a physical transfer simulation, nor an assumed good/bad Elo sign. No yin/yang ten-god distinction, combinations/clashes, hidden-stem emergence, hour, or dynamic calendar effects are added. With fixed m,q,lambda, all 86 features are within the span of the A1 complete pairwise raw-symbol representation. This experiment tests parameter sharing and regularization, not new birth information or greater representational expressivity.

The inequality constraints apply to feature construction. Because raw66 remains available and Ridge coefficients can have either sign, they do not constrain final Elo marginal effects. Selected qi/month parameters cannot be identified as true traditional strengths from this design.

## Training and selection

All pipelines use the original Ridge settings: lsqr, tol=1e-6, max_iter=10000, alpha in {0.1,1,10,100,1000}. Fit input StandardScaler and target StandardScaler inside each training fold, invert target scaling for every metric. B1 has 36 structural settings x 5 alpha = 180 candidates; raw and date controls have 5 each. This is unequal search scope, disclosed rather than padded with duplicate candidates.

Order candidates by representation B1/raw/date, then m, q, lambda, alpha in listed Cartesian-product order. Select the first candidate with complete pooled inner-held-out MAE <= minimum + 1e-12. Any failed/nonfinite candidate is invalid for that search; retain finite warning fits and report all warnings. Stop if a representation has no valid candidate. Do not increase iterations, expand the grid, or choose a model using outer or external results.

Rows use lexicographic canonical identity strings. Use the original five shuffled outer folds (seed 20261021), four shuffled inner folds (seed 20261022). Each outer fold independently chooses all hyperparameters using only its 800 training players; predict its 200 held-out players. Final searches use only all 1000 development players with the same four-fold rule; refit three selected models on all 1000. Median predictions use each respective training set.

## Evaluation and reproducibility

Report pooled 2013 outer-held-out MAE, RMSE, and Spearman; report B1-minus-raw and B1-minus-median paired absolute-error means (negative favors B1). These reuse previously inspected folds and outcomes and remain development diagnostics. After all six tasks finish, seal exact task files, model bytes, source/input lock fingerprint, and candidates. Only then load the previously seen NEW500 outcomes and jointly score B1/raw/date/median with the same metrics. No new p-values, equivalence tests, or confirmatory intervals.

Report every fold/final winner, weight stability, selected grid boundaries, search failures and warning counts. Report any mismatch with the expected 1000/500 persons or original input hashes as a failure, not a smaller relabeled sample. Freeze all B1 source/config/tests/workflow, bind the unchanged A1 lock and pinned Python 3.11.17 environment, and create immutable tag chess-single-b-structure-lock-v1 before research fitting. Preserve complete searches, outer predictions, final fitted models, seal, and reports in durable checkpoints. Tests may fit synthetic data before freezing; no B1 research fit is permitted before the lock/tag.
