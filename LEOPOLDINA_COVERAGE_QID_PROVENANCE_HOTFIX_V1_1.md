# Leopoldina coverage QID-provenance hotfix v1.1

Date: 2026-10-14

## Problem found during pre-freeze review

The first coverage-output candidate correctly classified Bernd Fleischmann and
Felix Eckstein as `accepted_official_after_candidate_exclusion`, but the
member-level builder filled its generic `wikidata_qid` field from the excluded
candidate whenever the official accepted record had no QID.

That reintroduced the two explicitly rejected identity/crosswalk QIDs into a
field that downstream analysis could mistake for the accepted identity. Counts,
DOBs, coverage rates, route tables, missingness states, and edge-audit rows were
not affected.

## Fix

The corrected builder writes three separate fields:

- `candidate_wikidata_qid` — preserves candidate provenance, including rejected QIDs;
- `accepted_wikidata_qid` — QID explicitly carried by the accepted record;
- `wikidata_qid` — safe unified analysis identity.

For an excluded candidate, the generic analysis QID is never inherited from the
candidate. The corrected expected rows are:

```text
bernd-fleischmann: candidate_wikidata_qid=Q61748241, accepted_wikidata_qid="", wikidata_qid=""
felix-eckstein:    candidate_wikidata_qid=Q15734524, accepted_wikidata_qid="", wikidata_qid=""
```

The script now hard-fails on any excluded-candidate QID leak and freezes these
additional invariants:

```text
accepted_primary_rows_with_verified_wikidata_qid = 724
accepted_primary_rows_without_verified_wikidata_qid = 54
excluded_candidate_qids_preserved_only_in_candidate_wikidata_qid = 2
excluded_candidate_qid_leaks_into_analysis_wikidata_qid = 0
```

## Scope

This is a provenance-only pre-freeze correction. It does not change:

- the 2,888-member roster;
- the 2,407 candidate partition;
- the 778 accepted exact DOBs;
- any accepted DOB value;
- any coverage or missingness rate;
- any prior frozen upstream file;
- any BaZi variable.

Delete or overwrite the first generated coverage-output directory, rerun the
corrected deterministic script, and review the new summary before committing the
coverage freeze.
