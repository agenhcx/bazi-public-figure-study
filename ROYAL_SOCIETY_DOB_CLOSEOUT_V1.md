# Royal Society Primary-Cohort DOB Closeout v1

## Final frozen state

- Primary Royal Society Fellow roster: **8,669**
- Past/deceased Fellows: **7,099**
- Current Fellows: **1,570**
- Exact DOB: **4,983 / 8,669 (57.4807%)**
- Unresolved: **3,686**
- Past exact DOB: **4,884 / 7,099 (68.7984%)**
- Current exact DOB: **99 / 1,570 (6.3057%)**
- BaZi variables computed or inspected during collection: **0**

The unified generated crosswalk SHA256 is `f6e382930d5d1ad294c78b4e6ae9132b8ad101b5e3304bc0e05b22e23ff6b698`.

## Provenance harmonization with NAS v17

Earlier draft collection work produced 125 current-Fellow exact-DOB candidates. That intermediate set was not frozen because 43 candidates relied on BnF, GND, or Czech National Library authority records.

The NAS v17 validation demonstrated that multiple library authorities can propagate the same incorrect day-level date. Royal Society therefore adopts the same final rule:

> Library-authority records are locators, not independent confirmation.

The 125-person candidate pool was re-audited before any BaZi computation:

- **82** candidates already had non-library evidence and were retained.
- **43** library-authority-only candidates were re-audited.
- **17** of those 43 were recovered using an independent non-library source that visibly states the same exact date.
- **26** were downgraded to unresolved.
- Final current-Fellow exact DOB: **99**.

The row-level decisions are frozen in `data/royal_society_dob_freeze_v1/royal_society_current_authority_reaudit_v1.csv`.

## Past-Fellow official pass

The past-Fellow pass remains unchanged at **4,884 exact DOBs**. These dates come from Royal Society catalogue structured records after the previously documented field-precedence and conflict adjudication rules. The exact accepted table is frozen at `data/royal_society_past_dob_closeout_v1/accepted_exact_dob_final_v1.csv`.

## Missingness diagnostics

Missingness is strongly non-random.

Past Fellows:
- pre-1900 elections: **54.5793%**
- 1900-1949: **98.8426%**
- 1950-1979: **99.4193%**
- 1980-1999: **99.7701%**
- 2000 onward: effectively **100%** in the past-Fellow catalogue pass

Current Fellows:
- 1950-1979 elections: **14.2857%**
- 1980-1999: **11.8598%**
- 2000-2009: **5.6757%**
- 2010-2019: **4.0179%**
- 2020-2025: **3.1792%**

This pattern is consistent with day-level DOBs becoming much less public for modern living scientists. Downstream hierarchy analysis must therefore treat DOB availability as non-random and retain election-era/current-status sensitivity analyses; complete-case results must not be described as if the observed exact-DOB rows were a random sample.

## Reproducibility checkpoint

Final validation workflow run: **38056983527**

Artifact ID: **11671182149**

Artifact ZIP SHA256: `dc5642a2a9933c3e16fbe1367ae0683ead6fa3c072524ea9d38ae05978a6f46a`

The repository also retains the final current 99-row exact-DOB table, the past 4,884-row exact-DOB table, the authority re-audit, the two missingness tables, the raw 125-person current candidate pool, the 17-person independent recovery whitelist, and the deterministic freeze builder.

## Superseded draft collection branches

Draft PRs **#36, #37, and #38** are retained as collection history only. Their intermediate acceptance logic is superseded wherever it treated a library authority record as independently sufficient evidence. They must not be used as the final Royal Society DOB definition.

## Stop rule

Royal Society DOB acquisition is frozen at **v1**. Do not resume broad source mining. Reopen only for a newly identified high-authority correction with independently auditable provenance, and version that correction before hierarchy outcome analysis.

The hierarchy-wide pre-unblinding rule remains in force. Do not compute, inspect, or summarize BaZi variables for Royal Society or any other hierarchy-study cohort until all primary cohorts are frozen.
