"""BNG intensity score per planning unit, from the 50 m rasters.

Run from the Pipeline folder, after both steps of src/intensity_grid.py:
    python src/intensity_score.py

Idea (toy model, FINDINGS section 2): BNG charges developers for the habitat value lost on
a site. New housing is built mostly on the edges of existing settlements, so BNG costs more
per dwelling where the undeveloped land next to settlements is semi-natural habitat
(Medium+ distinctiveness) than where it is arable or modified grassland (Low).

Main measure: share of developable land within 500 m of a settlement (built-up patch of at
least 10 ha) that has Medium+ distinctiveness. Variants: 250 m and 1 km zones, 50 ha
settlements, mean distinctiveness score, the crosswalk's 'alt' scores.

Outputs in PROCESSED_DIR/intensity:
    zone_class_counts.csv     cells by unit x class x ring x settlement rule
    intensity_lpa2025.csv     one row per unit: all variants, fringe ratio, main sample flag

Definitions and checks are pre-specified in notes/intensity.md.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from intensity_grid import CROSSWALK, RES, WORK, cell_area_ha  # noqa: E402

OUT_DIR = config.PROCESSED_DIR / "intensity"
PILOT_DIR = config.RAW_ROOT / "ProcessedData" / "planning"

SETTLEMENT_RULES = {"settle10ha": 10, "settle50ha": 50}       # minimum settlement size, ha
RING_EDGES_M = [250, 500, 1000]                               # ring 1: 0-250 m, 2: 250-500, 3: 500-1000
ZONES = {"z0_250": [1], "z0_500": [1, 2], "z0_1000": [1, 2, 3], "all_undeveloped": [1, 2, 3, 4]}
MEDIUM_PLUS = 4                                               # distinctiveness score threshold


# ---------------------------------------------------------------------------
# Raster operations (unit-tested in tests/test_intensity.py)
# ---------------------------------------------------------------------------

def settlements(built, min_cells):
    """Keep 8-connected patches of built-up cells with at least min_cells cells."""
    eight = np.ones((3, 3), dtype=bool)
    labels, n = ndimage.label(built, structure=eight)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= min_cells
    keep[0] = False                                   # label 0 is the background
    return keep[labels], int(keep.sum())


def rings(settle, res=RES, edges=RING_EDGES_M):
    """0 = settlement; 1, 2, 3 = within 250 / 500 / 1000 m of a settlement cell centre;
    4 = further. Distance = Euclidean distance between cell centres."""
    # distance_transform_edt gives, for each non-zero cell, the distance to the nearest
    # zero cell; passing ~settle makes settlement cells the zeros
    dist_m = ndimage.distance_transform_edt(~settle).astype(np.float32) * res
    ring = np.full(settle.shape, len(edges) + 1, dtype=np.uint8)
    for code, edge in reversed(list(enumerate(edges, start=1))):
        ring[dist_m <= edge] = code
    ring[settle] = 0
    return ring


def count_cells(units, cls, ring, n_units, n_cls):
    """Cells by (unit, class, ring), in row blocks to limit memory."""
    n_ring = len(RING_EDGES_M) + 2
    out = np.zeros((n_units + 1) * (n_cls + 1) * n_ring, dtype=np.int64)
    for r0 in range(0, units.shape[0], 1000):
        rows = slice(r0, r0 + 1000)
        idx = (units[rows].astype(np.int64) * (n_cls + 1) + cls[rows]) * n_ring + ring[rows]
        out += np.bincount(idx.ravel(), minlength=out.size)
    return out.reshape(n_units + 1, n_cls + 1, n_ring)


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

def scores(counts, crosswalk, units):
    d = counts.merge(crosswalk, on="le_class", how="left")
    d = d[d.developable == 1]
    parts = []
    for rule in SETTLEMENT_RULES:
        for zone, ring_codes in ZONES.items():
            z = d[(d.rule == rule) & d.ring.isin(ring_codes)]
            for col in ["main", "alt"]:
                s = z[f"distinctiveness_{col}"]
                g = (z.assign(w=z.ha * s, med=z.ha * (s >= MEDIUM_PLUS))
                     .groupby("unit_id")[["ha", "w", "med"]].sum())
                parts.append(pd.DataFrame({
                    f"{zone}_{rule}_{col}_share_medplus": g.med / g.ha,
                    f"{zone}_{rule}_{col}_mean_dist": g.w / g.ha,
                    f"{zone}_{rule}_ha": g.ha}))
    res = pd.concat(parts, axis=1)
    res = res.loc[:, ~res.columns.duplicated()]
    res = units.merge(res, left_on="unit_id", right_index=True, how="left", validate="one_to_one")
    res["intensity"] = res["z0_500_settle10ha_main_share_medplus"]                 # MAIN

    settle_ha = (counts[(counts.rule == "settle10ha") & (counts.ring == 0)]
                 .groupby("unit_id").ha.sum())
    res["settle_ha"] = res.unit_id.map(settle_ha)
    res["fringe_ratio"] = res["z0_500_settle10ha_ha"] / res.settle_ha
    res["main_sample"] = ((res.type == "council") & ~res.code.str.startswith("E09")
                          & (res.fringe_ratio >= 1))
    return res


# ---------------------------------------------------------------------------
# Comparison with the pilot (check I5)
# ---------------------------------------------------------------------------

def compare_with_pilot(counts, res):
    lookup = pd.read_csv(PILOT_DIR / "lpa2025_lookup.csv")[["unit_id", "code"]]
    old_c = pd.read_csv(PILOT_DIR / "le_zone_class_counts.csv")
    key = ["rule", "le_class", "ring"]
    tot_new = counts.groupby(key).cells.sum()
    tot_old = old_c.groupby(key).cells.sum()
    both = pd.concat({"new": tot_new, "pilot": tot_old}, axis=1).fillna(0)
    both["rel_diff"] = (both.new - both.pilot) / both.pilot.where(both.pilot > 0)
    big = both[both.pilot > 1_000]                    # classes x rings with > 250 ha
    print(f"\nI5 England cells by class x ring: max |relative difference| "
          f"{big.rel_diff.abs().max():.4%} over {len(big)} cells of the table")
    worst = big.reindex(big.rel_diff.abs().sort_values(ascending=False).index).head(5)
    print(worst.to_string())

    old = pd.read_csv(PILOT_DIR / "bng_intensity_lpa2025.csv")
    old_s = pd.read_csv(PILOT_DIR / "bng_intensity_sample.csv")[["code", "fringe_ratio", "main_sample"]]
    m = res.merge(old[["code", "intensity"]], on="code", suffixes=("", "_pilot"), validate="one_to_one")
    m = m.merge(old_s, on="code", suffixes=("", "_pilot"), validate="one_to_one")
    diff = (m.intensity - m.intensity_pilot).abs()
    corr = m[["intensity", "intensity_pilot"]].corr().iloc[0, 1]
    print(f"I5 intensity: corr {corr:.6f}; max |diff| {diff.max():.5f}; mean |diff| {diff.mean():.6f}")
    flips = m[m.main_sample != m.main_sample_pilot]
    print(f"I5 main sample: new {int(m.main_sample.sum())}, pilot {int(m.main_sample_pilot.sum())}, "
          f"units that switch: {flips[['code', 'name', 'fringe_ratio', 'fringe_ratio_pilot']].to_dict('records')}")
    return corr, diff.max(), flips, big.rel_diff.abs().max()


def main():
    state = json.loads((WORK / "habitat_state.json").read_text())
    assert state.get("complete"), "run: python src/intensity_grid.py habitat (until it finishes)"
    codes = json.loads((WORK / "habitat_classes.json").read_text())          # name -> code
    names = {v: k for k, v in codes.items()}
    crosswalk = pd.read_csv(CROSSWALK)
    units = pd.read_csv(WORK / "units_50m.csv")

    cls = np.load(WORK / "habitat_50m.npy")
    unit_r = np.load(WORK / "units_50m.npy")
    built = cls == codes["Built-up Areas and Gardens"]

    # I3 (second half): Living England cells outside every unit. As pre-specified this used
    # all classes and failed (1.74%: estuary water, beaches, saltmarsh beyond the clipped
    # coastline). Deviation recorded in notes/intensity.md: the test is on developable cells,
    # the only ones the score uses; the all-classes share is still reported.
    outside = (cls > 0) & (unit_r == 0)
    developable = np.zeros(256, dtype=bool)
    developable[[codes[c] for c in crosswalk.le_class[crosswalk.developable == 1]]] = True
    dev = developable[cls]
    share_all = outside.sum() / (cls > 0).sum()
    share_dev = (outside & dev).sum() / dev.sum()
    by_cls = pd.Series(np.bincount(cls[outside], minlength=len(codes) + 1)).rename(names)
    print(f"I3 Living England cells outside every unit: all classes {share_all:.3%} "
          f"(largest: {by_cls[by_cls > 0].nlargest(4).to_dict()}); developable {share_dev:.3%}")
    assert share_dev < 0.005, "I3 failed on developable cells"
    del outside, dev

    tables = []
    for rule, min_ha in SETTLEMENT_RULES.items():
        min_cells = int(min_ha * 10_000 // (RES * RES))
        settle, n_settle = settlements(built, min_cells)
        ring = rings(settle)
        del settle
        c = count_cells(unit_r, cls, ring, int(units.unit_id.max()), max(codes.values()))
        del ring
        u, k, r = np.nonzero(c)
        tables.append(pd.DataFrame({"rule": rule, "unit_id": u, "code": k, "ring": r, "cells": c[u, k, r]}))
        print(f"{rule}: {n_settle:,} settlements")
    del cls, unit_r, built

    counts = pd.concat(tables, ignore_index=True)
    counts = counts[counts.unit_id > 0]
    counts["le_class"] = counts.code.map(names).fillna("no data")
    counts["ha"] = cell_area_ha(counts.cells)
    res = scores(counts, crosswalk, units)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts.to_csv(OUT_DIR / "zone_class_counts.csv", index=False)
    res.to_csv(OUT_DIR / "intensity_lpa2025.csv", index=False)
    print(res[["intensity", "fringe_ratio"]].describe().round(3).to_string())
    print(f"main sample: {int(res.main_sample.sum())} units")

    corr, max_diff, flips, max_rel = compare_with_pilot(counts, res)
    ok = corr > 0.999 and max_diff < 0.005 and flips.empty and max_rel < 0.005
    print("I5 passed" if ok else "I5 NOT passed: explain before using the score")


if __name__ == "__main__":
    main()
