# Leopoldina Science-Core Roster Closeout v1

## Frozen cohort

The first hierarchy-study Leopoldina roster is frozen before any DOB acquisition or BaZi computation.

- Primary cohort: **2,888 members**
- Class I — Mathematics, Natural Sciences and Engineering: **1,131**
- Class II — Life Sciences: **946**
- Class III — Medicine: **811**
- Scientific sections represented: **22**
- Election/admission window: **through 2025**
- 2026 members excluded upstream: **40**
- Rows with deceased marker on the official detail page: **1,527**
- Rows without deceased marker: **1,361**
- DOB lookup performed: **0**
- BaZi variables computed: **0**

Roster CSV SHA256:

`c17e9297c6c3c7945381034bb48ca4e86582ff9c896fcd69ec3d31add354402a`

## Why the collection method changed

The official Leopoldina member directory reports **8,124** members across the complete historical directory, but GET requests containing the site's Solr pagination or Class query parameters are blocked from GitHub Actions by the site's WAF.

The collection therefore uses a reproducible alternative exposed by the same official directory:

1. Read official Class and election-year facets from the landing page.
2. POST the frozen Class and election-year filters.
3. Require every Class × election-year bucket to return exactly the official facet total.
4. Reject any bucket larger than the site's 50-row result cap.
5. Consolidate the resulting official member-detail URLs.
6. Exclude election year 2026.
7. Fetch every frozen detail URL independently and verify Section and Election year.

The class-year inventory reconciled exactly with the official Class facets. Across Classes I-III, there were **2,928** classified members including 2026; removing the **40** members elected in 2026 leaves **2,888** members through 2025.

## Detail-page audit

All 2,888 frozen member URLs were fetched in 16 independent shards.

Final audit:

- HTTP/required-field errors: **0**
- Election-year mismatches: **0**
- Duplicate URLs: **0**
- Section → Class ambiguities: **0**
- Heading-level honorary-member review candidates: **0**

The 22 observed Sections map uniquely to one of Classes I-III.

## Honorary/non-ordinary handling

The cohort-scope freeze requires honorary/non-ordinary categories to be excluded if encountered.

The official member-directory filter interface exposes Class, Section, Election year and Active/Historical status, but no separate honorary-membership category. The frozen Class I-III detail-page cohort produced zero member headings marked honorary. Official biographies for sampled members describe Leopoldina affiliation as **Member, German National Academy of Sciences Leopoldina**.

Therefore no row is removed for honorary/non-ordinary status in v1. If a future official source identifies such a case, it must be treated as a provenance-only roster correction, versioned before hierarchy-study unblinding.

## Reproducibility checkpoints

### URL-universe collection

- Workflow run: **38093754128**
- Consolidated artifact: **11684932133**
- Artifact ZIP SHA256: `a48fe6d9b05a1447b66f1b2f305560f03245fff806895b01f21b21395a1bbf01`
- Primary URL inventory SHA256: `41a57ab664902118dbd16b507cc4f99d181ab44ac874c3a72d0c2b1168cb81c4`
- Class-year bucket audit SHA256: `d678956ba2284e52fb9ebe9e4ebe1ee607efce7198be6a2ac997fe460a54f3b9`

### Detail-page validation

- Workflow run: **38095813825**
- Consolidated artifact: **11685369375**
- Artifact ZIP SHA256: `36458b7781f28a823d806c728f1572fbc70525fa0f27ebec7886755dfb00f3fe`
- Final roster CSV SHA256: `c17e9297c6c3c7945381034bb48ca4e86582ff9c896fcd69ec3d31add354402a`
- Section map SHA256: `aca68d61ccf1118768c372d264ba31d6d5f510ada9627f3dacdfb9d20f4a511c`

## Stop rule

The Leopoldina roster is frozen at **v1**.

The next phase is exact-DOB collection against this immutable roster. Do not change the cohort based on DOB availability. Do not compute or inspect any BaZi variable until all hierarchy-study primary cohorts are frozen under the global pre-unblinding rule.

Exploratory PR #51 is retained as collection-method history and is not the final roster definition.
