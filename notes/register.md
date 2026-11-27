# Gain Site Register: clean site file (validation target 1)

Script: `src/register.py`. Tests: `tests/test_register.py`.

## Part A: pre-specification (written 26 Nov 2026, before running)

**Purpose.** One row per biodiversity gain site for each register pull, plus a long
table of the developments allocated to each site. Every later design uses this file
(demand DiD treatment dates and locations; the bound on *s*; selection model).

**Inputs** (read-only, `RAW_ROOT/RawData-BNG/<pull>/`):
- `bng_sites_raw.json`: paginated `/bng/api/all` download.
- `bng_sites_by_reference.json`: sites the paginated API counted but did not serve,
  fetched one by one from `/bng/api/search/<ref>` (6 Nov pull only).
- `bng_site_<ref>_from_browser.json`: `/search/<ref>` responses copied from the browser
  for sites the endpoint refuses to scripts (6 Nov pull only).
- `download_meta.json`: the API's own record count (6 Nov pull only).

**Decision rules**
1. Unit = base reference (`BGS-DDMMYY###`, the text before any `" - <timestamp>"` suffix).
2. Duplicate versions of one site in the paginated file: keep the record **without** the
   timestamp suffix, after checking that the two agree on site size, grid reference and
   status. If they disagree, stop. (Observed before running: the timestamped copy has no
   allocations and no amendment history, so it is a partial snapshot.)
   This differs in wording from the old script (latest amendment, then timestamped form),
   but should pick the same record in both observed cases; check C7 confirms.
3. Source precedence: paginated API, then `/search/<ref>`, then browser copy. A site is
   never taken from a lower source if a higher one has it.
4. `/search/<ref>` records have no status field: status = Registered if `removalDate` is
   empty, else Internally Removed, with `status_inferred = True`.
5. **No carry-forward from earlier pulls.** The old script filled any site still missing
   from the previous pull. The new one stops with an error instead, so that a gap is
   seen and decided, not filled silently.
6. Internally Removed sites are **kept**, with their status; each design decides whether
   to drop them.
7. Coordinates: OS grid reference to British National Grid at the **centre** of the square
   it describes; `gr_digits` records the precision (6 digits = 100 m, 8 = 10 m, 10 = 1 m...).
   Written fresh from the OS lettering scheme, not ported from the old code.
8. `ref_date` = date encoded in the reference = date the registration application was
   submitted (Natural England), not the public listing date.

**Checks (all must pass, else stop and explain)**
- C1 Reconciliation (6 Nov): paginated records + `/search/<ref>` + browser copies
  = `api_total_count` in `download_meta.json`.
- C2 Counts: 6 Nov = **424** unique sites, split 414 / 8 / 2 by source.
  12 Oct = **402** unique sites from **404** records.
- C3 Duplicate pairs agree on size, grid reference and status (rule 2).
- C4 No base reference appears in more than one source after precedence.
- C5 Every base reference matches `BGS-\d{9}` and its date parses.
- C6 Every non-empty grid reference parses, and the point lies inside the English part of
  the GB grid bounding box (E 80,000-660,000; N 0-660,000). Empty grid references are
  listed. Full point-in-England test with the LAD boundaries waits for geopandas.
- C7 Against the old processed files (`ProcessedData/bng/bng_sites_clean_<date>.csv`):
  same set of sites, and identical reference date, works start, status, size, easting,
  northing, number of allocations and created area. Any difference is listed and
  explained before the file is used.
- C8 Allocation table rows = sum of `n_alloc`. Created-habitat areas all in hectares.
- C9 Unit tests for the grid conversion against hand-computed squares.

**Reported, not tested:** date ranges; median gap from works start to registration
(FINDINGS says about 11 months); allocations with no planning reference.

## Part B: results (26 Nov 2026)

**Validation target 1 reproduced exactly.**

| Check | 6 Nov 2026 | 12 Oct 2026 |
|---|---|---|
| C1 records = API count | 415 + 8 + 2 = 425 = `api_total_count` | no metadata file |
| C2 unique sites | **424** (414 / 8 / 2) | **402** from 404 records |
| C3 duplicate versions dropped | BGS-140125001 (timestamped copy) | BGS-260226001, BGS-050825004 |
| C4-C6, C8 | pass | pass |
| C7 vs pilot file | same 424 sites; 0 differences in all 10 fields | same 402 sites; 0 differences |
| C9 unit tests | 16 pass | |

Allocations: 3,437 rows on 261 sites (6 Nov); 3,144 rows on 239 sites (12 Oct). All have
a planning reference, which is what the bound on *s* needs.

**Deviation.** The first run failed 5 of 16 unit tests: the parser rejected grid
references with letters only (e.g. `SU`), which the tests and the old code treat as the
centre of the 100 km square. None occur in the register. Fixed by allowing them
(`gr_digits = 0` flags them). The site data were unaffected; the rerun is identical.

**Facts for later designs**
- **423 usable sites**, not 424: BGS-201225002 is Internally Removed (11 Sep 2026), with
  no grid reference and size 0. It is in both pulls.
- Location precision: 201 sites to 1 m, 66 to 10 m, 154 to 100 m, **2 only to 1 km**
  (BGS-190226001 `SU9986`, BGS-201125001 `SE3441`). A 1 km square is as wide as the
  treatment ring in the demand DiD: drop or test sensitivity to these two.
- Reference dates run from 29 Feb 2024 to 22 Oct 2026.
- Works start is recorded for only **167 of 424** sites. Where it is, the median gap to
  registration is 329 days (about 11 months, as in FINDINGS), IQR 122-618. One site
  (BGS-121125001) starts works 19 days *after* its reference date. A works-start
  treatment date therefore covers under 40% of sites.
- The 10 sites the paginated API withheld on 6 Nov were all present on 12 Oct; their
  status is inferred from the removal date (all Registered).
- **For validation target 6:** the demand pilot used the 404-row October file
  (`ProcessedData/bng/bng_sites_clean.csv`, before deduplication), so two sites
  (BGS-260226001, BGS-050825004) were counted twice there. Reproduce on that file first,
  then rerun on this one and report the difference.
