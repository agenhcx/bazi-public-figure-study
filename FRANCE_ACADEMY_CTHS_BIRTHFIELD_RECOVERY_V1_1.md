# France Academy CTHS birthday-field source QA and recovery v1_1

Pre-unblinding quality-control amendment, 2026-10-17 local / 2026-10-18 UTC.

## Frozen inputs and no-repeat-collection rule

- The original 562-person, SHA256-audited CTHS biography source capture exists on main and is untouched.
- The user-supplied offline integrity report confirmed 562/562 sources, 529 original parseable exact-date CTHS assertions, 33 parser failures, no network requests and no BaZi computations.
- The new Python script (scripts/france_academy_cths_birthfield_recovery_v1_1.py) uses only the frozen CTHS birth metadata CSV; it does not fetch pages, does not modify the original 562 rows, and does not independently accept any exact DOBs.
- Output goes to gitignored local_runs/france_academy_cths_birthfield_recovery_v1_1/.

## All 33 birth-field exceptions diagnosed

| Failure class | People | Action |
|---|---:|---|
| French first-day ordinal 1er | 28 | Recover calendar-valid CTHS date candidates |
| Source month typos avil / févier | 2 | Provisional ISO candidate, manual review |
| Source explicitly gives 1er juin ou juillet 1902 | 1 | Keep ambiguous, never choose a month by guess |
| Birth year only | 1 | Preserve year-only |
| Absent birth field | 1 | Seek other source |
| Total | 33 | |

After repair: 529+28=557 straightforward exact-day *CTHS source claims*, or 559 if both month typos are resolved. The latter are not independently verified. Only three still lack unambiguous day/month in frozen source text.

The 28 first-day assertions are not a reason to assume true births on the first rather than a possible default convention. Retain them in a separately identifiable DOB provenance review queue. No automatic DOB acceptance.

The output delta concerns 33 people; its remaining compact human review queue has 9 distinct people: 2 typo dates, 3 genuinely nonexact/missing birth fields and the 4 historical mixed full-/foreign-class cases.

## Case-level source review and membership guardrail

The additional five-row source-lead CSV is at data/france_academy_cths_birthfield_review_v1_1/external_source_review_leads_v1_1.csv. Each row explicitly sets accepted_exact_dob=0.

- **Paul Santy (CTHS 110681)**: the header says 16 avil 1887, but the same biography's narrative says 18 avril 1887. A specialist historical entry of the Lyon Académie, referring to his original birth registration, and the 1970 contemporary Le Monde obituary support 16 April. More seriously, CTHS calls him a member *corrrespondant* (triple r typo) of the PARIS Académie des sciences. The old lexical parser missed this typo and tagged him a full-like member. The independent Lyon academy biography confirms his Paris membership was corresponding. Preserve an explicit **corresponding-only / primary-full-cohort-exclusion candidate** overlay; official Paris member election record still needs adjudication. Sources:
  - https://cths.fr/an/savant.php?id=110681
  - https://academie-sbla-lyon.fr/DictionnaireHistorique/entree/19
  - https://www.lemonde.fr/archives/article/1970/01/22/mort-du-professeur-santy-l-un-des-maitres-de-l-ecole-de-cardiologie-lyonnaise_2652731_1819218.html
- **Émile Thellier (112913)**: CTHS writes 11 févier 1904, while a May 8 1968 contemporaneous Academy election article supplies 11 février 1904. Keep independent-source candidate and await policy-grade adjudication.
  - https://www.lemonde.fr/archives/article/1968/05/08/election-de-m-thellier_2502786_1819218.html
- **Léopold Escande (2092)**: CTHS clearly says 1er juin *ou* juillet 1902. Wikidata attributes June 1 to France's death-persons file but the original primary record has not been checked. Keep unresolved pending source.
  - https://cths.fr/an/savant.php?id=2092
  - https://www.wikidata.org/wiki/Q68800731
- **François Fontannes (107677)**: CTHS says birth year 1839, while Wikipedia-derived material claims September 16. Keep unresolved pending Lyon original civil source.
  - https://cths.fr/an/savant.php?id=107677
- **Hélène Bouchiat (128379)**: CTHS birth metadata missing, official Academy 2010/11 CV states only 1958. A separate Academy electee news reprint asserts May 8, 1958, but original day-level primary corroboration remains pending. Avoid conflating her with Marie-Anne Bouchiat.
  - https://www.academie-sciences.fr/pdf/membre/BouchiatH_extrait2011.pdf
  - https://www.mypharma-editions.com/neuf-nouveaux-membres-elus-a-lacademie-des-sciences

## Local operation

From the Windows project's existing root, after this branch is merged into main, run these single-line PowerShell commands:

    git pull --ff-only

    python .\scripts\france_academy_cths_birthfield_recovery_v1_1.py

The script uses the Python standard library only and produces:
- summary.json
- birthfield_parser_delta_33_v1_1.csv
- manual_review_remaining_9_v1_1.csv

No repeat network fetch or all-person logs are needed. Report only the small summary/review files if discussing results.

**No primary member roster freeze, zero independently accepted DOBs, no BaZi unblinding.**
