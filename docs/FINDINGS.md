# Findings and work to date (October to November 2026)

Summary for the rebuild. Pilot results came from exploratory code in the old
`Dissertation/` folder. Treat them as **validation targets and leads, not final
results**. Each design's own notes (pre-specification + results) are in
`Dissertation/Planning/output/<design>/*_NOTES.md` and `Dissertation/BNG/output/tests/`.

---

## 1. Question and scope

**How did England's mandatory BNG affect the housing market?**

- **RQ1 Supply.** Did BNG change the number of dwelling decisions, the share approved, or the mix of schemes, especially where it bites hardest (high-habitat land on settlement fringes)?
- **RQ2 Demand.** Did BNG change existing-home prices, near registered gain sites or across areas more exposed to BNG?
- **RQ3 Delivery and selection.** What share of BNG units is delivered on the development site (*s*)? Which land enters the register? Are off-site gains local to the developments they offset, as the status quo in Mancini et al. (2024) assumes?

Policy facts: Schedule 7A TCPA 1990 (inserted by the Environment Act 2021, Sch. 14). Mandatory from 12 Feb 2024 (major) and 2 Apr 2024 (small sites). Every permission must deliver a 10% gain under the statutory metric: on-site first, then registered off-site gains, then statutory credits as a last resort. Off-site land needs a conservation covenant or s106, with 30-year maintenance, entered on Natural England's register. Irreplaceable habitat is excluded. Wales (PPW net benefit) and Scotland (NPF4 Policy 3) strengthened policy in 2023 but have no metric, so comparisons estimate BNG *relative to* weaker policies.

---

## 2. Toy model (the unifying frame)

**Framing.** BNG works like a Pigouvian charge per habitat unit lost. Off-site units trade like permits (Montgomery 1972), and the market's thickness matters (Simpson, Hanley et al. 2021). With inelastic land supply (Hilber and Vermeulen 2016) the cost is passed back to land. Prices are read through hedonic theory (Rosen 1974). A non-marginal national shock gives capitalisation, not marginal WTP (Kuminoff and Pope 2014).

**Demand** (LPA *j*): `P = α + γA − δ(S0 + H)`.
Amenity: `A = A0 − η b [1 − ρ(1+θ) s T] H`.
- *b* = habitat units lost per dwelling, θ = 0.1, *s* = share delivered locally, ρ = credibility of delivery, η = share of local habitat change felt as amenity, *T* = 1 under BNG.
- Reduced form: `P = a − D H`, with `D = δ + γ η b [1 − ρ(1+θ) s T]`.

**Supply.** Marginal cost is `c0 + cH`. BNG cost per dwelling is `τ = (1+θ) b p_B + f`, with unit price `p_B = π0 + π1 Q_B` and `Q_B = (1+θ) b H`.
- `P = k + C H`, with `k = c0 + T[(1+θ) b π0 + f]` and `C = c + T π1 (1+θ)² b²`.

**Equilibrium.** `H* = (a − k)/(D + C)` and `P* = (aC + kD)/(D + C)`. BNG raises *k* and *C* and lowers *D*.

**Propositions.**
- **P1 Prices rise** under both the cost and the amenity channel.
- **P2 The quantity effect is ambiguous.** Its sign identifies which channel dominates; prices alone cannot.
- **P3 Delivery location matters.** As *s* → 0, BNG is a pure cost.
- **P4 Incidence.** With π1 = 0 and no amenity, buyers bear D/(D+C) and landowners C/(D+C). Where supply is tight, the cost falls on land.
- **P5 Grandfathered land.** Permitted land gains ΔP*; unpermitted land gains ΔP* − τ.

**Sign patterns** (price P, homes H, land rent R):

| Channel | P | H | R |
|---|---|---|---|
| Cost | + | − | − |
| Gain-site amenity | + | + | + |
| Signal of nearby development | − | − | − |

**What the evidence says about the parameters**
- **s is high but unmeasured since 2024.** About 95% was on developer land in early-adopter councils in 2020-21 (zu Ermgassen et al. 2021). Mancini et al.'s "mostly on-site" status quo is a modelling assumption traced to that source. Their LEEP code (Run_NEV_Scenarios, BNG branch) contains no such calculation.
- **η is small.** 44% of planned off-site habitat is "other neutral grassland", mostly enhancement (Duffus et al. 2025). Semi-natural grassland carries no price premium (Gibbons et al. 2014).
- **π1 ≈ 0.** About 2% of registered off-site area had sold after 16 months (Duffus et al. 2025).
- **Overall:** a near-pure cost shock. Expect small falls in homes on high-*b* greenfield sites, a price rise too small to detect on the existing stock, and falling unpermitted land values.

**Mapping to regressions.** In `Y = μ_j + λ_t + β(Treat × Post) + ε`: `β_H = −Δτ/(D+C)`, `β_P = DΔτ/(D+C)` and `β_R = −CΔτ/(D+C)`. This motivates continuous treatments using proxies for:
- *b*: BNG intensity
- *c*: refusal rates, developable land
- *s*: same-authority purchases
- ρ: creation vs enhancement

The model is static and not estimated structurally; it disciplines signs and heterogeneity tests.

---

## 3. Data in hand

All raw data are in `Dissertation/RawData-*/`. Full metadata is in `SourceLog.xlsx` (37 datasets, 360 files).

| Area | Data | Notes |
|---|---|---|
| Gain sites | Natural England register: 6 Nov 2026 pull (424 sites), 12 Oct snapshot (402) | Point locations only. Clean file: `ProcessedData/bng/bng_sites_clean_2026-11-06.csv` |
| Prices | HMLR Price Paid 2018-2026; ONSPD Aug 2026; domestic EPC bulk zip; UCL PPD-EPC link 1995-2023 | EPC match about 94% for sales near sites |
| Planning, England | MHCLG PS1/PS2 to 2026Q2; Live Tables 122, 253, 253a, PDR1 (unused) | Panel on 2025 LPAs: `panel_lpa2025_quarter.csv` |
| Planning, Wales | DMQS, 25 LPAs, 2016Q1-2026Q1 | `wales_dmqs_lpa_quarter.csv` |
| Planning, Scotland | Planning statistics 2019/20-2025; PlanIt for border councils | Major = 50+ dwellings |
| Land cover / habitat | Living England 2022-23; UKCEH LCM2021 and LCM2025 (GB); LIFE rasters (coarse) | Distinctiveness crosswalks in `Planning/code/*_crosswalk.csv` |
| Controls | IoD 2025; flood zones; Green Belt; nutrient-neutrality list and catchments; Wales phosphate catchments; LAD, national parks, National Character Areas | |
| Land ownership | HMLR CCOD; Companies House; INSPIRE (10 border LAs) | Not yet used |
| Birds | BBS 1994-2024 (not yet read); eBird re-requested 26 Nov | |

**Gaps to resolve**
- **Price Paid before 2018 is not downloaded.** The Nov proposal says January 2015: check which is right before using longer pre-trends.
- **Agricultural Land Classification** is listed as a covariate in the proposal but is not in the folder.
- **Data to request:**
  - Duffus et al.: about 1,700 habitat parcels, 234 unit sales, 76 development boundaries.
  - Unit transaction prices.
  - First-seen dates from the Wildlife Trusts' gain-site map (these would measure the listing lag).

---

## 4. Demand results (gain sites → nearby prices; Oct 2026, 404-row register)

**Design.** Staggered DiD around each site's registration date.
- Treated: sales within 1 km after registration.
- Controls: farther sales near the same site, plus not-yet-registered sites (as in zu Ermgassen et al. 2023).
- Fixed effects: site, and LA × quarter. EPC hedonic controls. SEs clustered by site.
- Outer-ring definition: TODO, confirm from the old scripts.

| Specification | Sites | Estimate | 95% CI |
|---|---|---|---|
| Ring design (urban fringe) | 72 | +0.1% | [−1.4, +1.7] |
| Later sites as controls | 156 | +0.8% | [−1.2, +2.8] |
| Synthetic DiD | 64 | −0.3% | [−2.2, +1.5] |
| EPC hedonic controls | – | +0.4% | [−1.0, +1.8] |
| Price per m² | – | +0.4% | [−1.1, +1.9] |
| Works start date as treatment | – | +0.4% (+0.36%: confirm) | [−1.3, +2.1] |

**Precision.** MDE ≈ 2.2%. Approximate equivalence tests reject ±3% in every specification. Exact TOST output: TODO.

**Design checks**
- Pre-trends: p = 0.24.
- Fake dates two years earlier, and shuffled dates: null.
- Placebo sites on open land reject 5.2% of the time (correct size); postcode-centred placebos reject about 20%.
- No change in sales volume or in the mix of homes sold.

**Descriptive findings**
- 13.5% of people within 1 km of a gain site live in England's most deprived 30% of areas, against 30.9% elsewhere.
- Before BNG, homes within 500 m of future sites already sold at about +6%: site selection is not random.
- Only about 46 of 404 sites had enough nearby sales in the earliest pilot. Sites cluster at the urban fringe.

**Treatment-date caveat.** The reference date is the submission date; public listing comes later, by an unknown lag. This biases estimates towards zero. Repeated register pulls can measure the lag.

---

## 5. Supply results

**Pilot 1, national series (descriptive; 2 Nov)**
- Dwelling grant rates, pre → post BNG:
  - major 80.0 → 84.5%
  - minor 71.5 → 74.6%
  - householder (exempt) 89.7 → 90.3%
- No visible rush of decisions before the deadlines. The Apr 2025 fee rise does show a rush, so the method can detect one.
- Minor-dwelling decisions fell 13-19% year on year in 2024Q3-2025Q2: the only volume break aligned with BNG.
- Major-dwelling decisions have fallen steadily since 2019 (7,249 a year → 4,313 in 2025).
- Householder applications are a weak national control (near-zero correlation with dwelling shocks; 2021 boom).

**Border designs (6 Nov).** RDiT around 2 Apr 2024 and an England-Scotland diff-in-disc (Northumberland vs Scottish Borders): **inconclusive because of power**, not a clean null.

**PlanIt refresh (3 Nov).** Resolved only 2 of 1,105 stale "Undecided" records. Scottish Borders 2024Q4-2025Q1 needs worst/best-case bounds.

**BNG intensity DiD, within England (6 Nov; main supply design)**
- Specification: `y_it = a_i + l_t + β(I_i × Post_t)`, with I standardised and SEs clustered by LPA.
- Post = 2024Q3-2026Q2; 2023Q4-2024Q2 dropped.
- Main sample: non-urban councils (fringe ratio ≥ 1, no London, no national parks).

| Check | log dwelling decisions | grant rate | householder (placebo) |
|---|---|---|---|
| Baseline | +0.036 (p .04) | +0.008 (p .20) | +0.010 (p .16) |
| All councils | +0.003 | +0.011 (p .03) | **+0.025 (p .001)** |
| Region × quarter FE | +0.042 (p .07) | +0.018 (p .01) | +0.005 |
| Pre-fitted LPA trends removed | +0.029 (p .14) | +0.015 (p .03) | +0.006 |
| Placebo Post 2021-23 | +0.014 | −0.007 | +0.003 |
| NN share × quarter | +0.038 (p .03) | +0.007 | +0.011 |

Reading:
- **No sign BNG reduced dwelling decisions.** The small positive estimates likely reflect high-intensity councils catching up since 2016-21.
- **The grant-rate effect (+1.7-1.8 pp per SD) appears only with region × quarter FE.** It is consistent with selection (weaker schemes screened out), but fragile: this is decision 1 for Ben.
- The householder placebo fails once urban councils are included, which supports excluding them.
- Still outstanding: an applications-by-type outcome (tests "fewer schemes come forward" directly); SEs in the de-trended check ignore the first-step estimation.

**England-Wales triple difference (6 Nov).** 178 English + 21 Welsh councils; LCM2021 intensity.
- Dwelling decisions δ = +0.017 (se .036).
- Grant rate δ = −0.032 (se .016), mostly driven by Wales; it matches the fake-2021 placebo.
- Householder placebo +0.040 (se .018): **fails**.

**SDID, England vs 21 Welsh donors (17 Nov)**
- Grant-rate τ = +0.017 (SE 0.013); plain DiD +0.062; MDE 3.7 pp.
- Placebo in time: +0.039 (larger than the main estimate).
- Householder log decisions −0.034 (SE 0.016).
- **Verdict: Low.** Welsh grant rates fell from about 80% to 65% over 2016-23 while England stayed near 75%: a divergence no weighting removes. **Wales is not a usable donor pool for planning outcomes.** This is a property of the comparison group, not of the estimator.

---

## 6. Validation targets for the rebuild

Reproduce these first, from raw data, with new code:
1. Clean register: 424 unique sites (6 Nov), split by source as 414 / 8 / 2. The October file has 402 sites (404 rows).
2. England panel: 306 LPAs on 2025 boundaries, 2015Q1-2026Q2. Wales: 25 LPAs, 2016Q1-2026Q1.
3. Pilot 1 grant rates in section 5.
4. Intensity DiD baseline: log dwelling decisions β = 0.0361, SE 0.0177 (hand-recomputed). Top vs bottom tercile 2×2 DiD = 0.0541.
5. SDID: DiD special case 0.061973; SDID τ 0.017323.
6. Demand: the gain-site estimates in section 4, within rounding, on the 404-row file.

---

## 7. Next steps (proposed 18 Nov; confirm with Lucas)

1. **Supply:** rebuild the within-England intensity design. Decide the region × quarter question. Add applications by type and composition (major/minor; brownfield share if obtainable). Cross-check intensity against eBird pre-2022 effort-adjusted richness, using a checklist-level FE model with complete checklists only.
2. **Demand (a):** rerun the gain-site DiD on 424 sites with doubly robust Callaway-Sant'Anna. Use baseline habitat and selection covariates. Report TOST against ±3%.
3. **Demand (b):** England-Wales prices by intensity. Pass a fake-date placebo and a hold-out pre-trend test *before* committing.
   - Exclude new builds (estimate them separately).
   - Drop quarters around the Apr 2025 stamp duty change.
   - Robustness: drop high-second-home Welsh councils.
   - Use wild cluster bootstrap.
4. **Measure s:** match register allocations (LPA, planning reference) to planning data. This gives the share of BNG-liable developments buying off-site at all, a bound on *s*.
5. **Selection:** conditional logit of registration on land grade, LIFE, distance to urban areas, deprivation, pre-BNG prices and eBird.
6. **Later:** bunching below the 0.2 ha exemption (Aug 2026); land values near permitted vs unpermitted sites (P5); CCOD corporate land purchases.
7. **Duffus data, if obtained:**
   - Split sites into creation vs enhancement (mechanism for the price null).
   - 38% of units bought within the same LPA and 26% from a neighbouring one; 70% of buying developments are under 1 ha.
   - Their 234 sales are an independent check on the register scrape.

---

## 8. Key literature (all in the project reading folder unless noted)

| Paper | Relevance |
|---|---|
| Mancini et al. 2024, One Earth (Ben co-author) | Offset allocation scenarios |
| Faccioli et al. 2024/25, AJAE | Stated preferences on who should benefit; WTP rises with access |
| Duffus et al. 2025 (bioRxiv) | The offset market so far |
| zu Ermgassen et al. 2021 | Conservation Letters; early-adopter outcomes; the *s* ≈ 95% estimate |
| zu Ermgassen et al. 2023 | Global Change Biology; not-yet-treated controls |
| Gibbons, Mourato and Resende 2014 | Amenity premiums by habitat |
| Simpson, Hanley et al. 2021 | Q Open; offset market |
| Hilber and Vermeulen 2016 | EJ; supply constraints |
| Koetter, Winter and Woebbeking 2025 | Price and quantity framework |
| Callaway and Sant'Anna 2021; Arkhangelsky et al. 2021 | Estimators |
| Lakens 2017 | Equivalence tests |
| Tingley et al. 2025 | LEEP synthesis |

Verify every citation before it goes into the write-up.
