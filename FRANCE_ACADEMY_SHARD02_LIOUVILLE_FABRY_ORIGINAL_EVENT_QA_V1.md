# France Académie des sciences: Shard 02, Joseph Liouville 1839 and Charles Fabry 1927 direct original journal scan audit

Research checkpoint: **2026-10-18 UTC**. Public, reproducible first-party source inspection **before** freezing the overall French historical full-member roster. No astrological variables inspected or accepted member/DOB study records changed. Historical Academy membership categories are deliberately separate from nominal/official office elections and correspondent/foreign status.

## A. Prespecified 16-volume shard 02 results

The next fixed source batch was part of the **172-volume, 11-shard plan created BEFORE network requests**: `data/france_academy_unprobed_16_volume_batch_v1/remaining_172_toc_shard_plan_v1.csv`.

Actual checked volumes: **9, 10, 37, 38, 67, 68, 98, 99, 127, 128, 129, 157, 160, 161, 189, 190**. The original printed volumes are published by **Académie des sciences**; the current machine-readable source is a French Wikisource *Table des matières* transcription, **not direct examination of the elected persons' original journal pages**. Every fetched index source has an actual response SHA256, individual event rows are re-parsed from the **same cached source bytes**, and no person-level extra download was required.

### Actual results, not extrapolated

| Source item | Observed count |
|---|---:|
| Unique historical volume TOC subpages checked | **16** |
| Intended Wikisource TOC HTML200 | **12** |
| TOC-only HTTP404, election presence unknown | **4** |
| Source TOCs with an election heading recognized | **10** |
| Candidate event **rows**, not unique full members | **35** |
| Provisional full-like event classes | **17** |
| Correspondent class | 17 |
| Foreign associate class | 1 |
| Unique strict-name candidate matches to existing frozen CTHS priority 562 | **7 events** |

The 17 full-like index-event candidates contain 11 `FULL_SECTION_MEMBER`, 4 `FULL_NONRESIDENT_MEMBER`, and 2 `FULL_ACADEMICIAN_LIBRE`. No 35-person or 17-person cohort has been accepted. The CTHS 562 records are a historically selected *partial* birth/role priority frame, so the other 28 index-event name strings do not establish nonmembership. Grouping by unique people across years and transitions is not yet complete.

**Important historical false-zero risk:** The readable 1853 Tome **37**, 1884 Tome **98**, and 1899 Tome **128** all expose an election heading, but the current parser yielded **0 named election rows**. This is a strong **parser audit priority**, not evidence that no members were elected. Readable 1915 volumes **160** and **161** have no election heading detected and are a separate classification of manual review (not proof of historical zero). The five rows, their original TOC page URLs and source SHA256 hashes are quarantined in `shard02_source_parser_false_zero_review_queue_v1.csv`.

**Cumulative source-only coverage**: previous 72 disjoint checked TOCs plus these 16 = **88 of 211 distinct original half-year volumes checked** (1835–1940), with **63** successful TOC HTML200, **25** TOC-subpage HTTP404, **224** total *index* event candidates across member, correspondent, foreign and occasional administrative-office categories; **123 never-checked** volume TOC endpoints remain. The cumulative 88-row source metadata and per-role summaries are reproducible using `scripts/france_academy_cumulative_88_volume_source_QA_v1.py`; a TOC-specific 404 is not a missing journal and can NEVER be counted as zero historical elections.

Shard evidence: `data/france_academy_remaining_172_toc_batch_v1/shard_02/verified_transcribed_person_event_candidates_v1.csv`, `summary.json`, `person_event_ledger_summary_v1.json`. Successful actual source run https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39127905966 . Independent cumulative offline replay https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39128301796 .

## B. FIRST-PARTY direct scan source evidence: Liouville 1839

**Person**: Joseph Liouville (birthyear 1809 in CTHS; **OUTSIDE** the research birthyear 1835–1985 eligibility frame). Historical source: *Comptes rendus hebdomadaires des séances de l’Académie des sciences*, **Tome 8 (1839), original pages 873–874 and 919**, Wikimedia Commons original scanned DjVu image frames 879, 880 and 925.

These THREE **original printed-page images have actually been opened and read**, not only OCR or Wikisource Table des matières.

- Original p. **873**: Academy election begins to fill astronomy-section vacancy; source explicitly states **51 voting members**.
- Original p. **874**: **Liouville 29, de Pontécoulant 18, Francoeur 2, blank ballots 2**; total 51; Liouville proclaimed elected by absolute majority, Academy election to be submitted to the King for approval.
- Original p. **919**: under `CORRESPONDANCE`, the Minister of Public Education sends a copy of a **royal ordinance confirming Liouville's election** for the astronomy vacancy after Lefrançais-Lalande. Liouville was present and was invited to take his seat among full Academy members.

CTHS records the Academy election date as **3 June 1839** (https://cths.fr/an/savant.php?id=101610), but the visually inspected p873–874 do not repeat that meeting date at their page heads. Historical secondary biography Lutzen/other chronologies date the public confirmation/seating report to the **10 June 1839** meeting. The **separately signed royal ordinance and its signature date have NOT been inspected**; do not equate the reading/report date with signature date. The original journal visibly supports election, royal approval communicated, and taking the seat. Excellent *method positive control*; **not eligible** for this particular restricted birthyear cohort.

## C. FIRST-PARTY direct scan source evidence: Fabry 1927

**Person**: Marie Paul Auguste Charles Fabry, CTHS ID **112133**, candidate DOB **1867-06-11** (CTHS and Le Monde 1946; DOB not accepted in the final cohort yet). Unlike Liouville, he **is within the 1835–1985 birthyear frame**.

Original source: *Comptes rendus*, **Tome 184 (1927), printed pages 1516–1517 and 1609**. These THREE original source scans have been opened and read, via **fr.wikisource.org local DjVu file hosting** (the Commons imageinfo endpoint returns **missing**, but the same publicly indexed volume is present in the local Wikisource file library). This is a source **hosting distinction**, not an absent journal.

- Printed **p1516** (DjVu frame1516): opening of `ÉLECTIONS` for physics-general section vacancy after Daniel Berthelot; **54 participants**.
- Printed **p1517** (frame1517): meeting header **20 June 1927**; Fabry **51 / 54** ballots; Henri Abraham 1, Paul Langevin 1, Georges Sagnac 1. Fabry proclaimed elected and his election to be submitted to President of the Republic for approval. The same page also reports Alexis Carrel's **correspondent election**, a separate category not to be treated as Fabry's new full membership.
- Printed **p1609** (frame1609): meeting header **27 June 1927**; the public-education minister transmits copy of the presidential **decree dated 23 June 1927** approving Fabry's ordinary Academy election for physics-general section. Decree read to the assembly and Fabry invited to take his place among colleagues.

Thus the original contemporary printed journal supports precisely differentiated dates:

`ACADEMY_VOTE = 1927-06-20` → `DECREED_APPROVAL_DATE_AS_REPORTED_BY_ACADEMY = 1927-06-23` → `PUBLIC_READ_AND_SEATING_DATE = 1927-06-27`.

The original independently signed presidential decree document has **not been separately examined**. Nevertheless, its exact approval date is explicitly stated in the Academy's first-party contemporaneous account—stronger than reading only a TOC entry. These are event-level evidence statements, **not** automatic acceptance of a final year-stratified Academy cohort member.

External DOB/source references: CTHS https://www.cths.fr/an/savant.php?id=112133 ; Academy's 1946 memorial reportage in Le Monde https://www.lemonde.fr/archives/article/1946/12/18/academie-des-sciences-l-eloge-de-charles-fabry_3060800_1819218.html .

## D. Methodological implications and reproducibility

The six original scanned pages have public origin URLs and **exact actual JPEG SHA256** archived in `data/france_academy_1839_1927_original_event_QA_v1/six_firstparty_journal_scans_event_stage_review_v1.json`. The actual visual interpretation is a human observation layered AFTER source fetch and checksum, and not an automated algorithm that claims to read an image. Images were in private-to-workflow **14-day GitHub Actions artifacts**, not redistributed as image blobs in the research repository.

The source acquisition was by:
- `scripts/france_academy_1839_1927_original_scan_audit_v1.py`: 1839 original p873+p919; first attempts of 1927 Commons returned a **missing file**.
- `scripts/france_academy_1839_1927_source_supplement_v1.py`: p874 additional Liouville tally plus 1927 local Wikisource **imageinfo** fallback retrieving p1516.
- `scripts/france_academy_generic_original_page_source_v1.py`: reusable source Book→printed page→DjVu frame, Commons→local Wikisource fallback to retrieve Fabry p1517+p1609; accepts bounded user-selected page list, stores only SHA+link metadata and temporary private artifact JPGs.
- `scripts/france_academy_1839_1927_original_event_QA_v1.py`: pure offline source-ledger crosswalk, checks all six visual-review image SHA and page frames against metadata plus analytic cohort frozen gates.

Three major lessons for 1835–1940 systematic historical membership reconstruction:

1. **Index page normally marks the START**, not necessarily entire election ballot. The Liouville tally is on p874 even though index cites p873; Fabry on p1517 although index cites p1516. Always open original page and its continuation for vote/category/dates.
2. **Governmental confirmation and seating are distinct events**; approval might occur on another printed page or even the NEXT half-year volume. Liouville's original journal reports a royal ordinance without printing its signed date; Fabry's original journal expressly prints the decree date and later reading/seating date.
3. **Images may be locally hosted by fr.wikisource.org**, not Commons; a Commons API `missing` response is a hosting signal, NEVER missing first-party historical election evidence.

The next work priority is **NOT** indiscriminately running all 123 remaining unprobed TOCs. First inspect the high-priority false-zero readable index volume trio **37 (1853), 98 (1884), 128 (1899)** and confirm whether heading grammar misses additional candidate events. Once those older historical patterns have robust regressions, continue prespecified Shard03 while retaining original plan, local caching, SHA, firstparty image spot-check and strict "no final study acceptance without institutional census freeze" rule.

As of this checkpoint: historical final denominator completeness NOT established; `accepted_french_full_members=0` for this work, `accepted_DOB=0`, and `bazi_variables_computed=0`. Source-only verifications do NOT unblind or alter the hypotheses of any Nobel/table-tennis/music/chess studies.
