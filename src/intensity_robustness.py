"""Robustness checks and event study for the within-England BNG intensity DiD (target 4b).

Run from the Pipeline folder, after the planning panel, intensity score and NN scripts:
    python src/intensity_robustness.py

Baseline:  y_it = a_i + l_t + beta * (I_i x Post_t) + e_it   (notes/intensity_did.md)
Checks 1-18, the event study and the pre-trend test are the pilot's pre-registered set,
rebuilt here; definitions and checks in notes/intensity_robustness.md.

Every linear estimate is computed twice: pyfixest, and by hand (demeaning on all fixed
effects, OLS on the remaining regressors, hand-coded CRV1 with the pilot's K). PPML is
computed with pyfixest and with statsmodels GLM on explicit dummies.
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
import scipy.sparse as sp
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from planning_panel import PS2_FILE, TO_2025, load_england, read_mhclg  # noqa: E402

warnings.filterwarnings("ignore", category=FutureWarning)

PROC = config.PROCESSED_DIR
PANEL = PROC / "planning" / "panel_england_lpa2025_quarter.csv"
UNITS = PROC / "planning" / "units_england_lpa2025.csv"
NN = PROC / "planning" / "nutrient_neutrality_lpa2025.csv"
INTENSITY = PROC / "intensity" / "intensity_lpa2025.csv"
OUT_DIR = PROC / "intensity"
PILOT_DIR = config.RAW_ROOT / "Planning" / "output" / "intensity"

DROP_QUARTERS = ["2023 Q4", "2024 Q1", "2024 Q2"]
POST_START, PRE_END, REF_Q = "2024 Q3", "2023 Q3", "2023 Q3"

OUTCOMES = [("ly", "log(1+dwelling decisions)", None),
            ("grate", "dwelling grant rate", "dw_dec"),
            ("lhh", "log(1+householder decisions) [placebo]", None)]
COUNTS = {"ly": "dw_dec", "lhh": "dec_hh"}          # PPML outcomes

# fixed-effect specifications: absorbed FE (pyfixest syntax and demeaning groups)
FE = {
    "lpa+quarter": ["code", "Quarter"],
    "region_quarter": ["code", "region^Quarter"],
    "nn_quarter": ["code", "nn^Quarter"],
    "region_nn_quarter": ["code", "region^Quarter", "nn^Quarter"],
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def quarter_number(quarter):
    """'2024 Q3' -> 2024.5"""
    return quarter.str[:4].astype(int) + (quarter.str[-1].astype(int) - 1) / 4


def load():
    p = pd.read_csv(PANEL)
    r = pd.read_csv(INTENSITY)
    keep = ["code", "intensity", "main_sample", "fringe_ratio"] + [c for c in r.columns if c.startswith("z0_")]
    p = p.merge(r[keep], on="code", how="left", validate="many_to_one")
    nn = pd.read_csv(NN)[["code", "nn", "nn_area_share"]]
    p = p.merge(nn, on="code", how="left", validate="many_to_one")
    units = pd.read_csv(UNITS)[["code", "dc_note"]]
    p["dc_host"] = p.code.isin(units.loc[units.dc_note.notna(), "code"])

    # region of each 2025 unit (constant within a unit; checked)
    ps2 = read_mhclg(PS2_FILE)[["LPACD", "Quarter", "Region"]]
    ps2["code"] = ps2.LPACD.map(TO_2025).fillna(ps2.LPACD)
    n_regions = ps2.groupby("code").Region.nunique()
    assert (n_regions == 1).all(), f"units in two regions: {n_regions[n_regions > 1].index.tolist()}"
    p["region"] = p.code.map(ps2.groupby("code").Region.first())

    # anomalous LPA-quarters: total decisions < 25% of the council's own median (median > 50),
    # found on the raw council rows before aggregation, as in the pilot
    raw = load_england()
    raw["code"] = raw.LPACD.map(TO_2025).fillna(raw.LPACD)
    med = raw.groupby("LPACD").decided_total.transform("median")
    anom = raw.loc[(raw.decided_total < 0.25 * med) & (med > 50), ["code", "Quarter"]]
    p["anom"] = pd.MultiIndex.from_frame(p[["code", "Quarter"]]).isin(pd.MultiIndex.from_frame(anom))
    p["merged"] = p.groupby("code").n_predecessors.transform("max") > 1

    p["q"] = quarter_number(p.Quarter)
    p["t"] = p.q - 2015
    p["dw_dec"] = p.dec_major + p.dec_minor
    p["dw_grant"] = p.grant_major + p.grant_minor
    p["ly"], p["lhh"] = np.log1p(p.dw_dec), np.log1p(p.dec_hh)
    p["grate"] = p.dw_grant / p.dw_dec.where(p.dw_dec > 0)
    p["post"] = (p.Quarter >= POST_START).astype(int)
    p["is_council"] = p.type == "council"
    p["main_sample"] = p.main_sample.astype(bool)
    print(f"anomalous LPA-quarters: {anom.merge(p[['code', 'name']].drop_duplicates()).values.tolist()}")
    return p


# ---------------------------------------------------------------------------
# Estimation: hand route
# ---------------------------------------------------------------------------

def indicator(groups):
    """Sparse n x G matrix of group dummies."""
    idx, _ = pd.factorize(groups)
    n = len(idx)
    return sp.csr_matrix((np.ones(n), (np.arange(n), idx)), shape=(n, idx.max() + 1))


def fe_groups(d, fe_cols):
    out = []
    for col in fe_cols:
        if "^" in col:
            a, b = col.split("^")
            out.append(d[a].astype(str) + "_" + d[b].astype(str))
        else:
            out.append(d[col])
    return out


def demean(M, groups, w, tol=1e-13, max_iter=20_000):
    """Weighted alternating projections on several sets of fixed effects (FWL)."""
    M = M.astype(float).copy()
    mats = [indicator(g) for g in groups]
    wsum = [S.T @ w for S in mats]
    for _ in range(max_iter):
        before = M.copy()
        for S, ws in zip(mats, wsum):
            means = (S.T @ (M * w[:, None])) / ws[:, None]
            M -= S @ means
        if np.max(np.abs(M - before)) < tol:
            return M
    raise RuntimeError("demeaning did not converge")


def fit_hand(d, y, w, fe_cols, xcols, k):
    """OLS of demeaned y on demeaned regressors; CRV1 by LPA with G/(G-1) x (N-1)/(N-k).
    Returns the coefficient and SE of the first regressor."""
    wt = d[w].to_numpy(float) if w else np.ones(len(d))
    M = demean(d[[y] + xcols].to_numpy(), fe_groups(d, fe_cols), wt)
    yy, X = M[:, 0], M[:, 1:]
    XtWX = X.T @ (X * wt[:, None])
    b = np.linalg.solve(XtWX, X.T @ (wt * yy))
    e = yy - X @ b
    scores = indicator(d.code).T @ (X * (wt * e)[:, None])        # G x p
    n, g = len(d), scores.shape[0]
    bread = np.linalg.inv(XtWX)
    V = g / (g - 1) * (n - 1) / (n - k) * bread @ (scores.T @ scores) @ bread
    return b[0], np.sqrt(V[0, 0])


def pilot_k(d, fe, n_extra):
    """Columns of the pilot's statsmodels design: intercept, LPA dummies, group x quarter
    dummies (one base quarter per group omitted), the treatment and any extra regressors."""
    n_lpa, n_q = d.code.nunique(), d.Quarter.nunique()
    groups = {"lpa+quarter": 1, "region_quarter": d.region.nunique(), "nn_quarter": d.nn.nunique(),
              "region_nn_quarter": d.region.nunique() + 1}[fe]
    return 1 + (n_lpa - 1) + groups * (n_q - 1) + 1 + n_extra


# ---------------------------------------------------------------------------
# One check
# ---------------------------------------------------------------------------

def standardise(d, ivar, by_rows=False):
    """Per SD across LPAs (DiD); by_rows reproduces the pilot's event-study scaling."""
    if by_rows:
        return (d[ivar] - d[ivar].mean()) / d[ivar].std()
    per_lpa = d.groupby("code")[ivar].first()
    return (d[ivar] - per_lpa.mean()) / per_lpa.std()


def add_share_terms(d):
    """NN catchment share x quarter dummies, first quarter omitted (the share is constant
    within an LPA, so all quarters would be collinear with the LPA effects)."""
    names = []
    for i, q in enumerate(sorted(d.Quarter.unique())[1:]):
        d[f"sq{i}"] = d.nn_area_share * (d.Quarter == q)
        names.append(f"sq{i}")
    return names


def estimate(d, y, w, ivar="intensity", fe="lpa+quarter", post="post", share=False, binary=False):
    d = d.dropna(subset=[y, ivar]).copy()
    if binary:
        # pilot: terciles of intensity over rows (identical to LPA terciles when balanced)
        terc = pd.qcut(d.groupby("code")[ivar].transform("first"), 3, labels=False)
        d = d[terc != 1].copy()
        d["I"] = (terc[terc != 1] == 2).astype(float)
    else:
        d["I"] = standardise(d, ivar)
    d["IxP"] = d.I * d[post]
    extra = add_share_terms(d) if share else []

    fe_cols = FE[fe]
    rhs = " + ".join(["IxP"] + extra)
    m = pf.feols(f"{y} ~ {rhs} | {' + '.join(fe_cols)}", data=d, weights=w,
                 vcov={"CRV1": "code"}, ssc=pf.ssc(k_fixef="nonnested"))
    k = pilot_k(d, fe, len(extra))
    b_hand, se_hand = fit_hand(d, y, w, fe_cols, ["IxP"] + extra, k)
    return {"beta": float(m.coef()["IxP"]), "se": float(m.se()["IxP"]), "p": float(m.pvalue()["IxP"]),
            "beta_hand": b_hand, "se_hand_pilot_k": se_hand, "n_lpa": d.code.nunique(), "n_obs": len(d)}


def estimate_ppml(d, y):
    d = d.dropna(subset=[y, "intensity"]).copy()
    d["I"] = standardise(d, "intensity")
    d["IxP"] = d.I * d.post
    m = pf.fepois(f"{y} ~ IxP | code + Quarter", data=d, vcov={"CRV1": "code"})
    g = smf.glm(f"{y} ~ IxP + C(code) + C(Quarter)", d, family=sm.families.Poisson()).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d.code)[0]})
    return {"beta": float(m.coef()["IxP"]), "se": float(m.se()["IxP"]), "p": float(m.pvalue()["IxP"]),
            "beta_hand": g.params["IxP"], "se_hand_pilot_k": g.bse["IxP"],
            "n_lpa": d.code.nunique(), "n_obs": len(d)}


def detrend(d, y, w, full_rank=False):
    """Check 5, step one: LPA-specific linear trends fitted on 2015 Q1-2023 Q3 only
    (LPA dummies, quarter dummies, LPA x t), then removed from every quarter.

    LPA dummies + quarter dummies + all LPA x t columns are rank-deficient by one (the
    slopes summed over LPAs equal t, which the quarter dummies span), so the slopes are
    identified only up to a common shift; the shift is absorbed by the quarter effects in
    step two. lstsq returns the minimum-norm solution. full_rank=True instead fixes the
    last LPA's slope at 0; both must give the same beta (checked in run_checks)."""
    pre = d[d.Quarter <= PRE_END].dropna(subset=[y])
    lpa = pd.get_dummies(pre.code, dtype=float)
    qtr = pd.get_dummies(pre.Quarter, dtype=float).iloc[:, 1:]
    slopes = lpa.mul(pre.t, axis=0).add_suffix(":t")
    if full_rank:
        slopes = slopes.iloc[:, :-1]
    X = pd.concat([lpa, qtr, slopes], axis=1)
    wt = np.sqrt(pre[w].to_numpy(float)) if w else np.ones(len(pre))
    coef, *_ = np.linalg.lstsq(X.to_numpy() * wt[:, None], pre[y].to_numpy() * wt, rcond=None)
    slope = pd.Series(coef[-slopes.shape[1]:], index=lpa.columns[:slopes.shape[1]])
    d = d.copy()
    d[y + "_dt"] = d[y] - d.code.map(slope).fillna(0) * d.t
    return d, y + "_dt"


# ---------------------------------------------------------------------------
# All checks
# ---------------------------------------------------------------------------

def run_checks(p):
    full = p
    p = p[~p.Quarter.isin(DROP_QUARTERS)]
    main = p[p.main_sample]
    rows = []

    def add(check, d, **kw):
        for y, label, w in OUTCOMES:
            if kw.get("ppml"):
                if y == "grate":
                    continue
                res = estimate_ppml(d, COUNTS[y])
            elif kw.get("detrend"):
                dd, yy = detrend(d, y, w)
                res = estimate(dd, yy, w)
                dd2, _ = detrend(d, y, w, full_rank=True)
                b2 = estimate(dd2, yy, w)["beta"]
                assert abs(res["beta"] - b2) < 1e-8, f"check 5 ({y}): {res['beta']} vs {b2}"
                res["beta_full_rank_first_step"] = b2
            else:
                res = estimate(d, y, w, **kw)
            rows.append({"check": check, "outcome": label, **res})

    add("1 baseline (main sample)", main)
    add("2 all councils", p[p.is_council])
    add("3 main + London", p[p.main_sample | p.code.str.startswith("E09")])
    add("4 region x quarter FE", main, fe="region_quarter")
    add("5 LPA trends (pre-fitted) removed", main, detrend=True)
    add("6 window 2021Q1+", main[main.q >= 2021])
    for v, lab in [("z0_250_settle10ha_main_share_medplus", "0-250 m"),
                   ("z0_1000_settle10ha_main_share_medplus", "0-1 km"),
                   ("z0_500_settle50ha_main_share_medplus", "settlements >= 50 ha"),
                   ("z0_500_settle10ha_alt_share_medplus", "alt crosswalk"),
                   ("z0_500_settle10ha_main_mean_dist", "mean distinctiveness")]:
        add(f"7 intensity: {lab}", main, ivar=v)
    add("8 top vs bottom tercile", main, binary=True)
    add("9 PPML counts", main, ppml=True)
    add("10 drop anomalies, merged, DC hosts", main[~main.anom & ~main.merged & ~main.dc_host])
    for reg in sorted(main.region.unique()):
        add(f"11 drop {reg}", main[main.region != reg])
    add("13 drop nutrient-neutrality LPAs", main[main.nn == 0])
    add("14 NN x quarter FE", main, fe="nn_quarter")
    add("15 region x quarter + NN x quarter FE", main, fe="region_nn_quarter")
    add("16 NN catchment share x quarter", main, share=True)
    add("17 drop LPAs >=10% in NN catchment", main[main.nn_area_share < 0.10])
    add("18 region x quarter + NN share x quarter", main, fe="region_quarter", share=True)
    placebo = main[main.Quarter <= PRE_END].copy()
    placebo["post_fake"] = (placebo.q >= 2021).astype(int)
    add("12 placebo: fake Post 2021Q1-2023Q3", placebo, post="post_fake")
    return pd.DataFrame(rows), full


# ---------------------------------------------------------------------------
# Event study and pre-trend test
# ---------------------------------------------------------------------------

def event_study(full):
    coefs, trends = [], []
    samples = {"main": full[full.main_sample], "all_councils": full[full.is_council]}
    for sname, d0 in samples.items():
        for scale, by_rows in [("pilot_rows", True), ("per_lpa", False)]:
            d0 = d0.copy()
            d0["I"] = standardise(d0, "intensity", by_rows=by_rows)
            for y, label, w in OUTCOMES:
                d = d0.dropna(subset=[y]).copy()
                quarters = sorted(d.Quarter.unique())
                ev = []
                for q in quarters:
                    if q != REF_Q:
                        d[f"e{q.replace(' ', '')}"] = d.I * (d.Quarter == q)
                        ev.append(f"e{q.replace(' ', '')}")
                m = pf.feols(f"{y} ~ {' + '.join(ev)} | code + Quarter", data=d, weights=w,
                             vcov={"CRV1": "code"}, ssc=pf.ssc(k_fixef="nonnested"))
                k = 1 + (d.code.nunique() - 1) + (len(quarters) - 1) + len(ev)
                hand = {}
                if scale == "pilot_rows":          # hand route for every coefficient
                    for name in ev:
                        others = [e for e in ev if e != name]
                        hand[name] = fit_hand(d, y, w, ["code", "Quarter"], [name] + others, k)
                for q in quarters:
                    name = f"e{q.replace(' ', '')}"
                    b = float(m.coef().get(name, 0.0))
                    row = {"sample": sname, "scale": scale, "outcome": label, "quarter": q, "b": b,
                           "se": float(m.se().get(name, 0.0))}
                    if name in hand:
                        row["b_hand"], row["se_hand_pilot_k"] = hand[name]
                    coefs.append(row)

                # pre-BNG linear differential trend (2015 Q1-2023 Q3)
                pre = d[d.Quarter <= PRE_END].copy()
                pre["It"] = pre.I * pre.t
                mt = pf.feols(f"{y} ~ It | code + Quarter", data=pre, weights=w,
                              vcov={"CRV1": "code"}, ssc=pf.ssc(k_fixef="nonnested"))
                trends.append({"sample": sname, "scale": scale, "outcome": label,
                               "slope_per_year": float(mt.coef()["It"]), "se": float(mt.se()["It"]),
                               "p": float(mt.pvalue()["It"])})
    return pd.DataFrame(coefs), pd.DataFrame(trends)


# ---------------------------------------------------------------------------
# Comparison with the pilot
# ---------------------------------------------------------------------------

def compare(tab, ev):
    old = pd.read_csv(PILOT_DIR / "robustness_table.csv")
    m = tab.merge(old, on=["check", "outcome"], suffixes=("", "_pilot"), how="outer", indicator=True)
    unmatched = m[m._merge != "both"][["check", "outcome", "_merge"]]
    assert unmatched.empty, f"rows not in both tables:\n{unmatched}"
    m["d_beta"] = (m.beta - m.beta_pilot).abs()
    m["d_se"] = (m.se_hand_pilot_k - m.se_pilot).abs()
    m["d_route"] = (m.beta - m.beta_hand).abs()
    m["n_same"] = (m.n_lpa == m.n_lpa_pilot) & (m.n_obs == m.n_obs_pilot)
    print(f"\nR1 robustness table ({len(m)} rows): max |beta - pilot| {m.d_beta.max():.1e}")
    print(f"R2 max |hand SE (pilot K) - pilot SE| {m.d_se.max():.1e}")
    print(f"R3 max |pyfixest - second route| beta {m.d_route.max():.1e}")
    print(f"R4 sample sizes equal in {int(m.n_same.sum())} of {len(m)} rows")
    bad = m[(m.d_beta > 1e-6) | (m.d_se > 1e-6) | (m.d_route > 1e-6) | ~m.n_same]
    # check 5: the pilot's first step (statsmodels, rank-deficient design) returned slopes
    # shifted by ~1e10, and the rounding error left after removing them moved beta by ~4e-4.
    # The rebuild's beta is confirmed by a full-rank first step (run_checks). See notes.
    explained = bad.check.str.startswith("5 ")
    if explained.any():
        print("differences explained by the pilot's numerical error in check 5:")
        print(bad.loc[explained, ["check", "outcome", "beta", "beta_pilot", "se_hand_pilot_k",
                                  "se_pilot"]].to_string(index=False))
    bad = bad[~explained]
    if len(bad):
        print(bad[["check", "outcome", "beta", "beta_pilot", "se_hand_pilot_k", "se_pilot",
                   "beta_hand", "n_lpa", "n_lpa_pilot", "n_obs", "n_obs_pilot"]].to_string(index=False))

    old_ev = pd.read_csv(PILOT_DIR / "event_study_coefs.csv")
    e = ev[ev.scale == "pilot_rows"].merge(old_ev, on=["sample", "outcome", "quarter"],
                                           suffixes=("", "_pilot"), validate="one_to_one")
    e_hand = e.dropna(subset=["b_hand"])
    print(f"R1 event study ({len(e)} coefficients): max |b - pilot| {(e.b - e.b_pilot).abs().max():.1e}; "
          f"R2 max |hand SE - pilot SE| {(e_hand.se_hand_pilot_k - e_hand.se_pilot).abs().max():.1e}; "
          f"R3 max |pyfixest - hand| {(e_hand.b - e_hand.b_hand).abs().max():.1e}")
    return m, bad


def main():
    p = load()
    tab, full = run_checks(p)
    ev, trends = event_study(full)
    m, bad = compare(tab, ev)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tab.to_csv(OUT_DIR / "robustness_table.csv", index=False)
    ev.to_csv(OUT_DIR / "event_study_coefs.csv", index=False)
    trends.to_csv(OUT_DIR / "pretrend_tests.csv", index=False)

    show = tab[~tab.check.str.startswith("11")].copy()
    pd.set_option("display.width", 220)
    wide = show.assign(cell=[f"{b:+.4f} ({s:.4f}) p={pv:.3f}" for b, s, pv in zip(show.beta, show.se, show.p)])
    print("\nbeta per SD x Post; SE CRV1 by LPA, pyfixest default correction")
    print(wide.pivot(index="check", columns="outcome", values="cell")
          .reindex(show.check.unique()).to_string())
    loro = tab[tab.check.str.startswith("11")].groupby("outcome").beta.agg(["min", "max"])
    print("\n11 leave-one-region-out range:\n" + loro.round(4).to_string())
    print("\npre-BNG linear differential trend (per year per SD):")
    print(trends.round(4).to_string(index=False))
    print("\nR1-R4 passed" if bad.empty else "\nR1-R4 NOT all passed: see rows above")


if __name__ == "__main__":
    main()
