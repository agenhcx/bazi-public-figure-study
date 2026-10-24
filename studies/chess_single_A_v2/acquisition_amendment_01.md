# Acquisition amendment 01: restore the original-sized 2023 NEW target

Recorded: 2026-10-22 (UTC acquisition log). Status: before predictive fitting,
BaZi-outcome association analysis or new external predictive scores.

## Change and reason

Keep the expanded January-2013 development pool at Top1,000 eligible men plus
cutoff ties, the primary Random1000 training subset, the Random500/800
comparisons and all other model/selection definitions. Change only the planned
January-2023 NEW eligible target from **1,000 to 500, with all cutoff ties**.
Every prespecified model and training size still uses this same reconstructed
NEW cohort. The expanded 2023 FULL remains Top1,000 eligible plus ties as a
supplementary diagnostic, distinct from the historical FULL501 file.

The user's instruction was to expand 2013 to 1,000 and rebuild 2023 NEW because
the enlarged development set changes its exclusions. The earlier v2 draft
additionally expanded NEW to 1,000 on the assistant's assumption; the user had
not specifically requested that second expansion. This amendment corrects that
assumption to the original approximately-500 NEW target. It does not rewrite
the earlier acquisition lock or claim the original v2 target was always 500.

## Acquisition and data access before amendment

Initial source/rules lock: `0ce667b3555119f09af8a056988d2d96b05bf0a8`.
Executing collector commit for the interrupted 1,000-NEW attempt:
`779c9c891ca94bb2022c5d0e7642deb786badf62`.
The attempt is retained in
[Actions run 39697928640](https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39697928640)
and checkpoint commit `72cf94268cb438daaf2cf6e4bf0ac1af4ee1d312`.

At interruption, progress recorded:

- 2013: 1,300 candidates scanned; 1,000 eligible development people reached.
- 2023: 31,311 candidates scanned; 1,668 eligible people in total and 797 eligible
  unseen people under the expanded-development/historical-cohort exclusions.
- The 1,000-NEW target had not been reached. A network timeout left an auditable
  checkpoint rather than a complete 1,000-NEW cohort.

These counts describe observed coverage at the checkpoint; they do not establish
that 1,000 eligible NEW people are impossible to obtain. Raw identity, DOB,
hemisphere, historical Elo and eligibility records were available during this
acquisition. No predictive model was fitted, no BaZi-outcome association was
calculated and no new external predictive score was used to choose the target.
Prior 2013/2023 outcome access from older studies remains disclosed as before.

The amendment responds to the original scope and observed acquisition coverage,
not a p-value, model error, interval or desired direction of effect. It is a
documented acquisition-stage change after viewing coverage and raw data, not a
claim of outcome-naive preregistration.

## Applying the corrected target

Preserve the interrupted attempt's caches, candidate audit and visited rows in
the immutable checkpoint commit and its run artifacts; the corrected run need
not duplicate the full 31,311-row audit in its completed output directory. Keep
that provenance explicit rather than conceal records below the corrected cutoff.
Reuse the same valid frozen and newly acquired evidence. Rebuild NEW by
historical Elo descending, excluding
the **entire** expanded 2013 pool and all four old 1994/2013 M/F frozen cohorts,
then retain the first 500 eligible unseen men plus every eligible unseen tie at
the 500th person's rating. Complete boundary-tie verification and all source,
identity/conflict and zero-overlap checks before marking acquisition complete.

Store the executing amended collector commit and explicit `new_target: 500` in
the acquisition manifest/summary. For historical manifests without `new_target`,
the old common `target` retains its original meaning; never reinterpret an old
1,000 target as 500. The subset builder reads the configured NEW target and
checks matching declared targets and fingerprints before use. Training still
requires at least 1,000 distinct development people.

Commit this amendment and corresponding configuration/collector change before
the corrected acquisition is finalized and before fitting. The later analysis
lock must include this amendment, final data/subset hashes and the unchanged
disclosure of prior outcome access. Further changes require another explicit
amendment; there is no model-result-driven expansion or stopping rule.
