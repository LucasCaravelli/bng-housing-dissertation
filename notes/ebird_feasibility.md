# eBird: can it say anything about BNG and biodiversity? (feasibility count)

Script: `src/ebird_counts.py`. Input: `Dissertation/ebd_GB_201501_202610_smp_relOct-2026.zip`
(eBird Basic Dataset, GB, Jan 2015-Oct 2026, release Oct 2026), checklist file only
(`*_sampling.txt`, 0.9 GB), streamed from the zip. The 21 GB observations file is not read
at this stage. Licence: research use with citation; no redistribution, so nothing derived at
checklist level goes into git.

## Part A: pre-specification (written 27 Nov 2026, before counting)

**Purpose.** Decide, from checklist counts only (no bird data), which of three uses the data
can support. Nothing about species is computed here, so no outcome is seen before designs are
specified.

**Usable checklist (eBird best-practice filters; Johnston et al. 2021, Diversity and
Distributions, TODO: verify reference):** complete ("all species reported" = 1); protocol
Stationary or Traveling; duration 5 min to 5 h; distance <= 5 km (traveling); <= 10 observers;
shared checklists counted once (one per group identifier). Located in England (on the 50 m
unit grid). Location = the checklist point (traveling lists start there; their true area is
larger, a known limitation).

**Counts.**
- Per gain site (6 Nov register, 423 sites), complete checklists within 0-500 m and 0-1 km of
  the implied edge, and 2-4 km, by half-year 2015H1-2026H2.
- Per planning unit, complete checklists 2015-2021 in the 0-500 m developable fringe zone
  (the intensity score's zone), and overall.

**Decision rules (fixed now)**
- *Use 1, selection/additionality (were gain sites already bird-rich?):* feasible if at least
  100 sites have >= 10 usable checklists within 1 km in 2018-2023.
- *Use 2, intensity cross-check (does the score track pre-BNG bird richness?):* feasible if at
  least 150 of the 205 main-sample councils have >= 100 usable checklists in their 0-500 m
  fringe zone in 2015-2021.
- *Use 3, impact (stacked DiD on richness near sites):* a treated site (registered 2024H1-2025H2)
  is "usable" if it has >= 3 usable checklists within 1 km in each of the 4 half-years before
  registration and in at least one half-year after. Feasible only if >= 50 sites are usable.
  Even then it is exploratory (at most 2.5 years after registration, while habitat is still
  being created), and must come with an effort placebo (checklist counts as the outcome).
- Each use, if feasible, gets its own Part A before any species data are read.

## Part B: results (27 Nov 2026)

**Checklists.** 3,568,099 GB checklists read (2015-01 to 2026-10); 1,971,277 pass the filters;
1,846,115 after counting shared lists once; **1,429,108 usable in England**. No species data
read. The zip sits at the top of the Dissertation folder, not in a dated raw-data folder
(note for Lucas).

| Use | Rule | Count | Verdict |
|---|---|---|---|
| 1 Selection / additionality | >= 100 sites with >= 10 checklists within 1 km, 2018-23 | **124** of 423 | **Feasible** |
| 2 Intensity cross-check | >= 150 of 205 councils with >= 100 fringe-zone checklists, 2015-21 | 128 | Not feasible (as pre-set) |
| 3 Impact near gain sites | >= 50 treated sites with >= 3 checklists in each of 4 pre half-years and >= 1 post | **26** of 225 | **Not feasible** |

**Coverage detail.**
- Within 1 km of a site, 2018-23: median **2** checklists per site; 134 sites have none; upper
  quartile 12, top decile 47. Within 2-4 km the median is 68, so the birders are nearby but
  rarely on or next to gain sites (mostly farmland).
- Treated 2024-25 sites: median 1 checklist within 1 km in the 2 years before registration,
  3 after; 153 of 225 have at least one post-registration checklist.
- Council fringe zones 2015-21: median 147 checklists; lower quartile 52; 159 councils have
  >= 50; 191 have >= 100 when the whole council is counted.

**Reading and recommendation.**
- *No impact estimate is possible from eBird.* Coverage on and next to gain sites is far too
  thin (26 usable sites, a median of one checklist in two pre-years), before even considering
  that habitat created in 2024-26 would barely have started to change. This confirms the
  earlier plan of not using eBird as an outcome. Saying so, with these counts, is itself a
  useful paragraph for the write-up (data limits of citizen science for evaluating offsets).
- *Use 1 is feasible but on a selected subset.* The 124 well-birded sites are not typical
  (likely near towns, reserves or footpaths). A pre-registration comparison of their
  effort-adjusted richness with nearby open land of similar observer effort would describe
  whether gain sites start out bird-rich (additionality, rho in the toy model), for those
  sites only. It needs its own Part A, and the species file (21 GB, streamed).
- *Use 2 fails the pre-set rule (128 < 150).* Lowering the threshold to 50 checklists would
  give 159 councils, or counting the whole council would give 191, but either is a change
  after seeing the counts and must be recorded as a deviation. Lucas's call; it is not done.
