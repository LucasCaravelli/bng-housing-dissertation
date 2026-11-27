"""Within-England BNG intensity DiD, baseline specification (validation target 4).

    y_it = a_i + l_t + beta * (I_i x Post_t) + e_it

Run from the Pipeline folder, after src/planning_panel.py and src/intensity_score.py:
    python src/intensity_did.py

Every estimate is computed twice: with pyfixest, and by hand (two-way within transformation
plus a hand-coded cluster-robust variance). Specification and checks are pre-specified in
notes/intensity_did.md.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

PANEL = config.PROCESSED_DIR / "planning" / "panel_england_lpa2025_quarter.csv"
INTENSITY = config.PROCESSED_DIR / "intensity" / "intensity_lpa2025.csv"
OUT = config.PROCESSED_DIR / "intensity" / "did_baseline.csv"

DROP_QUARTERS = ["2023 Q4", "2024 Q1", "2024 Q2"]   # fee rise and BNG transition
POST_START = "2024 Q3"

# (outcome, label, regression weight)
OUTCOMES = [("ly", "log(1 + dwelling decisions)", None),
            ("grate", "dwelling grant rate", "dw_dec"),
            ("lhh", "log(1 + householder decisions) [placebo]", None)]

# pilot results (Planning/output/intensity/robustness_summary.txt)
PILOT = {"ly": (0.0361, 0.0177), "grate": (0.008, None), "lhh": (0.010, None)}
PILOT_TERCILE = 0.0541


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load():
    p = pd.read_csv(PANEL)
    r = pd.read_csv(INTENSITY)[["code", "intensity", "main_sample"]]
    p = p.merge(r, on="code", how="left", validate="many_to_one")
    p = p[p.main_sample.astype(bool) & ~p.Quarter.isin(DROP_QUARTERS)].copy()

    p["dw_dec"] = p.dec_major + p.dec_minor
    p["dw_grant"] = p.grant_major + p.grant_minor
    p["ly"] = np.log1p(p.dw_dec)
    p["lhh"] = np.log1p(p.dec_hh)
    p["grate"] = p.dw_grant / p.dw_dec.where(p.dw_dec > 0)   # undefined with no decisions
    p["post"] = (p.Quarter >= POST_START).astype(int)
    return p


def prepare(p, y, ivar="intensity"):
    """Drop rows with a missing outcome, then standardise intensity across the LPAs left
    (not across rows), so beta is per SD of intensity between councils."""
    d = p.dropna(subset=[y, ivar]).copy()
    per_lpa = d.groupby("code")[ivar].first()
    d["I"] = (d[ivar] - per_lpa.mean()) / per_lpa.std()      # SD with ddof = 1, as in the pilot
    d["IxP"] = d.I * d.post
    return d


# ---------------------------------------------------------------------------
# Route 1: pyfixest
# ---------------------------------------------------------------------------

def fit_pyfixest(d, y, w, k_fixef):
    m = pf.feols(f"{y} ~ IxP | code + Quarter", data=d, weights=w,
                 vcov={"CRV1": "code"}, ssc=pf.ssc(k_fixef=k_fixef))
    return float(m.coef()["IxP"]), float(m.se()["IxP"]), float(m.pvalue()["IxP"])


# ---------------------------------------------------------------------------
# Route 2: by hand
# ---------------------------------------------------------------------------

def demean_two_way(v, g1, g2, w, tol=1e-12, max_iter=10_000):
    """Remove LPA and quarter means (weighted) by alternating projections until nothing
    changes. With a balanced, unweighted panel one pass is exact; otherwise it converges
    to the same residual as regressing on both sets of dummies (Frisch-Waugh-Lovell)."""
    v = v.astype(float).copy()
    for _ in range(max_iter):
        before = v.copy()
        for g in (g1, g2):
            means = (pd.Series(v * w).groupby(g).transform("sum")
                     / pd.Series(w).groupby(g).transform("sum")).to_numpy()
            v -= means
        if np.max(np.abs(v - before)) < tol:
            return v
    raise RuntimeError("demeaning did not converge")


def fit_by_hand(d, y, w, k):
    """beta from the demeaned regression; CRV1 variance with G/(G-1) x (N-1)/(N-k)."""
    wt = d[w].to_numpy(float) if w else np.ones(len(d))
    g1, g2 = d.code.to_numpy(), d.Quarter.to_numpy()
    x = demean_two_way(d.IxP.to_numpy(), g1, g2, wt)
    yy = demean_two_way(d[y].to_numpy(), g1, g2, wt)
    sxx = np.sum(wt * x * x)
    beta = np.sum(wt * x * yy) / sxx
    e = yy - beta * x
    score_by_cluster = pd.Series(wt * x * e).groupby(g1).sum().to_numpy()
    n, n_clusters = len(d), len(score_by_cluster)
    correction = n_clusters / (n_clusters - 1) * (n - 1) / (n - k)
    se = np.sqrt(correction * np.sum(score_by_cluster ** 2) / sxx ** 2)
    return beta, se


def n_params_with_dummies(d):
    """k as statsmodels counts it with LPA and quarter dummies: intercept, (LPAs - 1),
    (quarters - 1) and the treatment term."""
    return 1 + (d.code.nunique() - 1) + (d.Quarter.nunique() - 1) + 1


# ---------------------------------------------------------------------------
# Tercile check
# ---------------------------------------------------------------------------

def tercile(p, y):
    """Top vs bottom tercile of intensity (middle dropped): binary TWFE and 2x2 means."""
    d = p.dropna(subset=[y]).copy()
    per_lpa = d.groupby("code").intensity.first()
    terc = pd.qcut(per_lpa, 3, labels=False)
    d["terc"] = d.code.map(terc)
    d = d[d.terc != 1].copy()
    d["IxP"] = (d.terc == 2).astype(float) * d.post
    beta_twfe, se, _ = fit_pyfixest(d, y, None, "full")
    cell = d.groupby([d.terc == 2, "post"])[y].mean()
    beta_2x2 = (cell[(True, 1)] - cell[(True, 0)]) - (cell[(False, 1)] - cell[(False, 0)])
    return beta_twfe, se, beta_2x2, d.code.nunique()


# ---------------------------------------------------------------------------

def main():
    p = load()

    # D1: sample
    n_lpa, n_q = p.code.nunique(), p.Quarter.nunique()
    print(f"D1 sample: {n_lpa} LPAs x {n_q} quarters = {len(p):,} rows; "
          f"post quarters {p.loc[p.post == 1, 'Quarter'].nunique()}; "
          f"missing ly {int(p.ly.isna().sum())}; grant rate undefined in {int(p.grate.isna().sum())} rows")
    assert n_lpa == 205 and n_q == 43 and len(p) == 205 * 43 and p.ly.notna().all(), "D1 failed"

    rows = []
    for y, label, w in OUTCOMES:
        d = prepare(p, y)
        k = n_params_with_dummies(d)
        b_pf, se_full, pval = fit_pyfixest(d, y, w, "full")
        _, se_default, _ = fit_pyfixest(d, y, w, "nonnested")
        b_hand, se_hand = fit_by_hand(d, y, w, k)

        # D3: the two routes agree
        assert abs(b_pf - b_hand) < 1e-8, f"D3 failed ({y}): beta {b_pf} vs {b_hand}"
        assert abs(se_full - se_hand) < 1e-6, f"D3 failed ({y}): SE {se_full} vs {se_hand}"
        rows.append({"outcome": label, "beta": b_pf, "se_pilot_correction": se_full,
                     "se_pyfixest_default": se_default, "p": pval, "beta_hand": b_hand,
                     "se_hand": se_hand, "n_lpa": d.code.nunique(), "n_obs": len(d), "k": k,
                     "pilot_beta": PILOT[y][0], "pilot_se": PILOT[y][1]})

    tab = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print("\nbeta per SD of intensity x Post (2024 Q3-2026 Q2), LPA and quarter FE, SE clustered by LPA")
    print(tab[["outcome", "beta", "se_pilot_correction", "se_pyfixest_default", "p",
               "pilot_beta", "pilot_se", "n_lpa", "n_obs"]].round(4).to_string(index=False))
    print(f"max |pyfixest - hand|: beta {np.max(np.abs(tab.beta - tab.beta_hand)):.1e}, "
          f"SE {np.max(np.abs(tab.se_pilot_correction - tab.se_hand)):.1e}")

    # D2: target for log dwelling decisions
    ly = tab.iloc[0]
    assert round(ly.beta, 4) == 0.0361 and round(ly.se_pilot_correction, 4) == 0.0177, "D2 failed"
    # D5: other outcomes to 3 decimals
    for i, (y, _, _) in enumerate(OUTCOMES[1:], start=1):
        assert round(tab.beta[i], 3) == PILOT[y][0], f"D5 failed ({y}): {tab.beta[i]:.4f}"

    # D4: tercile
    b_twfe, se_t, b_2x2, n_t = tercile(p, "ly")
    print(f"\nD4 top vs bottom tercile ({n_t} LPAs): TWFE {b_twfe:.4f} (SE {se_t:.4f}); "
          f"2x2 means {b_2x2:.4f}; pilot {PILOT_TERCILE}")
    assert abs(b_twfe - b_2x2) < 1e-8 and round(b_2x2, 4) == PILOT_TERCILE, "D4 failed"

    tab.to_csv(OUT, index=False)
    print(f"\nD1-D5 passed; wrote {OUT.name}")


if __name__ == "__main__":
    main()
