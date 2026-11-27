# Planning panels on 2025 LPAs (validation target 2)

Script: `src/planning_panel.py`.

## Part A: pre-specification (written 26 Nov 2026, before running)

**Purpose.** An LPA x quarter panel of planning applications and decisions on one fixed
set of authorities, for the within-England BNG intensity DiD (supply, RQ1). In the toy
model it measures *H* through decisions (quantity) and the grant rate (selection).

### England (MHCLG PS1/PS2, release to June 2026)

**Inputs** (read-only, `RawData-Planning/2026-10-29_MHCLG/`): `PS1_data_-_open_data_table__202606_.csv`
(applications received/decided) and `PS2_..._202606_.csv` (decisions by development type).
Unit list: English codes in `RawData-BNG/LAD_MAY_2025_UK_BGC_V2_*.gpkg` (attribute table
read with the standard-library `sqlite3`, since a GeoPackage is a SQLite file), plus the
10 national park authorities (`E26`).

**Decision rules**
1. Header row = the row whose first cell is `Region` (found, not hard-coded); encoding
   cp1252; `..` = missing.
2. Quarters **2015 Q1 to 2026 Q2** (46). Before 2015 the files contain duplicate
   LPA-quarter rows.
3. Variables: the 17 used in the pilot (received and decided in PS1; total, major
   dwellings, minor dwellings and householder decisions, grants, PA decisions and
   26+ week decisions in PS2), all "(all)" columns.
4. Councils merged in 2019-23 are summed into their 2025 successor (11 successors,
   listed in the script). Somerset West and Taunton (2019-23) and its two predecessors
   all map to Somerset (2023).
5. Development corporations (`E51`) are dropped: they have no boundary in the unit list.
   Their host councils are flagged (`dc_note`), because the hosts' series break when a
   corporation takes over part of their area.
6. **Strict missing rule.** If any predecessor is missing a value in a quarter, the
   unit's sum is missing for that variable (no partial sums). The pilot used partial sums
   (`min_count=1`); any cells this changes are listed in Part B.
7. PS1 and PS2 are joined on code x quarter; rows in one file but not the other are listed.

**Checks (all must pass, else stop and explain)**
- E1 46 quarters; no duplicate code x quarter rows from 2015 Q1.
- E2 Every code from 2015 is a 2025 council, a predecessor in the merger table, a national
  park or a development corporation. Nothing else.
- E3 Clean handover: for each merged unit, every predecessor's last quarter is the quarter
  before the successor's first, and no quarter has both.
- E4 Output is balanced: **306 units** (296 councils + 10 parks) x 46 quarters = 14,076 rows.
- E5 Conservation: for every variable and quarter, the England total after aggregation
  equals the total of the raw rows minus the development-corporation rows.
- E6 Logic: granted <= decisions in each category; no negative counts.
- E7 Against the pilot file `ProcessedData/planning/panel_lpa2025_quarter.csv`: same unit x
  quarter cells and identical values in all 17 variables, apart from cells changed by rule 6.

**Reported, not tested:** missing cells by variable and quarter; decisions dropped with the
development corporations; national grant rates for major, minor and householder (feeds
validation target 3).

### Wales (DMQS, 25 LPAs, 2016 Q1 to 2026 Q1)

*Written 26 Nov 2026, after a read-only survey of the files and before building.*

**Inputs** (read-only, `RawData-Planning/2026-10-29_Wales_DMQS/`): 36 quarterly `.ods`
releases, Jan-Mar 2017 to Jan-Mar 2026. Each has a hidden `Data` sheet with 25 authorities
(22 councils + 3 national park authorities) x 5 financial-year quarters, then footer rows.
The Oct-Dec 2022 release was never published as ODS (manifest: "no ODS link"); its
quarters are all in later releases. The manifest marks Apr-Jun 2017 as a download error,
but the file is present and has the same layout as the others. (The pilot script's
docstring says 37 releases; the folder has 36.)

**Decision rules**
1. Data rows = rows whose `Year` looks like `2016-17` and `Quarter` like `Q1`; footer
   rows are dropped.
2. Financial to calendar quarter: FY Q1 (Apr-Jun) = calendar Q2 of the first year;
   FY Q4 (Jan-Mar) = calendar Q1 of the second year. So Q1 2016-17 = 2016 Q2, and
   Q4 2025-26 = 2026 Q1.
3. A quarter appears in up to five releases. **The latest release wins**, because it
   carries any revisions. Revisions are counted and reported.
4. Variables: the 13 used in the pilot, with DMQS names kept (Dtrm = decided, Appd =
   granted, Refd = refused, Recd = received; MajDw = major dwellings, MinDw = minor
   dwellings, MinHou = householder).
5. Councils get their 2025 LAD code by matching names to the May 2025 boundary file.
   National park authorities have no LAD code and keep their DMQS name.

**Checks (all must pass, else stop and explain)**
- W1 36 releases; each has 125 data rows (25 authorities x 5 quarters) and all 13 variables.
- W2 Balanced output: **25 authorities x 41 quarters (2016 Q1-2026 Q1) = 1,025 rows**.
- W3 Unit tests for the quarter conversion (rule 2).
- W4 No negatives; granted <= decided for major, minor and householder. (Granted +
  refused = decided is reported, not tested: other outcomes may exist.)
- W5 All 22 councils match a Welsh LAD code, one to one.
- W6 Against the pilot file `ProcessedData/planning/wales_dmqs_lpa_quarter.csv`: same
  authority x quarter cells and identical values in all 13 variables.

**Reported, not tested:** cells revised between releases; missing values; Welsh grant
rates by year.

## Part B: results (26 Nov 2026)

### England: validation target 2 reproduced exactly

| Check | Result |
|---|---|
| E1 quarters, duplicates | 46 quarters (2015 Q1-2026 Q2); no duplicates |
| E2 codes | all codes are 2025 councils, merger predecessors, 10 parks or 5 development corporations |
| E3 handover | every predecessor ends the quarter before its successor starts |
| E4 balance | **306 units** (296 councils + 10 parks) x 46 = 14,076 rows |
| E5 conservation | England totals identical before and after aggregation, all 17 variables |
| E6 logic | no negatives; granted <= decisions everywhere |
| E7 vs pilot | same 14,076 cells; **0 differing values** in all 17 variables |
| PS1/PS2 join | every row in both files |

- The strict missing rule (rule 6) changed **no cells**: no predecessor is ever missing a
  value in a quarter its successor sums. The pilot's partial sums are therefore harmless.
- One missing cell in the whole panel: `received_total` for Windsor and Maidenhead,
  2015 Q3 (decisions are present). Not an outcome in the main design.
- Development corporations: 155 rows dropped, holding 0.20% of major and 0.01% of minor
  dwelling decisions. 11 host councils flagged. The LLDC note reads "2015 Q1 to 2024 Q4"
  because the panel starts in 2015; the corporation itself started in 2012.
- **Deviation (code only):** the first run crashed in the E7 comparison because the pilot
  file has both `code2025` and `code` columns. Fixed by keeping `code2025`. The build
  itself and checks E1-E6 had already passed; the outputs are unchanged.

National grant rates by calendar year (input to validation target 3):

| % | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 H1 |
|---|---|---|---|---|---|---|---|---|
| Major dwellings | 81.9 | 81.7 | 82.1 | 80.6 | 79.1 | 81.0 | 84.3 | 84.6 |
| Minor dwellings | 73.3 | 72.8 | 73.2 | 72.1 | 70.5 | 71.3 | 74.6 | 74.4 |
| Householder | 90.5 | 90.3 | 90.8 | 89.9 | 88.9 | 88.8 | 90.0 | 90.8 |

### Wales: validation target 2 reproduced exactly

Built in the `bng-diss` conda environment (`environment.yml`). Targets 1 and the England
panel were rerun in it first: all outputs byte-identical to the earlier runs.

| Check | Result |
|---|---|
| W1 releases | 36, each 125 data rows with all 13 variables |
| W2 balance | **25 authorities x 41 quarters (2016 Q1-2026 Q1) = 1,025 rows** |
| W3 unit tests | quarter conversion and release order: pass (23 tests in total) |
| W4 logic | no negatives; granted <= decided everywhere |
| W5 codes | all 22 councils matched to a 2025 LAD code |
| W6 vs pilot | same 1,025 cells; **0 differing values**; every cell from the same release |

- Revisions between releases are rare: 1 to 5 cells per variable over the whole panel.
- One pilot cell held the DMQS text marker `-` (`RecdTot`); both builds treat it as missing.
- **Deviation (code only):** the first W6 comparison crashed on that text value. Fixed by
  reading the pilot file as numbers; the build and W1-W5 had already passed.
- Granted + refused != decided in 18 (major) and 17 (minor) rows: exactly the rows where a
  value is missing. Where all three are present, the identity holds.

**Missing data that matter for any Wales design** (17-18 cells per variable):
- **Denbighshire: 2024 Q2 to 2026 Q1, the whole post-BNG window.** It contributes
  nothing after BNG and must be dropped or bounded in any England-Wales comparison.
- Snowdonia NPA: 2022 Q3, 2023 Q2, 2024 Q2-Q4.
- Newport 2021 Q3-Q4; Carmarthenshire 2021 Q3; Flintshire 2022 Q4; Blaenau Gwent 2021 Q3
  (one variable).

Welsh grant rates by calendar year (%), for comparison with England:

| | 2016 | 2018 | 2020 | 2022 | 2023 | 2024 | 2025 | 2026 Q1 |
|---|---|---|---|---|---|---|---|---|
| Major dwellings | 80.7 | 85.3 | 87.7 | 81.9 | 85.0 | 87.4 | 81.5 | 89.2 |
| Minor dwellings | 80.3 | 77.3 | 73.1 | 72.4 | 67.8 | 71.3 | 72.0 | 65.2 |
| Householder | 93.7 | 92.4 | 91.1 | 89.6 | 89.0 | 88.5 | 90.8 | 89.2 |

The minor-dwelling fall from about 80% to 68% over 2016-23, while England stayed near
72-74%, is the divergence behind the SDID "Low" verdict (FINDINGS section 5).
