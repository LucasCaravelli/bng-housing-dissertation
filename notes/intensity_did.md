# Within-England BNG intensity DiD: baseline (validation target 4)

Script: `src/intensity_did.py`. Inputs: `panel_england_lpa2025_quarter.csv` (planning
panel) and `intensity_lpa2025.csv` (intensity score), both rebuilt and validated.

## Part A: pre-specification (written 26 Nov 2026, before running)

**Specification (taken from the pilot, `Planning/code/11_intensity_robustness.py`, check 1)**

    y_it = a_i + l_t + beta * (I_i x Post_t) + e_it

- *i* = LPA, main sample: 205 councils outside London with fringe ratio >= 1.
- *t* = quarter, 2015 Q1-2026 Q2, **dropping 2023 Q4-2024 Q2** (fee rise and BNG transition;
  decisions then mostly concern pre-BNG applications). Post = 2024 Q3-2026 Q2.
- *I_i* = intensity standardised across the LPAs in the estimation sample (mean 0, SD 1),
  so beta is per SD of intensity.
- Outcomes: **log(1 + major + minor dwelling decisions)** (the target); also the dwelling
  grant rate (granted / decided, weighted by decisions) and log(1 + householder decisions)
  (placebo: BNG-exempt).
- SEs clustered by LPA (205 clusters).

**Model link (FINDINGS section 2).** Intensity proxies *b*, the habitat units lost per
dwelling. Cost channel: beta_H = -Delta tau / (D + C) < 0 for decisions, and a higher grant
rate if weaker schemes are screened out before submission. Householder decisions should
show beta = 0.

**Identifying assumption.** Absent BNG, log decisions in high- and low-intensity councils
would have moved in parallel after 2024 Q3. With a continuous dose, beta is a weighted
average of the effect of an extra SD of intensity, and reading it causally needs the
stronger version of parallel trends (no selection on gains across intensity levels;
Callaway, Goodman-Bacon and Sant'Anna, "Difference-in-differences with a continuous
treatment", TODO: verify reference). Known threat from the pilot: high-intensity councils
ran 3-5% below in 2016-21 and converged by 2023 (non-linear pre-trend), so a positive
beta may be catch-up rather than BNG.

**Targets** (pilot `robustness_summary.txt`; FINDINGS section 6.4):
- log dwelling decisions: beta = **0.0361**, SE = **0.0177**, 205 LPAs.
- Top vs bottom tercile, binary 2x2: **0.0541** (SE 0.0384, 137 LPAs).
- Also (FINDINGS section 5 table): grant rate +0.008 (p .20); householder +0.010 (p .16).

**Routes (project rule: verify every estimator two ways)**
1. `pyfixest.feols` with LPA and quarter fixed effects, CRV1 by LPA.
2. By hand: two-way within transformation (iterated demeaning to convergence), OLS on the
   demeaned regressor, and a hand-coded cluster-robust variance.
3. Tercile check: 2x2 difference of mean outcomes (top minus bottom, post minus pre), which
   equals the binary TWFE coefficient when the panel is balanced.

**Small-sample correction.** CRV1 = G/(G-1) x (N-1)/(N-K) x sandwich. The pilot used
statsmodels with LPA dummies, so K counts all the fixed effects. pyfixest's default does not
count fixed effects nested in the clusters. Both are reported; the target is matched with K
counting the fixed effects. The difference should be about 1-2% of the SE.

**Checks**
- D1 Sample: 205 LPAs x 43 quarters = 8,815 observations; balanced; no missing outcome.
- D2 Route 1 beta = 0.0361 and SE = 0.0177 (to 4 decimals, with the pilot's correction).
- D3 Route 2 beta equals route 1 to 1e-8; hand SE equals route 1 SE to 1e-6 under the same
  correction.
- D4 Tercile 2x2 mean difference = binary TWFE coefficient (to 1e-8) = 0.0541.
- D5 Grant rate and householder betas match the pilot table to 3 decimals.

Any failure is explained before moving on. No new specifications are run here; the
robustness checks are target 4b.

## Part B: results (26 Nov 2026)

**Validation target 4 reproduced exactly, on the rebuilt panel and intensity score.**
D1-D5 pass on the first run; no deviations.

| Outcome | beta per SD | SE (K incl. FE) | SE (pyfixest default) | p | pilot |
|---|---|---|---|---|---|
| log(1 + dwelling decisions) | **+0.0361** | **0.0177** | 0.0175 | 0.043 | 0.0361 (0.0177) |
| Dwelling grant rate (weighted) | +0.0075 | 0.0059 | 0.0059 | 0.20 | +0.008 (p .20) |
| log(1 + householder) [placebo] | +0.0104 | 0.0075 | 0.0074 | 0.17 | +0.010 (p .16) |

- D1: 205 LPAs x 43 quarters = 8,815 observations, balanced. The grant rate is undefined
  in 21 LPA-quarters with no dwelling decisions (zero weight in any case).
- D3: pyfixest and the hand-coded estimator agree to 7e-18 (beta) and 6e-13 (SE).
- D4: top vs bottom tercile (137 LPAs): binary TWFE = 2x2 difference of means = **0.0541**
  (SE 0.0384), as it must be in a balanced panel.
- **Small-sample correction.** Counting the 247 fixed-effect parameters in K raises the SE
  by about 1.4% (0.0177 vs 0.0175): sqrt((N-1)/(N-K)) = sqrt(8814/8567). Because the LPA
  effects are nested in the clusters they arguably shouldn't be counted (fixest's and
  pyfixest's default), so **0.0175 is the better SE for the write-up**; the pilot's 0.0177
  is reproduced only to validate.
- **p-values.** The pilot's 0.041 is from a normal reference distribution (statsmodels);
  pyfixest uses t with G-1 = 204 degrees of freedom, giving 0.043. With 205 clusters the
  difference is immaterial.

**Reading.** No sign that BNG reduced dwelling decisions where it bites hardest: the
estimate is positive (+3.6% per SD), the opposite of the cost channel's sign
(beta_H < 0). The placebo is small and insignificant here. The positive beta is most
likely the pre-trend catch-up recorded in the pilot (high-intensity councils 3-5% below in
2016-21, converging by 2023), not a BNG effect. That's why the de-trended and 2021+ window
checks matter (beta 0.029 and 0.027 in the pilot). The baseline is not read causally until
the event study and robustness checks are rebuilt (target 4b).
