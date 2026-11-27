"""T4: synthetic difference-in-differences for gain-site prices (validation target 6).

Run from the Pipeline folder, after src/gainsite_did.py (it writes the site cells):
    python src/gainsite_sdid.py

Arkhangelsky et al. (2021) SDID, run separately for each registration half-year (staggered
extension), cohort estimates averaged with weights (treated sites x post half-years).
Panel: unit = site; period = half-year 2018H1-2026H1 (17); outcome = mean quality-adjusted
log price of sales within 1 km of the site edge; sites need >= 3 such sales in every
half-year (a balanced panel). Treated cohorts: registered 2024H1-2025H2.
Donors: "pseudo-sites" 5-15 km from a treated site, >= 4 km beyond any real site's edge, with
similar urbanity (postcodes with sales within r + 1 km, +/-30%), given the paired site's size.
Alternative donors: real sites registered 2026H2. Inference: placebo SE (Algorithm 4), 200
reassignments of treatment to random donors.

The pilot's random draws are reproduced (seed 7, same order of calls). Weights use the pilot's
Frank-Wolfe solver (5,000 iterations); the exact optimum (accelerated projected gradient,
src/sdid.py) is also reported to show how much the solver matters.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from gainsite_did import OUT_DIR, PILOT, WORK, Cells, load_sites  # noqa: E402
from sdid import simplex_ridge  # noqa: E402

SEED, MIN_SALES, K_DONORS, N_PLACEBO, NH = 7, 3, 6, 200, 17


def inner_panel(cells_df, id_col="ref"):
    x = cells_df[cells_df.ring.isin(["0-500m", "500m-1km"])].copy()
    x["h"] = x.q // 2
    g = x.groupby([id_col, "h"])[["n", "u"]].sum()
    n = g.n.unstack().reindex(columns=range(NH)).fillna(0)
    u = g.u.unstack().reindex(columns=range(NH)).fillna(0)
    ok = (n >= MIN_SALES).all(axis=1)
    return u[ok] / n[ok]


def fw_simplex(A, b, eta, iters=5000, tol=1e-10):
    """min ||A w - b||^2 + eta ||w||^2 over the simplex (Frank-Wolfe, exact line search;
    the pilot's solver)."""
    n = A.shape[1]
    w = np.full(n, 1.0 / n)
    r = A @ w - b
    f_old = r @ r + eta * w @ w
    for _ in range(iters):
        g = 2 * A.T @ r + 2 * eta * w
        j = np.argmin(g)
        d = -w.copy()
        d[j] += 1
        Ad = A @ d
        den = 2 * (Ad @ Ad + eta * d @ d)
        if den <= 0:
            break
        gam = np.clip(-(g @ d) / den, 0, 1)
        w = w + gam * d
        r = r + gam * Ad
        f = r @ r + eta * w @ w
        if f_old - f < tol:
            break
        f_old = f
    return w


def sdid(Y0, Y1, T0, solver=fw_simplex):
    N0, T = Y0.shape
    N1, T1 = Y1.shape[0], T - T0
    sigma = np.std(np.diff(Y0[:, :T0], axis=1), ddof=1)
    zeta = (N1 * T1) ** 0.25 * sigma
    A, b = Y0[:, :T0].T, Y1[:, :T0].mean(axis=0)
    omega = solver(A - A.mean(axis=0), b - b.mean(), zeta ** 2 * T0)
    B, c = Y0[:, :T0], Y0[:, T0:].mean(axis=1)
    lam = solver(B - B.mean(axis=0), c - c.mean(), (1e-6 * sigma) ** 2 * N0)
    tr_post, tr_pre = Y1[:, T0:].mean(), Y1[:, :T0].mean(axis=0) @ lam
    co_post, co_pre = omega @ Y0[:, T0:].mean(axis=1), omega @ (Y0[:, :T0] @ lam)
    return (tr_post - tr_pre) - (co_post - co_pre), omega, lam


def staggered(Ytr, gh, Y0, solver=fw_simplex):
    rows = []
    for g in sorted(np.unique(gh)):
        Y1 = Ytr[gh == g]
        tau, om, _ = sdid(Y0, Y1, g, solver)
        rows.append({"cohort_halfyear": g, "n_treated": len(Y1), "post_periods": NH - g, "tau": tau,
                     "w": len(Y1) * (NH - g), "effective_donors": 1 / float(om @ om)})
    t = pd.DataFrame(rows)
    return (t.tau * t.w).sum() / t.w.sum(), t


def pseudo_sites(s, real, cells, rng):
    pxy = cells.xy
    site_tree = cKDTree(s[["easting", "northing"]].to_numpy())
    dmin, jmin = site_tree.query(pxy, k=1)
    beyond_edge = dmin - s.radius_m.to_numpy()[jmin]
    tr_sites = real[(real.gh >= 12) & (real.gh <= 15)]
    pts = []
    for r in tr_sites.itertuples():
        target = cells.postcode_density(r.easting, r.northing, r.radius_m)
        idx = np.asarray(cells.tree.query_ball_point([r.easting, r.northing], r=15000))
        dd = np.hypot(pxy[idx, 0] - r.easting, pxy[idx, 1] - r.northing)
        idx = idx[(dd >= 5000) & (beyond_edge[idx] >= r.radius_m + 4000)]
        dens = cells.tree.query_ball_point(pxy[idx], r=r.radius_m + 1000, return_length=True)
        ok = idx[(dens >= 0.7 * target) & (dens <= 1.3 * target)]
        for j in rng.choice(ok, size=min(K_DONORS, len(ok)), replace=False):
            pts.append({"ref": f"P_{r.Index}_{j}", "easting": pxy[j, 0], "northing": pxy[j, 1],
                        "radius_m": r.radius_m})
    pts = pd.DataFrame(pts)
    keep, kept = [], []          # pseudo-sites must not overlap each other's 0-1 km zone
    for p in pts.itertuples():
        if all(np.hypot(p.easting - a, p.northing - b) > 2000 + p.radius_m + rr for a, b, rr in kept):
            keep.append(p.Index)
            kept.append((p.easting, p.northing, p.radius_m))
    return tr_sites, pts.loc[keep]


def placebo_se(Y0, cohort_counts, reps, rng):
    taus, need = [], sum(cohort_counts.values())
    gh = np.concatenate([[g] * k for g, k in cohort_counts.items()])
    for _ in range(reps):
        perm = rng.permutation(Y0.shape[0])
        taus.append(staggered(Y0[perm[:need]], gh, Y0[perm[need:]])[0])
    return np.std(taus, ddof=1)


def main(tag="2026-10-12_rows"):
    rng = np.random.default_rng(SEED)
    s = load_sites(tag)
    s["gh"] = s.gq // 2
    cells = Cells()
    Yr = inner_panel(pd.read_parquet(WORK / f"site_cells_{tag}.parquet"))
    real = s.set_index("ref").loc[Yr.index]
    tr_sites, pts = pseudo_sites(s, real, cells, rng)
    Yp = inner_panel(cells.rings(pts))
    print(f"treated sites (balanced): {len(tr_sites)}; pseudo-site donors {len(Yp)} of {len(pts)} drawn; "
          f"late real donors (2026H2): {(real.gh == 17).sum()}")

    Ytr, ghs = Yr.loc[tr_sites.index].to_numpy(), tr_sites.gh.to_numpy()
    counts = tr_sites.gh.value_counts().sort_index().to_dict()
    rows = []
    for label, Y0 in [("Pseudo-site donors (never near a gain site)", Yp.to_numpy()),
                      ("Late real sites as donors (registered 2026H2)", Yr.loc[real.gh == 17].to_numpy())]:
        tau, tab = staggered(Ytr, ghs, Y0)
        tau_exact, _ = staggered(Ytr, ghs, Y0, solver=simplex_ridge)
        se = placebo_se(Y0, counts, N_PLACEBO, rng) if Y0.shape[0] > Ytr.shape[0] else np.nan
        rows.append({"donors": label, "n_donors": Y0.shape[0], "n_treated": len(Ytr), "tau": tau,
                     "se": se, "tau_exact_weights": tau_exact})
        print(f"{label}: tau {tau:.7f} (SE {se:.7f}); with exact-optimum weights {tau_exact:.7f}")
        print(tab.round(4).to_string(index=False))
    res = pd.DataFrame(rows)

    # pre-specified for the rerun: tau over 40 donor draws (seeds 1-40), point estimates only
    if "draws" in sys.argv[2:]:
        taus = []
        for seed in range(1, 41):
            tr_k, pts_k = pseudo_sites(s, real, cells, np.random.default_rng(seed))
            Yp_k = inner_panel(cells.rings(pts_k))
            taus.append(staggered(Yr.loc[tr_k.index].to_numpy(), tr_k.gh.to_numpy(), Yp_k.to_numpy())[0])
        taus = np.array(taus)
        res["tau_mean_40_draws"] = [taus.mean(), np.nan]
        res["tau_sd_40_draws"] = [taus.std(ddof=1), np.nan]
        print(f"40 donor draws: mean {taus.mean():.5f}, SD {taus.std(ddof=1):.5f}, "
              f"range {taus.min():.4f} to {taus.max():.4f}")

    old = pd.read_csv(PILOT / "test5_sdid.csv")
    m = res.merge(old, on="donors", suffixes=("", "_pilot"))
    print("\nT4 vs pilot:")
    print(m[["donors", "n_donors", "n_donors_pilot", "tau", "tau_pilot", "se", "se_pilot"]].to_string(index=False))
    res.to_csv(OUT_DIR / f"t4_sdid_{tag}.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-10-12_rows")
