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
