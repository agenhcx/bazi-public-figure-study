# France Académie des sciences — Historical roster and official-election audit v1

Collection checkpoint: 2026-10-17 (America/Los_Angeles); UTC 2026-10-18.

## Frozen research scope

- Institution: Académie des sciences (Paris), full/ordinary members elected through 2025, historical and living; foreign associates and corresponding-only members excluded.
- Analysis support birth years 1835–1985, per the Nobel support freeze. The complete archival roster can extend outside this range.
- Global no-BaZi unblinding remains absolute. Nothing in this note freezes the France primary cohort.

## Source inventory and historical candidate census

- Official present membership page rejected a GitHub Actions HTTP 403 request; an access error, not evidence of zero membership. Its published 300+ figure is modern only and its own note says it does not catalogue pre-2021 deaths.
- Wikidata discovery via P463=Q188771 and P6282 official profile IDs yielded 2,220 distinct person QIDs; 2,199 had a year claim; 1,288 single-year candidates within 1835–1985. None are independently verified full Academy members or certified exact DOBs.
- CTHS society record, https://cths.fr/an/societe.php?id=506&proso=y&soc_liees= : page advertises 2,177 profiles, actual source snapshot has 2,144 unique person profile links. Difference 33 is unresolved and NOT proof of missing full members.
- Source HTML SHA-256: 542001a28878b83ef4acfdb3362e8249b6b10110caccf51ccb2901a45a69f9f1.
- The v1 scraper misinterpreted mixed character encodings and its historical class counts are invalid. The audited v1_1 revision decoded CP1252 and repaired textual mojibake with ftfy; seven real example assertions pass.
- Corrected CTHS role-description CANDIDATES: full-like only 729; corresponding-to-full-like 138; mixed full and foreign 5; corresponding-only 951; foreign-only 166; foreign-corresponding-only 108; unresolved 47. None are class-verified full members.
- Birthyear support 1835–1985 holds for 1,325 CTHS profiles across all classes. This is not the primary study cohort.
- Conservatively joined Wikidata with CTHS by exact normalized name-token multiset and same unique birth year: 970 unique identity leads (608 with a CTHS full-like or transition description), 1,174 unresolved; eight QIDs collided with 16 CTHS people and were quarantined. Date agreement is NOT independent DOB evidence.

## Two-source primary evidence: 2024–2025 election approvals

2024 election (18 people): French presidential approval dated **2025-04-11**, https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000051452889 ; Academy ceremony source https://www.academie-sciences.fr/ceremonie-de-reception-des-nouveaux-membres-elus-en-2024 .

2025 election (18 people): presidential approval dated **2026-03-03**, https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053619394 ; Academy ceremony source https://www.academie-sciences.fr/ceremonie-de-reception-des-nouveaux-membres-elus-en-2025 .

The first-party and government sources name the SAME 18 people for each year. Retain 2024/2025 election years, **not** 2025/2026 ratification or ceremony years. French decree specifies elected "membres" but does not explicitly repeat "membre titulaire" as a per-person category: preserve this wording and note for downstream historical classification.

36 confirmed individual official member-election records entered in the evidence ledger. No exact DOB dates on the decrees. Strict names: 0/36 appear in CTHS profile candidate index and 16/36 in Wikidata; 20 remain without an exact Wiki name match. This is evidence of a recent-directory gap, NOT of nonexistence, and demonstrates that CTHS alone does not cover 2024–2025 adequately.

## DOB biography source collection queue (not inclusion)

The 1835–1985 historical CTHS priority queue has 562 people: 433 full-like role, 125 corresponding-to-full role, four mixed. Four deterministic shards have sizes 144, 130, 146, 142.

The script for source harvest retains person ID, literal profile URL, raw SHA-256 HTML, CTHS birth metadata text, parsed exact ISO candidate, conflicts and source-level missingness by decade. **Parsed CTHS dates are never accepted without verifying cited underlying sources** (CTHS can cite Wikipedia or derived biographies). No full-member class, exact-DOB eligibility, or BaZi variable is admitted by this stage.

## Outstanding work before science hierarchy unblinding

1. Complete and QA the raw CTHS biography capture and checksum archive; review source errors and candidate date coverage. Missingness must remain visible.
2. Independently verify DOB and conflicts against BnF records, academic publications with explicit birth information, university CVs, or official biographical archives. Preserve the exact original evidence, source capture and date precision; distinguish Gregorian/Julian historical calendars if relevant.
3. Obtain the institutional 1989 official member-only biographical directory and 1979 index, or equally reliable first-party historical roster records. The library listings are known but **their full pages have not been downloaded or certified here**.
4. Extend official ratified election lists before 2024, reconcile historical vs recent/deceased and enforce 2025 election cutoff.
5. Freeze France roster, exact DOB ledger, unresolved/conflict list, source coverage/missingness stratification and immutable hashes. Until the global collection freeze, do not compute or look at BaZi outputs.


## Completed 562-person source harvest (run 2026-10-18 UTC)

- All four source-fetch shards finished successfully: source https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39086523604 .
- The original archive job successfully consolidated 562 entries but its git push was rejected as non-fast-forward because other peer-review documentation had advanced the source branch in the meantime. The **reconciliation run** https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39086741592 downloaded the same four original source artifacts, audited all identities/hashes again, and committed them onto the branch head. The one-off recheckpoint workflow was removed after success.
- Original CTHS person webpages: **562/562 fetched successfully**, no fetch errors, no duplicate person IDs.
- **529/562 (94.13%)** CTHS biography assertions were parsed to calendar-valid exact ISO dates. **32** were nonexact/unparsed in the birth metadata and **1** had no birth metadata detected. **Zero** conflicts with the CTHS roster birth year were detected by the parser.
- A SHA-256 digest is attached to each source page. The full raw capture exists as a compressed archival bundle; public release/redistribution of CTHS biographies and site HTML should be checked against the original site's terms/rights before any formal public research-data publication.
- Source archive SHA256: 6258a366f69e120395450420fee8ae2587d586cb5db153937d1ef45267468811.
- Deterministic outputs: data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv, birthdate_parse_coverage_by_birth_decade_v1.csv, and summary.json.
- Importantly **529 is NOT accepted exact DOB coverage**. The 529 dates are CTHS claims, possibly sourced from Wikipedia, subject to individual source and calendar/canonical-identity checks. Verified independent DOBs in this new capture remain **zero**. Confirmed historical membership class in the main sample remains **zero** until formal adjudication. No study outcomes have been computed.
