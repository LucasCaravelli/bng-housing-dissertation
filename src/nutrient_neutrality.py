"""Nutrient neutrality (NN) status of each 2025 planning unit.

Run from the Pipeline folder, after src/planning_panel.py and `src/intensity_grid.py units`:
    python src/nutrient_neutrality.py

Why: from 2019 (Solent) and in a wave on 16 March 2022 (42 more LPAs), Natural England advised
74 LPAs not to permit new housing unless it was nutrient neutral. That stalled housing decisions
in 2022-24, inside the pre-period, and NN areas (rivers, wetlands) are not random with respect
to BNG intensity. Used in robustness checks 13-18 (notes/intensity_robustness.md).

Inputs (RAW_ROOT/RawData-Planning/2026-11-06_NutrientNeutrality/):
    nn_lpas_as_listed.csv          Defra lists (LGA board paper, 22 Mar 2022), transcribed by hand
    Nutrient_Neutrality_Catchments_England_*.gpkg   current catchment boundaries (39 polygons)
Output: PROCESSED_DIR/planning/nutrient_neutrality_lpa2025.csv, one row per unit:
    nn             1 if any predecessor council was advised
    wave           earliest wave listed
    nn_pred_share  share of the councils that existed in 2022 Q1 that were advised
    nn_area_share  share of the unit's land inside a current NN catchment (50 m grid)
"""

import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from intensity_grid import NCOL, NROW, TRANSFORM, WORK  # noqa: E402
from planning_panel import TO_2025, load_england  # noqa: E402

NN_DIR = config.RAW_ROOT / "RawData-Planning" / "2026-11-06_NutrientNeutrality"
LISTED = NN_DIR / "nn_lpas_as_listed.csv"
CATCHMENTS = next(NN_DIR.glob("Nutrient_Neutrality_Catchments_England_*.gpkg"))
UNITS = config.PROCESSED_DIR / "planning" / "units_england_lpa2025.csv"
OUT = config.PROCESSED_DIR / "planning" / "nutrient_neutrality_lpa2025.csv"
PILOT = config.RAW_ROOT / "ProcessedData" / "planning" / "nutrient_neutrality_lpa2025.csv"

COUNCIL_WORDS = r"\b(borough|district|city|county|council|of|the|authority)\b"


def normalise(name):
    """'Borough Council of King's Lynn and West Norfolk' -> 'kings lynn and west norfolk'.
    'National park' is kept, so Northumberland County and Northumberland National Park differ."""
    s = name.lower().replace("&", "and").replace("-", " ").replace("’", "").replace("'", "")
    s = re.sub(r"[,.]", " ", s)
    s = re.sub(COUNCIL_WORDS, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def listed_status(raw):
    nn = pd.read_csv(LISTED)
    assert len(nn) == 74, f"expected 74 listed entries, found {len(nn)}"
    # one printed entry covers two councils
    joint = nn.listed_name == "Broadland & South Norfolk Council"
    assert joint.sum() == 1
    nn = pd.concat([nn[~joint], pd.DataFrame({"listed_name": ["Broadland", "South Norfolk"],
                                              "wave": nn.loc[joint, "wave"].iloc[0]})],
                   ignore_index=True)
    nn["key"] = nn.listed_name.map(normalise)

    # every name an authority has used since 2015 (e.g. Shepway before Folkestone and Hythe)
    names = raw[["LPACD", "LPANM"]].drop_duplicates()
    names["key"] = names.LPANM.map(normalise)
    names = names.drop_duplicates("key")
    m = nn.merge(names, on="key", how="left", validate="one_to_one")
    unmatched = m.loc[m.LPACD.isna(), "listed_name"].tolist()
    assert not unmatched, f"listed names with no match: {unmatched}"
    m["code"] = m.LPACD.map(TO_2025).fillna(m.LPACD)

    # councils that existed when the 2022 wave was issued, per 2025 unit
    in_2022 = raw.loc[raw.Quarter == "2022 Q1", "LPACD"].drop_duplicates()
    n_councils_2022 = in_2022.map(TO_2025).fillna(in_2022).value_counts()
    out = (m.groupby("code").agg(wave=("wave", "min"), n_listed=("LPACD", "nunique"),
                                 listed=("listed_name", "; ".join)).reset_index())
    out["nn_pred_share"] = out.n_listed / out.code.map(n_councils_2022).fillna(1)
    out["nn"] = 1
    return out, len(nn)


def catchment_share(units):
    cat = gpd.read_file(CATCHMENTS)
    assert cat.crs.to_epsg() == 27700, cat.crs
    geoms = shapely.force_2d(cat.geometry.values)
    inside = rasterize(((g, 1) for g in geoms), out_shape=(NROW, NCOL), transform=TRANSFORM,
                       dtype=np.uint8)
    unit_r = np.load(WORK / "units_50m.npy")
    grid_units = pd.read_csv(WORK / "units_50m.csv")[["code", "unit_id"]]
    total = np.bincount(unit_r.ravel(), minlength=grid_units.unit_id.max() + 1)
    hit = np.bincount(unit_r.ravel(), weights=inside.ravel(), minlength=len(total))
    grid_units["nn_area_share"] = hit[grid_units.unit_id] / total[grid_units.unit_id]
    print(f"catchments: {len(cat)} polygons")
    return units.merge(grid_units[["code", "nn_area_share"]], on="code", how="left", validate="one_to_one")


def main():
    raw = load_england()
    units = pd.read_csv(UNITS)[["code", "name"]]
    listed, n_entries = listed_status(raw)
    out = units.merge(listed, on="code", how="left", validate="one_to_one")
    out["nn"] = out.nn.fillna(0).astype(int)
    out = catchment_share(out)
    out.to_csv(OUT, index=False)

    print(f"listed entries {n_entries} -> {int(out.nn.sum())} of {len(out)} units")
    print("partly advised units:")
    print(out[(out.nn == 1) & (out.nn_pred_share < 1)][["name", "nn_pred_share", "listed"]].to_string(index=False))
    listed_no_area = out[(out.nn == 1) & (out.nn_area_share < 0.01)]
    area_not_listed = out[(out.nn == 0) & (out.nn_area_share >= 0.05)]
    print("listed but < 1% of area in a catchment:", listed_no_area[["name", "nn_area_share"]].round(3).to_dict("records"))
    print("not listed but >= 5% in a catchment:", area_not_listed[["name", "nn_area_share"]].round(3).to_dict("records"))

    # comparison with the pilot file
    old = pd.read_csv(PILOT)
    m = out.merge(old, on="code", suffixes=("", "_pilot"), validate="one_to_one")
    for col in ["nn", "wave", "nn_pred_share", "nn_area_share"]:
        a, b = m[col], m[f"{col}_pilot"]
        if pd.api.types.is_numeric_dtype(a):
            same = (a - b).abs().lt(1e-12) | (a.isna() & b.isna())
        else:  # text: missing in both counts as the same
            same = (a.astype(str) == b.astype(str)).fillna(False) | (a.isna() & b.isna())
        print(f"  vs pilot, {col}: {int((~same).sum())} units differ")


if __name__ == "__main__":
    main()
