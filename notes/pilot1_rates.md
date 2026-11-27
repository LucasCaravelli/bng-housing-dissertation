# Pilot 1 national grant rates (validation target 3)

Script: `src/pilot1_rates.py`. Input: the England panel from `src/planning_panel.py`.

## Part A: pre-specification (written 26 Nov 2026, before running)

**Purpose.** Reproduce the descriptive national grant rates in FINDINGS section 5. In the
toy model a rising grant rate with falling applications is the selection reading (weaker
schemes screened out before submission); this series is descriptive only, with no
counterfactual.

**Targets** (`Planning/output/pilot1/pilot1_summary.txt`, section C):

| % granted | pre | post |
|---|---|---|
| Major dwellings | 80.0 | 84.5 |
| Minor dwellings | 71.5 | 74.6 |
| Householder (BNG-exempt) | 89.7 | 90.3 |

**Definitions, taken from the pilot script (`Planning/code/01_pilot1_series.py`)** and not
previously recorded in FINDINGS:
- Pre = **2022 Q1-2023 Q2**; post = **2025 Q1-2026 Q2**. Also reported: anticipation
  2023 Q3-2024 Q1 and transition 2024 Q2-2024 Q4.
- Quarterly national rate = England granted / England decisions, "(all)" columns.
- Window rate = **unweighted mean of the quarterly rates**.
- England total = sum of **every** LPA row, including development corporations.

**Routes**
1. *Pilot route:* totals from the raw PS2 rows (development corporations included).
   Must reproduce the targets to 0.1 pp.
2. *Panel route:* totals from the new 306-unit panel (development corporations excluded).
   Expected to differ by at most a few hundredths of a pp (they hold 0.2% of major decisions);
   any larger gap stops the work.
3. *Pooled rate* (sum granted / sum decisions over the window), reported as a sensitivity:
   the unweighted mean gives a quiet quarter the same weight as a busy one.

**Checks**
- R1 Route 1 = targets to 0.1 pp for all six numbers (plus the four-window table).
- R2 |route 1 - route 2| < 0.1 pp in every window.
- R3 2026 Q2 England totals equal the pilot's computed figures (received 78,706; decisions
  74,484; granted 65,211; householder decisions 37,712). The pilot also lists the release's
  rounded headline figures; those are not re-checked here (TODO: verify against the release).

**Also reported, not tested** (other Pilot 1 numbers in FINDINGS section 5): minor-dwelling
decisions year on year in 2024 Q3-2025 Q2 (FINDINGS: -13 to -19%); annual major-dwelling
decisions 2019 and 2025 (FINDINGS: 7,249 and 4,313).

## Part B: results (26 Nov 2026)

**Validation target 3 reproduced.** R1, R2 and R3 pass.

| % granted | window | target | pilot route | panel route | pooled (panel) |
|---|---|---|---|---|---|
| Major | pre | 80.0 | 79.96 | 79.96 | 80.05 |
| Major | post | 84.5 | 84.45 | 84.43 | 84.43 |
| Minor | pre | 71.5 | 71.55 | 71.55 | 71.57 |
| Minor | post | 74.6 | 74.55 | 74.55 | 74.55 |
| Householder | pre | 89.7 | 89.67 | 89.67 | 89.71 |
| Householder | post | 90.3 | 90.27 | 90.27 | 90.27 |

The anticipation and transition windows also match to 0.1 pp (full table in
`data/processed/planning/pilot1_grant_rates.csv`).
- Dropping development corporations moves no rate by more than 0.033 pp.
- Mean of quarterly rates vs pooled rate: at most 0.088 pp apart, so the pilot's
  definition doesn't matter here.
- 2026 Q2 England totals equal the pilot's (78,706 received; 74,484 decisions; 65,211
  granted; 37,712 householder decisions).
- Other FINDINGS section 5 numbers reproduced: minor-dwelling decisions -12.8, -14.1,
  -19.3 and -13.6% year on year in 2024 Q3-2025 Q2 ("13-19%"); major-dwelling decisions
  7,249 in 2019 and 4,313 in 2025.

**Deviation (code only):** the first run failed on an import-order bug (`config` imported
before its folder was on the path). Fixed; no result had been produced.

**Reading (descriptive, not causal).** Pre to post, the grant rate rose 4.5 pp for major
dwellings and 3.0 pp for minor dwellings, against 0.6 pp for BNG-exempt householder
applications. Relative to householder that's +3.9 and +2.4 pp. That fits the selection
channel (fewer, stronger schemes submitted), but the post window (2025 Q1-2026 Q2) falls
entirely after the December 2024 NPPF (housing targets, grey belt), which plausibly raises
grant rates for dwellings and not householder extensions. The national series can't
separate the two; the within-England intensity DiD (target 4) is the design meant to.
The major-dwelling rise starts in 2024 Q3 (82.5%), before the NPPF, which is weak evidence
in BNG's direction and worth a quarter-by-quarter figure.
