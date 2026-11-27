"""Price Paid and postcode inputs for the house-price designs.

Run from the Pipeline folder:
    python src/housing_inputs.py

Inputs (read-only, RAW_ROOT/RawData-Housing/):
    Land Registry Price Paid, yearly files/pp-YYYY.csv   2018-2026, no header row
    ONS_Postcode_Directory_(August_2026)_(Hosted_Table).csv
Outputs (PROCESSED_DIR/housing/):
    onspd_england.parquet   English postcodes with coordinates (terminated ones kept: old
                            sales use them), easting/northing to 1 m, LSOA 2021, LAD 2026
    ppd_YYYY.parquet        category A sales (standard sales at full market value) with an
                            English postcode; addr = postcode|PAON|SAON for the EPC link

Rules inferred from the pilot's output files (its conversion script was not found) and
checked against them (G1 in notes/gainsite_prices.md).
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

RAW = config.RAW_ROOT / "RawData-Housing"
PPD_DIR = RAW / "Land Registry Price Paid, yearly files"
ONSPD = RAW / "ONS_Postcode_Directory_(August_2026)_(Hosted_Table).csv"
OUT = config.PROCESSED_DIR / "housing"
PILOT = config.RAW_ROOT / "ProcessedData" / "housing"
YEARS = range(2018, 2027)

# Price Paid column order (HM Land Registry guidance; the files have no header row)
PPD_COLUMNS = ["tid", "price", "date", "postcode", "ptype", "new", "tenure", "paon", "saon",
               "street", "locality", "town", "district", "county", "category", "status"]
ENGLAND = "E92000001"


def build_onspd():
    cols = ["pcds", "east1m", "north1m", "gridind", "lsoa21cd", "lad26cd", "ctry26cd", "doterm"]
    o = pd.read_csv(ONSPD, usecols=cols, dtype=str, keep_default_na=False)
    eng = o[o.ctry26cd == ENGLAND]
    english_postcodes = set(eng.pcds)
    eng = eng[eng.east1m != ""]                       # a few postcodes have no grid reference
    out = pd.DataFrame({
        "pcds": eng.pcds.to_numpy(),
        "easting": eng.east1m.astype("int32").to_numpy(),
        "northing": eng.north1m.astype("int32").to_numpy(),
        "gridind": eng.gridind.astype("int8").to_numpy(),
        "lsoa21cd": eng.lsoa21cd.astype("category").to_numpy(),
        "lad26cd": eng.lad26cd.astype("category").to_numpy(),
        "live": (eng.doterm == "").to_numpy(),          # no termination date
    })
    assert out.pcds.is_unique
    out.to_parquet(OUT / "onspd_england.parquet", index=False)
    print(f"ONSPD: {len(o):,} postcodes; England {len(english_postcodes):,}; with coordinates {len(out):,}")
    return english_postcodes


def build_ppd(year, english_postcodes):
    x = pd.read_csv(PPD_DIR / f"pp-{year}.csv", header=None, names=PPD_COLUMNS, dtype=str,
                    keep_default_na=False)
    n_raw = len(x)
    assert x.tid.is_unique, f"{year}: duplicate transaction ids"
    x = x[(x.category == "A") & x.postcode.isin(english_postcodes)]
    out = pd.DataFrame({
        "tid": x.tid.str.strip("{}").to_numpy(),
        "price": x.price.astype("int64").to_numpy(),
        "date": pd.to_datetime(x.date, format="%Y-%m-%d %H:%M").to_numpy(),
        "pcds": x.postcode.to_numpy(),
        "ptype": x.ptype.astype("category").to_numpy(),
        "new": (x.new == "Y").to_numpy(),
        "tenure": x.tenure.astype("category").to_numpy(),
        # upper case: a few records are in mixed case (as the pilot did)
        "addr": (x.postcode + "|" + x.paon + "|" + x.saon).str.upper().to_numpy(),
        "district": x.district.astype("category").to_numpy(),
    })
    out.to_parquet(OUT / f"ppd_{year}.parquet", index=False)
    return n_raw, len(out), out


def compare_with_pilot(year, new):
    """G1: same transactions and identical fields as the pilot's file."""
    path = PILOT / f"ppd_{year}.parquet"
    if not path.exists():
        return "no pilot file"
    old = pd.read_parquet(path)
    if len(old) != len(new) or set(old.tid) != set(new.tid):
        return f"DIFFERENT rows: pilot {len(old):,}, new {len(new):,}"
    m = new.merge(old, on="tid", suffixes=("", "_pilot"), validate="one_to_one")
    bad = [c for c in ["price", "date", "pcds", "ptype", "new", "tenure", "addr", "district"]
           if not (m[c].astype(str) == m[f"{c}_pilot"].astype(str)).all()]
    return "identical" if not bad else f"fields differ: {bad}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    english = build_onspd()
    old_pc = pd.read_parquet(PILOT / "onspd_england.parquet")
    new_pc = pd.read_parquet(OUT / "onspd_england.parquet")
    same_pc = (len(old_pc) == len(new_pc)) and new_pc.merge(old_pc, on="pcds", suffixes=("", "_p")).pipe(
        lambda m: all((m[c].astype(str) == m[f"{c}_p"].astype(str)).all()
                      for c in ["easting", "northing", "gridind", "lsoa21cd", "lad26cd", "live"]))
    print(f"G1 ONSPD vs pilot: {'identical' if same_pc else 'DIFFERENT'}")
    for year in YEARS:
        n_raw, n_out, out = build_ppd(year, english)
        print(f"  {year}: {n_raw:,} rows -> {n_out:,} category A, English; G1 vs pilot: "
              f"{compare_with_pilot(year, out)}")


if __name__ == "__main__":
    main()
