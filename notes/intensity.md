# BNG intensity score, Living England (England only)

Scripts: `src/intensity_grid.py` (rasters), `src/intensity_score.py` (score).
Crosswalk: `inputs/le_distinctiveness_crosswalk.csv` (copied unchanged from
`Planning/code/`; Lucas's own table).

## Part A: pre-specification (written 26 Nov 2026, before running)

**Purpose.** A pre-determined, continuous treatment intensity *I_j* for the within-England
DiD (FINDINGS section 2: a proxy for *b*, habitat units lost per dwelling). BNG charges
developers for the habitat they remove; new housing goes mostly on settlement fringes;
so where fringe land is semi-natural habitat (Medium+ distinctiveness) BNG costs more per
dwelling. Cost channel: higher *I* means fewer dwelling decisions and, if weak schemes are
screened out, a higher grant rate.

**Inputs**
- Living England 2022-23 GeoPackage (`~/Diss Data/LivingEngland_2022_23/`, unzipped from
  `RawData-BNG/LivingEngland/`), class field `Prmry_H`.
- LAD May 2025 boundaries (`RawData-BNG/LAD_MAY_2025_UK_BGC_V2_*.gpkg`), English codes.
- National parks (`RawData-BNG/National_Parks_England.gpkg`); park land is its own unit,
  cut out of the host councils, as in the planning panel.
- The 306 units from `units_england_lpa2025.csv` (planning panel).

**Definitions (same as the pilot, so the rebuild can be validated)**
1. Grid: 50 m cells, British National Grid, x 82,000-656,000, y 5,000-658,000
   (11,480 x 13,060 cells). A cell takes the class of the polygon covering its centre.
2. Settlement = 8-connected patch of "Built-up Areas and Gardens" cells of at least 10 ha
   (40 cells). Sensitivity: 50 ha.
3. Zones by Euclidean distance between cell centres to the nearest settlement cell:
   0-250 m, 250-500 m, 500-1000 m, beyond. **Main zone = 0-500 m**, settlement cells excluded.
4. Developable land and distinctiveness scores from the crosswalk (`developable = 1`).
5. **Intensity = share of developable zone land with distinctiveness >= 4 (Medium+)**,
   using the `distinctiveness_main` column. Also: area-weighted mean score; `alt` column;
   0-250 and 0-1000 m zones; 50 ha settlements.
6. Fringe ratio = developable land in the 0-500 m zone / settlement area. **Main sample =
   councils outside London (not `E09`) with fringe ratio >= 1.** National parks excluded.

**Method differences from the pilot (implementation only)**
- Zones from `scipy.ndimage.distance_transform_edt` instead of OpenCV dilation with a
  disk (OpenCV is not an approved package). Both mark cells whose centre lies within
  r metres of a settlement cell centre, so they should agree cell for cell.
- Settlements labelled with `scipy.ndimage.label` (8-connectivity) instead of OpenCV.

**Checks (all must pass, else stop and explain)**
- I1 Unit tests on small synthetic grids: a 1-cell farmstead creates no zone; ring codes at
  known distances; the distance transform agrees with a brute-force disk dilation.
- I2 Rasterised class areas within 2% of polygon areas for every class covering more than
  10,000 ha (small or thin classes can lose area at 50 m; listed, not tested).
- I3 Unit raster: each cell carries at most one unit (by construction); fewer than 0.5% of
  Living England-classified cells fall outside every unit (coastline differences between
  the generalised LAD boundaries and Living England), listed by class; raster area within
  1% of the boundary-file area for every unit larger than 1,000 ha.
- I4 Every Living England class is in the crosswalk.
- I5 Against the pilot (`ProcessedData/planning/le_zone_class_counts.csv` and
  `bng_intensity_lpa2025.csv`): England totals by class and ring within 0.5%; main
  intensity correlation > 0.999 across the 306 units and max absolute difference < 0.005;
  main sample identical (205 councils). Any larger gap is explained before the score is
  used.

**Not done here (TODO).** The crosswalk scores are a judgement mapping from Living England
classes to the statutory metric; they have not been re-checked against the metric's
habitat list (TODO: verify against the Statutory Biodiversity Metric user guide).
Living England has no condition data and has known class errors (NERR141 confusion
matrices).

## Part B: results (26 Nov 2026)

**The pilot's intensity score is reproduced exactly**, by a different route (scipy distance
transform and labelling instead of OpenCV dilation).

| Check | Result |
|---|---|
| I1 unit tests | pass (5 tests; distance-transform rings = brute-force disk dilation cell for cell) |
| I2 class areas | every class within 0.1% of its polygon area (13.2 million polygons, 13 layers) |
| I3 unit raster | raster vs boundary area 0.9985-1.0028 for units > 1,000 ha; unit areas identical to the pilot's to the hectare; developable cells outside every unit 0.088% (see deviation) |
| I4 crosswalk | every Living England class present |
| I5 vs pilot | all 30,428 unit x class x ring x rule cell counts identical; all 40 score variants identical (max difference 0.0); main sample 205 councils, the same units |

Score: mean 0.477, SD 0.210, range 0.027-0.929 across 306 units. 9,136 settlements of
10 ha or more; 2,234 of 50 ha or more. Northumberland National Park has no 10 ha
settlement, so its fringe ratio is undefined (parks are outside the main sample anyway).

**Deviations**
1. *Check I3 failed as written.* 1.74% of Living England cells lie outside every unit,
   against a 0.5% threshold. These are almost all estuary water, beaches and saltmarsh
   that Living England maps beyond the coastline-clipped LAD boundaries. The threshold was
   set on the wrong base: the score only uses developable land, and developable cells outside
   every unit are 0.088% (10,038 ha, two-thirds bare ground). The check now tests
   developable cells; the all-classes share is still printed. The score is unaffected:
   these cells sit outside every unit in both the pilot and the rebuild.
2. *Code bugs, fixed before any result.* (a) On a GeoDataFrame `.type` is the geometry type,
   not a column called `type`, so the first unit raster was empty (I3 caught it). Renamed
   to `kind`. (b) A column-name clash in an ad hoc comparison script; no effect on outputs.

**What exact replication does and does not show.** It confirms the pilot's code does what
its description says, and that the score is not an artefact of OpenCV. It does not validate
the judgement calls that both share: the crosswalk scores (TODO: verify against the
statutory metric), the 10 ha and 500 m thresholds, and Living England's class accuracy.
Those are robustness questions for the DiD (alt scores, 250 m and 1 km zones, 50 ha
settlements, and the LCM2021 version).

Runtime: units raster a few seconds; habitat raster about 3 minutes; score about 20 seconds.
Work rasters in `~/Diss Data/intensity/` (not in git or OneDrive).
