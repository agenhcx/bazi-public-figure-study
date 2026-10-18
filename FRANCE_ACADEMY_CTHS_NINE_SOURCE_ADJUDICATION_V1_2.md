# France Academy CTHS nine-person source adjudication v1_2

Date: 2026-10-17 Pacific local (UTC 2026-10-18). Evidence collection only; no BaZi-feature derivation or study unblinding.

## Input freeze and procedure

The user supplied `summary(20261018-015853).json` and `manual_review_remaining_9_v1_1.csv` from the new Windows offline parser. Its invariant output was 529 existing exact CTHS DOB claims plus 28 first-day ordinals = 557 syntactically unambiguous source claims; two month typos could raise the ceiling to 559. Three cases still have missing/ambiguous birth metadata. Four mixed historical member-type cases remain separate. The exact source-site page hashes remain those in the previously checked 562-page source capture.

This v1_2 adds an **evidence overlay** and **29 source/claim entries**; no frozen CTHS rows are mutated. For all 9 records the `frozen_study_DOB_accepted`, `frozen_study_membership_accepted` and `bazi_variables_computed` fields remain zero.

## Evidence status, not final study membership

| CTHS ID | Person | DOB evidence | France Academy membership evidence | Disposition |
|---|---|---|---|---|
| 2092 | Léopold Escande | 1902-06-01 BnF; 1902-07-01 Toulouse Académie biography; 1902-09-13 Hager article; CTHS says June **or** July | CTHS mentions nonresident 1954 and member 1976, not yet first-party resolved | Hold DOB; original Toulouse civil source required |
| 107677 | François Fontannes | 1839 CTHS only; 1839-09-16 Wikipedia-derived lead | CTHS claims 'Membre 1886', while 1887 historical Academy notes publicly memorialize his 1883 grand prize; original 1886 member election unverified | Hold both; prize ≠ membership |
| 110681 | Paul Santy | CTHS header 1887-04-16 but biography says 1887-04-18; Lyon Academy biographical source and 1970 obituary favor April 16 | Paris Academy **correspondant** only according to Lyon Academy history; full Lyon membership must not be confused with full Paris membership | Provisional exclude from Paris full cohort; verify in Academy original and birth act |
| 112913 | Émile Thellier | 1904-02-11 Academy official historical member/astronomy list; contemporary Le Monde cross-check | First-party Academy 1968-05-06 ordinary election | First-party full election and DOB *source evidence verified* |
| 128379 | Hélène Bouchiat | 1958-05-08 in original 2011 Academy press release (2010 election list, PDF page 4) | First-party Academy confirms 2010-11-30 full-member election | First-party full election and DOB *source evidence verified* |
| 111758 | Anatole Abragam | 1914-12-15 in Collège de France formal institutional biography and independent CEA institutional material | Collège de France / CEA agree French Academy member since 1973; CTHS asserts a discordant 1976 French foreign-member role | DOB source-verified, official historical type needs adjudication |
| 117565 | Manne Siegbahn | CTHS DOB claim only | CTHS: corresponding 1951 and **foreign** free associate 1953 | Provisional foreign-only, not primary full member |
| 117620 | Ralph Wyckoff | CTHS DOB claim only | CTHS: foreign corresponding 1965 and foreign associate 1974 | Provisional foreign-only, not primary full member |
| 125186 | Mikhaïl Gromov | 1943-12-23 in Société Mathématique de France 2012 document and contemporaneous 1997 Le Monde article | First-party Academy profile confirms **foreign 1989-03-20 then full ordinary member 1997-02-03** | First-party full election and DOB *independently corroborated* |

The Academy news document of 2011 is at https://verimag.univ-grenoble-alpes.fr/IMG/pdf/CP_12NvxMembres_Elus15mars2011.pdf ; it is authored by the Académie des sciences but mirrored by a Grenoble university. The name and membership class are explicit. The modern Academy page for Hélène also includes biography information belonging to her mother **Marie-Anne Bouchiat** (including incorrect 1986/1988 identity-specific membership milestones), so **use the contemporaneous Academy original document** rather than cross-person profile text.

The official Academy astronomy document is https://www.academie-sciences.fr/pdf/dossiers/ama/astronomes.pdf (Thellier PDF index 30). This original secondary official compilation itself contains typos on some OTHER people; only Thellier's dated entry and parallel contemporaneous source have been checked here. Do not bulk-auto-accept everything in that PDF without source controls.

The Collège de France individual's profile is https://www.college-de-france.fr/fr/personne/anatole-abragam ; historical 2014 memorial explicitly says French Academy member elected 1973: https://www.college-de-france.fr/fr/agenda/colloque/hommage-anatole-abragam . The apparently contradictory foreign-role label in CTHS remains quarantined for an original Academy directory check. Another institution's foreign membership must not be transferred to France.

### Why Léopold Escande is NOT resolved

BnF https://catalogue.bnf.fr/ark:/12148/cb134750614 has June 1, **but its own source list cites CTHS**, so it is not a fully independent datum. Toulouse Académie biography by Serge Bories https://www.academie-sciences-lettres-toulouse.fr/wp-content/uploads/2021/05/Escande.pdf says July 1. W. H. Hager's professional article https://www.idrotecnicaitaliana.it/wp-content/uploads/2020/04/Hager-LAcqua-n.-1-2003.pdf says September 13 (identical month/day to recorded date of death, 1980-09-13), which may be a confusion of dates but cannot be silently deleted. Need original civil registration for a true adjudication. Do not choose a date by majority vote.

### Why François Fontannes is suspicious

CTHS claims member in 1886 but original Academy 1887 volume merely mentions the 1883 physical-sciences grand prize and commemorates him as a geologist: https://fr.wikisource.org/wiki/Comptes_rendus_de_l%E2%80%99Acad%C3%A9mie_des_sciences/Tome_104%2C_1887/Table_des_mati%C3%A8res . This does not disprove membership; it is a **potential status false positive**, to be resolved via Academy 1886 election records. His 1839-09-16 date is only a Wikipedia-derived candidate pending an independent birth registration.

## Source evidence summary

- 9 reviewed people; 29 person-specific claims recorded with original URLs, issuer/tier hints and conflicting statement notes.
- **4** people have exact DOB claims backed by outside institutions or professional sources (Thellier, Hélène Bouchiat, Abragam, Gromov).
- **3** people have French Academy first-party documentation explicitly establishing ordinary/full-member election (Thellier, Hélène Bouchiat, Gromov).
- Abragam has corroborated 1973 Academy membership from his employing institutions, but his historical formal category conflict requires official Academy-level adjudication.
- Siegbahn and Wyckoff have **foreign-associate-only** descriptions; Santy a **corresponding-only** description. These are provisional exclusions, not official roster omissions.
- Escande and Santy have date conflicts. Escande, Fontannes and Santy have unresolved full-cohort or exact date issues.
- All accepted study DOB/membership flags remain zero pending formal freeze and recorded evidence adjudication policies.

## Source-audited files

- `data/france_academy_cths_nine_source_adjudication_v1_2/person_evidence_triage_v1_2.csv`
- `data/france_academy_cths_nine_source_adjudication_v1_2/source_claim_evidence_ledger_v1_2.csv`
- `scripts/france_academy_cths_nine_source_adjudication_audit_v1_2.py`

### Local quick check

From the Windows project clone root, after merging this branch:

`git pull --ff-only`

`python .\scripts\france_academy_cths_nine_source_adjudication_audit_v1_2.py`

The script uses Python standard library, **zero network**, checks all 9 people against previously frozen 562 source records, and generates compact outputs under gitignored `local_runs/france_academy_cths_nine_source_adjudication_v1_2/`: `summary.json`, `nine_person_source_qc.csv` and `unresolved_status_or_dob_review.csv`.

**Next-stage scripts should be tested on a tiny batch before any Windows-local bulk fetching, with checkpoint, resume and SHA-based provenance. No BaZi outcomes before global freeze.**
