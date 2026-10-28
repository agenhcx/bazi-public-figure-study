# Offline pilot merge and validation

`merge_pilot.py` uses Python 3.11+ standard-library modules. It performs no
network requests. Run from the repository root, with one input file per country:

```bash
python studies/professor_qs2027_pilot_v1/scripts/merge_pilot.py --inputs studies/professor_qs2027_pilot_v1/inputs/US/country_pilot.json studies/professor_qs2027_pilot_v1/inputs/UK/country_pilot.json studies/professor_qs2027_pilot_v1/inputs/CN/country_pilot.json --output-dir local_runs/professor_qs2027_pilot_v1
```

The output directory must be new or empty. Tests are offline:

```bash
python -m unittest discover -s studies/professor_qs2027_pilot_v1/tests
```

Inputs retain all 18 department records, including partial or blocked
directories. The protocol requires each department's roster to be frozen before
DOB checking. An optional `dob_check_started_at_utc` is validated between the
freeze and completion timestamps when actually recorded. Without it, the output
explicitly reports `completion_timestamp_only_start_unverified`: completion time
alone cannot establish the start of checking. No missing start is fabricated.
If metadata is corrected after DOB reading, a `prior_sampling_snapshot` must
retain the complete original rows and sampling manifest, a correction reason,
and the actual `corrected_at_utc`. Both hashes and seeded selections are
recomputed; selected identities and order must remain unchanged. The current
manifest timestamp must equal the correction timestamp. Only this validated
original selection supplies the earlier sampling-time boundary. Current row
hashes are explicitly bound at correction time and are not backdated.
Eligibility
for pilot sampling uses explicit faculty-role evidence, with all faculty ranks
permitted; unknown-role records remain in the observed roster but cannot be
sampled without role verification.

Names use NFKC, casefold and collapsed whitespace. Profile URLs lose only the
fragment and surrounding whitespace. A person key is `prof-` plus the first
20 SHA256 hex characters of `country|institution_id|department|normalized_name|profile_url`.
The six sample positions are determined by ascending SHA256 of
`professor-qs2027-pilot-v1|person_key`, using only eligible roster rows. The full
roster hash binds all row fields, sorted by person key, as compact UTF-8 JSON
with `ensure_ascii=False` and `sort_keys=True`. `freeze_roster()` provides this
shared implementation.

The merger validates roster hashes, sample identities and recorded collection
budgets before producing output. The uniform body-confirmation clarification
permits at most one institution-hosted original body opened from the single
bounded search result, recorded as `search_result_body_fetch_attempts` (0–1).
Earlier input records without this field mean zero; they are not assigned an
unobserved request. The one-profile, one-direct-CV and one-query budgets remain
unchanged, with no retries or sample substitutions. The parent scope records
retain the original protocol and date this clarification separately, after some
search snippets had been seen and before the additional body confirmations.
It does not fill blocked departments with
people from other departments. Duplicate department-person keys are rejected;
exact profile reuse and same-institution exact normalized names are flagged as
identity-review candidates without merging people, including within-department
multi-URL records. Counts are affiliation/person-record checks, not guaranteed
independent people. The legacy `cross_department_identity_review_v1.csv` output
also includes these within-department candidates, with an explicit `scope`
column to distinguish them.
The higher-tier overlap status defaults to `not_systematically_checked`.
When a result supplies `observed_higher_tier_overlaps` with a tier, source URL
and factual excerpt/note, the full evidence objects are retained and the
status is `observed_positive_not_exhaustive`. These positive observations do
not imply an exhaustive overlap audit, and absence of a flag is not evidence
of non-membership in an academy or the Nobel cohort. No sample is replaced
because an overlap is found.

DOB precision is **availability**, requiring `body_observed` claims with a
matching source-ledger URL whose status is also `body_observed`. A blocked
source entry alone cannot support a body-observed claim. Snippets
do not contribute. Unknown years remain unknown. Explicit lunar and unstated
calendars remain separate from explicit Gregorian markers; dates are not
converted or imputed. Competing printed dates are flagged and retained in the
input evidence. Formal accepted exact-DOB count remains zero because this
pilot does not perform final source/calendar adjudication.

The existing 1835–1985 birth-year support window is reported from explicit
body-supported year claims; it is not claimed to match the actual Nobel or
academy age distributions. Neither a final professor cohort freeze nor any
cross-tier analysis or BaZi calculation is performed.
