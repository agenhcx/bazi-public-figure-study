# France Académie des sciences — source discovery and roster pilot v1

Date: 2026-10-17. **Pre-unblinding discovery only.** Primary scope is fixed in `ACADEMY_COHORT_SCOPE_FREEZE_V1.md`; this document does not change it.

## Scope

- Institution: Académie des sciences, Institut de France (NOT Académie française, Académie nationale de médecine, or Académie des Inscriptions et Belles-Lettres).
- Primary institutional roster: all verifiable **full members / académiciens / académiciennes**, active and deceased, **elected by 2025**; retain scientific section/division and election date.
- Keep **associés étrangers**, **correspondants**, and other statuses separate; *do not* promote a correspondant to full member without an explicitly documented later full-membership election.
- Historical French membership classes changed by period. Preserve original French labels and transition/election history instead of assuming a one-to-one equivalence for ancienne Académie / pensionnaire / membre libre.
- Study birth-year support: **1835–1985** per previously fixed Nobel support; do not use exact-DOB availability to choose this range. Preserve full historical/master roster outside the analysis range.
- No BaZi features computed before all global cohorts are frozen.

## Source landscape, checked 2026-10-17

| route | address | known support / limitation | handling |
|---|---|---|---|
| Official present/recent | https://www.academie-sciences.fr/les-academiciens | Site says it lists current members and persons deceased in roughly last five years, not all historical members; exposes category, scientific section and elected year on many profiles; usually only birth year | Stage-0 candidate catalog; do not claim complete historical roster |
| Official biographical archive | https://archives.academie-sciences.fr/n/fichier-des-membres-de-l-academie-issu-de-l-index-biographique-par-henri-leridon/n:155 | Archivist page identifies an index-derived member file (2016); direct access currently blocked by site challenge | Primary historical-source target; record access failure; no bypass or fabricated content |
| Institution's historical printed index | `Index biographique des membres et correspondants de l'Académie des Sciences, 1666–1967` (3rd ed. 1968, 574 pp.) | Described in René Taton, *Revue d'histoire des sciences* 23(2), 1970, pp.173–174; includes birth place/date, election dates and person membership status | Seek legal digital or library copy; do not mistake review for complete underlying index |
| Archive biography dossiers | https://www.academie-sciences.fr/nos-archives-le-patrimoine-scientifique-de-lacademie | Official archive holds member biographical files, potentially useful for individual verification | Supplement with exact source provenance |
| French institutional authority records | BnF, university CVs, government and recognized archive sources | May supply day-precision DOB independently | Tier-specific evidence review; no automatic acceptance of Wikipedia/Wikidata-only P569 |

Official website section labels include: Applications des sciences; Biologie humaine et sciences médicales; Biologie intégrative; Biologie moléculaire et cellulaire, génomique; Chimie; Mathématique; Physique; Sciences de l'univers; Sciences mécaniques et informatiques. Preserve historical spelling/year and avoid projecting modern section onto historical members.

## Crucial false-positive safeguards

1. Modern site label **"Membre historique" alone is not proof of past *full* membership** (it denotes a deceased member display class; individual profile/election history must prove full membership).
2. Full member, foreign associate, and correspondent labels must be parsed from the actual individual profile and historically correct election status, not a career-occupation or secondary category.
3. The current site's top-level ~312 "Membres" statistic is **not** a historically complete, verified primary-study cohort count.
4. A birth year alone is `year_only`, not `exact_dob`; date citations must remain provenance-linked.
5. Site availability problems and blocked archives are **not evidence of zero members**.
6. No calendar/BaZi features, frequencies, enrichment analyses or confirmatory tests are performed in discovery.

## Pilot and intended next steps

1. Run `scripts/france_academy_current_roster_pilot_v1.py` to catalog a bounded number of official list pages and profile pages, with raw page hashes and explicit statuses. This is a **pilot**, not a frozen full roster.
2. Audit extraction accuracy and counts of `full`, `foreign_associate`, `correspondant`, `unknown`. Fix parsing before scaling.
3. Secure/parse the official 2016 historical index-derived file or the underlying 1968 print index through an allowable accessible source; reconcile overlap and election classes.
4. Build a full historical roster through 2025; track birth-year eligibility, person IDs, duplicate elections, section/time, member categories.
5. Enrich exact day/month/year DOB from indexed historical profiles, BnF, institutional and archival records. Publish coverage/missingness and conflicts by birth decade, election era, section/status.
6. Freeze the *France cohort only* with source snapshots and SHA-256 once full historical roster + DOB QA passes; later global freeze still blocks unblinding.

Source references:
- https://www.academie-sciences.fr/les-academiciens
- https://archives.academie-sciences.fr/n/fichier-des-membres-de-l-academie-issu-de-l-index-biographique-par-henri-leridon/n:155
- https://www.persee.fr/doc/rhs_0048-7996_1970_num_23_2_3126_t1_0173_0000_1
- https://www.academie-sciences.fr/nos-archives-le-patrimoine-scientifique-de-lacademie

`bazi_variables_computed=0`.
