# Athlete name coding for the publication data

Release date: 2026-10-23.

This is a post-analysis change to how athlete names are displayed in the current chess and table-tennis data files. Athlete name fields use consistent research codes such as `C0001`. Different recorded names for the same linked person use the same code, including records repeated across cohorts and analysis outputs.

The migration preserves record order, cohort membership, dates of birth, recorded sex, performance values, source identifiers, all other scientific variables, and the original analysis results. The accompanying manifest records the original and updated file hashes and the validation counts. Original source-hash manifests continue to describe the original frozen inputs.

The correspondence between original names and research codes is retained privately by the author. It is not included in this release.

## Identification and provenance

This release changes name fields only. Exact birth dates, existing FIDE/ITTF identifiers, Wikidata identifiers, and source links remain where already present. Those fields and earlier repository versions can still identify athletes. This name-coding release should therefore be described as removal of names from the specified current data fields, rather than complete anonymization of the repository.

The historical preregistration tags and commits remain intact. They preserve the original cohorts, source records, and timing of the analysis plans. Collection scripts and historical provenance text may contain original names required for source matching. A workflow that fetches source records or reads the original frozen tags can regenerate original names; apply publication-stage name coding before redistributing such outputs.

## Verification

The validation compares each edited CSV with the original as strings, preserving headers and record order and requiring equality of every cell outside the explicitly listed name columns. It also checks consistent codes across aliases and repeated records, name-based join cardinalities, unchanged aggregate/result artifacts, and the original preregistration tag references.

See `manifest.json` for file-level scope and hashes, and `validation.json` for the recorded checks.
