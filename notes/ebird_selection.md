# Were gain sites already bird-rich? (eBird, selection / additionality)

Scripts: `src/ebird_species.py` (species per checklist, streamed), `src/ebird_selection.py`.
Feasibility: `notes/ebird_feasibility.md` (use 1: feasible on 124 sites).

## Part A: pre-specification (written 27 Nov 2026, before any species data are read)

**Question.** Before BNG, was the land around future gain sites richer in birds than its
wider surroundings, for the same observer effort? Model link (FINDINGS 2, RQ3): additionality
and rho. If offsets go onto land that is already bird-rich, the measured gain overstates the
change (less additional); if onto poor farmland, there is more room for real gains. This is a
descriptive comparison of places, not a causal estimate.

**Sample.**
- Checklists: the usable complete checklists of the feasibility step (complete; stationary or
  traveling; 5 min-5 h; <= 5 km; <= 10 observers; shared lists once), dated **2015-01 to
  2023-12**. That is before mandatory BNG and before every site's reference date (earliest
  29 Feb 2024), so no checklist can reflect registration or works.
- Rings around each site's implied edge: **inner 0-1 km** vs **outer 2-4 km** (1-2 km dropped
  as a buffer, as in the price designs). Stacked: one row per site x checklist; a checklist
  near two sites appears in both stacks.
- Sites, main: the **124 sites** with >= 10 inner checklists in 2018-23 (selected on observer
  effort only, never on birds). Robustness: every site with >= 1 inner and >= 1 outer checklist.

**Outcome.** Species richness of the checklist: distinct species, counting category "species"
and "issf" (subspecies groups, collapsed to species by the first two words of the scientific
name); excluding spuhs, slashes, hybrids, domestics and escapees (exotic code "X"); approved
records only. Secondary: number of the 19 Farmland Bird Index species recorded (Defra's
England farmland indicator; species list TODO: verify against Defra's current definition).

**Model.** Poisson pseudo-maximum likelihood (richness is a count):

    E[richness_cs] = exp( a_site + beta x Inner_cs + effort_c + month_c + year_c )

effort = log duration, log(1 + distance km), observer-number bins (1, 2, 3+), traveling
dummy, start-hour bins (before 08:00, 08-11, 11-15, 15+, missing). SEs clustered by site.
beta = log ratio of expected richness, inner vs outer, same site and same effort.
Second route: statsmodels GLM Poisson with explicit dummies (main spec); must agree to 1e-6.

**Reported, all of them.** (1) main; (2) without effort controls (to show how much effort
differences matter); (3) inner 0-500 m only vs 2-4 km; (4) all sites with any checklist in
both rings; (5) Farmland Bird Index species as the outcome. Also descriptive: mean effort
(duration, distance, observers) inner vs outer.

**Reading rules (fixed now).** beta > 0 and significant at 5%: land near future gain sites was
already richer than its surroundings, at the same effort (selection on existing value).
beta < 0 and significant: poorer (more scope for additional gains). Otherwise: no evidence
of selection on bird richness. A 95% interval inside +/-5% (log points +/-0.049) is read as
"similar", outside it as inconclusive.

**Threats, stated before seeing results.** Birders choose where to go, so inner checklists may
sit at reserves or rivers that happen to lie near a site (effort FE do not remove choice of
place); the 124 well-surveyed sites are not representative (likely near towns and paths);
traveling checklists are placed at their start point; the outer ring includes towns, which
lowers its richness for reasons that are not about the site's land.

## Part B: results (27 Nov 2026)

**Data.** 100,914 usable complete checklists 2015-2023 within 0-1 km or 2-4 km of a site
(114,196 site x checklist pairs); 55.8 million observation rows streamed; 391 species; mean
richness 21.0. All 19 Farmland Bird Index names were found in the data. Main sample: the same
124 sites as in the feasibility count. No deviations from Part A.

**Effort is balanced across rings** (main sample, means): duration 68.8 vs 68.6 min, distance
1.42 vs 1.35 km, observers 1.36 vs 1.36, traveling 74% vs 71% (0-1 km vs 2-4 km). Raw means:
richness 21.97 vs 19.67; FBI species 4.27 vs 3.83.

**Second route.** statsmodels GLM Poisson with explicit dummies = pyfixest PPML (|diff| 6e-13).

| Spec | beta (log points) | SE | % (95% CI) | Sites | Reading (pre-set rules) |
|---|---|---|---|---|---|
| 1 Main: richness, 0-1 km vs 2-4 km | +0.060 | 0.049 | **+6.2% (-3.4% to +16.8%)** | 124 | inconclusive |
| 2 No effort controls | +0.062 | 0.052 | +6.4% (-3.9% to +17.7%) | 124 | inconclusive |
| 3 0-500 m vs 2-4 km | +0.112 | 0.075 | +11.9% (-3.3% to +29.5%) | 124 | inconclusive |
| 4 All sites with lists in both rings | +0.054 | 0.047 | +5.5% (-3.8% to +15.7%) | 298 | inconclusive |
| 5 Farmland Bird Index species | +0.137 | 0.054 | **+14.7% (+3.2% to +27.4%)** | 124 | richer near future sites |

**Reading.**
- *Overall species richness:* checklists next to future gain sites record about 6% more
  species than checklists 2-4 km away, at the same effort, but the interval (-3% to +17%)
  includes zero and is too wide to call the places "similar". By the pre-set rule:
  inconclusive. The point estimate rises closer to the site (0-500 m: +12%), also insignificant.
- *Farmland birds:* the land around future gain sites held about 15% more Farmland Bird Index
  species before BNG (95% CI +3% to +27%). That is the one rule-based "richer" result. Two
  caveats, both stated in Part A: (i) the outer ring includes towns, where farmland birds
  are absent for land-use reasons, so part of this is simply "gain sites sit in farmland";
  (ii) it is one of five pre-specified comparisons (p about 0.011, just above a Bonferroni
  0.05/5 = 0.010 threshold), so it should be reported as suggestive.
- *What it means for additionality (rho).* Future gain sites are not in visibly bird-poor
  places; if anything they sit in farmland that already supports farmland birds. Creating
  or enhancing grassland there could benefit those species (or, for open-field species like
  skylark and lapwing, change their habitat), but the baseline is not empty. Consistent with
  Duffus et al.'s picture (offsets mostly on farmland, grassland enhancement), not evidence
  that offsets are non-additional.
- *Limits.* Well-surveyed sites only (124 of 423; 298 in spec 4 give the same answer);
  birders choose where to go; traveling checklists placed at their start; descriptive only.
  A sharper test would compare future gain sites with nearby open-land placebo points of the
  same land cover, which would separate "farmland" from "chosen land"; not run.
