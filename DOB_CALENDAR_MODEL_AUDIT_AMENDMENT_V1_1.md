# DOB Calendar-Model Audit Amendment v1.1

## Trigger

The first full audit identified 99 records with a Julian-model P569 claim. Review of those rows exposed two issues that must be corrected before any DOB amendment is considered:

1. The status name `stored_raw_julian_needs_amendment` was too strong. Matching a frozen source date to a Wikidata Julian claim is a **review trigger**, not proof that the frozen source is wrong.
2. Wikidata can encode a non-Julian historical calendar through claim qualifiers even when the time value's `calendarmodel` is Julian. The concrete discovery case is **Anders Celsius (Q81130)**: his 27 November 1701 birth claim carries a Swedish-calendar sourcing circumstance. Sweden used its special Swedish calendar from 1700 to 1712, so applying an ordinary Julian-to-Gregorian offset gives the wrong absolute day.

This amendment was made before any BaZi computation and before changing any frozen DOB.

## Revised rules

- Rename the raw-Julian match state to:
  - `stored_matches_raw_julian_claim_requires_source_adjudication`
- A frozen DOB is never called erroneous from Wikidata calendar metadata alone.
- Parse entity-valued P569 qualifiers. If a claim has sourcing-circumstance qualifier **Swedish calendar (Q1130275)**:
  - classify it as a special-calendar claim;
  - do not silently treat it as ordinary Julian;
  - normalize using the Swedish-calendar rule only for the documented 1700-1712 interval;
  - retain the special-calendar qualifier and normalization method in the exploded audit output.
- Any unsupported special-calendar qualifier is manual-review only.
- Source-level evidence remains decisive. The audit layer may propose a normalized absolute date, but any change to a frozen DOB dataset requires a separately versioned adjudication/amendment.

## Evidence motivating the amendment

- Royal Society records preserve historical civil dates for figures such as Isaac Newton (25 December 1642) and Robert Hooke (18 July 1635).
- Royal Society records Anders Celsius as 27 November 1701.
- Wikidata marks Celsius's date with a Swedish-calendar sourcing circumstance.
- The Swedish calendar was in use from 1700 to 1712 and differed from ordinary Julian dating; 27 November 1701 Swedish corresponds to 7 December 1701 Gregorian, not 8 December.
- Katherine Esau provides a separate caution: NAS's own biographical memoir and member page state 3 April 1898. Therefore a Wikidata Julian calendarmodel alone is not sufficient to rewrite the NAS frozen DOB to 15 April.

## Versioning

The original v1 output remains an audit artifact documenting the discovery. v1.1 supersedes v1 for calendar-model classification. No BaZi variables are computed in either version.
