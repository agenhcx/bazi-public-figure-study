# Chess BaZi Study — Preregistration v1

## Freeze point

This file is generated **before any chess BaZi calculation or reveal**.
Population construction and DOB auditing were completed first.

## Frozen historical snapshots

### January 1994

Selection before DOB filtering:
- active men: Top 500 classical Elo + all cutoff ties;
- active women: Top 200 classical Elo + all cutoff ties;
- Garry Kasparov and Nigel Short were restored before reranking because their
  omission from the official 1994 FIDE list followed the 1993 FIDE/PCA split.

PRIMARY clean DOB rule:
1. exact Gregorian YYYY-MM-DD required;
2. unresolved DOB excluded;
3. any credible exact-date source conflict is excluded from PRIMARY, even if a
   manual adjudication favors one candidate;
4. previously missing but later non-conflicting exact DOB may be retained;
5. no guessing, majority voting, or post-reveal date adjudication.

Frozen PRIMARY:
- men: **494**
- women: **188**

A separate adjudicated 1994 sensitivity cohort retains resolved source-conflict
cases. It is not primary.

### January 2013

Selection before DOB filtering:
- active men: Top 500 classical Elo + all cutoff ties;
- active women: Top 200 classical Elo + all cutoff ties.

Only pre-reveal exact day-level DOBs are retained.

Frozen PRIMARY:
- men: **492**
- women: **197**

## Primary period comparison

Compare January 1994 (near the midpoint of the traditional 七运 period) with
January 2013 (near the midpoint of 八运). The labels define the predefined
historical-period comparison; they do not establish causality.

## Primary performance endpoint

Primary continuous endpoint:

`elo_z_within_snapshot_sex = (Elo - group mean) / group SD`

Secondary descriptive endpoints:
- raw classical Elo;
- within-snapshot-sex rank percentile;
- explicitly labeled elite-tail sensitivity analyses.

## Pre-reveal hypotheses

### H1 — temporal element-gradient replication
Test the previously generated hypothesis that Metal Day Masters are relatively
more represented earlier and Earth Day Masters relatively more represented later.

### H2 — predefined historical-period distribution
Test whether Day-Master element distribution differs between the frozen 1994
and 2013 chess snapshots.

### H3 — measurable three-pillar exposure
Because exact birth times are not available at useful coverage, PRIMARY does
not label players 伤官格 or 偏印格. Use predefined measurable three-pillar proxies
for 伤官 exposure and 偏印 exposure.

### Negative controls
Retain the previously defined negative controls:
- year-stem 食神 frequency;
- Food-God performance;
- age-12 Food-God / Seven-Killings Dayun enrichment, only if implemented with
  the definition fixed before viewing chess BaZi results.

## Calendar/null comparison
BaZi distributions must be compared against a calendar-matched null rather than
naive uniform 20% five-element expectations.

## Sex
Male and female populations have different selection thresholds. Report sex
separately descriptively; pooled performance uses snapshot × sex standardized
Elo.

## DOB sensitivity
PRIMARY: clean exact-DOB cohort only.
Sensitivity: manually adjudicated 1994 DOB cohort.
Unresolved DOBs are never imputed.

## Elo-threshold sensitivity
Top-N-with-ties is PRIMARY. Fixed thresholds such as Elo >= 2500 are secondary
sensitivity analyses because the rating pool changed between 1994 and 2013.

## Engine-era issue
Engine adoption (including Stockfish and earlier engines) is recognized as a
historical confound but is not used to redefine the 1994/2013 primary windows
after the fact. Any such analysis is secondary/exploratory unless separately
preregistered before BaZi reveal.

## Reveal rule
After this file is committed and tagged:
1. frozen PRIMARY cohort files are immutable;
2. BaZi is calculated once from `exact_dob_frozen`;
3. newly noticed patterns are exploratory;
4. the chess cohort is not repeatedly mined for new confirmatory hypotheses.

## Frozen files
PRIMARY:
- `chess_freeze/primary_clean_top_1994_M.csv`
- `chess_freeze/primary_clean_top_1994_F.csv`
- `chess_freeze/primary_clean_top_2013_M.csv`
- `chess_freeze/primary_clean_top_2013_F.csv`

Sensitivity:
- `chess_freeze/sensitivity_adjudicated_top_1994_M.csv`
- `chess_freeze/sensitivity_adjudicated_top_1994_F.csv`

Provenance:
- `chess_freeze/1994_final_audit_resolved_v1.csv`
- `chess_freeze/chess_cohort_freeze_summary.json`

**No BaZi values are contained in this freeze.**
