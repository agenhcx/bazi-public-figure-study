# Chess single-player A v2: model comparison

This study compares six position-specific stem/branch identities with ordinary
age and birth-season features for predicting snapshot standard Elo. The fixed
development pool has 1,000 eligible January-2013 men. The common independent-person
January-2023 NEW cohort has 500 men. Expanded FULL (1,001) and legacy FULL (501)
are overlapping supplementary cohorts. See the acquisition manifests and
`acquisition_amendment_01.md` for exclusions, the NEW500 scope correction and
the retained interrupted NEW1000 attempt.

## Inputs and fixed comparisons

`model_inputs.py` generates the same date-only three pillars as the earlier
scripts using `sxtwl==2.0.7`. Every matching old birthday and pillar must agree.
It supplies exactly 66 fixed-vocabulary indicators for raw A and seven age/season
features for the date control. Names, IDs, titles, federation, ranking and
traditional feature labels are not predictors.

Both representations use the same five-family menu and 33 candidate settings:
Ridge, generic pairwise Ridge, RBF kernel ridge, shallow gradient boosting and a
small MLP. Inputs and targets are scaled inside each training fold only. MLP
predictions average the three fixed seeds. Finite convergence-limit fits remain
in the search with their warnings; numerical failures are explicitly recorded.
No family, seed or size is selected using an external score.

The final nested random subsets have exactly 500, 800 and 1,000 people. Ranked
sensitivity subsets have 501, 801 and 1,000 people after retaining cutoff ties.
The identical Random1000 and Ranked1000 person sets share fitted objects while
retaining both report labels. Ranked comparisons change Elo range and population
composition as well as training size.

## Execution and freeze barrier

The preflight workflow installs the exact requirements, runs synthetic tests,
checks the completed source cohorts and prepares input fingerprints. It performs
no research-data model fitting. A synthetic integration test exercises every
production stage with generated data and dummy estimators.

`analysis_lock.json` binds the final configuration, methods, implementation,
tests, source/derived inputs, training IDs and numerical environment. The locked
model workflow verifies every binding and creates the immutable
`chess-single-a-analysis-lock-v2` tag before any research-data fit.

Twenty training tasks then run using only 2013:

- Fifteen outer-fold tasks: five held-out folds at training sizes 400, 600 and
  800, with a fresh four-fold inner search in every task.
- Five distinct final training subsets, each using four-fold inner selection
  and independently tuned family refits.

The 800-person outer tasks also provide the main nested-CV estimate, covering
1,000 held-out development people. There is no internal-CV estimate for a model
trained on 1,000 people.

All twenty task manifests and every fitted-model/file hash must pass the seal
step. The complete sealed collection is uploaded before the evaluation job can
start. Evaluation verifies that collection again before reading external frames,
then scores every prespecified family, selected procedure, size and median
benchmark together. The selected global candidate can have its own fitted
object if a numerical near-tie makes it differ from its family's independent
winner; both identities and scores are checked against the full search log.

The workflow uses Python 3.11.17, the exact versions in `requirements-model.txt`,
one numerical thread and `PYTHONHASHSEED=0`. Production entry points reject a
different configuration, file fingerprint or required environment version.

## Saved results and reproducibility

The joint report is `results/REPORT.md`. Machine-readable outputs include the
complete metrics, compressed per-person external predictions, primary paired
losses/interval, descriptive training-size contrasts and internal held-out
learning curves. PNG and SVG plots accompany the tables.

`results/training_checkpoint_bundle.zip` retains the sealed fitted models,
selected settings, full search/diagnostic logs, fold IDs and fingerprints in the
repository. The companion JSON records the archive and seal hashes. This copy
does not depend on the lifetime of GitHub Actions artifacts.

Local entry points use the same locked inputs and environment. Commands are
single-line, run from the repository root:

`python -m pip install -r studies/chess_single_A_v2/requirements-model.txt`

`python studies/chess_single_A_v2/lock_utils.py verify --repo-root .`

`python studies/chess_single_A_v2/train_models.py --repo-root . --task final_random_1000 --output-dir training_runs/final_random_1000`

The seal and evaluation commands require the complete twenty-task collection,
not only the example final task. Input preparation is a pre-lock operation;
re-running it changes provenance timestamps and requires a documented new lock.

## Interpretation

The primary endpoint is Random1000 NEW MAE(date control) minus MAE(raw A), with
a 95% paired person-level percentile bootstrap interval using 10,000 draws.
The interval conditions on the fixed fitted models. It does not include every
source of training or subset uncertainty. Secondary intervals have no joint
coverage or separate formal significance claim.

Raw A versus date control compares representations; it does not establish
information beyond a sufficiently flexible date model or a causal mechanism.
Historical outcomes were previously explored, and the acquisition-stage target
amendment followed observed coverage. Neither this lock nor its tag makes the
study newly blind. A finite model menu and an uncertain result cannot prove the
absence of every possible association.
