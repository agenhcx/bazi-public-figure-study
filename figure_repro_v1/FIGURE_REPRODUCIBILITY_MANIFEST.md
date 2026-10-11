# Manuscript Figure Reproducibility Manifest — v1

This package is the handoff point for the current main-figure set.

## Current main figures

1. **Figure 1 — Methodological workflow**
   - Code: `make_main_figures_v1.py::figure1`
   - Data: none; schematic encodes the manuscript's frozen methodological framing.
   - Output: `outputs/figure1_methodological_workflow.png`

2. **Figure 2 — Chess Ten-God profile**
   - Data: `data/figure2_deviation_bar_source.csv`
   - Code: `make_main_figures_v1.py::figure2`
   - Three male cohorts: 2013 discovery, 2023 full, 2023 new target.
   - Ratio-scale bars centered at R=1 with approximate sigma guides.

3. **Figure 3 — Hurting-Officer conditional companion structures**
   - Data: `data/figure3_ho_conditional_zscore_sigma_source.csv`
   - Code: `make_main_figures_v1.py::figure3`
   - Displayed directly in Z/sigma units because conditional tests have different null variances.
   - Pathways shown: Direct Resource, Indirect Resource, Any Resource, Seven Killings, Any Wealth, Direct Officer.
   - `Any Major Outlet` is deliberately not in the main panel because the conditional-null expectation is ~0.94–0.95, creating a ceiling/saturation issue.
   - Outlet extension provenance: post-reveal frozen methodological extension; not original preregistered confirmation.

4. **Figure 4 — Table-tennis historical vs modern Ten-God profile**
   - Data: `data/figure4_tt_true_values_with_sigma_source.csv`
   - Code: `make_main_figures_v1.py::figure4`
   - Historical 1950–1984 vs modern 1985–2008.
   - Separate approximate null-sigma guide families.

5. **Figure 5 — Rob-Wealth temporal transfer**
   - Data: `data/figure5_6_tt_chess_window_compare_source.csv`
   - Code: `make_main_figures_v1.py::figure5`
   - Same five complete birth-year windows for table tennis and chess.
   - Main interpretation: broad TT cohort shift with noisy years; prespecified Chess transfer failed.

## Key frozen interpretation rules

- Do not claim proof/disproof of BaZi as a whole.
- M0 is the primary main-qi known-date encoding; M1–M3 are sensitivity models.
- Calendar-conditioned nulls are preferred to naive uniform Ten-God expectations.
- Discovery, validation, holdout, and post-reveal extensions must remain explicitly separated.
- Null and reversal results are retained.
- For traditional configurations, this framework can test **necessary component co-occurrence** before subjective full-configuration adjudication.
- Necessary-component non-enrichment rejects the simple population-level enrichment operationalization; it does not prove that a complete classical configuration is impossible.

## Run

From this folder:

`python make_main_figures_v1.py`

Dependencies:

`pip install numpy pandas matplotlib`

## Portability

If a future ChatGPT conversation loses context, upload this ZIP/package plus the current manuscript/handoff document. The script and bundled CSVs are sufficient to regenerate the five current main figures.
