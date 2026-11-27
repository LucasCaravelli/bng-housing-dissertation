"""Feasibility counts of eBird checklists near gain sites and in council fringe zones.

Run from the Pipeline folder, after the intensity rasters and src/gainsite_context.py:
    python src/ebird_counts.py

Reads only the checklist ("sampling event") file of the eBird Basic Dataset, streamed from
the zip; no bird observations are read. Usable checklists follow eBird best practice:
complete, stationary or traveling, 5 min-5 h, <= 5 km, <= 10 observers, shared lists once.
Decision rules: notes/ebird_feasibility.md.

Outputs: WORK_ROOT/ebird/checklists_usable.parquet (checklist-level, licensed data: never in
git); PROCESSED_DIR/ebird/feasibility_*.csv (counts only).
"""

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from intensity_grid import CROSSWALK, NCOL, NROW, RES, WORK as GRID_WORK, X0, Y1  # noqa: E402
from intensity_score import rings, settlements  # noqa: E402

ZIP = config.RAW_ROOT / "ebd_GB_201501_202610_smp_relOct-2026.zip"
MEMBER = "ebd_GB_201501_202610_smp_relOct-2026_sampling.txt"
OUT_WORK = config.WORK_ROOT / "ebird"
OUT = config.PROCESSED_DIR / "ebird"
SITES = config.PROCESSED_DIR / "bng" / "gainsite_context_2026-11-06_sites.csv"
INTENSITY = config.PROCESSED_DIR / "intensity" / "intensity_lpa2025.csv"
COLS = ["SAMPLING EVENT IDENTIFIER", "LATITUDE", "LONGITUDE", "OBSERVATION DATE", "PROTOCOL NAME",
        "DURATION MINUTES", "EFFORT DISTANCE KM", "NUMBER OBSERVERS", "ALL SPECIES REPORTED",
        "GROUP IDENTIFIER", "OBSERVER ID", "TIME OBSERVATIONS STARTED"]


def halfyear(dates):
    """2015H1 = 0."""
    return (dates.dt.year - 2015) * 2 + (dates.dt.month > 6).astype(int)


def usable_checklists():
    z = zipfile.ZipFile(ZIP)
    parts, n_read = [], 0
    with z.open(MEMBER) as f:
        for chunk in pd.read_csv(f, sep="\t", usecols=COLS, dtype=str, quoting=3, chunksize=500_000,
                                 keep_default_na=False):
            n_read += len(chunk)
            dur = pd.to_numeric(chunk["DURATION MINUTES"], errors="coerce")
            dist = pd.to_numeric(chunk["EFFORT DISTANCE KM"], errors="coerce").fillna(0)
            obs = pd.to_numeric(chunk["NUMBER OBSERVERS"], errors="coerce")
            ok = ((chunk["ALL SPECIES REPORTED"] == "1")
                  & chunk["PROTOCOL NAME"].isin(["Stationary", "Traveling"])
                  & dur.between(5, 300) & (dist <= 5) & (obs <= 10))
            parts.append(chunk[ok].assign(duration=dur[ok], distance=dist[ok], observers=obs[ok]))
    d = pd.concat(parts, ignore_index=True)
    n_ok = len(d)
    grouped = d["GROUP IDENTIFIER"] != ""
    d = pd.concat([d[~grouped], d[grouped].drop_duplicates("GROUP IDENTIFIER")], ignore_index=True)
    tf = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
    d["easting"], d["northing"] = tf.transform(d.LONGITUDE.astype(float).to_numpy(),
                                               d.LATITUDE.astype(float).to_numpy())
    d["date"] = pd.to_datetime(d["OBSERVATION DATE"])
    d["h"] = halfyear(d.date)

    # place on the 50 m grid; England = cells inside one of the 306 planning units
    col = ((d.easting - X0) // RES).astype(int)
    row = ((Y1 - d.northing) // RES).astype(int)
    inside = col.between(0, NCOL - 1) & row.between(0, NROW - 1)
    units = np.load(GRID_WORK / "units_50m.npy")
    d["unit_id"] = 0
    d.loc[inside, "unit_id"] = units[row[inside], col[inside]]
    d["row"], d["col"] = row.where(inside, -1), col.where(inside, -1)
    eng = d[d.unit_id > 0].reset_index(drop=True)
    print(f"checklists read {n_read:,}; usable {n_ok:,}; after removing shared duplicates {len(d):,}; "
          f"in England {len(eng):,}; date range {eng.date.min():%Y-%m} to {eng.date.max():%Y-%m}")
    keep = ["SAMPLING EVENT IDENTIFIER", "OBSERVER ID", "date", "h", "TIME OBSERVATIONS STARTED",
            "PROTOCOL NAME", "duration", "distance", "observers", "easting", "northing", "unit_id", "row", "col"]
    OUT_WORK.mkdir(parents=True, exist_ok=True)
    eng[keep].to_parquet(OUT_WORK / "checklists_usable.parquet", index=False)
    return eng


def site_counts(ck):
    s = pd.read_csv(SITES)
    s["treat"] = pd.to_datetime(s.treat)
    s["h_reg"] = halfyear(s.treat)
    tree = cKDTree(ck[["easting", "northing"]].to_numpy())
    xy = ck[["easting", "northing"]].to_numpy()
    rows = []
    for r in s.itertuples():
        idx = np.asarray(tree.query_ball_point([r.easting, r.northing], r=r.radius_m + 4000), dtype=int)
        d = np.clip(np.hypot(xy[idx, 0] - r.easting, xy[idx, 1] - r.northing) - r.radius_m, 0, None)
        h = ck.h.to_numpy()[idx]
        for band, sel in [("0-500m", d < 500), ("0-1km", d < 1000), ("2-4km", (d >= 2000) & (d < 4000))]:
            counts = np.bincount(h[sel], minlength=24)
            rows += [{"ref": r.ref, "band": band, "h": k, "n": int(c), "h_reg": r.h_reg} for k, c in enumerate(counts)]
    return pd.DataFrame(rows)


def fringe_counts(ck):
    """Checklists in each unit's developable 0-500 m settlement fringe (the intensity zone)."""
    codes = json.loads((GRID_WORK / "habitat_classes.json").read_text())
    cls = np.load(GRID_WORK / "habitat_50m.npy")
    settle, _ = settlements(cls == codes["Built-up Areas and Gardens"], 40)
    ring = rings(settle)
    del settle
    xw = pd.read_csv(CROSSWALK)
    developable = np.zeros(256, dtype=bool)
    developable[[codes[c] for c in xw.le_class[xw.developable == 1]]] = True
    r, c = ck.row.to_numpy(), ck.col.to_numpy()
    ck = ck.assign(ring=ring[r, c], developable=developable[cls[r, c]])
    pre = ck[(ck.date.dt.year <= 2021)]
    zone = pre[pre.ring.isin([1, 2]) & pre.developable]
    units = pd.read_csv(GRID_WORK / "units_50m.csv")[["unit_id", "code", "name"]]
    out = units.merge(zone.groupby("unit_id").size().rename("fringe_2015_21").reset_index(), how="left")
    out = out.merge(pre.groupby("unit_id").size().rename("all_2015_21").reset_index(), how="left")
    return out.fillna({"fringe_2015_21": 0, "all_2015_21": 0})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ck = usable_checklists()
    sc = site_counts(ck)
    sc.to_csv(OUT / "feasibility_site_counts.csv", index=False)
    fc = fringe_counts(ck)
    fc.to_csv(OUT / "feasibility_fringe_counts.csv", index=False)

    # Use 1: selection/additionality
    k = sc[(sc.band == "0-1km") & sc.h.between(6, 17)].groupby("ref").n.sum()       # 2018-2023
    use1 = int((k >= 10).sum())
    print(f"\nUse 1 (selection): sites with >= 10 checklists within 1 km in 2018-23: {use1} of {len(k)} "
          f"(threshold 100) -> {'FEASIBLE' if use1 >= 100 else 'not feasible'}; median {k.median():.0f}")
    # Use 2: intensity cross-check
    main_codes = pd.read_csv(INTENSITY).query("main_sample")[["code"]]
    m = main_codes.merge(fc, on="code", how="left").fillna(0)
    use2 = int((m.fringe_2015_21 >= 100).sum())
    print(f"Use 2 (intensity check): main-sample councils with >= 100 fringe-zone checklists 2015-21: "
          f"{use2} of {len(m)} (threshold 150) -> {'FEASIBLE' if use2 >= 150 else 'not feasible'}; "
          f"median {m.fringe_2015_21.median():.0f}")
    # Use 3: impact
    t = sc[(sc.band == "0-1km") & sc.h_reg.between(18, 21)]                          # 2024H1-2025H2
    ok = []
    for ref, g in t.groupby("ref"):
        hr = g.h_reg.iloc[0]
        n = g.set_index("h").n
        pre_ok = all(n.get(hr - k, 0) >= 3 for k in range(1, 5))
        post_ok = any(n.get(hh, 0) >= 3 for hh in range(hr, 24))
        ok.append(pre_ok and post_ok)
    use3 = int(np.sum(ok))
    print(f"Use 3 (impact): treated sites 2024-25 with >= 3 checklists within 1 km in each of the 4 pre "
          f"half-years and >= 1 post half-year: {use3} of {len(ok)} (threshold 50) -> "
          f"{'FEASIBLE' if use3 >= 50 else 'not feasible'}")


if __name__ == "__main__":
    main()
