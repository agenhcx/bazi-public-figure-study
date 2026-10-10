# NAS Science-Core Exact-DOB Collection Closeout v17

## Final frozen state

- Science-core cohort: **3,051**
- Exact DOB: **2,242 / 3,051 (73.4841%)**
- Unresolved: **809**
- Deceased: **1,361 / 1,361 exact DOB (100%)**
- Living: **881 / 1,690 exact DOB (52.1302%)**
- BaZi variables computed or inspected during collection: **0**

The frozen v17 CSV SHA256 is `a897797d59c25f0fe7f4fcfb61b417338394b577c3380a456faeb8135e0cef29`.

## Post-v16 corrections

Four previously unresolved rows were accepted only after independent non-library provenance review:

1. **Jay Quade — 1955-12-13.** Current NAS profile plus University of Arizona-hosted personal CV; operational deceased flag also corrected using the NAS death date 2025-10-17.
2. **Mark Johnston — 1951-12-20.** University of Colorado School of Medicine-hosted CV.
3. **John M. Tranquada — 1955-10-05.** Brookhaven National Laboratory-hosted professional biographical record.
4. **John E. Dowling — 1935-08-31.** Society for Neuroscience-published autobiography with Harvard identity corroboration.

## New source classes tested after v16

### Institutional official-profile/CV locator pilot

A deterministic pilot of 240 living members (80 known-DOB validation + 160 unresolved) resolved 202 institutional domains but recovered **0 day-level DOBs**. This route was closed rather than expanded to all unresolved rows.

### IdRef

Among the diagnostic targets, 411 Wikidata P269 links were present. **246 IdRef authority records returned successfully**, but they produced **0 day-level exact DOBs** in either validation or unresolved rows. IdRef is therefore closed as a systematic exact-DOB source for this cohort.

### VIAF

VIAF was useful as a locator, not as final evidence:

- 404 unresolved members had VIAF IDs.
- 21 had a full VIAF date.
- 19 passed initial uniqueness/age screening.
- 15 had birth-specific evidence in contributing processed authority records.

However, validation showed that wrong dates can propagate across multiple library authorities. Examples included a wrong date supported by two contributing authority systems and another wrong date supported by three. Therefore neither VIAF nor a count of agreeing library authorities is sufficient for acceptance.

Full frozen-DOB validation:
- Comparable exact dates: **1,709**
- Matches: **1,653**
- Conflicts: **56**
- Overall match rate: **96.7232%**
- Living match rate: **97.9798%**

The 15 birth-supported unresolved VIAF candidates were therefore subjected to targeted non-library source review. Four met the acceptance threshold above; one (George Gloeckler) had a non-library date conflict and was explicitly rejected; ten remain unresolved.

The row-level audit is retained in `data/nas_viaf_independent_source_audit_v1.csv`.

## Stop rule

NAS science-core DOB acquisition is frozen at **v17**. Do not resume broad source mining. Reopen only for a newly identified high-authority correction with independently auditable provenance, and version that correction before any hierarchy outcome analysis.

The hierarchy-wide pre-unblinding rule remains in force. Do not compute, inspect, or summarize BaZi variables for NAS or any other hierarchy-study cohort until all primary cohorts are frozen.
