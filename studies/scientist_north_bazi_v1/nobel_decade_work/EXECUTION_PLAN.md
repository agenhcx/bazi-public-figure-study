# Nobel birth-decade exploration V1

The user asks whether the revealed Nobel group has birth-decade enrichment and asks which later Nobel birthdays reproduce their year/month/day pillars in2027–2028. This is a new post-reveal exploration, separate from the unchanged original global18. Earlier Nobel aggregate and decade descriptive tables have already been seen. No new decade p-value is computed before the present execution lock.

## Fixed people, dates and endpoints

Use the full-official-roster Nobel selections from frozenV4:621 strict(S1+S2) and627 expanded(+S3), northern hemisphere,1835–1985 births, honors through2025. Legacy Nobel candidates cannot substitute for the full selection. Preserve all source, identity, DOB and hold decisions. Reuse byte-identical calendar_pool.npz and hidden_pool.npz; their hashes and V4 hash are pinned in SCOPE.json. No new BaZi conversion is needed for the decade analysis.

Endpoint order25: ten M0 Ten-God counts in canonical order; ten Day-Master one-hot indicators in canonical stem order; water Day Master; narrow官印共现; narrow伤官配印共现; M1_priority_5偏印 count; M1_priority_5伤官 count. Ten-God and priority counts are one integer count0–5 per person, using the actual within-calendar joint count distribution, not five independent positions. Other endpoints are binary per person. The priority cache must reproduce exact integer counts after division by72. No inferred hour is used in these25 endpoints.

Birth decades are1830,1840,...1980, with the1830bin limited to1835–1839 and last window ending1985. All selected people and all16 bins enter global tests. Plotting/descriptive highlights use only bins with at least20 people in both source groups (1850–1960). Full tables retain every bin, including tiny/empty bins. There are no local-decade p-values or outcome-selected windows.

## Conditional temporal null

For each endpoint/source group, hold the observed whole-group totalK fixed. Each person's candidate count c has the exact histogram probability of that count among all365/366 valid dates in their own Gregorian birthyear. Condition the independent person draws on sum(c)=K. This permits a common exponential enrichment tilt of the calendar PMFs, P_y(c)*lambda^c: lambda cancels conditional onK. For binary endpoints this reduces to cancellation of a common odds multiplier. It distinguishes temporal redistribution from a cohort-wide excess/deficit under this stated nuisance model; it does not assert a causal selection mechanism.

Build birth-decade count polynomials from person-year count PMFs, without probability cutoffs, truncating only coefficients aboveK. Prefix/suffix or balanced products give each bin's exact conditional finite-support marginal. Float64 polynomial masses, means and variances are checked for normalization and support. The main sampler draws conditional bin-count vectors forward/backward while preserving totalK exactly. One person, including their full count, remains the unit behind these distributions.

## Two global tests per endpoint

1. Heterogeneity Q=sum((observed_bin-conditionalE_bin)^2/conditionalVar_bin) over bins with nonzero conditional variance. Calibrate by the conditional sampler, not an asymptotic chi-square distribution. Inclusive tolerance1e-12*max(1,abs(Qobserved)).
2. Linear L=sum(x_bin*count_bin), integer x=(decade-1900)/10. Test two-sided absolute deviation from E(L|K). Compute E(L|K) as an exact rational via integer polynomial count/moment recurrence with calendar-day histogram frequencies. For outcome c, update Cnew[k]+=f_c*Cold[k-c] and Mnew[k]+=f_c*(Mold[k-c]+x*c*Cold[k-c]). Inclusive reflected integer tail cutoffs use the rational expectation, avoiding floating tie decisions. Report raw and conditional-excess weighted-person OLS slopes in percentage points per birth decade, dividing count endpoints by5 for position-share display.

Exactly50 tests comprise one Holm FWER0.05 exploratory family in the strict group. Expanded repeats the same50 as a source-sensitivity reference, not independent replication. Endpoint-specific conditional vectors are reused for Q and L only. R=99999, NumPy PCG64 seed202611160000+1000*zero_based_endpoint_index+100*source_index(strict0,expanded1). Monte Carlo p=(1+inclusive_extreme_count)/(R+1). No adaptive repetitions, endpoint removal, or post-result change of tail/correction.

Degenerate conditional distributions report a nonrejection/not-estimable diagnostic with p1; impossible conditioning totals raise an explicit error. Separate endpoint streams do not imply a joint conditional model across all25 endpoints. Holm validity does not require independence among endpoint p-values.

## Independent audit and delivery

Before execution, remotely commit scope, plan, metadata, code, original references and pure synthetic checks; verify remote bytes and issue a lock receipt. Independent audit reconstructs the year count histograms, bin marginal distributions, all50 source cases' observed/expected statistics, exact linear means/cutoffs and Holm50 without importing main statistical functions. It uses a distinct person-level suffix sampler for10000 strict draws per endpoint, PCG64 seed202611170000+1000*endpoint_index. Both Q/L p-values are compared with the primary Monte Carlo estimates using a fixed tolerance of six combined standard errors plus0.002. These QA p-values never replace main p-values. Toys enumerate generalized counts, impossible totals, binary edges, zero variance and exponential-tilt cancellation.

Report raw bin counts/shares, ordinary own-year calendar expectation, and conditional-on-K expectation separately. Figures preselect M0偏印, M0伤官, water日主 and narrow伤官配印; all other endpoints remain in full tables. No local high point alone is called significant. Save a new complete HTML/JSON/PNG/SVG ZIP and keep the existing Nobel/global18 deliverable unchanged. Code and execution receipts go into the existing Git study.

The separate birthday correspondence is a descriptive calendar lookup, not a statistical test. Search Nobel births on/after1967-08-16, compare all year/month/day pillars with every date in Gregorian2027–2028, and preserve the no-match result. Closest same-day-pillar dates with different month pillars must be labeled nonmatches. DATE_MAPPING_QA.json records the two calendar implementations and the original/nearest-date pillars. The earlier academy list is a different population.
