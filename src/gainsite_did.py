"""Gain-site price tests on ring x quarter cells: ring DiD (T1) and stacked DiD with
later-registered sites as controls (T2, T3), with the event study (validation target 6).

Run from the Pipeline folder, after src/hedonic_base.py and src/gainsite_context.py:
    python src/gainsite_did.py

Cells: for each site, postcodes within (r + 4 km) are put into rings by distance from the
implied site edge, and their postcode x quarter sales counts and residual sums (first stage,
src/hedonic_base.py) are added up per ring and quarter. A cell-level weighted regression
(y = mean residual, weight = sales) equals the sale-level one when every regressor is constant
within a ring x quarter.

T1 Ring DiD (pilot): urban-fringe sites treated in 2024-25; 0-1 km (inner) vs 2-4 km (outer);
   FE site x ring and site x quarter; SE clustered by site.
T2/T3 Stacked clean-control DiD (zu Ermgassen et al. 2023: later offsets as controls;
   Cengiz et al. 2019 stacking): for each registration quarter g, treated = sites registered in
   g, controls = sites registered after g + 3 (+ buffer); window g-12 .. g+3; inner ring;
   FE stack x site and stack x quarter. T3 times treatment at works start when earlier.
Specification and checks: notes/gainsite_prices.md.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
from scipy import sparse
from scipy.spatial import cKDTree
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from hedonic_base import Q_END, WORK, quarter_index  # noqa: E402
from intensity_robustness import fit_hand  # noqa: E402

CONTEXT = config.PROCESSED_DIR / "bng"
OUT_DIR = config.PROCESSED_DIR / "gainsites"
PILOT = config.RAW_ROOT / "BNG" / "output" / "tests"
MAXD = 4000
RING_EDGES = np.array([500.0, 1000.0, 2000.0])
RING_LABELS = np.array(["0-500m", "500m-1km", "1-2km", "2-4km"])
PRE, POST = 12, 3


# ---------------------------------------------------------------------------
# Sites and cells
# ---------------------------------------------------------------------------

def load_sites(tag):
    s = pd.read_csv(CONTEXT / f"gainsite_context_{tag}.csv")
    s["treat"] = pd.to_datetime(s.treat)
    s["works"] = pd.to_datetime(s.works_start, errors="coerce")
    s["treat_early"] = s[["treat", "works"]].min(axis=1)       # works start if earlier
    s["gq"] = quarter_index(s.treat)
    s["gq_early"] = quarter_index(s.treat_early)
    return s


class Cells:
    """Postcode x quarter matrices and a tree of postcode locations."""

    def __init__(self):
        self.pc = pd.read_parquet(WORK / "pc_index.parquet")
        self.xy = self.pc[["easting", "northing"]].to_numpy().astype(float)
        self.tree = cKDTree(self.xy)
        self.M = {k: sparse.load_npz(WORK / f"pcq_{k}.npz").tocsr() for k in ["n", "u", "n_ex", "u_ex"]}
        self.nq = self.M["n"].shape[1]

    def postcode_density(self, x, y, r, within=1000):
        """Postcodes with any sale within `within` m of the edge (a proxy for urbanity)."""
        return len(self.tree.query_ball_point([x, y], r=r + within))

    def rings(self, pts, id_col="ref"):
        out = []
        for p in pts.itertuples(index=False):
            pid, x, y, r = getattr(p, id_col), p.easting, p.northing, p.radius_m
            idx = np.asarray(self.tree.query_ball_point([x, y], r=r + MAXD), dtype=int)
            if idx.size == 0:
                continue
            d = np.clip(np.hypot(self.xy[idx, 0] - x, self.xy[idx, 1] - y) - r, 0, None)
            ring = np.searchsorted(RING_EDGES, d, side="right")       # 0..3, edges excluded right
            ind = sparse.csr_matrix((np.ones(idx.size), (ring, np.arange(idx.size))), shape=(4, idx.size))
            blocks = {k: (ind @ m[idx]).toarray() for k, m in self.M.items()}
            rr, qq = np.meshgrid(np.arange(4), np.arange(self.nq), indexing="ij")
            out.append(pd.DataFrame({id_col: pid, "ring": RING_LABELS[rr.ravel()], "q": qq.ravel(),
                                     **{k: v.ravel() for k, v in blocks.items()}}))
        return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------
# T1: ring DiD, pilot sample
# ---------------------------------------------------------------------------

def ring_did(s, c):
    p = s[s.urban_fringe & (s.cohort <= 2025)][["ref", "gq"]]
    x = c.merge(p, on="ref")
    x = x[(x.ring != "1-2km") & (x.n > 0)].copy()
    x["e"] = x.q - x.gq
    x = x[x.e >= -20]                                   # up to 5 years before treatment
    x["inner"] = (x.ring != "2-4km").astype(int)
    x.loc[x.inner == 1, "ring"] = "0-1km"
    x = x.groupby(["ref", "ring", "q", "e", "inner"], as_index=False)[["n", "u"]].sum()
    x["y"] = x.u / x.n
    x["inner_post"] = x.inner * (x.e >= 0)
    x["site_ring"] = x.ref + "_" + x.ring
    x["site_q"] = x.ref + "_" + x.q.astype(str)
    m = pf.feols("y ~ inner_post | site_ring + site_q", data=x, weights="n", vcov={"CRV1": "ref"})
    b, se = float(m.coef()["inner_post"]), float(m.se()["inner_post"])
    # hand route. Compared like with like: pyfixest by default drops singleton fixed-effect
    # cells (98 here), which leaves beta unchanged but moves the clustered SE by ~1e-4
    # relative; and its (N-1)/(N-k) factor is switched off in both routes.
    m0 = pf.feols("y ~ inner_post | site_ring + site_q", data=x, weights="n", vcov={"CRV1": "ref"},
                  ssc=pf.ssc(k_adj=False), fixef_rm="none")
    b_hand, se_hand = fit_hand(x.rename(columns={"ref": "code"}), "y", "n", ["site_ring", "site_q"],
                               ["inner_post"], k=1)
    assert abs(b - b_hand) < 1e-9 and abs(se_hand - float(m0.se()["inner_post"])) < 1e-9, "T1 hand route"
    return {"beta": b, "se": se, "beta_hand": b_hand, "se_hand_no_k_adj": se_hand,
            "se_pyfixest_no_k_adj": float(m0.se()["inner_post"]),
            "sites": x.ref.nunique(), "sales": int(x.n.sum())}


# ---------------------------------------------------------------------------
# T2, T3: stacked DiD
# ---------------------------------------------------------------------------

def inner_outer(c):
    c = c[c.ring != "1-2km"].copy()
    c["ring"] = np.where(c.ring == "2-4km", "outer", "inner")
    return c.groupby(["ref", "ring", "q"], as_index=False)[["n", "u", "n_ex", "u_ex"]].sum()


def build_stacks(c2, sites, gcol="gq", buffer=0, existing=False):
    nn, uu = ("n_ex", "u_ex") if existing else ("n", "u")
    stacks, info = [], []
    for g in sorted(sites[gcol].unique()):
        if g + POST > Q_END:
            continue
        tr = sites.loc[sites[gcol] == g, "ref"]
        co = sites.loc[sites[gcol] > g + POST + buffer, "ref"]
        if len(tr) == 0 or len(co) == 0:
            continue
        x = c2[c2.ref.isin(pd.concat([tr, co])) & c2.q.between(g - PRE, g + POST)].copy()
        x["n_"], x["u_"] = x[nn], x[uu]
        x = x[x.n_ > 0]
        x["stk"], x["treated"], x["e"] = g, x.ref.isin(tr).astype(int), x.q - g
        stacks.append(x)
        info.append({"g": g, "treated": len(tr), "controls": len(co)})
    d = pd.concat(stacks, ignore_index=True)
    d["y"] = d.u_ / d.n_
    d["post"] = (d.e >= 0).astype(int)
    d["inner"] = (d.ring == "inner").astype(int)
    d["tp"] = d.treated * d.post
    d["itp"] = d.inner * d.tp
    st = d.stk.astype(str)
    d["s_site"] = st + "_" + d.ref
    d["s_q"] = st + "_" + d.q.astype(str)
    d["s_site_ring"] = d.s_site + "_" + d.ring
    d["s_site_q"] = d.s_site + "_" + d.q.astype(str)
    d["s_ring_q"] = st + "_" + d.ring + "_" + d.q.astype(str)
    return d, pd.DataFrame(info)


def fit_stack(d, kind):
    if kind == "inner":
        x = d[d.inner == 1]
        m = pf.feols("y ~ tp | s_site + s_q", data=x, weights="n_", vcov={"CRV1": "ref"})
        k = "tp"
    else:
        x = d
        m = pf.feols("y ~ itp | s_site_ring + s_site_q + s_ring_q", data=x, weights="n_", vcov={"CRV1": "ref"})
        k = "itp"
    xi = x[x.inner == 1]
    return {"beta": float(m.coef()[k]), "se": float(m.se()[k]),
            "treated_sites": xi.loc[xi.treated == 1, "ref"].nunique(),
            "control_sites": xi.loc[xi.treated == 0, "ref"].nunique(), "cells": m._N}


def event_study(d):
    x = d[d.inner == 1].copy()
    x["b"] = np.floor(x.e / 2).astype(int)              # half-years: -6..-1 pre, 0..1 post
    bins = [k for k in sorted(x.b.unique()) if k != -1]
    names = []
    for k in bins:
        nm = f"b_{k}".replace("-", "m")
        x[nm] = ((x.b == k) & (x.treated == 1)).astype(int)
        names.append(nm)
    m = pf.feols(f"y ~ {' + '.join(names)} | s_site + s_q", data=x, weights="n_", vcov={"CRV1": "ref"})
    es = pd.DataFrame({"halfyear": bins, "beta": m.coef()[names].values, "se": m.se()[names].values})
    pre = [nm for k, nm in zip(bins, names) if k < -1]
    cn = list(m.coef().index)
    w = m.wald_test(R=np.eye(len(cn))[[cn.index(p) for p in pre]])
    # pyfixest 0.70 reports an F statistic (Wald / q); the pilot's version reported the
    # chi-square form. Report the chi-square p-value for comparability, and the F p-value.
    q = len(pre)
    p_chi2 = float(chi2.sf(w.wald_statistic * q, q)) if w.distribution == "F" else float(w.pvalue)
    return es, p_chi2, float(w.pvalue)


# ---------------------------------------------------------------------------

def main(tag="2026-10-12_rows", exclude_coarse=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s = load_sites(tag)
    if exclude_coarse:
        # sensitivity: sites located only to 1 km (4-digit grid reference) dropped
        print(f"dropping {int((s.gr_digits == 4).sum())} sites located only to 1 km: "
              f"{s.loc[s.gr_digits == 4, 'ref'].tolist()}")
        s = s[s.gr_digits != 4].copy()
        tag_out = tag + "_no1km"
    else:
        tag_out = tag
    cells = Cells()
    c = cells.rings(s[["ref", "easting", "northing", "radius_m"]])
    c.to_parquet(WORK / f"site_cells_{tag}.parquet", index=False)
    print(f"cells: {len(c):,}; sites {c.ref.nunique()}; inner-ring sales (repeats across sites) "
          f"{int(c.loc[c.ring.isin(['0-500m', '500m-1km']), 'n'].sum()):,}")

    t1 = ring_did(s, c)
    print(f"\nT1 ring DiD: beta {t1['beta']:.7f} (SE {t1['se']:.7f}); sites {t1['sites']}, sales {t1['sales']:,}")
    print(f"   hand route: beta {t1['beta_hand']:.7f}; SE without k-adjustment: hand "
          f"{t1['se_hand_no_k_adj']:.9f} vs pyfixest {t1['se_pyfixest_no_k_adj']:.9f}")

    c2 = inner_outer(c)
    specs = [("1a All sites, inner ring only", {}, "inner", None),
             ("1b All sites, ring DDD (inner vs 2-4 km)", {}, "ddd", None),
             ("1c Urban fringe only, inner ring", {}, "inner", "fringe"),
             ("1d Urban fringe only, ring DDD", {}, "ddd", "fringe"),
             ("1e Anticipation buffer: controls registered >= 1 year after window", {"buffer": 4}, "inner", None),
             ("1f Treatment = works start if earlier than reference date", {"gcol": "gq_early"}, "inner", None),
             ("1g Existing homes only (no new builds)", {"existing": True}, "inner", None)]
    rows = []
    for label, kw, kind, sub in specs:
        ss = s[s.urban_fringe] if sub == "fringe" else s
        d, _ = build_stacks(c2, ss, **kw)
        rows.append({"spec": label, **fit_stack(d, kind)})
    t = pd.DataFrame(rows)
    d, _ = build_stacks(c2, s)
    es, p_pre, p_pre_f = event_study(d)

    # comparison with the pilot (G4)
    old = pd.read_csv(PILOT / "test1_staggered.csv")
    m = t.merge(old, on="spec", suffixes=("", "_pilot"), validate="one_to_one")
    m["d_beta"], m["d_se"] = (m.beta - m.beta_pilot).abs(), (m.se - m.se_pilot).abs()
    pd.set_option("display.width", 200)
    print("\nT2/T3 stacked DiD vs pilot:")
    print(m[["spec", "beta", "beta_pilot", "se", "se_pilot", "treated_sites", "treated_sites_pilot",
             "control_sites", "cells", "cells_pilot"]].round(7).to_string(index=False))
    print(f"max |beta - pilot| {m.d_beta.max():.1e}; max |SE - pilot| {m.d_se.max():.1e}")
    old_es = pd.read_csv(PILOT / "test1_event_study.csv")
    e = es.merge(old_es, on="halfyear", suffixes=("", "_pilot"))
    print(f"event study: max |beta - pilot| {(e.beta - e.beta_pilot).abs().max():.1e}; "
          f"joint pre-test p = {p_pre:.4f} chi-square (pilot 0.2378); F version {p_pre_f:.4f}")

    pd.DataFrame([{"test": "T1 ring DiD (urban fringe, 2024-25)", **t1, "pretrend_p_chi2": p_pre}]).to_csv(
        OUT_DIR / f"t1_ring_did_{tag_out}.csv", index=False)
    t.to_csv(OUT_DIR / f"t2_stacked_{tag_out}.csv", index=False)
    es.to_csv(OUT_DIR / f"t2_event_study_{tag_out}.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-10-12_rows",
         exclude_coarse="no1km" in sys.argv[2:])
