# Gain sites and nearby prices: doubly robust Callaway-Sant'Anna (FINDINGS 7.2)

Script: `src/gainsite_cs.py`; estimator tests: `tests/test_drdid.py`.
Design choices agreed with Lucas on 27 Nov 2026 (outcome; covariates). Everything else below
is fixed before any estimate is computed.

## Part A: pre-specification (written 27 Nov 2026, before running)

**Question and model link.** Does registering an off-site gain site change the prices of
nearby existing homes? Toy model (FINDINGS 2): amenity channel P up (through eta, rho, s), signal
of nearby development P down; the evidence points to eta small, so the expected effect is
close to zero. This design reports a causal estimate under the assumption below, and
an equivalence test against +/-3%.

**Why Callaway-Sant'Anna.** Registration is staggered (2024H1-2025H2). TWFE with staggered
timing uses already-treated sites as controls and can weight cohort effects negatively
(Goodman-Bacon 2021). CS (Callaway and Sant'Anna 2021) estimates each cohort x period effect
ATT(g,t) against not-yet-treated sites only, then aggregates with explicit weights. The
doubly robust (DR) version (Sant'Anna and Zhao 2020) conditions parallel trends on covariates
and is consistent if either the propensity score or the outcome model is right.

**Panel**
- Units: the 423 registered sites with coordinates (6 Nov 2026 register, one row per site).
- Periods: half-years 2018H1-2026H1 (17). Quarters are too sparse: the median site has under
  one sale within 1 km per quarter.
- Outcome Y_it (agreed): mean quality-adjusted log price (first-stage residual u) of sales
  0-1 km from the site edge **minus** the same for 2-4 km, all sales. Defined only if both
  rings have at least one sale in the half-year. Local market shocks around a site cancel;
  the covariates address selection across sites.
- Cohort G_i: half-year of the reference date (application submission). Treated cohorts:
  2024H1-2025H2 (g = 12-15). Sites registered later (2026H1 onwards) are controls until they
  are treated; there are no never-treated sites.

**Covariates X_i (agreed: full selection set; all fixed before 2024)**
1. log site area (ha);
2. built-up share of the 0-1 km ring (Living England 2022-23);
3. main created habitat is woodland (0/1);
4. surrounding deprivation: population-weighted mean IMD 2025 score of the LSOAs with at
   least one postcode within 1 km of the site edge;
5. pre-BNG price level: mean u of sales within 1 km in 2018-2019. Sites with no such sale
   are dropped (count reported).

**Estimator (fixed)**
- Anticipation delta = 1 half-year: works start a median ~11 months before the reference
  date, so the base period is b = g - 2 and the comparison group for (g,t) is sites with
  G > max(t, b) + 1 (not yet treated, nor in their own anticipation half-year).
- Universal base period (b = g - 2 for every t), so pre-period ATT(g,t) are placebos
  comparable with post ones (Roth 2024).
- For each (g,t): units in cohort g or the comparison group with Y observed at both b and t;
  dY = Y_t - Y_b. DR ATT (Sant'Anna-Zhao "traditional" panel estimator): logit propensity
  score p(X) for being in cohort g vs comparison, OLS outcome model m(X) for dY among
  comparison units, ATT = mean over treated of (dY - m(X)) minus the weighted mean over
  controls with weights p/(1-p), normalised. Controls with p(X) > 0.995 are trimmed.
  A cell is estimated only if it has at least 5 treated and 10 comparison units with Y at
  both b and t (added before running, as the cohort sizes are small); skipped cells are
  listed. The logit is fitted by Newton-Raphson, checked against statsmodels in the tests.
- Aggregation: overall ATT = average of ATT(g,t) for t >= g (post), weighted by cohort size x
  periods (CS "simple"); event study by e = t - g from -8 to +3, cohort-size weighted.
- Inference: site-level (cluster) bootstrap, resampling sites with replacement and
  re-estimating everything (scores, outcome models, ATTs), B = 499, seed = config.SEED.
  Percentile 95% and 90% intervals; bootstrap SE. Pre-trend test: Wald test of all pre-period
  event-time coefficients (e <= -3; e = -2 is the base, e = -1 the anticipation half-year)
  using the bootstrap covariance.
- **Equivalence (TOST, Lakens 2017):** bound +/-3% in price = +/-log(1.03) = +/-0.0296 log
  points. Equivalence at 5% if the 90% bootstrap interval of the overall ATT lies within it.

**Identifying assumption.** Conditional on X, the inner-minus-outer price gap around sites
registered in g would have evolved like the gap around sites registered later, from b to t,
absent registration (and no effect before g - 1). Threats: selection on unobserved trends
(landowners choose when to register); spillovers between overlapping sites; the treatment
date is the application date, before public listing, which biases towards zero.

**Checks (all must pass)**
- C1 Unit tests on simulated data: (a) with no covariates, DR ATT(g,t) equals the 2x2
  difference of means exactly; (b) with selection on X and a known ATT, DR recovers it
  (within 3 simulation SEs) while unadjusted DiD is biased; (c) the bootstrap reproduces
  under a fixed seed.
- C2 Real data, no covariates: every ATT(g,t) equals the 2x2 means computed separately.
- C3 Overlap: propensity-score ranges per (g,t) reported; share trimmed reported.
- C4 DR, IPW-only and regression-only overall ATTs reported side by side.

**Pre-specified robustness (all reported)**
R1 no covariates (unconditional CS); R2 delta = 0 (base g - 1); R3 existing homes only;
R4 urban-fringe sites only; R5 drop the two sites located only to 1 km.

## Part B: results (27 Nov 2026)

**Sample.** 423 sites; 68 dropped for having no sale within 1 km in 2018-19 (the pre-price
covariate rule), 5 of them also without an IMD value. 355 sites remain, 192 treated in
2024H1-2025H2 (by cohort 5 / 32 / 61 / 94); 76% of site x half-year cells observed. 60
ATT(g,t) cells estimated; 4 skipped (2024H1 cohort below 5 treated units).

**Process.** A 5-replication smoke test was run first to time the code; it showed point
estimates. No specification was changed after it. The full run used B = 499.

**Checks.**
- C1 unit tests pass (5): no covariates = 2x2 means; Newton logit = statsmodels to 1e-8;
  with selection on X the DR estimator recovers the true ATT where naive DiD is biased;
  placebo pre-periods zero; bootstrap reproducible.
- C2 real data, no covariates: all 60 ATT(g,t) equal the 2x2 means (max |diff| 3e-17).
- C3 overlap: control propensity scores 0.000-0.887; no control trimmed (0 of 953).
- C4 overall ATT: DR -0.0233, IPW -0.0210, regression -0.0225 (both models agree).

**Results** (overall ATT, log points; bootstrap over sites, B = 499):

| Spec | ATT | SE | 95% CI | 90% CI | Equivalent within +/-3%? | Pre-trend p |
|---|---|---|---|---|---|---|
| **Main: DR, full covariates, delta 1** | **-0.023** | **0.031** | [-0.089, +0.032] | [-0.080, +0.020] | **No** | 0.46 |
| R1 No covariates | -0.029 | 0.031 | [-0.091, +0.027] | [-0.083, +0.019] | No | 0.51 |
| R2 delta 0 (base g-1) | -0.005 | 0.029 | [-0.062, +0.050] | [-0.056, +0.040] | No | 0.85 |
| R3 Existing homes only | -0.031 | 0.031 | [-0.092, +0.027] | [-0.082, +0.019] | No | 0.60 |
| R4 Urban-fringe sites only | -0.050 | 0.048 | [-0.121, +0.040] | [-0.107, +0.021] | No | 0.21 |
| R5 Drop the two 1 km sites | identical to main: both were already dropped (no 2018-19 sales) | | | | | |

Event study (main): pre-period coefficients e = -8 to -3 between -0.025 and +0.052, none
individually significant, jointly p = 0.46; post e = 0, 1, 2, 3: -0.027, -0.040, +0.042,
-0.021 (SEs 0.035-0.094).

**Reading.**
- *No detectable effect, but not a precise null.* The main estimate is -2.3% (SE 3.1%); the
  95% interval runs from -8.5% to +3.2%. Parallel pre-trends are not rejected (p = 0.46).
- *The equivalence test fails, through imprecision, not through a large estimate.* The 90%
  interval (-7.6% to +2.0% in price) is wider than the +/-3% bound. The MDE at 80% power is
  about 2.8 x 0.031 = 8.7%, against about 2.2-2.7% for the ring and stacked designs.
- *Why it is much less precise than the earlier designs.* (i) CS weights every site equally,
  while the ring and stacked designs weight cells by sales, so sparse rural sites with very
  noisy gaps count as much as busy urban-fringe ones. (ii) The inner-minus-outer gap needs
  sales in both rings in both the base and the comparison half-year. (iii) 68 sites drop out
  for the pre-price covariate. (iv) Each ATT(g,t) is a 2x2 against one base period, not the
  whole pre-period.
- *Direction.* Every specification is negative (-0.5% to -5.0%), all insignificant;
  covariates move the estimate only slightly (-2.9% to -2.3%), so selection on the observed
  covariates is not driving the earlier near-zero results. The negative sign would fit the
  "signal of nearby development" channel, but nothing here distinguishes it from zero.
- *For the write-up.* The sales-weighted ring and stacked designs (intervals inside about
  +/-2.5%) remain the precise evidence. CS-DR is the staggered-timing and selection
  robustness check: it agrees on "no detectable effect" but cannot by itself establish
  equivalence. Not causal beyond the conditional parallel-trends assumption, with the
  application date as treatment (biased towards zero).

**Possible next steps (not run; each is a new pre-specified design, Lucas's call).**
Sales-weighted CS aggregation (weights proportional to sales per site), or pooling the
base over several pre-periods, would recover precision; a TOST on the stacked design (1a:
90% CI 0.006 +/- 1.645 x 0.0098 = [-1.0%, +2.2%]) would already pass the +/-3% bound.

## Sales-weighted version (pre-specified 27 Nov 2026, after the unweighted run)

### Part A

**Why this exists, stated plainly.** It is chosen *after* seeing the unweighted CS results,
because those were too imprecise to test equivalence (SE 3.1%). That makes it a
forking-paths risk, so the rules are: (i) exactly one thing changes, the unit weights;
(ii) both versions are reported, whatever this one shows, and the unweighted run is not
dropped or relabelled; (iii) the weights are fixed from pre-BNG data only, never from
outcomes after 2023.

**The one change.** Each site gets weight w_i = number of sales within 0-1 km of its edge
in 2018-2019 (pre-BNG; every site in the sample has at least one, by the pre-price rule).
Why this weight: the noise in a site's inner-minus-outer gap is driven mainly by the few
inner-ring sales (variance roughly sigma^2 / n_inner), so weighting by inner sales
approximates precision weighting. It is fixed before BNG, so it cannot respond to treatment.
The weights enter every part of the doubly robust estimator: weighted logit for the
propensity score, weighted OLS for the outcome model, and weighted means for treated and
comparison units. Cohort weights in the aggregation are the summed site weights of each
cohort.

**What it estimates.** The ATT for the average pre-BNG sale near a gain site, rather than
for the average site. This is closer to what the ring and stacked designs estimate (they
weight by sales in each cell).

**Unchanged.** Panel, outcome, cohorts, covariates (same five, still standardised
unweighted), anticipation delta = 1, universal base, comparison group, trimming at 0.995,
minimum cell size, site bootstrap with B = 499 and seed = config.SEED (sites resampled
with their weights), equivalence bound +/-log(1.03), and robustness R1-R4 (R5 is empty).

**Checks**
- W1 Unit tests: equal weights reproduce the unweighted estimator exactly; integer weights
  equal duplicating each unit that many times (exactly); the weighted logit matches
  statsmodels GLM with frequency weights.
- W2 Real data: with all weights set to 1 the weighted code reproduces the unweighted main
  result (-0.0233) exactly.

**Also pre-specified now: the TOST that FINDINGS 7.2 asks for, on the existing sales-weighted
designs.** For T1 (ring DiD) and T2 (stacked, 1a) on the 423-site run, using their clustered
SEs (normal approximation): equivalence at 5% if beta +/- 1.645 x SE lies inside +/-0.0296.
These numbers already exist; the test only applies the bound.

### Part B (27 Nov 2026)

**Checks.** W1: 3 new unit tests pass (equal weights = unweighted; integer weights =
duplicated units for DR, IPW and regression; weighted logit = statsmodels GLM with frequency
weights). W2: with all weights 1 the weighted code gives -0.023252789081, identical to the
saved unweighted result.
*Deviation (code, no effect on results):* the first W2 printout compared against a value
typed into the code by hand (-0.0232932) instead of reading the saved result; the real saved value is
-0.0232527891, which W2 matches exactly. The check now reads the saved file and asserts
equality.

**Weights.** 2018-19 sales within 1 km: median 13, IQR 4-56, max 758. Very skewed: the
effective number of sites is 86 of 355, and the 10 busiest sites carry 24% of the weight.

**Results (same sample, B = 499):**

| Spec | ATT | SE | 90% CI | Within +/-3%? | Pre-trend p |
|---|---|---|---|---|---|
| **W Main: DR, sales-weighted** | **-0.008** | **0.050** | [-0.107, +0.049] | No | 0.30 |
| W-R1 No covariates | -0.030 | 0.020 | [-0.066, -0.000] | No | **0.03** |
| W-R2 delta 0 | -0.017 | 0.038 | [-0.078, +0.028] | No | 0.12 |
| W-R3 Existing homes only | +0.001 | 0.043 | [-0.071, +0.059] | No | 0.41 |
| W-R4 Urban fringe only | -0.010 | 0.082 | [-0.132, +0.076] | No | 0.15 |
| *Unweighted main (for reference)* | *-0.023* | *0.031* | *[-0.080, +0.020]* | *No* | *0.46* |

**Reading.**
- *The pre-specified rationale did not hold.* Weighting by pre-BNG sales made the main
  estimate less precise (SE 0.050 vs 0.031), not more. The site-level noise is not mainly
  sampling noise in each site's price gap (which sales weighting would reduce); it is
  heterogeneity across sites, and concentrating weight on 86 effective sites amplifies it.
  So this version does not rescue the equivalence test. It is reported, not dropped, as Part A
  required.
- The weighted no-covariate version (W-R1) is the most precise (SE 0.020) but fails its
  pre-trend test (p = 0.03): among busy sites, early and late registrants were already on
  different paths before BNG, which the covariates absorb (W main pre-trend p = 0.30).
- Every CS estimate, weighted or not, is between -3.1% and +0.1% and insignificant.
  Callaway-Sant'Anna therefore agrees on "no detectable effect" but cannot show equivalence
  at the site level.

**TOST on the existing sales-weighted designs (pre-specified above; 423-site run).**

| Design | beta | 90% CI (beta +/- 1.645 SE) | Within +/-0.0296? |
|---|---|---|---|
| T1 Ring DiD, urban fringe 2024-25 (71 sites) | +0.0003 | [-0.0125, +0.0132] | **Yes** |
| T2 Later sites as controls (1a, 155 treated) | +0.0060 | [-0.0101, +0.0221] | **Yes** |
| T3 Works start as treatment (1f) | +0.0026 | [-0.0116, +0.0168] | **Yes** |

**Conclusion for the write-up.** In the sales-weighted ring and stacked designs, effects on
nearby existing-home prices larger than +/-3% are rejected at the 5% level (TOST). The
staggered, covariate-adjusted CS design agrees on the sign and on the absence of an effect,
but is too imprecise at the site level to test equivalence (unweighted MDE about 8.7%). The
precise null rests on the ring/stacked identification (parallel trends of the inner ring
relative to the outer ring, or relative to later-registered sites) and the application-date
treatment, which biases towards zero. These are the assumptions to defend in the write-up.
