# France Académie des sciences: first-party 1856 original facsimiles and shard-01 historical election-source audit

Checkpoint **2026-10-18 UTC**. Historical source/identity verification ONLY. This audit does not modify the frozen CTHS 562 biography sources, the French 1989 bibliography sources, Nobel/other academies' study acceptance rules, or any BaZi features.

## 1. Original 1856 pages: direct scan inspection, not just Wikisource transcription

We resolved the specific *Livre: Comptes rendus hebdomadaires des séances de l'Académie des sciences, Tome 43, 1856.djvu* public original via the Wikisource ProofreadPage book index and Wikimedia Commons DjVu preview API (source metadata and images SHA256 logged).

**Critical pagination:** Original printed page **84** equals **DjVu frame 88**, printed p85 → frame 89, printed p169 → frame 173. Printed-page labels are source edition page numbers, NOT the same as DjVu frame counts. Some Wikisource Page namespace pages are not transcribed and have redlinks; this does not imply their original scanned images are absent.

For archival integrity, four JPEG previews were downloaded as a short-lived GitHub Actions **artifact**, inspected visually, SHA256-verified separately, and not redistributed in the repository. The permanent, reproducible visual evidence and each public Commons source JPEG URL+SHA is at `data/france_academy_1856_commons_original_page_map_v1/four_original_pages_visual_adjudication_v1.json`; original uninspected-image discovery flags remain in `source_preview_metadata_v1.json` for provenance (metadata acquisition predated the human visual review).

### Exact 1856 Hermite event

| Stage | Original printed page and frame | Direct facsimile observation | Evidence |
|---|---|---|---|
| Nomination/election vote | **p84, DjVu frame88** | After the vacancy following M. Binet's death, **48 participating voters**: Hermite 40, Puiseux 4, Serret 3, blank 1; Hermite proclaimed elected by absolute majority, submitted for imperial approval | **Original Academy printed journal directly visually verified** |
| TOC's wrong election page | **p85, frame89** | Actually a plant physiology article by Georges Ville about nitrates. No Hermite ballot on this leaf. The Wikisource TOC's `p85` citation is **off by one**; retain it as source claim but the corrected facsimile leaf is **p84** | Original scan checked; preserve correction overlay |
| Approval report and seating | **p169, frame173** | **Séance du lundi 28 juillet 1856.** Ministry communicated imperial decree confirming the appointment; document read aloud; President invited Hermite to take his seat among colleagues | **Original Academy printed journal directly visually verified** |
| Earlier neighboring leaf | **p83, frame87** | Astronomy and other scientific reports, no ballot content | Negative *page context* only; not a negative Academy membership |

The election date **14 July 1856** is directly stated by external CTHS's historical biography (https://cths.fr/an/savant.php?id=100246) and other historical scientific biographies; **p84 itself does not restate the meeting date**. The scan-based approval/entry-into-seat report is **dated 28 July 1856**. The original separately signed **imperial decree** and its signing date were **not** obtained, so do not invent a legal effective signature date.

The single source event row can now be classified `HISTORICAL_FIRSTPARTY_ACADEMY_ELECTION_VOTE_AND_IMPERIAL_CONFIRMATION_REPORTED`. It can be used as an **event-level QA positive control** to check other indexes/approvals. However, Hermite's independent historical DOB year is **1822**, outside the Nobel-comparison **1835–1985** birth cohort. Accordingly, **Hermite is NOT added to the science hierarchy analytical dataset**, despite excellent source evidence. Final member additions **0**, DOB additions **0**, BaZi calculations **0**.

### First-party source vs derivative distinction

This direct scan review is markedly stronger than the usual Wikisource index transcriptions, but is limited to **one person's four leaves**. It does not establish error rates or legal status for all Academy members. The incorrect `p85` TOC reference is itself a useful counterexample to assuming all printed page locators are exact. The historical journal's reported decree reading and seating are verified; the actual signed decree instrument is not.

## 2. New 16-volume batch (pre-frozen Shard 01) and individual audit

This is the second actual shard from the frozen 172-volume deterministic plan, `remaining_172_toc_shard_plan_v1.csv`, run using `scripts/france_academy_run_remaining_172_toc_batch_v1.py --shard 1 --run`. The individual candidate records were reconstructed from the **same per-volume cached HTML source bytes** and SHA256-checked against the source volume audit, without network per person.

Shard 01 selected 16 previously unprobed volume IDs: **7,8,35,36,64,65,66,95,96,97,125,126,155,156,187,188** (source code's selection order is fixed and may be interleaved).

- **12** Table des matières pages HTTP200; **4** requested TOC subpages HTTP404 (NOT absence of journal/science election).
- **48** historical index event/office rows after a small, audited **1839 false-negative repair**. The first live parse found 47, then review of Tome8/1839 restored `M Owen` (missing period after `M`) for 48.
- Roles in final 48: **17 explicit full-section**, **1 full académicien libre**, **1 contextual full-section vacancy**, **26 correspondents**, **2 foreign associates**, **1 internal-office election**. Exactly **19 full-like SOURCE candidates**; not 19 accepted main members. 
- **2** conservative unique-name matches against frozen CTHS 562 priority biography subset, not verified identities.
- Key 1839 distinction: Boussingault elected `pour la place vacante dans la section d'Économie rurale`, without an explicit `membre` in the same sentence, so classified **FULL_SECTION_MEMBER_CONTEXTUAL_ELECTION**, not automatically full-member accepted.
- Key 1868 distinction: `M. Dumas est élu Secrétaire perpétuel`, an Academy **office election**, not a first membership election.
- `Sir Ernest Rutherford` name precedent (1927 Tome185) remains captured via the existing stable multi-honorific rule and is a **foreign associate**, not regular French academician.

Bounded successful GitHub Action for the corrected Shard01 and publication-image locator: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39126298996 .

Files:
- `data/france_academy_remaining_172_toc_batch_v1/shard_01/verified_transcribed_person_event_candidates_v1.csv`: 48 original journal index source claims, name/class/action/page, per-volume source SHA and frozen study flags.
- `data/france_academy_remaining_172_toc_batch_v1/shard_01/person_event_ledger_summary_v1.json`, `summary.json` and `source_only_shard_checkpoint_v1.json`.
- `scripts/france_academy_1856_scan_locator_v1.py` (book page-index diagnostics); `scripts/france_academy_1856_commons_original_preview_v1.py` (Commons preview with source page-count and mime guards; raw images private artifact only).
- `scripts/france_academy_wikisource_election_rows_v1.py`: contextual 1839 event + plain `M Owen` parser regression, never admitting them.

## 3. Cumulative distinct historical TOC audit: now 72 volumes

All earlier 56 source-checked volumes were retained in a nonoverlapping cumulative audit. The second 16-volume shard adds **zero overlap**. The combined metadata integrity was checked on all 211 official-to-Wikisource source items.

| Historical TOC measure | Reconciled cumulative |
|---|---:|
| Full original journal volumes catalogued for 1835–1940 | **211** |
| Original volume IDs with intended TOC subpage actually attempted | **72** |
| TOC HTML200 successfully read | **51** |
| TOC subpage HTTP404 (unknown election count) | **21** |
| Event/office-like index rows parsed (NOT unique full members) | **189** |
| Never attempted source TOCs remaining | **139** |

Earlier 56 had 141 event rows; new Shard01 has 48; **141+48=189**, including distinct non-full-member classes and offices. The new 72-row de-duplicated source audit is `data/france_academy_remaining_172_toc_batch_v1/cumulative_72_source_checked_unique_volumes_v1.csv`, with a paired `cumulative_72_source_summary_v1.json`. Offline reproducibility gate: `scripts/france_academy_72_source_and_original_image_QA_v1.py`.

A missing TOC index, omitted heading or truncated original scan must **never** be converted to a historical zero election observation. Shard 01 is purposefully spread across decades; it is not a random sample from which to estimate membership rates. The original prespecified 172-target plan is retained as originally written even though later source checks have occurred.

## 4. Next scientific collection and research safeguards

**Next sensible task:** move to Shard02 while sampling two or three printed original election/approval leaf pairs from different historical eras. It is now especially important to preserve both `TOC_printed_page_claim` and `FIRSTPARTY_verified_printed_page` as separate fields, because the Hermite p85→p84 discrepancy is an observed error.

For historical institutional class eligibility, work event by event: appointment/election, government approval notice, actual original event page, original legal decree where available, and any subsequent corresponding/foreign/nonresident-to-regular role transitions. Birth date and birth-year eligibility have distinct provenance and acceptance gates. France still lacks a demonstrably complete 1666–2025 historical ordinary-member denominator; the 211-volume 1835–1940 publication index helps reconstruct part of it, not the entirety.

**All final cohort additions, final DOB acceptance and BaZi feature computation remain zero.** No archived CTHS source changed; no request for restricted membership records; raw original printed source images remain outside the GitHub repository.
