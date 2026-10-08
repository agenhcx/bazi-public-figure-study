# Scientist Hierarchy Study — Pre-Unblinding Amendment v1

## Reason for amendment

This amendment is frozen before inspecting any NAS BaZi feature output.

The hierarchy study should remain blinded at the BaZi-variable level until the relevant data-collection cohorts are complete. Collecting NAS first and immediately transforming NAS DOBs into BaZi variables would create an opportunity to see academy-tier patterns before the professor and other academy cohorts are frozen, which could influence later collection or analysis choices.

Therefore the stronger rule below supersedes the narrower NAS-only timing language in the earlier preregistration.

## Global blinding rule

**Do not compute, inspect, summarize, or analyze BaZi variables for any hierarchy-study cohort until all primary data collection for the hierarchy study is frozen.**

The primary hierarchy study is:

- professor cohort;
- academy-member cohort(s), including NAS and the other national academies selected for the study;
- Nobel science cohort.

Roster definition, inclusion/exclusion rules, exact-DOB acquisition, provenance review, and missingness characterization must be frozen for every primary cohort before the first cross-cohort BaZi transformation run.

The parallel Fields Medal analysis is not required to block the hierarchy-study unblinding unless it is later declared part of the same confirmatory family before unblinding.

## Required pre-unblinding freeze

Before any BaZi-variable computation, the repository must contain for every primary cohort:

1. a frozen roster definition and immutable source snapshot or equivalent reproducible source record;
2. a frozen exact-DOB table with source provenance;
3. exact-DOB coverage and missingness diagnostics;
4. documented treatment of unresolved/conflicting DOBs;
5. a cohort-level checksum/hash;
6. a cross-tier analysis preregistration specifying:
   - primary hypotheses;
   - primary BaZi features;
   - cohort/era adjustment or matching;
   - missingness sensitivity analyses;
   - multiple-testing correction;
   - primary and sensitivity populations.

Only after those conditions are met should a single audited transformation pipeline be run across all primary cohorts.

## Treatment of PR #31

PR #31 (`nas-bazi-features-v1`) was started too early and is closed unmerged.

No BaZi feature output or artifact from that premature run is to be inspected, summarized, or used for scientific inference before the global collection freeze. If an Actions artifact exists, it is considered quarantined pre-unblinding material.

After the global freeze, BaZi features should be recomputed fresh from the frozen cohort inputs using the final audited transformation code. The earlier branch may be reused only as implementation code after review; its output must not be treated as the analysis dataset.

## Status at amendment

- NAS exact-DOB collection is frozen at v16.
- NAS: 3,051 science-core members; 2,238 exact DOB; 813 unresolved.
- NAS BaZi outcome frequencies have not been inspected in this protocol sequence.
- `bazi_variables_computed` remains conceptually **not unblinded** for the hierarchy study until the global collection freeze.

## Anti-HARKing rule

Patterns from one cohort must not be viewed and then used to change:
- who is collected in another cohort;
- DOB-source acceptance thresholds;
- cohort era boundaries;
- primary Ten-God hypotheses;
- multiple-testing families;
- matching/weighting strategy.

Any unavoidable data-source correction after global freeze must be versioned, justified from provenance alone, and performed without reference to BaZi outcomes.
