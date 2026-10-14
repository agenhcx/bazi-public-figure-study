# Leopoldina Coverage and Missingness Freeze Plan v1

Frozen plan date: 2026-10-14
Upstream DOB closeout tag: `leopoldina-manual-dob-closeout-v1`
Upstream closeout commit: `a91c6e798945d98a52968a128e784c170676bf40`

## Purpose

Freeze descriptive DOB coverage and missingness diagnostics for the Leopoldina
science-core roster before any Leopoldina BaZi variables are computed and before
any hierarchy outcome is inspected.

This step does not reopen person-by-person DOB searching. It consumes only the
already frozen roster and the already frozen DOB adjudication closeout.

## Frozen universes

### Roster universe

All 2,888 official Leopoldina members in Class I, II, or III, elected through
2025. Class IV and post-2025 elections remain excluded under the roster freeze.

### Candidate universe

The 2,407 exact-day P569 candidate records inside the 1835-1985 birthyear
window. This universe is fully partitioned into:

- 724 accepted candidate records;
- 1,681 unresolved candidate records;
- 2 excluded invalid identity/crosswalk records.

Candidate-level acceptance rates condition on entering this candidate universe.
They are not full-roster DOB coverage rates.

### Accepted primary universe

The 778 accepted exact-DOB records inside the 1835-1985 window:

- 724 accepted candidate records;
- 54 accepted official-only records.

The quantity `778 / 2,888` is named the **accepted primary-window inclusion
rate**. It must not be described as an all-years exact-DOB availability rate,
because members without an accepted primary-window record can include:

- unresolved in-window candidates;
- members with no exact-day candidate;
- members whose birthyear may lie outside the primary window.

## Frozen descriptive stratifications

The script reports roster-level inclusion and candidate-level evidence yield by:

1. Leopoldina class;
2. section;
3. deceased-marker status;
4. election era: `<=1900`, `1901-1950`, `1951-2000`, `2001-2025`;
5. election decade;
6. class × election era;
7. candidate birth year and candidate birth decade;
8. accepted birth year and accepted birth decade, as numerator descriptions only;
9. acceptance route;
10. candidate final evidence status.

No cut point will be changed after inspecting BaZi outcomes.

## Member-level missingness states

Every roster member receives exactly one state:

- `accepted_candidate_primary`;
- `accepted_official_only_primary`;
- `accepted_official_after_candidate_exclusion`;
- `accepted_official_over_unresolved_candidate`, if ever observed;
- `unresolved_primary_candidate`;
- `excluded_candidate_without_official_acceptance`, if ever observed;
- `no_primary_candidate_or_official_acceptance`.

The expected closeout decomposition is:

- 724 `accepted_candidate_primary`;
- 52 `accepted_official_only_primary`;
- 2 `accepted_official_after_candidate_exclusion`;
- 1,681 `unresolved_primary_candidate`;
- 429 `no_primary_candidate_or_official_acceptance`.

These expected counts are derived only from the already frozen closeout and are
checked by the script; they do not depend on BaZi features.

## QID provenance guardrail

The member-level file separates identity provenance into three fields:

- `candidate_wikidata_qid`: the QID carried by the frozen candidate row, including
  a wrong-identity/crosswalk QID retained strictly as excluded provenance;
- `accepted_wikidata_qid`: a QID explicitly attached to the accepted record;
- `wikidata_qid`: the safe unified analysis identity.

A candidate QID from `excluded_invalid_identity_or_crosswalk` must never populate
`wikidata_qid`. For the two accepted official records created after candidate
exclusion, the rejected QIDs remain visible only in `candidate_wikidata_qid`, while
`accepted_wikidata_qid` and `wikidata_qid` remain blank until a separately verified
replacement QID is frozen. Across the 778 accepted records, 724 are expected to have
a verified analysis QID and 54 are expected to remain blank.

The script hard-fails if an excluded candidate QID leaks back into the unified
analysis field. This guardrail preserves the identity decisions made in the upstream
manual adjudication closeout.

## Edge audit

The script records, without silently repairing:

- accepted dates outside 1835-1985;
- candidate or accepted year-only age at election outside 15-110;
- versioned DOB overlays;
- excluded candidate records whose official member record was accepted separately.

Age-at-election checks use election year minus birth year and are therefore
coarse diagnostics, not exact ages.

## Guardrails

- `inferential_tests_run = 0`
- `missingness_model_fit = 0`
- `bazi_variables_computed = 0`
- `prior_frozen_inputs_modified = 0`
- `open_ended_person_search_allowed = 0`

No logistic regression, weighting, imputation, complete-case correction, or
BaZi analysis is performed in this freeze. Any such method requires a separate
pre-unblinding analysis amendment after these descriptive outputs are reviewed.

## Canonical inputs

- `data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv`
- `data/leopoldina_roster_freeze_v1.json`
- `data/leopoldina_manual_adjudication_closeout_v1/final/`

The script verifies the roster hash from the roster freeze metadata and verifies
all consumed closeout files against the closeout manifest.

## Canonical command

```powershell
python .\scripts\freeze_leopoldina_coverage_missingness_v1.py --self-test
python .\scripts\freeze_leopoldina_coverage_missingness_v1.py
```

The output directory is:

```text
data/leopoldina_coverage_missingness_freeze_v1/
```

## Freeze decision after review

After the output summary and edge audit are reviewed, commit the deterministic
outputs and create the annotated tag:

```text
leopoldina-coverage-missingness-freeze-v1
```

Only after that tag exists should the project freeze the cross-institution common
birthyear support and the hierarchy comparison covariates.
