"""Species richness per eBird checklist near gain sites, streamed from the 21 GB file.

Run from the Pipeline folder, after src/ebird_counts.py:
    python src/ebird_species.py

Only checklists in the selection design (usable, 2015-2023, within 0-1 km or 2-4 km of a gain
site edge) are kept. Richness counts distinct species: category "species" or "issf"
(subspecies groups, collapsed to species by the first two words of the scientific name);
spuhs, slashes, hybrids, domestics and escapees (exotic code "X") excluded; approved records
only. Also counts the 19 Farmland Bird Index species (matched on eBird English names; any
name not found in the data is reported). Specification: notes/ebird_selection.md.

Output: WORK_ROOT/ebird/richness_2015_2023.parquet (checklist level; licensed data, not in git)
"""

import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from ebird_counts import OUT_WORK, SITES, ZIP  # noqa: E402

MEMBER = "ebd_GB_201501_202610_smp_relOct-2026.txt"
COLS = ["SAMPLING EVENT IDENTIFIER", "CATEGORY", "COMMON NAME", "SCIENTIFIC NAME", "EXOTIC CODE", "APPROVED"]

# UK Farmland Bird Index (19 species), eBird English names. TODO: verify list against Defra.
FBI = ["Corn Bunting", "European Goldfinch", "European Greenfinch", "Gray Partridge",
       "Eurasian Jackdaw", "Eurasian Kestrel", "Northern Lapwing", "Eurasian Linnet",
       "Reed Bunting", "Rook", "Eurasian Skylark", "European Starling", "Stock Dove",
       "Eurasian Tree Sparrow", "European Turtle-Dove", "Greater Whitethroat",
       "Common Wood-Pigeon", "Western Yellow Wagtail", "Yellowhammer"]


def design_pairs():
    """Site x checklist pairs: inner 0-1 km or outer 2-4 km of the edge, 2015-2023."""
    ck = pd.read_parquet(OUT_WORK / "checklists_usable.parquet")
    ck = ck[ck.date.dt.year <= 2023].reset_index(drop=True)
    s = pd.read_csv(SITES)
    tree = cKDTree(ck[["easting", "northing"]].to_numpy())
    xy = ck[["easting", "northing"]].to_numpy()
    pairs = []
    for r in s.itertuples():
        idx = np.asarray(tree.query_ball_point([r.easting, r.northing], r=r.radius_m + 4000), dtype=int)
        d = np.clip(np.hypot(xy[idx, 0] - r.easting, xy[idx, 1] - r.northing) - r.radius_m, 0, None)
        keep = (d < 1000) | (d >= 2000)
        pairs.append(pd.DataFrame({"ref": r.ref, "ck": idx[keep], "d_edge": d[keep]}))
    pairs = pd.concat(pairs, ignore_index=True)
    pairs = pairs.merge(ck.reset_index().rename(columns={"index": "ck"}), on="ck").drop(columns="ck")
    return pairs


def main():
    pairs = design_pairs()
    wanted = set(pairs["SAMPLING EVENT IDENTIFIER"])
    print(f"design: {len(pairs):,} site x checklist pairs; {len(wanted):,} distinct checklists")
    z = zipfile.ZipFile(ZIP)
    parts, t0, n_rows = [], time.time(), 0
    with z.open(MEMBER) as f:
        for i, chunk in enumerate(pd.read_csv(f, sep="\t", usecols=COLS, dtype=str, quoting=3,
                                              chunksize=2_000_000, keep_default_na=False)):
            n_rows += len(chunk)
            c = chunk[chunk["SAMPLING EVENT IDENTIFIER"].isin(wanted) & (chunk.APPROVED == "1")
                      & chunk.CATEGORY.isin(["species", "issf"]) & (chunk["EXOTIC CODE"] != "X")]
            sp = c["SCIENTIFIC NAME"].str.split().str[:2].str.join(" ")
            parts.append(pd.DataFrame({"id": c["SAMPLING EVENT IDENTIFIER"].to_numpy(), "species": sp.to_numpy(),
                                       "fbi": c["COMMON NAME"].isin(FBI).to_numpy(),
                                       "common": c["COMMON NAME"].to_numpy()}).drop_duplicates(["id", "species"]))
            if i % 10 == 0:
                print(f"  {n_rows:,} rows ({time.time() - t0:.0f} s)", flush=True)
    obs = pd.concat(parts, ignore_index=True).drop_duplicates(["id", "species"])
    found = set(obs.loc[obs.fbi, "common"])
    missing = [n for n in FBI if n not in found]
    print(f"observation rows read {n_rows:,}; species records kept {len(obs):,}; "
          f"distinct species {obs.species.nunique()}; FBI names not found in the data: {missing}")
    rich = obs.groupby("id").agg(richness=("species", "size"), fbi=("fbi", "sum")).reset_index()
    # complete checklists with no qualifying species have richness 0
    rich = pd.DataFrame({"id": sorted(wanted)}).merge(rich, on="id", how="left").fillna({"richness": 0, "fbi": 0})
    rich.to_parquet(OUT_WORK / "richness_2015_2023.parquet", index=False)
    pairs.to_parquet(OUT_WORK / "selection_pairs_2015_2023.parquet", index=False)
    print(f"checklists with richness: {len(rich):,}; mean richness {rich.richness.mean():.1f}; "
          f"zero-species lists {int((rich.richness == 0).sum())}")


if __name__ == "__main__":
    main()
