# C7 HIDDEN-STEM + HOUR-PILLAR PERFORMANCE SENSITIVITY PLAN V1

Status: FROZEN BEFORE REVEAL
Date: 2026-10-06
Target: Chess C7 — 伤官/偏印 six-position counts vs Elo within elite Chess
Role: Post-validation method sensitivity; original C7 remains frozen primary diagnostic.

## Frozen coding
- M0: original six-position main-qi Ten-God counts.
- M1 priority/share/any: six-position exposure-aware counts.
- Day stem excluded from 透干.
- No exposed hidden stem -> fallback to main qi.
- Priority rule: main > middle > residual.
- M2/M3: add Hour stem + Hour branch and marginalize over 12 double-hours.
- Primary hour distribution: uniform 1/12.

## Performance outcome
- Use frozen 2023 FULL and NEW_TARGET cohorts.
- Standardize rating within sex, then pool M/F for the primary C7 replication diagnostic.
- Report sex-stratified correlations descriptively.
- Primary statistic: Spearman rho.

## Nonlinear hour sensitivity
Because correlation is nonlinear:
- report rho using exact per-player expected feature across 12 hours;
- additionally sample one hour independently per player and recompute rho;
- repeat 10,000 times by default;
- report median, mean, 2.5/97.5 percentiles, P(rho>0).

## Sanity targets
Before interpreting sensitivity:
- FULL SG rho approximately +0.006; PY approximately -0.059.
- NEW_TARGET SG approximately +0.031; PY approximately +0.059.
If M0 fails to reproduce these approximately, stop and debug.

## Interpretation
C7 remains a robust negative performance result if correlations remain near zero
across the prespecified exposure rules and hour uncertainty.

A nominal result in one sensitivity rule is not sufficient to revise C7.

If a materially nonzero association of consistent sign appears in both FULL and
independent NEW_TARGET under the same full-chart coding, C7 must be revised.

## Frozen implementation
Script: `run_chess_c7_hiddenstem_hour_performance_sensitivity_v1.py`
SHA-256: `93774e8a71f826d816ab113046a4dee27c95761f67701ec8e1ab21a4a2ebbeba`

No coding rule, cohort, target Ten God, performance metric, or hour treatment may
be changed after first reveal except to correct a documented mechanical bug.
