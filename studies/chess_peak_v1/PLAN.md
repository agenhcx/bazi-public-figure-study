# Observed peak Elo collection and Shangguan association

The user changed the outcome from snapshot Elo after inspecting the original A/B results. This is an exploratory extension, not a new blind preregistration. Preserve every original study and result. Predictive model training is paused; complete acquisition and inspect the fixed Shangguan association first.

Use exactly the original 2013 Random1000 and 2023 NEW500. Preserve frozen people, DOBs, six symbols and eligibility. Verify zero overlap in FIDE IDs and linked Wikidata identities. No peak-based recruitment, replacement, exclusion or sample-size choice.

The outcome is the maximum recorded **official published standard rating from July 1971 through the December 2023 list**. Ignore live, rapid, blitz, performance ratings and all 2024 onward lists. Both groups have the same cutoff. Their names describe roster origin, not a real-time forecast from 2013. This observed maximum is not an unknown final career maximum; younger players may improve later.

## Sources and audit

Uniformly prefer the Lichess FIDE-derived history at `https://lichess.org/api/fide/player/FIDE_ID/ratings`; use direct FIDE history when that source is unavailable. Reuse any already verified direct-FIDE cache. Choose sources by availability, never by the larger rating. Lichess integer points encode YYYYMM*10000+rating and compress equal-rating streaks while preserving first/last points and all rating changes. This preserves maxima but not every repeated peak month. Record source provider, compression and incomplete peak-month ties. A frozen snapshot month may be reconstructed only as an explicitly documented piecewise-constant state within the observed series, must equal frozen Elo, and must not be called an observed peak date. Keep unrated transitions intact.

Direct FIDE endpoint: POST `https://ratings.fide.com/a_chart_data.phtml?event=FIDE_ID&period=0`; use only `rating` and `date_2`. Preserve response bytes, URL, method, timestamp and SHA256. Non-null conflicting person IDs, conflicting duplicate months or snapshot disagreement require resolution. Retry unavailable sources with bounded attempts; stop on HTTP429 or cooperative STOP. Serialize Lichess requests. The first production attempt stopped at a rate limit after 60 people; resume those verified records after at least a minute of cooldown, with one worker and at most one request every two seconds. A pilot of Carlsen, Abasov and Karpov had 342 exact overlapping rating points across the two providers.

Some available mirrors have a truncated window. Before association results, a Kiik source check found the mirror began in 2015 while the official chart supplied 2003 onward and exactly matched the frozen 2013 rating. Restore the official AJAX Origin and X-Requested-With headers. Apply the same coverage rule to everyone: if the mirror lacks the frozen snapshot, or begins after April 2003 for a person born before 1985, check direct FIDE history. Select a verified official window by coverage availability, never a larger peak. Preserve both raw sources and the reason, fingerprints and snapshot verification. A present-but-disagreeing snapshot or an identity/data conflict remains fatal. Unresolved required coverage prevents the final dataset and association stage. An official chart that confirms a genuine later start may resolve the coverage check without inventing earlier ratings.

Several direct charts start in April 2003. Supplement historical published lists with OlimpBase's transcriptions:

- `https://www.olimpbase.org/Elo/data/elo1967-2001.zip`, SHA256 `a93c69d1e3218769935aba92db50877a2e9c26cc62d377c1b663f37a786fe89b`.
- `https://www.olimpbase.org/Elo/data/elo2002-2009.zip`, SHA256 `41131d4b573f033ccf8f2df927f820046cfbee305051b83145c2955220d89003`.

Use only official periods July 1971 through April 2003 from those archives, not earlier unofficial lists. Preserve selected source rows, archive/member/line provenance and archive fingerprints. Historical numeric IDs were reused: require the canonical historical person group plus normalized full-name agreement or independent exact-DOB agreement; audit aliases and old-ID bridges explicitly. Do not fuzzy-match ambiguous people. Source DOB discrepancies never replace frozen DOBs. Matching modern ID and normalized full name can support a rating while flagging a source DOB discrepancy. Do not resolve identity from rating magnitude or a model result.

Every one of the 1500 people must have an auditable label at least as high as their frozen snapshot Elo. Unresolved identity or unavailable histories halt preparation; never silently drop people. Record missing historical coverage and archive omissions; no claim of complete unobserved career history.

Historical transcriptions can contain conflicting ratings for one person and published month. Resolve identity first, then retain all candidate ratings and original rows. A peak value is identifiable only if the maximum over other unambiguous months is at least every ambiguous month's upper candidate bound. In that case keep the ambiguous month with no selected rating, record its candidate set and audit that its uncertainty cannot change the peak value. Do not count that month as an observed peak date. If any candidate exceeds the unambiguous peak, or no unambiguous peak exists, halt preparation for independent source resolution. Never choose the larger or smaller conflicting row. Frozen snapshot consistency must still be exact and unambiguous. This source-quality policy was specified before any Shangguan association results were inspected.

## Next analysis

Apply `SHANGGUAN_PLAN.md` separately to the 2013 and 2023 NEW groups after all collection checks pass. Do not pool cohorts to select a favorable result. Freeze that plan and source before reading association results. This stage contains no A/B predictive training, hyperparameter selection or model analysis tag. Further model work needs a later explicit stage.
