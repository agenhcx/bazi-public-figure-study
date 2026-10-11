# Leopoldina DOB Content Verification v2

## Purpose

Verify the actual content of the trusted source records discovered in DOB source-discovery v2. This remains a DOB collection/provenance stage only.

## Inputs

Primary input:

`data/leopoldina_dob_source_discovery_v2/trusted_source_candidate_records_v2.csv`

Frozen source policy:

`data/leopoldina_dob_source_policy_v1/trusted_source_registry_v1.csv`

The v2 discovery checkpoint contains 2,407 primary-window candidates, of whom 1,523 have at least one trusted source locator and 884 have none.

## Policy-aware verification

The content verifier now prefers the frozen `policy_tier` supplied by v2 discovery rather than reclassifying source quality from labels.

It also carries through:

- `single_source_sufficient`
- `independence_group`
- `discovery_route`

Machine evidence aggregation counts independent source groups, not merely URLs.

## Cache reuse

The verifier supports `--cache-dir`. v1 and v2 source verification may therefore share the same URL cache safely because cache keys are URL SHA256 values. Successful responses are reused; failed responses are retried.

## Collection-only invariant

A content match remains evidence, not acceptance.

- `final_exact_dob_written = 0`
- `automatic_acceptance = 0`
- `bazi_variables_computed = 0`

Final DOB acceptance will occur only in a later separately frozen adjudication stage.
