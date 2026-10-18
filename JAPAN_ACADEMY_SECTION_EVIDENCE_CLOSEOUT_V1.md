# Japan Academy residual section-evidence closeout v1

Date: 2026-10-17. Scope: Section I/II and subsection evidence for the last 40 postwar ambiguous persons only.

**This closes a bounded *source-discovery/adjudication route*, not the entire Japan Academy roster or exact-DOB study.** It does not alter an already frozen row, compute BaZi outcomes, or claim that Japan academy primary-cohort data and missingness are globally frozen.

## Audited inputs and adjudication

- The previously frozen single-science-degree rule accepted **199** broad Section II cases among 239 ambiguous postwar records. Its frozen 151-check empirical validation had no observed broad-section mismatch. **It does not support any of subsections 4–7**.
- The resulting **40** cases required explicit Tier-A Japan Academy or Tier-B institutional evidence.
- Four cases were directly resolved by later source review: **Hiratsuka Naohide** Section II / subsection 6; **Yoshikawa Itsuji**, **Nanbara Shigeru**, and **Doi Kōchi** Section I.
- The effective residual is **36** cases. **Ōta Hirotarō** has membership-only source evidence, not verified Section I/II or subsection assignment.
- The targeted Tobunken sweep produced 42 hits relating to 9 people, one P1 and no P2. The P1 Yanagita Kunio snippet was a cross-institution semantic false positive: the division pertained to the Japan Art Academy, not Yanagita's Japan Academy membership. Accepted new section labels: zero.
- J-STAGE, non-Academy institutional, historical Academy HTML, and Wayback routes were explored and did not produce a further accepted explicit section assignment by this closeout.
- A subsequent Wikipedia/university cross-check yielded **six Wikipedia subsection leads** with birthdate fields consistent with official source material but no independent Tier-A/Tier-B subsection confirmation. These are discovery leads **only**, not accepted labels.

## Final evidence treatment for this route

1. Keep already verified broad Section II and exact subsections only at the demonstrated level.
2. Do not infer exact subsection from science degree, discipline, job, or even Wiki classification.
3. The 36 residual rows carry `broad_section=unresolved` and `subsection=unresolved` **unless a previously accepted upstream official record already proves a narrower field**; never overwrite upstream accepted facts.
4. Keep unverified candidates, contradictory claims, status as of source date, and provenance in a separate adjudication ledger.
5. Treat inability to retrieve further evidence as **missing data**, not proof of Section I or Section II.
6. No change is made here to Japan roster membership, DOB assertions, final study inclusion, missingness, or the global no-BaZi/unblinding rule.

## Stop condition and reopening

The targeted section-search route is closed to avoid unbounded searching. Reopen individual cases *only* if a new explicit person-specific Academy or recognized institutional source appears; store quoted wording, URL, capture, date, identity tie, and reviewer outcome.

Final study eligibility/section-specific sensitivity analyses must still be derived through the normal frozen roster + DOB + missingness pipeline. Do not interpret this note as its completion.

## Repository references

- `data/japan_academy_broad_section_degree_rule_freeze_v1/summary.json`
- `data/japan_academy_remaining40_explicit_source_policy_freeze_v1/`
- `scripts/adjudicate_closeout_japan_academy_remaining36_tobunken_p1_v1.py`
- `scripts/discover_japan_academy_remaining36_wayback_official_subsections_v1.py`

`bazi_variables_computed=0`.
