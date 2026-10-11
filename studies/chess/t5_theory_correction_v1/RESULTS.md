# T5 Theory-Aligned Correction V1 — Results

Status: **post-reveal exploratory correction**. These results do not replace or retroactively redefine the frozen T5/T5G analysis.

GitHub Actions run: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/38099554106  
Artifact ID: 11687194163  
Monte Carlo simulations: 200,000  
Seed: 20261010

## Reproduction check

The reconstructed conditional null closely reproduces the archived 2023_M_NEW_TARGET values:

- T5 observed: 0.317757 vs archived 0.3178 (absolute difference 0.000043)
- T5 null: 0.362365 vs archived 0.3621 (absolute difference 0.000265)
- Geng+HO observed: 0.200000 vs archived 0.2000
- Geng+HO null: 0.326671 vs archived 0.3264 (absolute difference 0.000271)

Reproduction check: **PASS**.

## Cohort results

| Cohort | HO+ N | T5 obs | T5 null | Ratio | p depletion | p enrichment | p2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2013_M_DISCOVERY | 210 | 0.404762 | 0.330639 | 1.2242 | 0.990325 | 0.013800 | 0.027600 |
| 2023_M_FULL | 220 | 0.395455 | 0.350409 | 1.1286 | 0.930345 | 0.090300 | 0.180599 |
| 2023_M_NEW_TARGET | 214 | 0.317757 | 0.362365 | 0.8769 | 0.095885 | 0.926095 | 0.191769 |

The theory-aligned depletion direction is therefore not consistent across cohorts. The 2013 discovery cohort shows significant departure in the opposite (enrichment) direction; 2023_M_FULL also points toward enrichment; only the non-overlapping 2023_M_NEW_TARGET points toward depletion, and its exploratory lower-tail p-value is 0.0959.

## Geng subgroup

| Cohort | Geng+HO N | Obs | Null | Ratio | p depletion | p enrichment | p2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2013_M_DISCOVERY | 30 | 0.466667 | 0.371471 | 1.2563 | 0.931365 | 0.143239 | 0.286479 |
| 2023_M_FULL | 26 | 0.384615 | 0.409956 | 0.9382 | 0.481153 | 0.713991 | 0.962305 |
| 2023_M_NEW_TARGET | 20 | 0.200000 | 0.326671 | 0.6122 | 0.136574 | 0.956240 | 0.273149 |

The Geng subgroup is also heterogeneous across cohorts.

## Geng-exception interaction

Interaction is defined as:

I = (observed_Geng - null_Geng) - (observed_nonGeng - null_nonGeng).

Positive I would support the proposed Geng exception by showing less depletion / more enrichment than non-Geng after subgroup-specific calendar centering.

| Cohort | Interaction I | Z | p positive-exception | p negative | p2 |
|---|---:|---:|---:|---:|---:|
| 2013_M_DISCOVERY | +0.024697 | +0.304 | 0.375683 | 0.639292 | 0.751366 |
| 2023_M_FULL | -0.074426 | -0.893 | 0.815356 | 0.188929 | 0.377858 |
| 2023_M_NEW_TARGET | -0.097265 | -0.975 | 0.834361 | 0.169559 | 0.339118 |

No cohort provides statistical support for a positive Geng-exception interaction. In both 2023 cohorts the point estimate is opposite to the proposed exception.

## Interpretation

The original T5 directional operationalization was misaligned with the classical depletion proposition. After correcting the direction transparently, the existing revealed cohorts do not support a stable Hurting-Officer–Direct-Officer depletion rule. The Geng-specific exception is likewise unsupported.

Because the corrected hypotheses were formulated after the original results were visible, all p-values above are exploratory/descriptive regardless of nominal significance.
