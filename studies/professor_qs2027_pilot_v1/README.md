# Professor QS2027 feasibility pilot v1

Start with [REPORT_zh.md](REPORT_zh.md) for actual results and limitations, or [PLAN.md](PLAN.md) for scope. The study contains nine institutions and eighteen physics/chemistry directory records selected from QS 2027 overall ranks.

The actual saved pilot has 1,490 affiliation records, ninety sampled-record checks, six body-supported day claims, six month claims, two year claims and seventy-six unknowns. These are source-availability observations, not a formally accepted Gregorian-DOB cohort.

- `inputs/{US,UK,CN}/country_pilot.json`: current roster, fixed sample, claims, access failures and metadata revision snapshots.
- `inputs/*/initial_sampling_snapshot.json`: original worker snapshots preserved for audit; UK/CN correction overlays are included separately.
- `results/`: deterministic offline outputs with per-department/country counts and identity/overlap diagnostics.
- `scope_history/initial/`: exact original scope before the uniform search-result-body budget clarification.
- `scripts/`, `tests/`: standard-library-only validator, merger and safeguards.
- `MANIFEST.json`: public package file hashes; no raw sources are included.

Run the single-line commands in [scripts/README.md](scripts/README.md). The workflow only validates saved inputs, with no live source requests. Dataset creation does not reopen academy collection, freeze the final professor cohort or permit hierarchy unblinding.
