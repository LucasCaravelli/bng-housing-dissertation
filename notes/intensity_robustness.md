# Intensity DiD: robustness checks and event study (validation target 4b)

Scripts: `src/nutrient_neutrality.py` (NN inputs), `src/intensity_robustness.py`.
Baseline specification and notation: `notes/intensity_did.md`.

## Part A: pre-specification (written 26 Nov 2026, before running)

**Purpose.** Rebuild the pilot's pre-registered robustness checks (pilot
`Planning/output/intensity/INTENSITY_NOTES.md`, checks 1-18) and its event study, from the
rebuilt panel, intensity score and NN inputs, and reproduce the pilot numbers
(`robustness_table.csv`, `event_study_coefs.csv`). Nothing new is estimated here; new
specifications (open decision 1: region x quarter FE as main) are for later, after Ben.

**Inputs.** Panel, intensity score and NN file, all rebuilt and matching the pilot exactly
(NN: 68 of 306 units listed, 53 in the main sample, catchment shares identical).
Also from the raw PS1/PS2 rows: each LPA's region (last listed), and "anomalous" LPA-quarters
(total decisions below 25% of that council's own median, median > 50).

**Checks to reproduce** (the pilot's definitions, each for the three outcomes)
1. Baseline (205). 2. All councils (296). 3. Main + London.
4. Region x quarter FE. 5. LPA linear trends fitted on 2015 Q1-2023 Q3 and removed (two-step).
6. Window 2021 Q1+. 7. Intensity variants (0-250 m, 0-1 km, 50 ha settlements, alt crosswalk,
   mean distinctiveness). 8. Top vs bottom tercile. 9. PPML on counts.
10. Drop anomalous LPA-quarters, merged councils and development-corporation hosts.
11. Leave one region out (range). 12. Placebo: fake Post = 2021 Q1-2023 Q3 on pre-BNG data.
13. Drop NN councils. 14. NN x quarter FE. 15. Region x quarter + NN x quarter FE.
16. NN catchment share x quarter. 17. Drop councils with >= 10% in a catchment.
18. Region x quarter FE + NN share x quarter.
Event study: intensity x quarter (reference 2023 Q3), LPA and quarter FE, all 46 quarters,
main sample and all councils; pre-BNG linear differential-trend test (2015 Q1-2023 Q3).

**Implementation.** Group x quarter effects are absorbed as fixed effects (pyfixest
`region^Quarter`), so the collinearity with LPA effects that broke the pilot's SEs cannot
arise. The pilot instead built dummies and omitted one base quarter per group. Both span the
same space, so the coefficients must agree exactly; the SEs differ only through K in the
small-sample correction.

**Verification routes (project rule: every estimator two ways)**
- Every linear check: pyfixest and a hand route (iterated weighted demeaning on all fixed
  effects, then OLS on the remaining regressors with a hand-coded CRV1). Hand SEs use the
  pilot's K (the number of dummy columns the pilot's design had), so they can be compared
  with the pilot to the last digit.
- PPML: pyfixest `fepois` and statsmodels GLM Poisson with dummies.
- Two-step detrending: first step by `numpy.linalg.lstsq` on explicit dummies.

**Checks on the rebuild**
- R1 Every beta equals the pilot's to 1e-6 (all checks, outcomes and the event study).
- R2 Hand SE (pilot K) equals the pilot SE to 1e-6.
- R3 pyfixest beta equals the hand beta to 1e-8; PPML routes agree to 1e-6.
- R4 Sample sizes (LPAs, observations) equal the pilot's in every row.
Any mismatch is explained before the table is used.

**Known pilot inconsistency (to be checked, not fixed silently).** The event study and the
pre-trend test standardise intensity across rows, while the DiD standardises across LPAs.
In a balanced panel the means agree but the SDs differ by a factor
sqrt(T(N-1)/(NT-1)) (about 0.998), so the event-study coefficients are about 0.2% smaller than
on the DiD scale. The rebuild reproduces the pilot's version for R1 and also writes the
per-LPA version, which should be used from now on.

## Part B: results (26 Nov 2026)

**Inputs.** NN variables rebuilt and identical to the pilot (68 units listed, 53 in the main
sample, 32 main-sample councils with >= 10% in a catchment; catchment shares identical).
Anomalous LPA-quarters found again: Hackney 2020 Q4, Milton Keynes 2024 Q4, Kensington and
Chelsea 2026 Q1.

**Reproduction: all pass, with one pilot error found.**

| Check | Result |
|---|---|
| R1 betas | 84 of 86 table rows and all 184 event-study coefficients equal the pilot to 1e-13 |
| R2 SEs (pilot K) | same rows equal the pilot to 1e-14 |
| R3 second route | pyfixest = hand route (and statsmodels for PPML) to 2e-15 |
| R4 samples | LPAs and observations equal in all 86 rows |

**Pilot error in check 5 (LPA trends removed).** The first step (LPA dummies + quarter
dummies + LPA x t) is rank-deficient by one: 443 of 444 columns, condition number 1e14.
Summed over LPAs the slopes give t, which the quarter dummies span, so the slopes are
identified only up to a common shift that step two absorbs. The pilot's statsmodels
pseudo-inverse returned slopes shifted by about 1e10; subtracting (slope x t) of order 1e11
and then absorbing it left floating-point error that moved beta by 4e-4.
- log dwelling decisions: **+0.0290** (pilot 0.0285); householder: +0.0057 (pilot 0.0056).
  The grant rate matched (its error was below 1e-6).
- Confirmed two ways: the rebuild's minimum-norm `lstsq` first step and a full-rank first
  step (one LPA's slope fixed at 0) give the same beta to 1e-8 (asserted in the code).
- FINDINGS section 5 reports "+0.029 (p .14)". The corrected value is +0.029, p .131 with
  the pyfixest correction. The conclusion doesn't change.
- Lesson (as in the region x quarter bug): never let a solver silently handle a
  rank-deficient design; parametrise it to full rank or check invariance.

**Event-study scaling.** Coefficients per LPA-SD are 1.0017-1.0024 times the pilot's
per-row-SD ones, as predicted. Per-LPA scaling is used from now on
(`event_study_coefs.csv`, `scale = per_lpa`).

**Results** (pyfixest, CRV1 by LPA, default small-sample correction; beta per SD x Post):

| Check | log dwelling decisions | dwelling grant rate | householder (placebo) |
|---|---|---|---|
| 1 baseline | +0.036 (0.018) p .04 | +0.008 (0.006) p .20 | +0.010 (0.007) p .16 |
| 2 all councils | +0.003 p .85 | +0.011 p .03 | **+0.025 p .001** |
| 3 main + London | +0.010 p .65 | +0.012 p .04 | **+0.026 p .002** |
| 4 region x quarter FE | +0.042 p .07 | +0.018 p .01 | +0.005 p .59 |
| 5 LPA trends removed | +0.029 p .13 | +0.015 p .03 | +0.006 p .59 |
| 6 window 2021+ | +0.027 p .11 | +0.012 p .03 | +0.008 p .24 |
| 7 intensity variants | +0.029 to +0.037 | +0.003 to +0.008 | +0.008 to +0.011 |
| 8 top vs bottom tercile | +0.054 p .16 | +0.017 p .23 | +0.009 p .59 |
| 9 PPML | +0.044 p .006 | - | -0.000 p .99 |
| 10 drop anomalies etc. | +0.033 p .07 | +0.007 p .27 | +0.009 p .26 |
| 11 leave one region out | +0.027 to +0.042 | +0.002 to +0.013 | -0.005 to +0.018 |
| 12 placebo Post 2021-23 | +0.014 p .31 | -0.007 p .12 | +0.003 p .67 |
| 13 drop NN councils | +0.041 p .05 | +0.002 p .75 | +0.018 p .046 |
| 14 NN x quarter FE | +0.035 p .05 | +0.007 p .23 | +0.010 p .17 |
| 15 region x qtr + NN x qtr | +0.039 p .09 | +0.017 p .02 | +0.005 p .57 |
| 16 NN share x quarter | +0.038 p .03 | +0.007 p .23 | +0.011 p .13 |
| 17 drop >= 10% NN catchment | +0.040 p .04 | +0.007 p .34 | +0.014 p .10 |
| 18 region x qtr + NN share x qtr | +0.045 p .06 | +0.017 p .02 | +0.005 p .56 |

Pre-BNG linear differential trend (2015 Q1-2023 Q3, per year per SD): dwelling decisions
+0.0012 (p .68), grant rate -0.0013 (p .17), householder +0.0008 (p .65); identical to the
pilot.

**Reading (descriptive of the design, not yet a causal claim).**
- *The event study explains the positive dwelling beta.* Main sample, per-LPA SD, yearly
  means of the quarterly coefficients (reference 2023 Q3): 2015-21 between -0.022 and
  -0.052; 2022 -0.019; 2023 +0.006; post-BNG 2024 +0.002, 2025 +0.013, 2026 -0.017.
  High-intensity councils were 2-5% below in 2015-21 and caught up by 2023; **after BNG
  there's no further movement relative to 2023.** The DiD's +3.6% compares the post
  period with the whole low 2015-23 average, so it measures the catch-up. Checks that
  shorten or de-trend the pre-period (5, 6) pull it towards zero, and the linear trend
  test misses the non-linear drift.
- *Grant rate.* Positive in every check (+0.2 to +1.8 pp per SD), significant only with
  region x quarter FE (4, 15, 18), the de-trended check and the short window, and the
  event study rises steadily to +2.1 pp in 2026. Consistent with selection, still fragile:
  this is open decision 1 for Ben.
- *Householder placebo* fails whenever urban councils are included (checks 2-3), which
  supports the main sample, and is marginal when NN councils are dropped (check 13).
- Precision: the dwelling-decision SE is about 0.018, so the MDE at 80% power is about
  2.8 x 0.018 = 5% per SD. Effects smaller than that are not ruled out. An equivalence
  test needs a bound agreed with Ben (TODO).
