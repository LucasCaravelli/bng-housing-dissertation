"""Gain sites for the house-price designs, with their land-cover context.

Run from the Pipeline folder, after src/register.py (it reuses its record parser):
    python src/gainsite_context.py BNG_Register_snapshot_2026-10-12 rows
        one row per raw register record, as in the pilot (403 rows with coordinates; two
        amended sites appear twice). For validation only.
    python src/gainsite_context.py 2026-11-06_BNG_Register sites
        one row per site (the deduplicated register). For new estimates.

Per site: treatment date (date in the reference), works start, size, implied radius
r = sqrt(area / pi), main created/enhanced broad habitat, and Living England 2022-23 land
cover on the site disc and in the 0-1 km and 1-2 km rings around it. The urban-fringe split
(built-up share of the 0-1 km ring >= 10%) is fixed here, before any price is used.

Geometry: no site boundaries exist; each site is a disc around its grid-reference point,
drawn with 64 segments per quarter circle (as in the pilot). Land-cover shares are areas of
Living England polygons intersected with the disc or ring, divided by the area Living England
covers there.

Outputs (PROCESSED_DIR/bng/): gainsite_context_<date>_<rows|sites>.csv
Resumable: per-site land-cover areas are cached in WORK_ROOT/gainsites/.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from register import REGISTER_DIR, drop_duplicate_versions, pull_date, site_row, to_all_layout  # noqa: E402

LE_GPKG = config.WORK_ROOT / "LivingEngland_2022_23" / "Living_England_2022_2023.gpkg"
CACHE_DIR = config.WORK_ROOT / "gainsites"
OUT_DIR = config.PROCESSED_DIR / "bng"
BUILT = "Built-up Areas and Gardens"
FRINGE_CUT = 0.10
QUAD_SEGS = 64


def site_rows(folder, mode):
    """Register records -> rows. mode 'rows' keeps every raw record (pilot); 'sites'
    keeps one per site and adds the records fetched one by one."""
    path = REGISTER_DIR / folder
    raw = json.loads((path / "bng_sites_raw.json").read_text())
    records = raw
    if mode == "sites":
        records, _ = drop_duplicate_versions(raw)
        byref = path / "bng_sites_by_reference.json"
        extra = json.loads(byref.read_text()) if byref.exists() else []
        extra += [json.loads(p.read_text()) for p in sorted(path.glob("bng_site_*_from_browser.json"))]
        records = records + [to_all_layout(r) for r in extra]
    rows = pd.DataFrame([site_row(r, "register") for r in records])
    rows["main_habitat"] = [main_habitat(r) for r in records]
    rows = rows[(rows.status == "Registered") & rows.easting.notna()].copy()
    rows["ref"] = rows.reference                       # the pilot keyed sites on the raw string
    rows["treat"] = pd.to_datetime(rows.ref_date)
    rows["cohort"] = rows.treat.dt.year
    rows["radius_m"] = np.sqrt(rows.site_ha * 10_000 / np.pi)
    return rows.reset_index(drop=True), pull_date(path)


def main_habitat(rec):
    """Broad habitat with the largest created/enhanced area ('None recorded' if none)."""
    area = {}
    for block in rec.get("habitats") or []:
        if block.get("type") == "Baseline":
            continue
        for a in block.get("areas") or []:
            broad = (a.get("type") or "Unknown").split(" - ")[0].strip()
            area[broad] = area.get(broad, 0) + (a.get("size") or 0)
    return max(area, key=area.get) if area else "None recorded"


def landcover(site, layers, bounds):
    """Area (m2) of each Living England class on the site disc and in the two rings."""
    centre = shapely.Point(site.easting, site.northing)
    discs = {"site": centre.buffer(site.radius_m, QUAD_SEGS),
             "d1": centre.buffer(site.radius_m + 1000, QUAD_SEGS),
             "d2": centre.buffer(site.radius_m + 2000, QUAD_SEGS)}
    box = discs["d2"].bounds
    parts = []
    for layer in layers:
        b = bounds[layer]
        if b[0] > box[2] or b[2] < box[0] or b[1] > box[3] or b[3] < box[1]:
            continue
        g = pyogrio.read_dataframe(LE_GPKG, layer=layer, bbox=box, columns=["Prmry_H"])
        if len(g):
            parts.append(g)
    if not parts:
        return [{"ref": site.ref, "zone": "site", "cls": "NO DATA", "area": 0.0}]
    g = pd.concat(parts, ignore_index=True)
    geoms = g.geometry.values
    a = {k: shapely.area(shapely.intersection(geoms, disc)) for k, disc in discs.items()}
    zones = {"site": a["site"], "ring_0_1k": a["d1"] - a["site"], "ring_1_2k": a["d2"] - a["d1"]}
    rows = []
    for zone, areas in zones.items():
        for cls, v in pd.Series(areas).groupby(g.Prmry_H.values).sum().items():
            rows.append({"ref": site.ref, "zone": zone, "cls": cls, "area": float(v)})
    return rows


def landcover_all(sites, tag):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"landcover_{tag}.csv"
    done = pd.read_csv(cache) if cache.exists() else pd.DataFrame(columns=["ref", "zone", "cls", "area"])
    layers = [name for name, _ in pyogrio.list_layers(LE_GPKG)]
    bounds = {layer: pyogrio.read_info(LE_GPKG, layer=layer)["total_bounds"] for layer in layers}
    todo = sites[~sites.ref.isin(done.ref)].drop_duplicates("ref")
    t0 = time.time()
    for i, site in enumerate(todo.itertuples(), start=1):
        new = pd.DataFrame(landcover(site, layers, bounds))
        done = pd.concat([done, new], ignore_index=True)
        if i % 20 == 0 or i == len(todo):
            done.to_csv(cache, index=False)
            print(f"  land cover: {i}/{len(todo)} sites ({time.time() - t0:.0f} s)", flush=True)
    return done


def shares(lc):
    lc = lc[lc.cls != "NO DATA"]
    wide = lc.pivot_table(index=["ref", "zone"], columns="cls", values="area", aggfunc="sum", fill_value=0)
    covered = wide.sum(axis=1)
    wide = wide.div(covered, axis=0)
    out = pd.DataFrame({
        "builtup_site": wide[BUILT].xs("site", level="zone"),
        "builtup_0_1k": wide[BUILT].xs("ring_0_1k", level="zone"),
        "builtup_1_2k": wide[BUILT].xs("ring_1_2k", level="zone"),
        "covered_0_1k_m2": covered.xs("ring_0_1k", level="zone"),
    })
    return out


def compare_with_pilot(ctx):
    """G2: built-up shares and site attributes against the pilot files."""
    base = config.RAW_ROOT
    old_lc = pd.read_csv(base / "BNG" / "output" / "02_site_landcover.csv", index_col=0)
    old_sites = pd.read_csv(base / "ProcessedData" / "bng" / "bng_sites_clean.csv")
    # the pilot kept the trailing space of the two timestamped reference strings
    old_lc.index = old_lc.index.str.strip()
    old_sites["ref"] = old_sites.ref.str.strip()
    m = ctx.merge(old_lc[["builtup_0_1k", "builtup_site"]], left_on="ref", right_index=True,
                  suffixes=("", "_pilot"), how="left")
    d = (m.builtup_0_1k - m.builtup_0_1k_pilot).abs()
    print(f"G2 vs pilot: {len(ctx)} rows ({len(old_lc)} in pilot land-cover file); "
          f"max |built-up 0-1 km diff| {d.max():.2e}; "
          f"urban fringe: new {int(ctx.urban_fringe.sum())}, pilot {int((m.builtup_0_1k_pilot >= FRINGE_CUT).sum())}")
    s = ctx.merge(old_sites, on="ref", suffixes=("", "_p"), how="left")
    for a, b in [("easting", "easting_p"), ("northing", "northing_p"), ("site_ha", "size"),
                 ("n_alloc", "n_alloc_p")]:
        print(f"   {a}: {int(((s[a] - s[b]).abs() > 1e-9).sum())} rows differ from the pilot site file")


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "BNG_Register_snapshot_2026-10-12"
    mode = sys.argv[2] if len(sys.argv) > 2 else "rows"
    sites, date = site_rows(folder, mode)
    tag = f"{date}_{mode}"
    print(f"{tag}: {len(sites)} registered rows with coordinates ({sites.base_ref.nunique()} distinct sites)")
    lc = landcover_all(sites, tag)
    ctx = sites.merge(shares(lc), left_on="ref", right_index=True, how="left", validate="many_to_one")
    ctx["urban_fringe"] = ctx.builtup_0_1k >= FRINGE_CUT
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ctx.to_csv(OUT_DIR / f"gainsite_context_{tag}.csv", index=False)
    print(f"urban fringe: {int(ctx.urban_fringe.sum())}; of which treated 2024-25: "
          f"{int((ctx.urban_fringe & (ctx.cohort <= 2025)).sum())}")
    if mode == "rows":
        compare_with_pilot(ctx)


if __name__ == "__main__":
    main()
