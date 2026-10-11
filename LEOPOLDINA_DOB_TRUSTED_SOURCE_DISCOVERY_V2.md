# Leopoldina DOB Trusted-Source Discovery v2

## Purpose

Continue DOB collection for the frozen Leopoldina science-core cohort before any conversion or BaZi computation.

The v1 content-verification pass showed that only a minority of the 2,407 primary-window DOB candidates currently have content-level evidence. The dominant remaining task is therefore **source discovery**, not conversion and not outcome analysis.

## Frozen primary window

- Birth-year support: **1835-1985**
- Primary-window Leopoldina DOB candidates: **2,407**
- Frozen candidate source: `data/leopoldina_dob_local_v1/candidate_unique_day_p569_v1.csv`

## v1 content-verification checkpoint

The completed full v1 pass partitioned the 2,407 candidates into:

- 49 original machine-threshold candidates (Tier-A-candidate or >=2 Tier-B-candidate positives)
- 216 one-Tier-B positives
- 169 attempted with no machine exact-date positive
- 125 source candidates not actually attempted because no usable URL was available
- 1,848 with no content-source candidate in the P569-reference resolver

The partition sums to 2,407.

These are collection-status categories only. They are not final DOB acceptance categories.

## Why v2 discovery is different

v1 followed sources explicitly attached to Wikidata P569 claims.

v2 instead uses each already-fixed person QID only as an **identity locator**. Before fetching any new content, a source registry and the allowed external-ID properties are frozen. The script then checks only those pre-whitelisted properties on each exact person QID and constructs the corresponding official/scholarly source-record URLs.

Wikidata is therefore not DOB evidence. It only supplies external IDs pointing to pre-approved target sources.

## Trusted source registry

`data/leopoldina_dob_source_policy_v1/trusted_source_registry_v1.csv`

The registry distinguishes:

- **Tier A**: official academy/member databases, official university professor catalogs, national/institutional archival databases, or comparable institutional biographical records. A content-verified exact DOB may later be sufficient alone, subject to final adjudication.
- **Tier B**: edited scholarly/national biographical dictionaries and encyclopedias. A single Tier B source is not sufficient for final acceptance; at least two independent Tier B sources are planned for the later acceptance stage.

Weak/user-generated/locator-only sources are deliberately excluded from v2 trusted-source discovery. Examples not counted as trusted acceptance sources include Prabook, SNAC, Open Library, authority files, and similar locator/aggregation systems.

## Property whitelist

Each trusted source has an explicit `allowed_properties` list. Only those exact external-ID properties may be used for discovery. This prevents unrelated IDs on the same platform (for example contributor IDs) from being mistaken for person-biography records.

## v2 outputs

`data/leopoldina_dob_source_discovery_v2/`

- `trusted_source_candidate_records_v2.csv`
- `candidate_trusted_source_coverage_v2.csv`
- `source_yield_inventory_v2.csv`
- `summary.json`

The candidate-record file is intentionally shaped so it can be passed into the existing source-content verifier.

## Next stage

After v2 discovery:

1. run source-content verification on the trusted-source v2 records;
2. merge v1 and v2 evidence at the person/source level;
3. continue targeted discovery for candidates still lacking sufficient provenance;
4. freeze final exact DOBs only after the separately frozen acceptance/adjudication rule is satisfied.

## Invariants

- No frozen source DOB is overwritten.
- `final_exact_dob_written = 0`
- `automatic_acceptance = 0`
- `bazi_variables_computed = 0`

No conversion or BaZi inspection is permitted in this stage.
