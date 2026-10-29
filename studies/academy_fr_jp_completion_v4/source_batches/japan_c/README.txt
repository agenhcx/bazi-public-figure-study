C worker v4 evidence handoff

40 assigned roster members received one query each. The queue produced 8 institutional day claims, 23 calendar-comparable publisher-dictionary day claims, 3 historical era day expressions retained under claim-level calendar holds, 1 month-only institutional claim, 1 year-only institutional claim, and 4 no-new-claim outcomes.

claims.json contains the institutional layer (10 rows), including an explicitly tagged official corporate director-candidate CV for Sasaki. secondary_claims.json contains the edited publisher dictionary layer (26 rows). Full selected dictionary bodies, publisher labels and matching academic careers were read; they are not counted as university verification. Missing day/month fields stay null.

bulk_sendai_claims.json contains all 10 name matches to the existing 482-member roster in the already captured Sendai honorary-citizens PDF. bulk_sendai_inventory.json preserves the complete roster matching inventory, including table-of-contents vs detailed pages. Kumagai is also present in the assigned queue; do not double count. Abe is the only additional person outside the assigned queue, and was already in the 482-row roster. His membership section/scope is not inferred here. Two Sendai early-era claims (Honda and Shiga) remain noncomparable without downgrading existing source-supplied modern dates.

No new actual birth-date conflicts were found. Different death months in a dictionary and source page title errors are not birth conflicts. Year-only parentheses and identical month/day in Western digits are not treated as supplied lunar-to-Gregorian conversions. No date conversion was performed.

Every accepted evidence row has an actual original-byte SHA256, body verification and same-person career support. Failed PDF/body attempts produce no birth claim. Source captures, full text and JPEG/PDF page renders stay under private/ and must not be published. source_capture_log.json is metadata only; request_log.json records 40 queries, body operations, capture failures and the single accidental same-hash redundant Sendai GET.

All evidence rows selected=false, all final cohort acceptance flags false, zero BaZi variables. This handoff does not modify the baseline v3 study or shared repository.

Safe handoff files: claims.json, secondary_claims.json, bulk_sendai_claims.json, bulk_sendai_inventory.json, processed.csv, holds.json, summary.json, request_log.json, source_capture_log.json, observations.json, evidence_verification.json, README.txt and MANIFEST.json. Python scripts are reproducibility helpers and do not contain source full text.
