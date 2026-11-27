"""EPC certificates near gain sites, streamed from the bulk zip without unzipping it.

Run from the Pipeline folder, after src/gainsite_context.py:
    python src/epc_extract.py 2026-10-12_rows [seconds]

Input : RAW_ROOT/RawData-Housing/domestic-csv.zip (domestic EPC open data, ~8 GB)
Output: WORK_ROOT/gainsites/epc_near_sites_<tag>.csv.gz, one row per certificate in a
        postcode within 4 km of any gain-site edge (selected columns)

Resumable: each finished zip member is written to its own part file and listed in a progress
file, so a crash or a full disk never leaves a half-written output; parts are combined once
every member is done. Column names differ between EPC releases (UPPER_CASE in the older bulk
files, snake_case later), so each field is found from a list of candidate names.
"""

import csv
import gzip
import io
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
from gainsite_did import MAXD, load_sites  # noqa: E402
from hedonic_base import HOUS, WORK  # noqa: E402

ZIP = config.RAW_ROOT / "RawData-Housing" / "domestic-csv.zip"
FIELDS = {
    "cert_id": ["LMK_KEY", "certificate_number", "lmk_key", "CERTIFICATE_NUMBER"],
    "address1": ["ADDRESS1", "address1", "address_line_1", "ADDRESS_LINE_1"],
    "address2": ["ADDRESS2", "address2", "address_line_2", "ADDRESS_LINE_2"],
    "address3": ["ADDRESS3", "address3", "address_line_3", "ADDRESS_LINE_3"],
    "postcode": ["POSTCODE", "postcode"],
    "uprn": ["UPRN", "uprn"],
    "lodgement_date": ["LODGEMENT_DATE", "lodgement_date", "registration_date", "REGISTRATION_DATE"],
    "inspection_date": ["INSPECTION_DATE", "inspection_date"],
    "floor_area": ["TOTAL_FLOOR_AREA", "total_floor_area"],
    "rooms": ["NUMBER_HABITABLE_ROOMS", "number_habitable_rooms"],
    "age_band": ["CONSTRUCTION_AGE_BAND", "construction_age_band"],
    "property_type": ["PROPERTY_TYPE", "property_type"],
    "built_form": ["BUILT_FORM", "built_form"],
    "rating": ["CURRENT_ENERGY_RATING", "current_energy_rating", "current_energy_efficiency_band"],
    "transaction_type": ["TRANSACTION_TYPE", "transaction_type"],
}


def norm_postcode(p):
    p = (p or "").upper().replace(" ", "")
    return p[:-3] + " " + p[-3:] if len(p) >= 5 else p


def postcodes_near_sites(tag):
    s = load_sites(tag)
    pc = pd.read_parquet(HOUS / "onspd_england.parquet", columns=["pcds", "easting", "northing"]).dropna()
    tree = cKDTree(pc[["easting", "northing"]].to_numpy())
    near = set()
    for r in s.itertuples():
        near.update(pc.pcds.to_numpy()[tree.query_ball_point([r.easting, r.northing], r=r.radius_m + MAXD)])
    return {norm_postcode(p) for p in near}


def main(tag, budget):
    keep = postcodes_near_sites(tag)
    parts = WORK / f"epc_parts_{tag}"
    parts.mkdir(parents=True, exist_ok=True)
    progress = parts / "progress.txt"
    out = WORK / f"epc_near_sites_{tag}.csv.gz"
    done = set(progress.read_text().split("\n")) if progress.exists() else set()
    z = zipfile.ZipFile(ZIP)
    members = [m for m in z.namelist() if m.lower().endswith(".csv") and "recommendation" not in m.lower()]
    todo = [m for m in members if m not in done]
    print(f"CSV members: {len(members)}; done: {len(members) - len(todo)}; postcodes kept: {len(keep):,}")
    csv.field_size_limit(10 ** 8)
    i_pc = list(FIELDS).index("postcode")
    t0, kept, read = time.time(), 0, 0
    for m in todo:
        if time.time() - t0 > budget:
            break
        buf, stopped = [], False
        with z.open(m) as fb:
            reader = csv.reader(io.TextIOWrapper(fb, encoding="utf-8", errors="replace", newline=""))
            head = next(reader)
            pos = {k: next((head.index(c) for c in cands if c in head), None) for k, cands in FIELDS.items()}
            if pos["postcode"] is None:
                print("no postcode column in", m)
                continue
            ip = pos["postcode"]
            for i, row in enumerate(reader):
                if i % 200_000 == 0 and time.time() - t0 > budget:
                    stopped = True
                    break
                read += 1
                if len(row) <= ip:
                    continue
                pcn = norm_postcode(row[ip])
                if pcn in keep:
                    rec = [row[pos[k]] if pos[k] is not None and pos[k] < len(row) else "" for k in FIELDS]
                    rec[i_pc] = pcn
                    buf.append(rec)
        if stopped:
            print(f"time budget reached inside {m}; it will be redone next run")
            break
        with gzip.open(parts / (Path(m).name + ".gz"), "wt", newline="") as fo:
            csv.writer(fo).writerows(buf)
        kept += len(buf)
        with open(progress, "a") as fp:
            fp.write(m + "\n")
    finished = set(progress.read_text().split("\n")) if progress.exists() else set()
    remaining = [m for m in members if m not in finished]
    print(f"read {read:,} rows, kept {kept:,} in {time.time() - t0:.0f} s; remaining members: {len(remaining)}")
    if not remaining:
        total = 0
        with gzip.open(out, "wt", newline="") as fo:
            w = csv.writer(fo)
            w.writerow(list(FIELDS))
            for m in members:
                with gzip.open(parts / (Path(m).name + ".gz"), "rt", newline="") as fi:
                    for row in csv.reader(fi):
                        w.writerow(row)
                        total += 1
        print(f"combined {total:,} certificates into {out.name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-10-12_rows",
         float(sys.argv[2]) if len(sys.argv) > 2 else 1e9)
