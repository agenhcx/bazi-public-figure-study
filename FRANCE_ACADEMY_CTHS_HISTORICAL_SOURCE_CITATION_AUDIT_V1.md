# France Academy CTHS historical source-citation audit v1

Collection QA as of 2026-10-18 UTC. This is a **blinded evidence discovery output**, not a historical complete roster, a final membership adjudication, or a DOB freeze.

## Scope and reproducibility

All 562 pre-existing CTHS biography HTML pages were read OFFLINE from their SHA-256-verified immutable source archive. The parser examined their "Sources biographiques" field and captured only compact source-category flags, field SHA-256, person IDs and links, not the long copied source prose. No websites were refetched and no BaZi variables generated.

GitHub successful source audit: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39094153009

- Source pages audited: **562/562** and all individual SHA-256 hashes verified.
- Missing CTHS bibliography field: **1**, not proof the person has no external sources.
- People with a bibliographical reference to *some* Academy historical index or directory: **130** (some cite more than one publication).
- Individual citation categories, which can overlap:
  - 1979 Academy historical index: 1
  - 1989 Academy **member-only** biographical directory: 17
  - 1993 Academy directory of both members **and correspondents**: 114
  - 1994 supplement to original index: 0
  - 2008 members/correspondents directory: 0
- Bibliography category leads also included Academy notices/Comptes rendus (266), institutional academic CV or travaux (207), Archives nationales / Légion d'honneur (46), Wikipedia/Wikidata (44), biographical dictionaries (35), media/newspapers (17), and civil birth record/état civil mentions (3).

**Neither a citation to a volume nor a source-category flag independently validates the specific person's DOB, membership class or election year.** Opening the referenced publication, locating the person's entry and verifying the actual original dates/wording are separate, required steps.

## Historical directory distinctions

- The Académie's **1989 Répertoire biographique des membres** explicitly excludes foreign associates and correspondents and is useful to confirm people belonging to the 1989 full-member snapshot. It does not list all people elected since the 1800s and is not a complete historical denominator.
- The Académie's **1993 Répertoire biographique des membres et membres correspondants** includes corresponding members and is **not by itself** sufficient to admit a person to the primary full-member cohort.
- The official 1979 index covers 1666–1978, its 1994 supplement 1978–1993, and a 2008 directory of members and correspondents is catalogued. These printed sources have not been retrieved and parsed in this workflow. A BnF Gallica link shown for the 1994 supplement is a discovery target, not demonstrated ingestion.

## Exact identity overlap with 160 first-party selected recent electees

A strict normalized complete-name crosswalk (plus source birth year agreement where the latter states a year) finds **3** of the 562 priority CTHS historical people in the selected 160 first-party recent election records:

- Jean-Paul Laumond, CTHS ID 128378, elected 2017.
- Hélène Bouchiat, CTHS ID 128379, elected 2010.
- Yves Couder, CTHS ID 128396, elected 2013.

No source-year contradictions among these three. This does **not** imply the other 559 CTHS entries are not French Academy full members. The two data collection frames are profoundly different: the 562 form a deliberately prioritized historical subset, while the 160 are a selective set of official modern election years.

## Annual election gap audit: never turn missing search hits into zero members

A separate five-row evidence inventory was frozen under data/france_academy_cths_historical_source_citation_audit_v1/modern_missing_election_year_evidence_v1.csv:

| Year | What is corroborated in Academy first-party documents | What remains unresolved |
|---|---|---|
| 2012 | 2013-14 Academy report confirms 2013 and 2014 elected total 27; does not cover 2012 | Ordinary elections in 2012 |
| 2015 | 15 foreign associates elected 2015-11-17, approved in March 2016 | Any distinct ordinary-member session |
| 2016 | 2016 decree/2017 reception concern 2015 foreign associates | Any ordinary-member elections in 2016 |
| 2018 | Official 2018 reception was for the 18 people elected in **2017** | Whether there was a separate 2018 election |
| 2021 | 16 foreign associates were elected during 2021; the 2019–20 ordinary cohort reception occurred in 2021 | Whether there was a separate regular-member election |

Positive evidence for another election category does not prove zero full-member elections in that year. Annual JORF records and historical Academy registers should be systematically checked before labeling an actual "zero election year."

## Outputs

- scripts/france_academy_cths_original_citation_audit_v1.py
- data/france_academy_cths_historical_source_citation_audit_v1/summary.json
- data/france_academy_cths_historical_source_citation_audit_v1/cths_562_cited_source_metadata_v1.csv
- data/france_academy_cths_historical_source_citation_audit_v1/institutional_directory_citation_review_queue_v1.csv (130 people)
- data/france_academy_cths_historical_source_citation_audit_v1/firstparty_election_identity_intersection_v1.csv (3 people)
- data/france_academy_cths_historical_source_citation_audit_v1/firstparty_name_year_conflicts_v1.csv (currently empty)
- data/france_academy_cths_historical_source_citation_audit_v1/modern_missing_election_year_evidence_v1.csv

## Next step

Prioritize those 130 citation-backed CTHS persons for **human-verifiable original directory entry** checks (1989 member-only first, 1993 mixed member/correspondent second). Make a small 10–20-person pilot and freeze first-party acceptance criteria before bulk local collection. Use Windows local with checkpoint, resume and source hashes for any new large scrape. Share only compact summary and unresolved conflicts back into the conversation.

Original 562-person CTHS snapshots and all frozen eligibility parameters remain intact. Study DOBs accepted here: 0; study membership accepted here: 0; BaZi outcomes inspected here: 0.


## 1994 digital supplement: rights record found, API access not yet possible

The French national library catalog at https://catalogue.bnf.fr/ark:/12148/cb35792869s identifies the 133-page *Index biographique de l'Académie des sciences, supplément 1978–1993* (1994), with a Gallica digitization and catalogued **LIBRE DE DROITS** rights flag. The direct official digitized item is https://gallica.bnf.fr/ark:/12148/bd6t5922329w .

BnF official technical documentation describes three programmatic access routes for Gallica:
- OAI bibliographic document metadata: https://gallica.bnf.fr/services/OAIRecord?ark=bd6t5922329w
- IIIF presentation: https://gallica.bnf.fr/iiif/ark:/12148/bd6t5922329w/manifest.json
- OCR text: https://gallica.bnf.fr/ark:/12148/bd6t5922329w.texteBrut

The official BnF API specification and public-catalog information were read. A **bounded three-request Github Action** tested the actual item on 2026-10-18 UTC: all 3 Gallica endpoints returned HTTP **403** from the runner; none yielded original cataloguing XML, source images or digitized OCR text. Logs and status are frozen at data/france_academy_cths_historical_source_citation_audit_v1/gallica_1994_index_access_v1/summary.json, source workflow https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39094555283 .

**Do not infer that the digitized book is empty or unavailable to a normal permitted browser**; this is a crawler/runner access restriction. No retry flood, access-control bypass, or fabricated page text. A Windows-local, manually saved source document could be handled in a separate audited ingest workflow if legitimately obtained. The 1994 source is not counted as read or independently DOB-confirming.

## 130 source-citation leads -> first 20 entry checks

An offline deterministic worklist, independent of BaZi features, was built from the 562 source bibliography fields. Exactly **130** individuals cite at least one listed Academy biographical index or directory. Per-person first-preferred citation source:
- **17** citing the explicitly member-only **1989** directory (higher priority for member-class confirmation);
- **1** citing the **1979** biographical index and not the higher-ranked 1989;
- **112** citing the **1993** mixed member/correspondent repertoire (not sufficient by itself for full-member classification).

Some of the 17 also cite the mixed 1993 source, therefore this *first-preferred* classification is not the same as nonexclusive source mention totals.

The first **20** review targets are 17 from the member-only directory, 1 from 1979, and 2 from the mixed repertoire, with explicit CTHS person IDs, name, source URL, original-bibliography digest, still-unverified birthdate claim, provisional class, and separate research admission flags all zero. All 130 remain available in the full queue.

- Script: scripts/france_academy_historical_directory_entry_review_queue_v1.py
- Full 130: data/france_academy_cths_historical_source_citation_audit_v1/historical_directory_entry_review_v1/directory_entry_review_queue_all130_v1.csv
- First 20: data/france_academy_cths_historical_source_citation_audit_v1/historical_directory_entry_review_v1/first20_directory_entry_checks_v1.csv
- Summary: data/france_academy_cths_historical_source_citation_audit_v1/historical_directory_entry_review_v1/summary.json
- Successful offline workflow: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39094667441

This is a **source-location review queue, not 130 or 20 newly admitted full members and not accepted DOB dates**. Original printed book entries have NOT been inspected or downloaded from this batch. Individual source citations (even 1989 member-only) cannot substitute for actual member entry in the book. Date provenance should be checked only after the original page is secured and identity/status reconciled. Research unblinding remains forbidden.
