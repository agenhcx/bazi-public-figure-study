# French Académie des sciences: 17 public BnF authority records and historical source closeout v1

Research checkpoint: **2026-10-18 UTC**. This is a source-only, pre-unblinding review. The original 562 CTHS source biographies and all accepted-study flags remain frozen and unchanged. The historical institution roster is **NOT** complete.

## Input frame and observed results

This is a **deliberately selected list of 17 CTHS biographies whose bibliography points to the French Academy's 1989 member-only biographical directory**. A bibliography reference is not an examination of a person's original directory page, and selection is not random.

Reusable script: `scripts/france_academy_bnf_authority_pilot_v1.py`. Live, bounded source results and Python 3.10/3.13 checks: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39112560757 .

**Observed, not imputed:**
- 17 selected CTHS persons.
- 15 obtained BnF person notices through *previously matched* unique CTHS–Wikidata candidate QIDs and P268 BnF authority identifiers.
- Of the 15 notices: 9 exact day/month/year DOB claims match CTHS; 2 BnF exact-day claims fill empty CTHS date fields; **2 conflict** with CTHS; 2 BnF notices lack an exact birth day. These add to 15.
- The other two people, **Paul Mandel (CTHS 112705)** and **Alexis Moyse (CTHS 112731)**, were not linked by the frozen strict crosswalk; they were researched separately rather than silently dropped.
- BnF bibliography may cite CTHS or matchID, thus apparent cross-source numerical agreement is not automatically independent evidence.

Auditable, compact one-person-per-row evidence ledger: `data/france_academy_bnf_authority_public_pilot_v1/bnf_17_candidate_dob_evidence_ledger_v1.csv`. It gives source ID, exact original and candidate dates, authority URL, flags for CTHS/matchID bibliography dependence, additional sources, and zero study-acceptance fields. The published output is a **provenance overlay**, NOT a copy of BnF catalogue text or raw biographical records.

## Critical conflicting DOB assertions (unresolved)

| CTHS ID | Scientist | Frozen CTHS exact-day claim | BnF exact-day claim | Evidence and follow-up |
|---|---|---|---|---|
| 2067 | Jean Roche | **1901-02-14** | **1901-01-14** | BnF, EPHE, 1961 Le Monde report and matchID/INSEE favor January 14; Collège de France and CTHS state February 14. BnF's source list cites CTHS and matchID. Search original 1901 Sorgues (Vaucluse) birth registration, not a derived genealogy summary. |
| 112935 | Robert de Vernejoul | **1890-03-20** | **1890-03-19** | BnF, original biographical publication by Académie des sciences, lettres et arts de Marseille and contemporary Le Monde 1992 obituary favor March 19. Seek original 1890 Montcaret (Dordogne) birth act to adjudicate rather than substituting a majority-vote DOB. |

First-person public authority notices:
- Jean Roche https://catalogue.bnf.fr/ark:/12148/cb12252855s .
- Robert de Vernejoul https://catalogue.bnf.fr/ark:/12148/cb12021146p .

Other source leads:
- Jean Roche EPHE https://prosopo.ephe.psl.eu/jean-roche specifically cites the *1989* Académie des sciences member-only `Répertoire biographique des membres`, pp. **210–211**, and an original Academy 1963 `Exposé de titres et travaux`. These are **bibliographic locators**, not opened first-party election records.
- Sorgues original vital-register access policy: https://memento.vaucluse.fr/aide-a-la-recherche/genealogie/je-cherche-un-acte-de-bapteme-naissance-mariage-sepulture-deces-ou-divorce . Digitized pre-1922 birth registers, but earchives request returned 403 from this environment; source scan not inspected.
- Robert de Vernejoul Marseille Academy original biographical volume https://www.academie-sla-marseille.fr/medias/files/fauteuil-23-mercier.pdf ; contemporary 1992-10-17 obituary https://www.lemonde.fr/archives/article/1992/10/17/la-mort-de-robert-de-vernejoul_3894097_1819218.html . Dordogne's official digital civil registers portal https://archives.dordogne.fr/archives-numerisees/genealogie/registres-paroissiaux-et-detat-civil ; **original act itself not retrieved**.

Both stay `DOB_CONFLICT_HOLD`; frozen CTHS date fields are NOT edited.

## CTHS missing exact day: two BnF birth-date candidates

- **Jean Dieudonné (112083)**: BnF 1906-07-01; the original French Academy's archival fonds inventory separately states that full date and documented 1965 correspondant -> 1968 ordinary member transition: https://www.academie-sciences.fr/pdf/dossiers/fonds_pdf/11J_Jean_Dieudonne.pdf . This is particularly useful independent official-document evidence, but still no overall France source-cohort freeze.
- **Charles Louis Dubost (112087)**: BnF 1914-10-01, corroborated by historical clinical reportage; do not confuse the cardiac surgeon with a namesake prosecutor born in 1905. Exact original civil registration not inspected.

## BnF unavailable exact day or absent strict crosswalk

- **Jean Piveteau (107885)**: BnF entry https://catalogue.bnf.fr/ark:/12148/cb119199581 lacks full day, CTHS says 1899-09-23. Belgium's Royal Academy institutional biog offers an external full-date source but Belgian Academy membership and French Paris Academy election must not be conflated.
- **Pierre Rouard (112838)**: BnF https://catalogue.bnf.fr/ark:/12148/cb13477284t lacks exact full day, though CTHS says 1908-10-25.
- **Paul Mandel (112705)**: omitted from strict CTHS–Wikidata identity crosswalk but BnF authority https://catalogue.bnf.fr/ark:/12148/cb122742582 claims born **1908-11-14**, and membership French Académie des sciences in **1982**; university/Strasbourg academic biography https://www.recherche.unistra.fr/uploads/media/colloque_mandel_PROGRAMME.pdf also says birth 14 November 1908 in Łódź. Do not infer historical calendar conversion from this without the original record or contemporary institutional evidence.
- **Alexis Moyse (112731)**: omitted from strict crosswalk; a public biographical bibliography at https://escholarship.org/uc/item/46t92266 states **2 October 1912** (`2.X.1912`), consistent with CTHS. A strict BnF person ID is **not** verified. Do not treat this publication as an original birth register.

## Membership status and methodological guardrails

1. BnF is an identity/biographical authority, NOT an Académie des sciences membership/election primary record. A `member in 1982` authority claim is a lead; the exact original election must still be verified.
2. The original French Academy 1989 member-only biographical directory has NOT been opened in this work, and is not a complete 1666–2025 institutional roster. The separate 160 first-party modern elections are a subset and still not a continuous list.
3. "BnF agrees with CTHS" may mean common borrowed source or cross-publication copying. BnF's `Source(s)` field is checked, but absent citations do not *prove* independence.
4. No denominator, acceptance criterion, frozen hypotheses or original CTHS HTML SHA-256 archive changed. The global analysis support birthyears **1835–1985** persists.
5. `final_exact_dob_accepted=0`, `final_academy_membership_accepted=0`, `bazi_variables_computed=0`.

## Next scientific-data collection decision

Prioritize **source identity and original historical member roster/election** over repeated CTHS DOB web scrapes. Good options are first-party Academy biographical entry pages, original 1989 member-only `Répertoire` pp. 210–211 for Roche, and official historical selection registers or the author-index digital 3218-person Leridon master *only if publicly and lawfully accessible*. The source-set is still not sufficient to freeze a French historical denominator. Any new bulk pipeline should first perform a bounded pilot with source hashes, class/election transitions and exact-day date precision, then be run on local Windows when it is stable.

No emails to archives were sent; no blocked-site access control was bypassed.
