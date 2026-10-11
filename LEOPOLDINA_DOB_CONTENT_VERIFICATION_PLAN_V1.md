# Leopoldina DOB Source-Content Verification Plan v1

## Position in the hierarchy workflow

This stage is DOB collection/provenance work only. It occurs after the immutable Leopoldina science-core roster freeze and after candidate exact-day P569/source resolution, but before any final DOB acceptance and before any BaZi conversion or inspection.

Primary hierarchy eligibility is restricted to the preregistered Nobel-supported birth-year window:

`1835 <= birth_year <= 1985`

The full 2,888-member Leopoldina roster and all 2,497 candidate exact-day P569 rows remain preserved. The year restriction only prioritizes the primary hierarchy DOB collection workload.

## Current input state

Upstream source resolution has already:

- frozen 2,497 unique-day P569 DOB candidates;
- resolved 224 distinct `stated in` source items;
- reconstructed 4,019 source-specific record URLs;
- retained direct P854 URLs where available;
- written **zero** `final_exact_dob` values.

The source resolver is a locator stage, not DOB acceptance.

## Source policy

The content verifier distinguishes:

- **Tier A candidate**: institutional, academy, university, archival, governmental, or comparable primary/scholarly institutional source;
- **Tier B candidate**: edited biographical/encyclopedic source such as Brockhaus, Britannica, Munzinger, MacTutor, national encyclopedias, professor catalogs, or comparable edited reference works;
- **locator only**: authority/catalog/aggregation systems used to find records but not sufficient independent DOB evidence.

Explicit locator-only examples include GND, BnF authorities, Czech authority records, DNB catalog, WorldCat Entities, SNAC, and Open Library.

Machine source classification is not final source adjudication.

## Content verification

`scripts/leopoldina_dob_content_verify_local_v1.py`:

1. reads the resolved content-source candidate references;
2. restricts to the frozen primary birth-year window;
3. fetches resolved source-record URLs and direct reference URLs with verified TLS;
4. caches each response locally so reruns are resumable;
5. records HTTP/final URL/content type/content SHA256;
6. extracts text from HTML/text/JSON/XML responses;
7. searches for the candidate exact DOB in common numeric and multilingual written-date forms;
8. records a local evidence snippet;
9. flags PDFs for separate verification rather than pretending to parse them;
10. writes machine evidence summaries by member.

A machine text match is **evidence only**. It does not write or accept `final_exact_dob`.

## Acceptance is a later frozen stage

This collection pass does not automatically implement the final acceptance rule. A subsequent, separately frozen adjudication stage will use source tier and source independence.

Planned conservative rule:

- one content-verified Tier A source may be sufficient;
- Tier B requires at least two independent content-verified sources, or Tier B plus an independently verified direct/primary source;
- locator-only sources are never sufficient alone;
- conflicts go to manual review;
- candidate rows with insufficient evidence remain unresolved and proceed to additional source discovery.

## Outputs

`data/leopoldina_dob_content_verify_local_v1/`

- `verification_rows_v1.csv`
- `candidate_content_verification_summary_v1.csv`
- `machine_positive_rows_v1.csv`
- `fetch_or_pdf_review_v1.csv`
- `summary.json`
- rebuildable `cache/` (gitignored)

## Invariants

- `final_exact_dob_written = 0`
- `automatic_acceptance = 0`
- `bazi_variables_computed = 0`

No BaZi conversion is permitted at this stage.
