# SDID: English councils vs Welsh donor councils (validation target 5)

Script: `src/sdid.py`. Inputs: the rebuilt England and Wales planning panels.

## Part A: pre-specification (written 26 Nov 2026, before running)

**Purpose.** Reproduce the pilot's SDID feasibility check (pilot `Planning/code/18_sdid_feasibility.py`,
`Planning/output/sdid/`). Its verdict, "Low" (Wales is not a usable donor pool for planning
outcomes), is already the basis of the plan, so this is a validation, not a new design.
Model link: the England-Wales contrast estimates BNG *relative to* Wales's weaker policy
(PPW net benefit), which is the effect of T on the grant rate (selection) and on decisions (H).

**Estimator** (Arkhangelsky et al. 2021, AER, Algorithm 1; TODO: verify the reference details)
- Units: English councils outside London (no national parks), and Welsh councils as donors.
- Quarters 2016 Q1-2026 Q1 (both countries publish); pre = 2016 Q1-2023 Q3 (31), post =
  2024 Q3-2026 Q1 (7); 2023 Q4-2024 Q2 dropped.
- Unit weights: min over the simplex of ||omega_0 + Y_co,pre' omega - mean(Y_tr,pre)||^2 +
  zeta^2 T_pre ||omega||^2, with zeta = (N_tr T_post)^(1/4) x sd(first differences of donor
  pre-period outcomes). Time weights: the same with lambda over pre-periods predicting each
  donor's post mean, penalty (1e-6 sd)^2 N_co. Intercepts handled by demeaning.
- tau = [treated post mean - lambda' treated pre] - omega'[donor post mean - lambda' donor pre].
- Also: DiD (uniform weights), synthetic control (no intercept, no penalty, no time weights),
  pre-period RMSE after level matching, effective donors 1/sum(omega^2).
- SE: jackknife over units with weights fixed (Algorithm 3).

**Data rules (pilot's)**: drop a council with any missing value at or after 2023 Q4
(Denbighshire); fill isolated pre-period gaps of up to 2 quarters by linear interpolation
(Flintshire, Carmarthenshire, Blaenau Gwent, Newport); in each outcome matrix drop units with
any undefined value (e.g. a grant rate in a quarter with no decisions).

**Checks to reproduce** (each for 5 outcomes: dwelling grant rate [primary], minor-dwelling
grant rate, log(1 + dwelling decisions), householder grant rate and log(1 + householder
decisions) [placebos]): 1 main; 2 placebo in time (fake post 2021 Q1-2023 Q3); 3 drop
interpolated councils; 4 fringe ratio >= 1 (**not reproduced now**: it needs the LCM2021
England-Wales intensity, not yet rebuilt); 5 each English region as the treated group
(primary outcome); annual major-dwelling grant rate (2016-23 vs 2025) and its placebo;
leave one donor out (weights re-fitted).

**Targets.** Primary: DiD special case **0.061973**, SDID **0.017323** (FINDINGS 6.5); SE
0.0132; placebo in time +0.039; log householder decisions -0.034 (SE 0.016).

**Verification routes**
- V1 Weight solver: accelerated projected gradient (FISTA) vs scipy SLSQP, for both omega
  and lambda: objectives equal to 1e-8, weights to 1e-6.
- V2 Uniform weights reproduce the 2x2 difference of means exactly.
- V3 SDID tau equals the weighted two-way FE regression (paper eq. 1) to 1e-8.
- V4 Every row of the pilot table (except check 4) and every leave-one-out tau match the
  pilot to 1e-6; sample counts equal.

**Caveats to carry into the write-up (not tested here)**
- The pilot solves the paper's objectives exactly; R's `synthdid` by default also sparsifies
  the weights (TODO: verify against the package). Not the package's default estimator.
- *Inference.* Treatment is assigned by country, so the design is close to two clusters
  (England vs Wales). The unit jackknife treats councils as independent and will understate
  uncertainty from country-level shocks. Project rule: use randomisation or placebo inference
  and say so. The placebo in time is the more honest guide.

## Part B: results (26 Nov 2026)

**Validation target 5 reproduced exactly** (check 4 not run: needs the LCM2021 England-Wales
intensity).

| Check | Result |
|---|---|
| Data rules | Denbighshire dropped; Flintshire, Carmarthenshire, Blaenau Gwent, Newport interpolated (same as pilot) |
| V1 solvers | FISTA = SLSQP: objectives equal to 1e-10 (omega and lambda), weights to 2e-8, same tau |
| V2 DiD | uniform weights = 2x2 means: **0.06197313** |
| V3 regression | SDID tau = weighted two-way FE regression: **0.01732320** |
| V4 vs pilot | 25 table rows: tau, SE, DiD, RMSEs and effective donors equal to 3e-15; all 105 leave-one-out taus to 1e-9; sample counts equal |

**Deviation (explained, not a result).** The synthetic-control column `tau_sc` differs from
the pilot by up to 3.1e-6. It has no ridge penalty, so projected gradient converges slowly;
the pilot stopped at 50,000 iterations before convergence. Tested on one problem: 50,000
iterations give tau_sc -0.0035102, while 200,000 iterations, 2 million iterations and SLSQP all
give -0.0035069 (objective lower by 1e-10). The rebuild's values are the converged ones.
`tau_sc` is a comparison statistic, not a target.

**Results** (primary outcome, dwelling grant rate; 21 Welsh donors, 259 English councils):
- SDID tau = **+0.017** (jackknife SE 0.013, MDE 3.7 pp); DiD +0.062; SC +0.027.
- **Placebo in time** (fake post 2021 Q1-2023 Q3): **+0.039**, larger than the main estimate.
- Effective donors 21.0 of 21: the ridge penalty makes the unit weights almost uniform, so
  SDID differs from DiD almost entirely through the time weights (late pre-period quarters).
- Pre-period RMSE after level matching: SDID 0.030 vs DiD 0.031 (no better fit).
- Placebos: householder grant rate +0.011 (SE 0.009); log householder decisions -0.034
  (SE 0.016). Leave-one-donor-out range for the primary: +0.014 to +0.025.
- By English region, tau runs from -0.031 (North East) to +0.057 (East of England).

**Verdict unchanged: Low.** The placebo in time is larger than the estimate, the donor
weighting cannot improve the pre-period fit (Welsh grant rates fell from about 80% to 65% in
2016-23 while England's held near 75%), and the BNG-exempt householder series also moves.
Wales is not a usable comparison group for planning outcomes. This is a property of the
donor pool, not of the estimator, which is verified three ways.

**Inference caveat, stated for the record.** The jackknife SE treats councils as
independent. Treatment is by country, so country-level shocks (Welsh policy, PPW, phosphate
advice) are shared by all donors. The effective number of independent comparisons is close
to two, and the SE above understates uncertainty. Any future England-Wales design (demand
(b), house prices) needs placebo-in-time or randomisation inference, as pre-specified in
FINDINGS section 7.

Runtime about 3 minutes (mostly the unpenalised synthetic-control fits).
