# Chess Hurting-Officer Outlet Extension V1

**Status:** FREEZE BEFORE FIRST RUN  
**Role:** Post-reveal methodological extension; not part of the original T1–T5 preregistered family.

## Purpose
Test necessary component co-occurrence for traditional Hurting-Officer structures without subjective 身强/身弱, 用神, 喜忌, or full 格局 adjudication.

## Cohorts
- Primary: `2023_M_NEW_TARGET`
- Consistency/descriptive: `2013_M_DISCOVERY`, `2023_M_FULL`

## Primary model
M0 five informative known-date positions, main qi: Year Stem, Year-Branch main qi, Month Stem, Month-Branch main qi, Day-Branch main qi. Day Stem is reference-only.

## Conditioning
Observed analysis is restricted to players with Hurting Officer present under M0. Null sampling holds Gregorian birth year fixed and samples uniformly from dates in that same year that also contain Hurting Officer under M0.

## E1 — Hurting Officer + Any Wealth
`Any Wealth = Direct Wealth OR Indirect Wealth`  
Directional prediction: `R_conditional > 1`.

## E2 — Hurting Officer + Any Major Outlet
`Any Major Outlet = Any Resource OR Any Wealth OR Seven Killings`  
Directional prediction: `R_conditional > 1`.

Direct Officer is excluded from E2 because 伤官见官 is not treated here as a generic positive outlet.

## Multiplicity
E1 and E2 form one two-test directional family. Report raw one-sided enrichment p-values and Holm2-adjusted p-values. Direct/Indirect Wealth decomposition is descriptive only.

## Sanity requirement
Before interpreting E1/E2, reconstruct the frozen T1–T5 M0 conditional ratios within ±0.03. If this fails, stop and debug.

## Monte Carlo
- simulations: 50,000
- seed: 20261010
- PRNG: NumPy `default_rng`

## Guardrails
These are necessary-component tests, not complete classical 格局 classifications. A null/depletion result can reject the simple enrichment operationalization but does not prove that a complete classical structure is impossible.
