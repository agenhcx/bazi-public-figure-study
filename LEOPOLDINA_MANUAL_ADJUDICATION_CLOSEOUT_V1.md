# Leopoldina manual DOB adjudication closeout v1

Frozen: 2026-10-14

This package closes the manual Leopoldina DOB follow-up branch. It is an offline,
versioned overlay. It does **not** rewrite any prior candidate, source-verification,
or official-profile input, and it performs no BaZi calculation.

## Final primary-window counts

- Candidate adjudication universe: 2,407
- Accepted candidate records: 724
- Unresolved candidate records: 1,681
- Excluded invalid identity/crosswalk candidate records: 2
- Accepted official-only records: 54
- Combined accepted exact-DOB records: 778
- Automatic acceptances: 668
- Manual or prior explicit acceptances: 110
- Remaining official/candidate mismatch holds: 0
- Candidate-date correction overlays: 3 total
- Frozen HTTP-403 archive exceptions: 1 (Friedrich Ehrendorfer / ÖAW)

The 2,407 candidate rows are fully partitioned as 724 accepted + 1,681 unresolved
+ 2 excluded invalid candidate records.

## Five official-profile mismatch decisions

1. **Felix Eckstein** — Q15734524 is a different, 1925-born person. Exclude the
   candidate join; accept the Leopoldina medical member record dated 1964-06-20
   without assigning an unverified replacement QID.
2. **Bernd Fleischmann** — exclude the invalid candidate identity/date crosswalk;
   accept the official record dated 1958-06-22 without assigning an unverified QID.
3. **Eicke Latz** — retain 1970-08-11, supported by the official Institute of
   Innate Immunity named-person CV; retain the Leopoldina 1970-07-11 value as a
   source-error provenance record.
4. **Stefanie Ritz-Timme** — apply a versioned overlay from 1962-06-16 to
   1962-06-13 based on the official Leopoldina new-member profile.
5. **Garret A. FitzGerald** — apply a versioned overlay from 1950-01-11 to
   1950-05-11 based on the official Leopoldina new-member profile.

## Archive exception

The ÖAW Friedrich Ehrendorfer obituary was manually reviewed and supports
1927-07-26, but compliant retrieval returned HTTP 403. It remains explicitly
recorded as:

`official_live_page_archive_exception_http_403`

`raw_response_archived` remains `0`; the exception is not misrepresented as a
locally archived response.

## Important outputs

Under `data/leopoldina_manual_adjudication_closeout_v1/final/`:

- `accepted_exact_dob_combined_primary_v1_1.csv` — final accepted primary table
- `candidate_final_dob_adjudication_v1_1.csv` — all 2,407 candidate decisions
- `accepted_candidate_dobs_v1_1.csv`
- `unresolved_candidate_dobs_v1_1.csv`
- `excluded_invalid_candidate_records_v1.csv`
- `official_only_accepted_dobs_v1_1.csv`
- `official_master_mismatch_adjudications_v1.csv`
- `official_master_candidate_mismatch_review_v1_1.csv`
- `candidate_dob_correction_overlay_v1_1.csv`
- `manual_source_policy_categories_v1.csv`
- `manual_source_domain_registry_v1_1.csv`
- `archive_exceptions_v1.csv`
- `manual_followup_missingness_freeze_v1_1.json`
- `final_dob_adjudication_rules_v1_1.json`
- `summary.json`
- `manifest.json`

## Reproduce locally

Run from the project root after extracting the ZIP:

```powershell
python .\scripts\freeze_leopoldina_manual_adjudication_v1.py --self-test
python .\scripts\resolve_leopoldina_official_mismatches_v1.py --self-test
python .\scripts\resolve_leopoldina_official_mismatches_v1.py
```

The closeout resolver is deterministic for all CSV/JSON outputs except the
manifest is also deterministic because no runtime timestamp is written.

## Frozen stop rule

No further open-ended person-by-person searching is permitted for this branch.
A later supplement requires a separately preregistered uniform protocol applied
to the eligible unresolved cohort. “Unresolved” means the frozen evidence
threshold was not met; it does not mean the candidate DOB is false.
