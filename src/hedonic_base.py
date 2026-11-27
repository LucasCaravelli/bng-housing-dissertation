"""Quality-adjusted prices for every English sale, and postcode x quarter cells.

Run from the Pipeline folder, after src/housing_inputs.py:
    python src/hedonic_base.py

Why: every gain-site test compares price changes across rings, sites or places. Doing the
hedonic adjustment once, for all of England, keeps the tests consistent and lets placebo
sites be drawn anywhere without re-reading Price Paid.

1. Sales: category A, England, Jan 2018-Jun 2026 (later 2026 months are incomplete:
   registration lag, worst for new builds), price >= GBP 20,000, with postcode coordinates.
2. First stage:  ln P_i = a_{LAD x quarter} + b_{type x tenure x new build} + u_i.
   u_i is the price relative to similar homes sold in the same council and quarter; taking out
   LAD x quarter removes local market cycles (e.g. the 2020-21 stamp duty holiday) before any
   site comparison. Checked against a hand route (alternating demeaning).
3. Cells: postcode x quarter counts and sums of u, all sales and existing homes only (new
   builds may be built by the gain site's own developer).

Outputs (WORK_ROOT/gainsites/, large, outside OneDrive):
    sales_resid.parquet, pc_index.parquet, pcq_{n,u,n_ex,u_ex}.npz
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from intensity_robustness import demean  # noqa: E402

HOUS = config.PROCESSED_DIR / "housing"
WORK = config.WORK_ROOT / "gainsites"
END = pd.Timestamp("2026-06-30")
FIRST_YEAR, MIN_PRICE = 2018, 20_000


def quarter_index(dates):
    """2018 Q1 = 0, so event time is a subtraction."""
    d = pd.to_datetime(dates)
    return ((d.dt.year - FIRST_YEAR) * 4 + (d.dt.quarter - 1)).astype(int)


Q_END = int(quarter_index(pd.Series([END]))[0])      # 2026 Q2 = 33


def load_sales():
    parts = []
    for year in range(FIRST_YEAR, END.year + 1):
        x = pd.read_parquet(HOUS / f"ppd_{year}.parquet",
                            columns=["tid", "price", "date", "pcds", "ptype", "new", "tenure", "addr"])
        parts.append(x[(x.date <= END) & (x.price >= MIN_PRICE)])
    d = pd.concat(parts, ignore_index=True)
    n0 = len(d)
    pc = pd.read_parquet(HOUS / "onspd_england.parquet",
                         columns=["pcds", "easting", "northing", "lsoa21cd", "lad26cd"]).dropna(subset=["easting"])
    d = d.merge(pc, on="pcds", how="inner")           # inner merge keeps the order of the sales
    print(f"sales {n0:,}; with postcode coordinates {len(d):,} ({len(d) / n0:.2%})")
    d["q"] = quarter_index(d.date)
    d["lp"] = np.log(d.price)
    d["ptype"], d["tenure"] = d.ptype.astype(str), d.tenure.astype(str)
    d["new"] = d.new.astype(int)
    d["lad"] = d.lad26cd.astype(str)
    d["hed"] = d.ptype + "_" + d.tenure + "_" + d.new.astype(str)
    d["lad_q"] = d.lad + "_" + d.q.astype(str)
    return d


def first_stage(d):
    m = pf.feols("lp ~ 1 | lad_q + hed", data=d[["lp", "lad_q", "hed"]], vcov="iid", fixef_rm="none")
    u = d.lp.to_numpy() - m.predict()
    # hand route: residual of lp after removing both sets of fixed effects
    u_hand = demean(d[["lp"]].to_numpy(), [d.lad_q, d.hed], np.ones(len(d)), tol=1e-10)[:, 0]
    diff = np.max(np.abs(u - u_hand))
    print(f"first stage: R2 {1 - u.var() / d.lp.var():.3f}; sd(u) {u.std():.4f}; "
          f"max |pyfixest - hand residual| {diff:.1e}")
    assert diff < 1e-6, "first-stage residuals disagree between routes"
    return u


def cells(d):
    pcs = d[["pcds", "easting", "northing"]].drop_duplicates("pcds").reset_index(drop=True)
    pcs["row"] = np.arange(len(pcs))
    rows = d[["pcds"]].merge(pcs[["pcds", "row"]], on="pcds", how="left").row.to_numpy()
    shape = (len(pcs), Q_END + 1)
    existing = (d.new == 0).to_numpy().astype(float)

    def mat(w):
        return sparse.csr_matrix((w, (rows, d.q.to_numpy())), shape=shape)

    sparse.save_npz(WORK / "pcq_n.npz", mat(np.ones(len(d))))
    sparse.save_npz(WORK / "pcq_u.npz", mat(d.u.to_numpy()))
    sparse.save_npz(WORK / "pcq_n_ex.npz", mat(existing))
    sparse.save_npz(WORK / "pcq_u_ex.npz", mat(d.u.to_numpy() * existing))
    pcs.to_parquet(WORK / "pc_index.parquet", index=False)
    print(f"postcodes with sales: {len(pcs):,}; quarters: {Q_END + 1}")


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    d = load_sales()
    d["u"] = first_stage(d)
    keep = ["tid", "price", "date", "q", "pcds", "easting", "northing", "lsoa21cd", "lad",
            "ptype", "tenure", "new", "addr", "lp", "u"]
    d[keep].to_parquet(WORK / "sales_resid.parquet", index=False)
    cells(d)


if __name__ == "__main__":
    main()
