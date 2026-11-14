# US NAS five-element and conditional-presence extension

This is an exploratory extension after NAS trait disclosure, requested by the user. It is not preregistration of an unseen population. Existing original 18 tests, country 36 diagnostics, and NAS birth-decade 30 trend tests are unchanged. No other country or Nobel subgroup outcomes may be opened.

## Population and counts

Use the same frozen Northern-Hemisphere, non-Nobel NAS samples: S1+S2 strict908; S1+S2+S3 expanded1462. No data corrections, changing eligibility, or all-NAS-inclusive trait aggregates.

Five informative positions are YG, MG, Ybranch, Mbranch, Dbranch. The DayStem is reference only, not a counted position or exposure source; there is no hour. Each person contributes exactly five element units and five TenGod units. Absolute elements are reported in 金木水火土 order. This is explicitly the five-position composition, distinct from historical six-character music analyses that included the DayStem.

M0 uses each branch main qi. M1 chooses one representative per branch: first hidden stem exposed in YG or MG in the frozen main/middle/residual ordering; if none, main qi. It does not count every hidden stem. No weighting or exposure rules change.

## Fixed 42 exploratory tests

- Five absolute-element count endpoints in both M0/M1:10.
- Count endpoints for 偏财,食神,七杀,偏印 in both models:8.
- All12 ordered pairs among those four gods, for both models:24. Presence means count>=1, not exact count or strength.

All42 strict tests form one Holm42 family, using two-sided calendar-centered tails. Expanded repeats the same42 tests and reports Holm42 as source sensitivity, not independent validation. Counts and conditional probabilities have distinct denominators. Positive excess and ratio>1 describe enrichment; direction must accompany the two-sided p-value. No outcome-selected further tests or directions.

## Calendar nulls

For element/god count totals, fix each observed Gregorian birthyear and draw a whole date uniformly among the365/366 dates in that year. Recompute the five-position count. The test unit is the person; 5N slots are not independent observations. DayMaster and pillar dependencies are preserved by the calendar-date vectors.

For P(target present|anchor present), use the observed anchor-positive people as a fixed subgroup. Each such person retains their Gregorian birthyear, and their candidate date is uniform among same-year dates satisfying the same anchor-presence event under the same model. Report observed joint/anchor counts, target and joint marginal descriptions, and the expected conditional probability weighted by the observed anchor subgroup's year composition. Never use the full cohort's year weights, pooled calendar years, independence products, or unconditioned target probabilities as this null.

For both kinds, compute the distribution of the sum of independent person-level counts using deterministic PMF convolution (counts0..5 or conditional Bernoulli). Two-sided p sums all integer totals whose absolute distance from the exact calendar expectation is at least the observed distance, inclusively. Expected values and reflected-tail cutoffs use Fraction arithmetic, PMF probabilities use float64; normalize and verify mean, variance, and total mass. No Monte Carlo p-values or random seed selection.

## Interpretation

FoodGod given SevenKillings tests a necessary component of 食神制杀, not a full structure classification. IndirectResource given SevenKillings tests a necessary component of 杀印相生. IndirectWealth and SevenKillings are co-presence: the generating direction is 财生杀; conditional probability direction does not imply an acting/casual direction. FoodGod with IndirectWealth is the 食神生财 component. Resource with FoodGod can also be reported as component co-presence, without automatically labelling a beneficial structure. No judgments of strength, relative positions, effective control, favorable elements, or causal intelligence from these counts alone. “水主智” motivates the user's hypothesis, not an empirical mechanism supplied by this analysis.

## Freeze and QA

Scope, code, endpoint list, and synthetic QA are committed and remotely verified before computing new NAS element/conditional aggregates. Input/code hashes are checked at execution. Independent audit uses literal chosen-stem encoding, reproduces all table counts/expectations, and verifies preselected p-values using a different convolution strategy. Preserve the previous V4 deliverable snapshot. Code lives in Git; the updated deliverable holds results, notes and receipts.
