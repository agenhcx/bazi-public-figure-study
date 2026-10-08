# Academy Cohort Scope Freeze v1

## Purpose

This document freezes the academy-tier collection targets **before any hierarchy-study BaZi outcomes are inspected**.

All primary academy cohorts are collected and frozen independently. They must not be pooled during collection, and no BaZi variables are computed until the global pre-unblinding rule is satisfied.

## Common time rule

For cross-academy comparability, the primary roster window is **elections/admissions through 2025**. 2026 elections are excluded from the first confirmatory freeze.

Where possible, collect the full historical ordinary-member roster through 2025, including deceased members, rather than only the current membership page.

For every institution preserve:
- name;
- membership type/status;
- election/admission year;
- scientific section/class;
- current/deceased status where available;
- institutional/source URL;
- exact DOB provenance;
- unresolved/conflicting DOB status.

No BaZi variables are computed during roster or DOB collection.

## Primary academy cohorts

### United States — National Academy of Sciences (NAS)

Already frozen at v16.

Primary cohort:
- science-core regular Member / Emeritus;
- primary sections 12–16, 21–29, 41–44;
- elections through 2025;
- exclude International Members, Resigned, Rescinded.

Frozen size: 3,051.
Exact DOB: 2,238.
Unresolved exact DOB: 813.

### United Kingdom — Royal Society

Institution: The Royal Society.

Primary cohort:
- Fellows elected through 2025;
- include historical/deceased Fellows where reproducibly recoverable;
- exclude Foreign Members from the primary UK cohort;
- exclude Honorary Fellows and Royal Fellows;
- preserve Applied & Innovation / General / other election-route metadata when available rather than dropping those Fellows.

Foreign Members may be retained as a separate non-primary table for sensitivity or identity cross-checking.

Official starting point:
https://royalsociety.org/fellows-directory/

### Germany — Leopoldina, German National Academy of Sciences

Institution: Nationale Akademie der Wissenschaften Leopoldina.

Primary science-core cohort:
- ordinary members admitted through 2025;
- Classes I–III only:
  - Mathematics, Natural Sciences and Engineering;
  - Life Sciences;
  - Medicine;
- exclude Class IV Humanities, Social and Behavioural Sciences from the primary science comparison;
- exclude honorary/non-ordinary categories if encountered.

Important comparability note:
Leopoldina membership is explicitly international. Do **not** silently reinterpret this as a German-nationality cohort. Preserve country/affiliation information when available and treat Leopoldina as an institution-selected academy cohort.

Official starting point:
https://www.leopoldina.org/en/members/

### Japan — The Japan Academy

Primary science-core cohort:
- ordinary Members elected through 2025;
- **Section II: Pure Sciences and Their Applications only**;
- subsections 4–7:
  - Pure Sciences;
  - Engineering;
  - Agriculture;
  - Medicine / Pharmaceutics / Dentistry;
- exclude Section I Humanities and Social Sciences;
- exclude Honorary Members.

Official starting point:
https://www.japan-acad.go.jp/en/members/

### France — Académie des sciences

Primary cohort:
- Académiciens / full members elected through 2025;
- all scientific sections in the two science divisions;
- include historical/deceased full members where reproducibly recoverable;
- exclude Associés étrangers from the primary France cohort;
- exclude Correspondants from the primary France cohort.

Foreign associates and correspondents may be retained in separate tables but must not be mixed into the primary cohort.

Official starting point:
https://www.academie-sciences.fr/les-academiciens

### China — Chinese Academy of Sciences (CAS)

Institution: 中国科学院学部 / Chinese Academy of Sciences.

Primary China cohort:
- 中国科学院院士 / CAS Academicians elected through 2025;
- all six science/technology divisions;
- include current and deceased Academicians;
- exclude 外籍院士 / Foreign Members from the primary China cohort;
- preserve division and election-year metadata.

Official starting point:
https://www.casad.cas.cn/

China is part of the primary academy collection freeze and therefore blocks hierarchy-study unblinding until the CAS roster/DOB collection is frozen.

## Secondary China engineering cohort

### Chinese Academy of Engineering (CAE)

The Chinese Academy of Engineering is scientifically valuable but should **not** be pooled with CAS because its engineering, applied-science, and medical composition differs materially.

If collected, CAE is a separate secondary academy cohort:
- regular Academicians elected through 2025;
- include deceased Academicians;
- exclude foreign Academicians from the primary CAE table;
- retain department/division metadata.

Official starting point:
https://www.cae.cn/

CAE does **not** block the first hierarchy-study unblinding unless it is promoted to the primary confirmatory family in a later pre-unblinding amendment.

## Analysis guardrails

1. Each academy remains an institution-specific cohort in the frozen data.
2. Do not create a single pooled "academy" sample until heterogeneity by institution, election era, section/class, and DOB coverage has been characterized.
3. Exact-DOB acceptance thresholds must be the same provenance-based standards used for NAS; weaker sources are not accepted merely to equalize coverage.
4. Missingness diagnostics are required separately for every academy.
5. Cross-tier professor → academy → Nobel analysis rules are frozen only after all primary academy cohorts, the Nobel cohort, and the professor cohort are collected.
6. No BaZi feature generation, frequency tables, enrichment tests, or hypothesis inspection before that global freeze.

## Primary academy collection set

The primary academy set for the first hierarchy-study unblinding is therefore:

- US NAS
- UK Royal Society
- Germany Leopoldina
- Japan Academy
- France Académie des sciences
- China CAS

Russia and Sweden remain optional expansion cohorts and are not required to block the first unblinding unless added by a later pre-unblinding amendment.
