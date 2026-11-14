# Targeted DayMaster birth-decade exploration

The user asks whether CAS Xin DayMaster and NAS Water DayMaster are enriched in particular birth decades. Their overall frequencies and existing decade summaries have already been seen. This is a post-reveal exploratory extension, not a retroactive confirmatory preregistration. Existing original18, country36, level40/42 and decade30 results are preserved without replacement. No Nobel or new other-institution outcomes or pooled China/West tests are computed.

## Fixed targets, samples and raw descriptions

Target order is CAS_xin (CAS, DayStem index7) then NAS_water (NAS, indices8/9 combined). Frozen V4 North non-Nobel institution selections and analysisDOB are unchanged. Strict/expanded sizes are821/904 forCAS and908/1462 forNAS. Each person contributes one binary DayMaster event, not five element units. Shared-source people retain their originalDOB; expanded contains strict and is not independent validation. CAS26 stays parked.

Use the original byte-identical55152-date calendar pool. For each person's Gregorian birthyear y, let s_y be event-positive calendar days and D_y all365/366 valid dates, p_y=s_y/D_y. No new BaZi conversion. Verify raw16-decade N, event counts and calendar expectations against existing saved reports.

All16 bins1830,1840,...1980 remain in tables, with original window1835–1985 (firstbinpartial1835–1839). The count/E/share descriptions remain unconditional-year-calendar descriptions. Empty bins have0 counts and undefined shares.

## Question: concentrated in an era beyond the overall excess?

Preserve the observed total event count K in each complete target/source cohort. Under the null, generate independent person-level Bernoulli events with year-specific p_y, then condition on exactly K events. This is equivalent to allowing one cohort-wide enrichment odds multiplier relative to calendar; that nuisance multiplier cancels when conditioned onK. It tests temporal redistribution of the observed Xin/Water people, rather than retesting whether the entire cohort is above10%/20%.

For each decade d, form the finite marginal count PMF B_d(k) from its individual calendarBernoulli terms. Prefix/suffix polynomial products give the conditional margins P(X_d=k | totalK). Normalize finite weights using float64, retain the full count support contributing to totalK, and verify mass/moments. Exact conditional draws are forward-back samples from these PMFs, using remaining-totalK at each decade. The MC must not use a uniform permutation that ignores p_y or an ordinary chi-square asymptotic distribution.

## Nineteen fixed tests

Local windows use the already established both-sourceN>=20 rule, selected from metadata:CAS1890..1960 inclusive (8bins),NAS1890..1950 inclusive (7bins). For all15 local endpoints, test the upper conditional marginal tail P(X_d>=observed | K); no local claims are made for tiny bins. Full global tests still retain every selected person and all16 bins.

Each of2 targets has2 global tests:

- Heterogeneity: Q=sum((observed_d-conditional_mean_d)^2/conditional_variance_d) over nondegenerate bins, calibrated by the exact conditional sampler, upper tail inclusive with fixed floating tie tolerance1e-12*max(1,abs(Qobs)).
- Linear: integer L=sum(x_d*X_d), x_d=(decade-1900)/10; two-sided absolute displacement from conditional E(L). Compute E(L|K) with integer unnormalized weightedBernoulli polynomial recurrence C_k<-f*C_k+s*C_(k-1), M_k<-f*M_k+s*(M_(k-1)+x*C_(k-1)), so E=M_K/C_K is rational. Inclusive reflected-tail cutoffs use exact Fraction arithmetic rather than floating ties. Report raw OLS and conditional-null-expected slopes in percentagepoints per birthdecade.

Together15local+2heterogeneity+2linear=19 endpoints, with one strict Holm19 family. Expanded repeats the same19 as source-sensitivity reference only. Local finite-sum probabilities use float64 weights, global p=(1+inclusive_extreme_count)/(99999+1). One99999-vector draw stream per target/source calibrates both global statistics. PCG64seed=202611240000+targetindex*1000+sourceindex*100, target0CAS/1NAS and source0strict/1expanded. No adaptive repeats or outcome-selected windows/directions.

CAS Xin's earlier unconditional-calendar linearp/Holm30 remains a separate historical reference. NAS Water's earlier separate Ren/Gui trend tests are not a test of their sum. New conditional-linearp answers the revised age-concentration question; it cannot overwrite or be presented as the prior test. No between-country difference is inferred from one target's p relative to the other's.

## QA and deliverable

Freeze code, scope, input hashes, metadata, existing aggregate readback and syntheticQA in remoteGit before computing any new p. Independent QA uses a separate year-polynomial/conditional-margin implementation, exact small exhaustive examples, person-level suffix conditional sampling instead of the main bin sampler, fixed strict15000 independentMC checks, all source/bin/moment/localtail/linear-boundary checks and independent Holm19. QA never replaces primaryp.

Plot only the predeclared adequately sized bins, in4 panels(two targets bytwo sources), observed% plus unconditional calendarE and conditional-on-K E. Allcategories/bins remain in complete tables; no p-selected colors/bars. Explain clearly the difference between an overall surplus and an era-specific surplus. Figures are descriptive and all significant claims use fixed19correction.

Deliver a new ZIP containing raw tables, both sources, all19tests, moment/calibration QA, old-test references, figures, code/source hash receipts and an HTML report. Code is stored in Git, not duplicated in the deliverable. Interpret all outcomes as targeted post-reveal exploration.
