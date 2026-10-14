# Leopoldina coverage and missingness freeze v1

Frozen: 2026-10-14

Source DOB closeout tag: `leopoldina-manual-dob-closeout-v1`

## Purpose

This layer freezes descriptive coverage and missingness diagnostics before any
Leopoldina BaZi variables are computed or any hierarchy outcome is inspected.
It does not reopen DOB collection and does not alter prior frozen inputs.

## Three distinct universes

1. **Roster universe**: 2,888 official Class I-III members elected through 2025.
2. **Candidate universe**: 2,407 exact-day P569 candidates in the 1835-1985 birthyear window.
3. **Accepted primary universe**: 778 accepted exact DOBs in the same birthyear window.

The full-roster accepted-primary inclusion rate is **26.939%**.
This is not an all-years DOB availability rate. The candidate evidence acceptance
rate is **30.079%** and conditions on
having entered the exact-day candidate universe.

## Frozen counts

- Accepted candidate rows: 724
- Unresolved candidate rows: 1,681
- Excluded invalid identity/crosswalk rows: 2
- Accepted official-only rows: 54
- Automatic acceptances: 668
- Manual or prior explicit acceptances: 110

## Outputs

- `member_level_primary_window_coverage_v1.csv`: one row per frozen roster member
- `coverage_overall_v1.csv`
- `coverage_by_class_v1.csv`
- `coverage_by_section_v1.csv`
- `coverage_by_deceased_status_v1.csv`
- `coverage_by_election_era_v1.csv`
- `coverage_by_election_decade_v1.csv`
- `coverage_by_class_election_era_v1.csv`
- `candidate_acceptance_by_birth_year_v1.csv`
- `candidate_acceptance_by_birth_decade_v1.csv`
- `accepted_primary_by_birth_year_v1.csv`
- `accepted_primary_by_birth_decade_v1.csv`
- `accepted_route_counts_v1.csv`
- `candidate_evidence_status_counts_v1.csv`
- `edge_case_audit_v1.csv`
- `summary.json`
- `manifest.json`

## Guardrails

- No inferential missingness model is fitted in this step.
- No BaZi variables are computed.
- No person-specific search is reopened.
- Unresolved means the frozen evidence threshold was not met; it does not mean the candidate date is false.
- Accepted birth-year tables are numerator descriptions only, because unknown DOBs cannot be assigned to birth-year denominators.
- QIDs from candidates excluded for wrong identity/crosswalk remain only in `candidate_wikidata_qid`; they are never copied into the unified analysis `wikidata_qid`.
