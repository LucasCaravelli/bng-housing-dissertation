# Gain sites and nearby house prices (validation target 6)

Scripts: `src/housing_inputs.py`, `src/gainsite_context.py`, `src/hedonic_base.py`,
`src/gainsite_did.py`, `src/gainsite_sdid.py`, `src/epc_extract.py`, `src/gainsite_epc.py`.

## Part A: pre-specification (written 26 Nov 2026, before running)

**Purpose.** Reproduce the pilot's gain-site price estimates (FINDINGS section 4;
pilot `BNG/code/01-04` and `BNG/code/tests/10-21`) from the raw files, with new code. In the
toy model these estimate the price effect of a nearby registered gain site: the amenity
channel (A, through eta and rho) predicts P up, the "signal of development" channel P down;
FINDINGS expects a near-zero effect (eta small).

**Targets** (`BNG/output/tests/summary_estimates.csv`, full precision):

| Row | beta | SE |
|---|---|---|
| T1 Ring DiD, 0-1 km vs 2-4 km, urban fringe (72 sites) | 0.0013833 | 0.0077928 |
| T2 Later sites as controls, all sites, 0-1 km (156 treated) | 0.0074801 | 0.0101225 |
| T3 Timing = works start | 0.0036180 | 0.0087748 |
| T4 Synthetic DiD, 64 sites vs pseudo-site donors | -0.0033329 | 0.0094719 |
| T5 EPC controls (floor area, rooms, age band, rating) | 0.0040029 | 0.0069391 |
| T6 Price per m2 | 0.0038922 | 0.0074496 |

Plus: test 1 joint pre-trend test p = 0.238; pilot sale-level ring DiD 0.0086 (0.0079),
220,826 sales; EPC match rate 93.9%.

**The 404-row site file, as in the pilot.** The pilot used every row of the 12 Oct 2026 register
with coordinates and status Registered: 403 rows for 401 sites, because two amended sites
(BGS-260226001, BGS-050825004) appear twice with different reference strings. Rule: rebuild
exactly that row set for validation (one row per raw record, no deduplication), then, after
validation, rerun on the deduplicated 6 Nov file (424 sites) and report the difference. That
rerun is a new estimate, not part of this target.

**Pipeline and fixed choices (the pilot's; each listed so differences can be traced)**
1. *Price Paid*: yearly CSVs 2018-2026, category A, record per transaction id; `addr =
   postcode|PAON|SAON`. Sample Jan 2018-Jun 2026, price >= GBP 20,000.
2. *Postcodes*: ONSPD Aug 2026, English postcodes (country E92000001) with coordinates,
   terminated postcodes kept (old sales use them).
3. *Sites*: status Registered with coordinates; treatment date = date in the reference; radius
   r = sqrt(area/pi); distance = postcode centroid to site point minus r (floored at 0).
   Rings 0-500 m, 500 m-1 km, 1-2 km, 2-4 km. Urban fringe = Living England built-up share of
   the 0-1 km ring >= 10% (vector intersection of discs, as in the pilot).
4. *First stage* (all England): ln P on LAD x quarter and type x tenure x new-build fixed effects;
   residual u. Postcode x quarter cells of counts and residual sums (all sales; existing only).
5. *T1*: urban-fringe sites with treatment in 2024-25, sales up to 20 quarters before; cell
   level, y = mean u, weights = sales, FE site x ring and site x quarter, SE by site.
6. *T2/T3*: stacked clean-control DiD, window g-12 to g+3, controls registered after g+3;
   inner ring; FE stack x site and stack x quarter; weights = sales; SE by site. T3 uses works
   start when earlier than the reference date. Event study in half-years, joint pre-test.
7. *T4*: site x half-year panel of inner-ring mean u, >= 3 sales every half-year; cohorts
   2024H1-2025H2; pseudo-site donors 5-15 km away (seed 7); Frank-Wolfe weights; placebo SE
   with 200 reps.
8. *T5/T6*: EPC certificates in postcodes within 4 km of any site (streamed from the zip),
   linked to sales by postcode and address rules; pilot ring DiD at sale level with EPC
   controls.

**Checks**
- G1 Inputs: Price Paid rows by year and ONSPD rows equal the pilot's parquet files; any
  difference listed (the pilot's conversion script was not found, so the rules are inferred
  from its output).
- G2 Sites: 403 rows; urban-fringe count 72 in the pilot sample; built-up shares equal the
  pilot's `02_site_landcover.csv` to 1e-9 (cross-checked against the 50 m raster).
- G3 First stage: number of sales and residual SD equal the pilot log.
- G4 Each target to the printed precision; SEs too. Hand route for T1 (two-way demeaning,
  hand CRV1) and for the T4 weights (exact optimum vs Frank-Wolfe).
- G5 EPC extract row count and match rate equal the pilot's.
If T4 cannot match exactly (it depends on the order in which random donors are drawn), the
result must be within one SE and the cause shown.

**Known inference caveats (for the write-up)**
- Sites cluster at the urban fringe and share comparison rings; clustering by site ignores
  overlap between sites (the pilot's "no other site within 4 km" split addresses this).
- Treatment date = application submission, before public listing: biases towards zero.

## Part B: results (26-27 Nov 2026)

**Validation target 6 reproduced: five of six rows exactly; T4 within donor-draw noise.**

| Row | Rebuild beta (SE) | Pilot beta (SE) | Match |
|---|---|---|---|
| T1 Ring DiD, urban fringe, 72 sites | 0.0013833 (0.0077928) | 0.0013833 (0.0077928) | exact; 221,518 sales |
| T2 Later sites as controls, 156 treated | 0.0074801 (0.0101225) | same | exact (1e-9), all 7 specs |
| T3 Works start as treatment, 202 treated | 0.0036180 (0.0087748) | same | exact |
| T4 SDID, 64 sites, pseudo-site donors | -0.0024327 (0.0096686) | -0.0033329 (0.0094719) | 0.1 SE apart (see below) |
| T5 EPC controls | 0.0040029 (0.0069391) | same | exact; 207,725 sales |
| T6 Price per m2 | 0.0038922 (0.0074496) | same | exact |

Also exact: test 1 event study (all bins, 1e-9) and the joint pre-trend test, p = 0.2378;
late-real-donor SDID -0.0157161; EPC match rate 93.9% and its change after registration
-0.0070 (0.0046); EPC composition checks 2c.

**Checks.**
- G1 Price Paid 2018-2026 (6,655,030 sales in the sample) and ONSPD (2,272,272 English
  postcodes) identical to the pilot's files, field by field. Rules recovered from the pilot's
  output: category A, postcode in the English ONSPD; addresses upper-cased.
- G2 403 site rows (401 sites), built-up shares identical (max difference 3e-16), 121
  urban-fringe rows, 72 in the pilot sample.
- G3 First stage R2 0.670, sd(u) 0.373; pyfixest and hand demeaning agree to 1e-7.
- G4 T1 hand route: beta identical; SE identical (1e-9) once pyfixest's singleton removal
  is matched (see deviations).
- G5 EPC: 3,675,199 certificates in 304,706 postcodes within 4 km of a site (19 zip members,
  30.4 million rows read, about 4 minutes).

**T4 (SDID): why not exact.** The pseudo-site donors are drawn at random (seed 7) from
candidate postcodes returned by scipy's ball query. For a single point that query returns
indices in tree order, not sorted (confirmed in scipy 1.18.1), and the order can differ
between scipy versions. So the same seed picks different donors (202 usable donors here vs
205 in the pilot). The deterministic parts all match exactly (late-real donors). Over 40 other
seeds the estimate has mean -0.0029, SD 0.0034, range -0.010 to +0.004; the pilot's value is
at the 42nd percentile and the rebuild's at the 50th. Exact-optimum weights instead of 5,000
Frank-Wolfe steps move tau by 1e-4.
*Implication for the write-up:* the donor draw adds variance of about a third of the
placebo SE that the placebo SE does not include. Average over many draws (or fix the draw
by sorting candidates) before reporting.

**Deviations (code and method details, no change to targets)**
1. Addresses: the first conversion kept the raw case; the pilot upper-cased (a handful of
   records). Fixed.
2. Pilot reference strings for the two timestamped records keep a trailing space; the
   comparison strips it.
3. pyfixest drops singleton fixed-effect cells by default (98 in T1). beta is unchanged but
   the clustered SE moves by 1e-4 relative. The pilot used the default, so its SE is
   reproduced; the hand route is compared with `fixef_rm="none"`.
4. pyfixest 0.70 reports Wald tests as F; the chi-square p-value is computed for
   comparability with the pilot (both 0.2378 here).
5. Added `pyarrow` to the environment (Lucas's OK, 26 Nov 2026).

**Reading.** All estimates are small: +0.1% to +0.8% for the DiD rows, -0.2% to -0.3% for
SDID, with 95% intervals within about +/-3%. That fits the toy model's expectation of a small
amenity effect (eta small, much of the created habitat is grassland enhancement). These rows
still use the pilot's 403-row site file with two sites counted twice, and a treatment date
(application submission) that precedes public listing, which biases towards zero.

## Rerun on the deduplicated 6 Nov 2026 register

### Part A: pre-specification (written 27 Nov 2026, before running)

**What changes, and only this.** Sites: the 6 Nov register, one row per site (`gainsite_context.py
2026-11-06_BNG_Register sites`): 423 registered sites with coordinates, against 403 rows (401
sites) in the validation run. Two differences: (i) the two duplicated sites now enter once;
(ii) 22 sites new since 12 Oct, all with reference dates in 2026 Q2-Q4, after the price data
end (Jun 2026). They cannot be treated in any design; they join the stacked DiD as
later-registered controls and the pseudo-site exclusion zones. Everything else (sales, first
stage, rings, windows, FE, clustering, seeds) is unchanged.

**Expectations, written down before running.** T1 changes only if a duplicated site is in the
72-site urban-fringe 2024-25 sample (then 71 sites, with its sales no longer double-weighted).
T2/T3 gain controls in late stacks, so estimates move slightly; the number of treated sites
does not change except for the duplicates. T4: same treated set minus duplicates; donors
redrawn (seed 7). T5/T6: the EPC extract is redone for the new postcode set.

**Reported in addition (pre-specified now, from lessons in the validation run)**
- T4 is reported as the mean and SD of tau over 40 donor draws (seeds 1-40) as well as seed 7,
  because the draw adds variance the placebo SE omits.
- Sensitivity: drop the two sites located only to 1 km (BGS-190226001, BGS-201125001) from
  T1-T3 (a 1 km square is as wide as the treatment ring).

**Decision rule.** These are the post-validation estimates; they replace the validation rows
in anything written up, with the validation run kept as the audit trail. A change larger
than one SE in any row is investigated before use (a bug is the first suspect).

### Part B: results (27 Nov 2026)

Sites: 423 (126 urban fringe; 71 in the T1 sample, since BGS-050825004 had been counted
twice). The 401 sites in both pulls are identical in location, dates and land cover. No
deviations from Part A. Every change against the validation run is below one SE.

| Row | 423 sites: beta (SE) | Validation run (403 rows) | Without the two 1 km sites |
|---|---|---|---|
| T1 Ring DiD, urban fringe 2024-25 | **+0.0003 (0.0078)**, 71 sites | +0.0014 (0.0078), 72 | +0.0001 (0.0078), 70 |
| T2 Later sites as controls (1a) | **+0.0060 (0.0098)**, 155 treated, 343 controls | +0.0075 (0.0101) | +0.0060 (0.0098) |
| 1b ring DDD | +0.0022 (0.0122) | +0.0034 (0.0128) | +0.0023 |
| 1c / 1d urban fringe | +0.0045 (0.0107) / -0.0004 (0.0135) | +0.0037 / -0.0026 | +0.0045 / -0.0002 |
| 1e buffer >= 1 year | +0.0282 (0.0221), **40 treated** (17 before) | +0.0425 (0.0250) | +0.0282 |
| T3 Works start (1f) | **+0.0026 (0.0086)**, 201 treated | +0.0036 (0.0088) | +0.0024 |
| 1g existing homes | +0.0056 (0.0094) | +0.0052 (0.0092) | +0.0057 |
| Pre-trend test (event study) | p = 0.39 | p = 0.24 | p = 0.40 |
| T4 SDID, seed 7 | +0.0032 (placebo SE 0.0088), 63 treated, 202 donors | -0.0024 (0.0097) | - |
| **T4 SDID, mean of 40 draws** | **-0.0047 (draw SD 0.0036)** | -0.0029 (SD 0.0034) | - |
| T4 late real donors (14) | -0.0111 | -0.0157 (9 donors) | - |
| T5 EPC controls | **+0.0040 (0.0070)**, 202,823 sales | +0.0040 (0.0069) | - |
| T6 Price per m2 | **+0.0039 (0.0075)** | +0.0039 (0.0074) | - |
| EPC composition: log floor area / share new | -0.0085 (0.0084) / -0.0076 (0.0099) | -0.0079 / -0.0068 | - |

EPC: 3,864,299 certificates near the 423 sites; match rate 93.9%, unchanged after
registration (-0.0072, SE 0.0047).

**Reading.**
- *A precise null on existing-home prices within 1 km of a registered gain site.* Every DiD
  row lies between -0.04% and +0.6%, with 95% intervals inside about +/-2.5%. The MDE at 80%
  power is about 2.8 x 0.0078 = 2.2% for T1 and 2.7% for T2. Consistent with FINDINGS
  (+/-3% equivalence) and with the toy model's small eta.
- *SDID.* Seed 7 happens to be the largest of the 40 draws (+0.0032), while the mean over
  draws is -0.0047. A single seed is not a reliable point estimate here; report the
  draw-average with both the placebo SE and the draw SD (combined, roughly
  sqrt(0.0088^2 + 0.0036^2) = 0.0095).
- *1e* gains power (40 treated, not 17) because the new 2026 sites serve as later controls;
  still insignificant (+2.8%, SE 2.2%).
- *Composition.* Homes sold within 1 km after registration are, if anything, slightly smaller
  and older (both insignificant), so EPC controls move the estimate up a little, not down.
- Dropping the two sites located only to 1 km changes nothing material.

Outputs: `data/processed/gainsites/*_2026-11-06_sites*.csv`.

**Not yet done (FINDINGS 7.2).** Doubly robust Callaway-Sant'Anna with baseline habitat and
selection covariates, and the formal TOST against +/-3%. The treatment date is still the
application date, which biases towards zero.

**Earlier note.** Rerun on the deduplicated 6 Nov register (424 sites, 423 usable)
with `python src/gainsite_context.py 2026-11-06_BNG_Register sites` and the scripts with tag
`2026-11-06_sites`. This is the doubly robust Callaway-Sant'Anna rerun planned in FINDINGS 7.2.
