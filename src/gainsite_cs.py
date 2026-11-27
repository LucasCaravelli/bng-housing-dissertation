"""Gain sites and nearby prices: doubly robust Callaway-Sant'Anna with an equivalence test.

Run from the Pipeline folder, after src/gainsite_did.py 2026-11-06_sites (site cells):
    python src/gainsite_cs.py [reps]

Panel: 423 sites x 17 half-years (2018H1-2026H1). Outcome: mean quality-adjusted log price
0-1 km minus 2-4 km around the site. Cohort: half-year of the reference date. Covariates:
log area, built-up share 0-1 km, woodland habitat, surrounding IMD 2025, 2018-19 price level.
Specification, checks and robustness are pre-specified in notes/gainsite_cs.md; the
estimator is in src/drdid.py.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import drdid  # noqa: E402
from gainsite_did import OUT_DIR, WORK, load_sites  # noqa: E402
from hedonic_base import HOUS  # noqa: E402

TAG = "2026-11-06_sites"
IMD_FILE = config.RAW_ROOT / "RawData-Housing" / "File_7_IoD2025_All_Ranks_Scores_Deciles_Population_Denominators.csv"
NH, COHORTS = 17, [12, 13, 14, 15]              # 2024H1 .. 2025H2
BOUND = np.log(1.03)                             # equivalence bound, log points
COVARIATES = ["log_area", "builtup_0_1k", "woodland", "imd_score", "pre_price"]


# ---------------------------------------------------------------------------
# Panel and covariates
# ---------------------------------------------------------------------------

def outcome_panel(sites, existing=False):
    """Sites x half-years: mean u 0-1 km minus mean u 2-4 km (NaN unless both rings sold)."""
    c = pd.read_parquet(WORK / f"site_cells_{TAG}.parquet")
    c = c[c.ring != "1-2km"].copy()
    c["ring"] = np.where(c.ring == "2-4km", "outer", "inner")
    nn, uu = ("n_ex", "u_ex") if existing else ("n", "u")
    c["h"] = c.q // 2
    g = c.groupby(["ref", "ring", "h"])[[nn, uu]].sum()
    n, u = g[nn].unstack("ring"), g[uu].unstack("ring")
    mean = (u / n.where(n >= 1))
    y = (mean.inner - mean.outer).unstack("h").reindex(index=sites.ref, columns=range(NH))
    return y.to_numpy()


def imd_near_sites(sites):
    """Population-weighted mean IMD 2025 score of the LSOAs with any postcode within 1 km of
    the site edge."""
    imd = pd.read_csv(IMD_FILE, usecols=["LSOA code (2021)", "Index of Multiple Deprivation (IMD) Score",
                                         "Total population: mid 2022"])
    imd.columns = ["lsoa21cd", "score", "pop"]
    pc = pd.read_parquet(HOUS / "onspd_england.parquet", columns=["pcds", "easting", "northing", "lsoa21cd"])
    tree = cKDTree(pc[["easting", "northing"]].to_numpy())
    lsoa = pc.lsoa21cd.astype(str).to_numpy()
    imd = imd.set_index("lsoa21cd")
    out = []
    for r in sites.itertuples():
        near = set(lsoa[tree.query_ball_point([r.easting, r.northing], r=r.radius_m + 1000)])
        sub = imd.reindex(sorted(near)).dropna()
        out.append(np.average(sub.score, weights=sub["pop"]) if len(sub) else np.nan)
    return np.array(out)


def pre_price(sites):
    """Mean u of sales within 1 km in 2018-2019 (half-years 0-3), and their number (the
    pre-BNG weight of the sales-weighted version)."""
    c = pd.read_parquet(WORK / f"site_cells_{TAG}.parquet")
    c = c[c.ring.isin(["0-500m", "500m-1km"]) & (c.q < 8)]
    g = c.groupby("ref")[["n", "u"]].sum()
    level = (g.u / g.n.where(g.n > 0)).reindex(sites.ref).to_numpy()
    return level, g.n.reindex(sites.ref).fillna(0).to_numpy()


def build():
    s = load_sites(TAG)
    s["G"] = (s.gq // 2).astype(float)
    s["log_area"] = np.log(s.site_ha)
    s["woodland"] = (s.main_habitat == "Woodland and forest").astype(float)
    s["imd_score"] = imd_near_sites(s)
    s["pre_price"], s["pre_sales"] = pre_price(s)
    missing = s[COVARIATES].isna().any(axis=1)
    print(f"sites {len(s)}; dropped for a missing covariate: {int(missing.sum())} "
          f"({s.loc[missing, COVARIATES].isna().sum().to_dict()})")
    s = s[~missing].reset_index(drop=True)
    return s


def standardise(X):
    return (X - X.mean(0)) / X.std(0)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_2x2(Y, G):
    """C2: with no covariates every ATT(g,t) equals the 2x2 difference of mean changes."""
    cells, _ = drdid.att_gt(Y, G, None, COHORTS)
    worst = 0.0
    for c in cells:
        g, t, b = c["g"], c["t"], c["g"] - 2
        ok = ~np.isnan(Y[:, t]) & ~np.isnan(Y[:, b])
        tr = (G == g) & ok
        co = (G > max(t, b) + 1) & (G != g) & ok
        manual = np.mean(Y[tr, t] - Y[tr, b]) - np.mean(Y[co, t] - Y[co, b])
        worst = max(worst, abs(manual - c["att"]))
    print(f"C2 no-covariate ATT(g,t) vs 2x2 means: max |diff| {worst:.1e} over {len(cells)} cells")
    assert worst < 1e-12, "C2 failed"


def overlap(Y, G, X):
    """C3: propensity-score range and trimmed share, post cells."""
    rows = []
    for g in COHORTS:
        b = g - 2
        for t in range(g, NH):
            ok = ~np.isnan(Y[:, t]) & ~np.isnan(Y[:, b])
            tr, co = (G == g) & ok, (G > t + 1) & (G != g) & ok
            keep = tr | co
            if tr.sum() < 5 or co.sum() < 10:
                continue
            Z = np.column_stack([np.ones(keep.sum()), X[keep]])
            p = 1 / (1 + np.exp(-np.clip(Z @ drdid.logit(Z, tr[keep].astype(float)), -35, 35)))
            pc = p[~tr[keep]]
            rows.append({"g": g, "t": t, "p_min_control": pc.min(), "p_max_control": pc.max(),
                         "trimmed": int((pc > drdid.TRIM).sum()), "controls": int(len(pc))})
    o = pd.DataFrame(rows)
    print(f"C3 overlap (post cells): control p range {o.p_min_control.min():.3f}-{o.p_max_control.max():.3f}; "
          f"controls trimmed {int(o.trimmed.sum())} of {int(o.controls.sum())} cell-units")
    return o


# ---------------------------------------------------------------------------
# One specification with bootstrap inference
# ---------------------------------------------------------------------------

def run(label, Y, G, X, reps, delta=1, W=None):
    est = drdid.estimate(Y, G, X, COHORTS, delta=delta, W=W)
    rng = np.random.default_rng(config.SEED)
    boot, boot_events = drdid.bootstrap(Y, G, X, COHORTS, reps, rng, delta=delta, W=W)
    boot = boot[~np.isnan(boot)]
    se = boot.std(ddof=1)
    lo95, hi95 = np.percentile(boot, [2.5, 97.5])
    lo90, hi90 = np.percentile(boot, [5, 95])
    # pre-trend Wald test on e <= -3 (e = -2 is the base, e = -1 the anticipation half-year)
    pre_e = [e for e in est["event"] if e <= -2 - delta]
    B = np.array([[be.get(e, np.nan) for e in pre_e] for be in boot_events])
    B = B[~np.isnan(B).any(axis=1)]
    beta_pre = np.array([est["event"][e] for e in pre_e])
    V = np.cov(B, rowvar=False)
    wald = float(beta_pre @ np.linalg.solve(V, beta_pre))
    row = {"spec": label, "att": est["overall"], "se_boot": se, "ci95_lo": lo95, "ci95_hi": hi95,
           "ci90_lo": lo90, "ci90_hi": hi90, "equivalent_3pct": bool(lo90 > -BOUND and hi90 < BOUND),
           "pct": 100 * (np.exp(est["overall"]) - 1), "pretrend_p": float(chi2.sf(wald, len(pre_e))),
           "n_sites": int(len(G)), "treated_sites": int(np.isin(G, COHORTS).sum()),
           "cells": len(est["cells"]), "skipped_cells": len(est["skipped"]), "reps_used": len(boot)}
    ev = pd.DataFrame({"e": list(est["event"]), "att": list(est["event"].values())})
    ev["se_boot"] = [np.nanstd([be.get(e, np.nan) for be in boot_events], ddof=1) for e in ev.e]
    ev["spec"] = label
    print(f"{label:38s} ATT {row['att']:+.4f} (SE {se:.4f}) 95% [{lo95:+.4f}, {hi95:+.4f}] "
          f"90% [{lo90:+.4f}, {hi90:+.4f}] equivalent(+/-3%) {row['equivalent_3pct']}; "
          f"pre-trend p {row['pretrend_p']:.2f}; cells {row['cells']} (skipped {row['skipped_cells']})")
    return row, ev, est


def tost_existing():
    """Equivalence (+/-3%) for the sales-weighted ring and stacked designs (pre-specified):
    beta +/- 1.645 SE inside +/-log(1.03), normal approximation, clustered SEs."""
    t1 = pd.read_csv(OUT_DIR / f"t1_ring_did_{TAG}.csv").iloc[0]
    t2 = pd.read_csv(OUT_DIR / f"t2_stacked_{TAG}.csv")
    rows = [("T1 ring DiD (urban fringe 2024-25)", t1.beta, t1.se)]
    rows += [(r.spec, r.beta, r.se) for r in t2.itertuples() if r.spec[:2] in ("1a", "1f")]
    out = []
    for label, b, se in rows:
        lo, hi = b - 1.645 * se, b + 1.645 * se
        out.append({"design": label, "beta": b, "se": se, "ci90_lo": lo, "ci90_hi": hi,
                    "equivalent_3pct": bool(lo > -BOUND and hi < BOUND)})
        print(f"TOST {label[:45]:45s} beta {b:+.4f} 90% [{lo:+.4f}, {hi:+.4f}] within +/-{BOUND:.4f}: "
              f"{lo > -BOUND and hi < BOUND}")
    pd.DataFrame(out).to_csv(OUT_DIR / f"tost_existing_{TAG}.csv", index=False)


def main_weighted(reps=499):
    """Sales-weighted version (pre-specified in notes/gainsite_cs.md, after the unweighted run)."""
    s = build()
    G = s.G.to_numpy()
    X = standardise(s[COVARIATES].to_numpy(float))
    Y = outcome_panel(s)
    W = s.pre_sales.to_numpy(float)
    assert (W >= 1).all()
    print(f"weights (2018-19 sales within 1 km): median {np.median(W):.0f}, IQR "
          f"{np.percentile(W, 25):.0f}-{np.percentile(W, 75):.0f}, max {W.max():.0f}; "
          f"effective sites {W.sum() ** 2 / (W ** 2).sum():.0f} of {len(W)}")
    w2 = drdid.estimate(Y, G, X, COHORTS, W=np.ones(len(G)))["overall"]
    unweighted = pd.read_csv(OUT_DIR / f"cs_drdid_{TAG}.csv").att.iloc[0]      # saved main result
    print(f"W2 weights all 1: {w2:.12f} vs saved unweighted main {unweighted:.12f}")
    assert abs(w2 - unweighted) < 1e-12, "W2 failed"
    rows, events = [], []
    specs = [("W Main: DR, full covariates, sales-weighted", Y, G, X, 1, None),
             ("W-R1 No covariates", Y, G, None, 1, None),
             ("W-R2 delta 0 (base g-1)", Y, G, X, 0, None),
             ("W-R3 Existing homes only", outcome_panel(s, existing=True), G, X, 1, None),
             ("W-R4 Urban-fringe sites only", Y, G, X, 1, s.urban_fringe.to_numpy())]
    for label, Yk, Gk, Xk, delta, keep in specs:
        Wk = W
        if keep is not None:
            Yk, Gk, Wk = Yk[keep], Gk[keep], W[keep]
            Xk = None if Xk is None else standardise(s.loc[keep, COVARIATES].to_numpy(float))
        row, ev, _ = run(label, Yk, Gk, Xk, reps, delta, W=Wk)
        rows.append(row)
        events.append(ev)
    pd.DataFrame(rows).to_csv(OUT_DIR / f"cs_drdid_weighted_{TAG}.csv", index=False)
    pd.concat(events).to_csv(OUT_DIR / f"cs_event_study_weighted_{TAG}.csv", index=False)
    print("\nweighted main event study:")
    print(events[0][["e", "att", "se_boot"]].round(4).to_string(index=False))
    print()
    tost_existing()


def main(reps=499):
    s = build()
    G = s.G.to_numpy()
    X = standardise(s[COVARIATES].to_numpy(float))
    Y = outcome_panel(s)
    print(f"panel: {Y.shape[0]} sites x {Y.shape[1]} half-years; observed cells {np.mean(~np.isnan(Y)):.0%}; "
          f"treated 2024H1-2025H2: {int(np.isin(G, COHORTS).sum())}; by cohort "
          f"{ {int(g): int((G == g).sum()) for g in COHORTS} }")

    check_2x2(Y, G)
    ov = overlap(Y, G, X)
    parts = {k: drdid.estimate(Y, G, X, COHORTS, kind=k)["overall"] for k in ["dr", "ipw", "or"]}
    print(f"C4 overall ATT: DR {parts['dr']:+.4f}, IPW {parts['ipw']:+.4f}, regression {parts['or']:+.4f}")

    rows, events = [], []
    specs = [("Main: DR, full covariates, delta 1", Y, G, X, 1, None),
             ("R1 No covariates", Y, G, None, 1, None),
             ("R2 delta 0 (base g-1)", Y, G, X, 0, None),
             ("R3 Existing homes only", outcome_panel(s, existing=True), G, X, 1, None),
             ("R4 Urban-fringe sites only", Y, G, X, 1, s.urban_fringe.to_numpy()),
             ("R5 Drop two 1 km sites", Y, G, X, 1, (s.gr_digits != 4).to_numpy())]
    for label, Yk, Gk, Xk, delta, keep in specs:
        if keep is not None:
            Yk, Gk = Yk[keep], Gk[keep]
            Xk = None if Xk is None else standardise(s.loc[keep, COVARIATES].to_numpy(float))
        row, ev, _ = run(label, Yk, Gk, Xk, reps, delta)
        rows.append(row)
        events.append(ev)

    tab = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tab.to_csv(OUT_DIR / f"cs_drdid_{TAG}.csv", index=False)
    pd.concat(events).to_csv(OUT_DIR / f"cs_event_study_{TAG}.csv", index=False)
    ov.to_csv(OUT_DIR / f"cs_overlap_{TAG}.csv", index=False)
    main_ev = events[0]
    print("\nmain event study (e = t - g; e = -2 is the base):")
    print(main_ev[["e", "att", "se_boot"]].round(4).to_string(index=False))


if __name__ == "__main__":
    n_reps = int(sys.argv[1]) if len(sys.argv) > 1 else 499
    main_weighted(n_reps) if "weighted" in sys.argv[2:] else main(n_reps)
