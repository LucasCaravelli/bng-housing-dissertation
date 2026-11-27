"""Rasters for the BNG intensity score: planning units and Living England habitat classes.

Run from the Pipeline folder, after src/planning_panel.py (it needs the unit list):
    python src/intensity_grid.py units     # 306 planning units -> units_50m.npy (a minute)
    python src/intensity_grid.py habitat   # Living England -> habitat_50m.npy (long; resumable)

Why a raster: the score needs habitat classes in distance bands around every settlement in
England (about 10 million Living England polygons). On a common 50 m grid this becomes array
arithmetic that fits in memory. Each cell takes the class of the polygon covering its centre,
so polygons smaller than a cell can be missed; check I2 compares class areas with polygon areas.

Outputs (large, so in WORK_ROOT/intensity, outside OneDrive and git):
    units_50m.npy, units_50m.csv               int16 unit id per cell (0 = no unit)
    habitat_50m.npy, habitat_classes.json      uint8 class code per cell (0 = no data)
    habitat_state.json                         progress and polygon areas (for resuming and I2)

Definitions and checks are pre-specified in notes/intensity.md.
"""

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from rasterio.features import rasterize
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

# 50 m grid over England in British National Grid (EPSG:27700), as in the pilot
RES = 50
X0, X1, Y0, Y1 = 82_000, 656_000, 5_000, 658_000
NCOL, NROW = (X1 - X0) // RES, (Y1 - Y0) // RES
TRANSFORM = from_origin(X0, Y1, RES, RES)  # top-left corner, cell size

WORK = config.WORK_ROOT / "intensity"
LE_GPKG = config.WORK_ROOT / "LivingEngland_2022_23" / "Living_England_2022_2023.gpkg"
LAD_FILE = next((config.RAW_ROOT / "RawData-BNG").glob("LAD_MAY_2025_UK_BGC*.gpkg"))
PARKS_FILE = config.RAW_ROOT / "RawData-BNG" / "National_Parks_England.gpkg"
UNITS_FILE = config.PROCESSED_DIR / "planning" / "units_england_lpa2025.csv"
CROSSWALK = Path(__file__).resolve().parents[1] / "inputs" / "le_distinctiveness_crosswalk.csv"

# park names in the boundary file -> planning authority code
PARK_CODES = {"DARTMOOR": "E26000001", "EXMOOR": "E26000002", "NORTHUMBERLAND": "E26000004",
              "NORTH YORK MOORS": "E26000005", "PEAK DISTRICT": "E26000006",
              "THE BROADS": "E26000007", "NEW FOREST": "E26000009", "SOUTH DOWNS": "E26000010",
              "LAKE DISTRICT": "E26000011", "YORKSHIRE DALES": "E26000012"}

CHUNK = 150_000  # polygons read at a time


def cell_area_ha(n_cells):
    return n_cells * RES * RES / 10_000


# ---------------------------------------------------------------------------
# Planning units
# ---------------------------------------------------------------------------

def build_units():
    units = pd.read_csv(UNITS_FILE)[["code", "name", "type"]]
    units["unit_id"] = np.arange(1, len(units) + 1, dtype=np.int16)

    lad = gpd.read_file(LAD_FILE, columns=["LAD25CD"]).rename(columns={"LAD25CD": "code"})
    lad = lad[lad.code.str.startswith("E")]
    parks = gpd.read_file(PARKS_FILE, columns=["name"])
    parks["code"] = parks["name"].map(PARK_CODES)
    assert parks.code.notna().all(), f"unknown park names: {parks.loc[parks.code.isna(), 'name'].tolist()}"
    for g in (lad, parks):
        assert g.crs.to_epsg() == 27700, f"expected British National Grid, got {g.crs}"

    # 'kind', not 'type': on a GeoDataFrame, .type is the geometry type
    geoms = pd.concat([lad[["code", "geometry"]], parks[["code", "geometry"]]], ignore_index=True)
    geoms = geoms.merge(units[["code", "unit_id", "type"]].rename(columns={"type": "kind"}),
                        on="code", how="left", validate="many_to_one")
    assert geoms.unit_id.notna().all(), f"boundaries without a unit: {geoms.loc[geoms.unit_id.isna(), 'code']}"
    assert set(units.code) == set(geoms.code), "units without a boundary"

    # councils first, then parks on top, so park land belongs to the park authority
    arr = np.zeros((NROW, NCOL), dtype=np.int16)
    for kind in ["council", "national park"]:
        part = geoms[geoms["kind"] == kind]
        assert len(part) > 0, f"no {kind} boundaries"
        rasterize(zip(part.geometry, part.unit_id.astype(int)), out=arr, transform=TRANSFORM)

    # I3: raster area vs boundary area. Parks are compared with their own polygon;
    # councils with their polygon minus any park land.
    cells = np.bincount(arr.ravel(), minlength=len(units) + 1)
    units["area_ha_raster"] = cell_area_ha(cells[units.unit_id])
    park_union = parks.geometry.union_all()
    vec = geoms.assign(geometry=[g if k == "national park" else g.difference(park_union)
                                 for g, k in zip(geoms.geometry, geoms["kind"])])
    vec_area = vec.assign(a=vec.area / 10_000).groupby("code").a.sum()
    units["area_ha_vector"] = units.code.map(vec_area)
    ratio = units.area_ha_raster / units.area_ha_vector
    big = units.area_ha_vector > 1_000
    bad = units[big & ((ratio - 1).abs() > 0.01)]
    assert bad.empty, f"I3 failed: raster vs vector area off by > 1%:\n{bad}"
    print(f"units: {len(units)}; raster/vector area ratio median {ratio.median():.4f}, "
          f"range {ratio[big].min():.4f}-{ratio[big].max():.4f} (units > 1,000 ha)")

    WORK.mkdir(parents=True, exist_ok=True)
    np.save(WORK / "units_50m.npy", arr)
    units.to_csv(WORK / "units_50m.csv", index=False)


# ---------------------------------------------------------------------------
# Living England habitat classes
# ---------------------------------------------------------------------------

def class_codes():
    """Stable class codes 1..n from the crosswalk order (0 = no data)."""
    xw = pd.read_csv(CROSSWALK)
    return {name: i + 1 for i, name in enumerate(xw.le_class)}


def build_habitat():
    """Resumable: progress is saved after every chunk; rerun after an interruption."""
    WORK.mkdir(parents=True, exist_ok=True)
    arr_f, state_f = WORK / "habitat_50m.npy", WORK / "habitat_state.json"
    codes = class_codes()
    (WORK / "habitat_classes.json").write_text(json.dumps(codes, indent=1))

    state = json.loads(state_f.read_text()) if state_f.exists() else {"done": {}, "poly_ha": {}}
    arr = np.load(arr_f) if arr_f.exists() else np.zeros((NROW, NCOL), dtype=np.uint8)
    t0 = time.time()
    layers = [name for name, _ in pyogrio.list_layers(LE_GPKG)]
    for layer in layers:
        info = pyogrio.read_info(LE_GPKG, layer=layer)
        assert info["crs"].endswith("27700"), f"{layer}: CRS {info['crs']}"
        n = info["features"]
        start = state["done"].get(layer, 0)
        while start < n:
            _, _, wkb, fields = pyogrio.raw.read(LE_GPKG, layer=layer, columns=["Prmry_H"],
                                                 skip_features=start, max_features=CHUNK)
            names = fields[0]
            unknown = set(names) - set(codes)
            assert not unknown, f"I4 failed: classes not in the crosswalk: {unknown}"
            values = np.array([codes[c] for c in names], dtype=np.uint8)
            geoms = shapely.from_wkb(wkb)
            rasterize(zip(geoms, values), out=arr, transform=TRANSFORM)

            areas = shapely.area(geoms) / 10_000
            for code in np.unique(values):
                key = str(int(code))
                state["poly_ha"][key] = state["poly_ha"].get(key, 0.0) + float(areas[values == code].sum())
            start += len(names)
            state["done"][layer] = start
            np.save(arr_f, arr)
            state_f.write_text(json.dumps(state))
            print(f"{layer}: {start:,}/{n:,}  ({time.time() - t0:,.0f} s)", flush=True)
    state["complete"] = True
    state_f.write_text(json.dumps(state))
    check_habitat(arr, codes, state)


def check_habitat(arr, codes, state):
    """I2: rasterised class areas vs polygon areas."""
    counts = np.bincount(arr.ravel(), minlength=256)
    rows = []
    for name, code in codes.items():
        poly = state["poly_ha"].get(str(code), 0.0)
        rows.append({"class": name, "raster_ha": cell_area_ha(counts[code]), "polygon_ha": poly})
    t = pd.DataFrame(rows)
    t["ratio"] = t.raster_ha / t.polygon_ha
    print(t.round(3).to_string(index=False))
    tested = t[t.polygon_ha > 10_000]
    bad = tested[(tested.ratio - 1).abs() > 0.02]
    assert bad.empty, f"I2 failed:\n{bad}"
    print("I2 passed")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "units":
        build_units()
    elif step == "habitat":
        build_habitat()
    else:
        sys.exit("usage: python src/intensity_grid.py units|habitat")
