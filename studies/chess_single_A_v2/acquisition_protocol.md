# Chess single-player A v2: acquisition protocol

Prepared: 2026-10-21. Status: acquisition rules ready for commit lock; no expansion
has been collected under this protocol and no predictive model has been fitted.

Initial acquisition-rules/source-probe lock:
`0ce667b3555119f09af8a056988d2d96b05bf0a8`. That commit launches only an official
archive/header probe, not DOB collection. This revision clarifies explicit
calendar checks and the supplementary expanded FULL output before first new DOB
collection. The executing collector commit containing these clarifications is
recorded separately in the acquisition run manifest.

The acquisition lock is the immutable repository commit containing this protocol
and the collector version used for a run. Record that exact commit SHA in the run
manifest before live cohort expansion. An earlier protocol/source-probe commit
may lock these rules while the collector is being implemented; the collector's
later commit must also be recorded. A source availability/header probe is allowed
before collection and must not calculate BaZi associations or model scores.
The modelling plan remains a review draft until implementation and environment
versions are fixed separately. This is not third-party registration or a claim
that previously explored 2013/2023 outcomes were unseen.

## Purpose and fixed scope

The user requested expansion before fitting: collect approximately 1,000 eligible
men from the January-2013 standard-rating snapshot and reconstruct January-2023
NEW after excluding the expanded development pool. This replaces the unexecuted
v1 proposal to train on the existing 501-person development cohort. Preserve all
v1 files and historical frozen cohorts; do not overwrite them.

Only male players and these two snapshots are added in this acquisition. Do not
add women, pool snapshots, switch to peak Elo, change month, or collect more
people in response to a model result. The existing January-2023 FULL501 file may
remain a separately identified supplementary evaluation; it is not a new,
independent or blind replication.

## Historical source population and eligibility

Use the full official active FIDE standard-rating population at each historical
snapshot. Archive identity, snapshot month and column interpretation must be
verified before scanning. Preserve the downloaded archive and its SHA256. A
current rating list, rapid/blitz list or year-of-birth-only input cannot replace
the required source. If the official archive cannot be obtained, stop/checkpoint
and report the blocker rather than substitute a different population.

Rank men by historical standard Elo descending. No GM-title requirement is
introduced. Reuse the audited eligibility definitions in
`chess_north_v2/build_chess_northern_cohorts_v1.py`, the temporal sanity rule in
`chess_north_v3/sanitize_chess_north_v2.py`, and the corresponding modern-ID
adjudication in `chess_2023_cohorts_v1/build_chess_2023_cohorts_v2.py`:

- One unambiguous person identity and one clean day-precision Gregorian DOB.
- DOB year agrees with the official historical FIDE birth year when available.
- DOB is on or before the first day of the historical snapshot month.
- Birthplace is confirmed north: birthplace latitude strictly greater than zero.
  Federation/nationality is not a substitute for birthplace.
- Missing/conflicting DOB, ambiguous identity, south, equator and unknown
  hemisphere are excluded with the reason retained.

Do not invert southern-hemisphere months or add traditional BaZi labels during
acquisition. For new candidates, use the existing Wikidata P1440/person,
day-precision P569 DOB and P19/P625 birthplace resolution rules. Save query/cache
provenance and response status. Requests that fail temporarily are retried or
checkpointed; a transient fetch failure must not silently become a substantive
missing-DOB or unknown-hemisphere exclusion.

Newly queried DOB claims must additionally retain and explicitly check the
Wikidata calendar model. Accept Gregorian dates only; missing/unknown or
non-Gregorian calendar claims are excluded with an audit reason. No implicit
Julian-to-Gregorian conversion is introduced. The older query did not retrieve
calendar-model metadata: reusing a legacy frozen DOB inherits that pipeline's
Gregorian interpretation and must be labeled `legacy_calendar_not_reverified`,
not described as a newly verified calendar check. Do not silently refresh a
legacy record to erase this limitation.

## Frozen annotations and identity

Reuse already frozen eligibility, identity bridge, DOB and hemisphere annotations
with their source filenames and hashes. Preserve previous acceptance/exclusion
decisions rather than opportunistically refreshing them from changed web data.
The historical archive's rating, sex, active flag and birth-year agreement still
need validation for the relevant snapshot. New candidates use the same rules;
no manual exception is introduced because an input or later model result looks
interesting. Conflicting frozen annotations or impossible dates are an audit
failure requiring a documented, outcome-independent amendment before final
cohort lock. They are not silently resolved in favor of eligibility.

Canonical identity is the normalized decimal `identity_bridge_modern_fide_id`
when present, otherwise normalized decimal `fide_id`. Historic 1994 raw IDs must
not be assumed to be modern IDs: retain their already audited bridges. Require
one row per canonical person. Audit identity/DOB consistency across snapshots.

## January-2013 development pool

Scan complete Elo groups in descending order until at least 1,000 eligible men
are reached. Complete the cutoff group and retain every eligible tie. The pool's
actual size can exceed 1,000. Report the cutoff and actual count, and audit how
the original 501-person development cohort is represented. Unexpected loss of a
previously eligible member is an input/audit issue, not a model-driven exclusion.

This is Top1,000 **eligible** men, with eligible cutoff ties, not necessarily the
official ranking's first 1,000 rows. The exact 500/800/1,000 random training
subsets and ranked sensitivity subsets are derived after collection according
to `config.json`; random selection never narrows the pool used for exclusion.

## Reconstructed January-2023 NEW cohort

First form the exclusion union using canonical identities from:

- The entire expanded 2013 development pool, including cutoff ties and members
  absent from any random training subset.
- `chess_north_v3/primary_north_top_1994_M.csv`.
- `chess_north_v3/primary_north_top_1994_F.csv`.
- `chess_north_v3/primary_north_top_2013_M.csv`.
- `chess_north_v3/primary_north_top_2013_F.csv`.

Then scan January-2023 men by complete descending Elo groups, applying the same
eligibility rules and excluding every canonical identity in this union, until
at least 1,000 eligible unseen men are reached. Complete the cutoff group and
retain every eligible unseen tie. Reuse valid frozen 2023 annotations while
recomputing the seen/unseen flag against this enlarged exclusion union. Do not
reuse the old NEW membership as if it remained independent after expansion.

The resulting NEW cohort is common to every prespecified training size and
model family. Development-pool/NEW overlap must be exactly zero. The NEW cohort
is not the actual Top1,000 list: exclusions and missing eligible DOB/birthplace
data can move its cutoff substantially lower. Report its actual range and
selection restrictions. Previously explored 2023 outcomes remain disclosed.

From the same completed candidate audit, also generate expanded 2023 FULL:
Top1,000 eligible men plus eligible cutoff ties before the seen/unseen exclusion.
This is a supplementary diagnostic cohort, not another independent validation.
Record its overlap with development and NEW, and keep it distinct from the
unchanged historical FULL501 file. No additional model-guided scan is allowed.

## Outputs, stopping and audit record

Save source URLs, retrieval timestamps, archive/cache/input hashes, code commit,
row-level candidate order, identity, eligibility and exclusion reasons, legacy
annotation provenance, cutoff Elo, selected canonical IDs and final counts.
Save ID-overlap checks and SHA256 values for every final output in a manifest.
No row is dropped because a later model makes a large error.

An interrupted run may resume from auditable checkpoints using these same rules.
If fewer than 1,000 eligible players can be established, or a source/identity
audit fails, report the failure and retain the checkpoint; do not silently lower
the target, change eligibility, omit tied rows, or label partial data complete.

Acquisition may inspect historical ratings to rank/select candidates and audit
their ranges. It must not fit predictive models, calculate BaZi-outcome
associations, evaluate feature hypotheses, or choose a sample size from results.
After complete acquisition and audits, fix data manifests, training-subset IDs,
analysis code, dependency versions and seeds in the separate analysis lock.
