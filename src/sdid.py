"""Synthetic difference-in-differences: English councils vs Welsh donor councils (target 5).

Run from the Pipeline folder, after src/planning_panel.py:
    python src/sdid.py

SDID (Arkhangelsky, Athey, Hirshberg, Imbens and Wager 2021, Algorithm 1):
  1. unit weights omega: Welsh donors whose weighted pre-BNG path (plus a constant) tracks
     the English mean; a ridge penalty spreads weight so one noisy council cannot dominate.
  2. time weights lambda: pre-BNG quarters whose weighted average best predicts each donor's
     post-period mean, i.e. the part of the pre-period that looks like the post-period.
  3. tau = [England post - lambda'England pre] - sum_i omega_i [donor_i post - lambda'donor_i pre]
DiD is the special case with uniform omega and lambda.

The estimator is two small constrained least-squares problems and a weighted average, so it
is written out here; each step is verified (V1-V4 in notes/sdid.md).
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from planning_panel import PS2_FILE, TO_2025, read_mhclg  # noqa: E402

PROC = config.PROCESSED_DIR / "planning"
OUT_DIR = config.PROCESSED_DIR / "sdid"
PILOT_DIR = config.RAW_ROOT / "Planning" / "output" / "sdid"

DROP_QUARTERS = ["2023 Q4", "2024 Q1", "2024 Q2"]
FIRST_Q, LAST_Q, POST_START = "2016 Q1", "2026 Q1", "2024 Q3"
COMPONENTS = ["maj_dec", "maj_gr", "min_dec", "min_gr", "hh_dec", "hh_gr"]
OUTCOMES = [("grate", "dwelling grant rate [primary]"), ("grate_min", "minor dwelling grant rate"),
            ("ly", "log(1+dwelling decisions)"), ("hh_rate", "householder grant rate [placebo]"),
            ("lhh", "log(1+householder decisions) [placebo]")]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load():
    e = pd.read_csv(PROC / "panel_england_lpa2025_quarter.csv")
    eng = pd.DataFrame({"lpa": e.code, "name": e["name"], "Quarter": e.Quarter, "type": e["type"],
                        "maj_dec": e.dec_major, "maj_gr": e.grant_major, "min_dec": e.dec_minor,
                        "min_gr": e.grant_minor, "hh_dec": e.dec_hh, "hh_gr": e.grant_hh,
                        "country": "England"})
    w = pd.read_csv(PROC / "panel_wales_lpa_quarter.csv")
    wal = pd.DataFrame({"lpa": w.code, "name": w["name"], "Quarter": w.Quarter, "type": w["type"],
                        "maj_dec": w.DtrmMajDw, "maj_gr": w.AppdMajDw, "min_dec": w.DtrmMinDw,
                        "min_gr": w.AppdMinDw, "hh_dec": w.DtrmMinHou, "hh_gr": w.AppdMinHou,
                        "country": "Wales"})
    d = pd.concat([eng, wal], ignore_index=True)
    d = d[d.Quarter.between(FIRST_Q, LAST_Q)]
    # councils only; London boroughs and national parks out (pre-specified)
    d = d[(d["type"] == "council") & ~d.lpa.str.startswith("E09")].copy()
    assert d.lpa.notna().all()

    # gaps: drop a council missing anything from 2023 Q4 on; interpolate short pre-period gaps
    d = d.sort_values(["lpa", "Quarter"])
    interpolated, dropped = [], []
    for lpa, g in d[d[COMPONENTS].isna().any(axis=1)].groupby("lpa"):
        quarters = g.Quarter.tolist()
        name = g["name"].iloc[0]
        if any(q >= DROP_QUARTERS[0] for q in quarters):
            dropped.append(name)
            d = d[d.lpa != lpa]
        else:
            interpolated.append(lpa)
            print(f"  interpolate {name}: {quarters}")
    print(f"  dropped (missing after 2023 Q3): {dropped}")
    d[COMPONENTS] = d.groupby("lpa")[COMPONENTS].transform(
        lambda s: s.interpolate(limit=2, limit_area="inside"))
    assert d[COMPONENTS].notna().all().all(), "gaps left after interpolation"

    d["dw_dec"], d["dw_gr"] = d.maj_dec + d.min_dec, d.maj_gr + d.min_gr
    d["grate"] = d.dw_gr / d.dw_dec.where(d.dw_dec > 0)
    d["grate_min"] = d.min_gr / d.min_dec.where(d.min_dec > 0)
    d["ly"] = np.log1p(d.dw_dec)
    d["hh_rate"] = d.hh_gr / d.hh_dec.where(d.hh_dec > 0)
    d["lhh"] = np.log1p(d.hh_dec)

    ps2 = read_mhclg(PS2_FILE)[["LPACD", "Region"]]
    ps2["code"] = ps2.LPACD.map(TO_2025).fillna(ps2.LPACD)
    region = ps2.groupby("code").Region.first()
    return d, interpolated, region


def outcome_matrix(d, y, quarters):
    """Units x quarters, Welsh donors first. Units with any undefined value are dropped."""
    m = d[d.Quarter.isin(quarters)].pivot(index="lpa", columns="Quarter", values=y)[quarters]
    incomplete = m.isna().any(axis=1)
    m = m[~incomplete]
    country = d.drop_duplicates("lpa").set_index("lpa").country.reindex(m.index)
    m = pd.concat([m[country == "Wales"], m[country == "England"]])
    return m, int((country == "Wales").sum()), int(incomplete.sum())


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

def project_to_simplex(v):
    """Euclidean projection onto {x >= 0, sum x = 1} (sort-based algorithm)."""
    u = np.sort(v)[::-1]
    css = np.cumsum(u) - 1
    k = np.nonzero(u - css / np.arange(1, len(v) + 1) > 0)[0][-1]
    return np.maximum(v - css[k] / (k + 1), 0)


def simplex_ridge(A, b, penalty, tol=1e-12, max_iter=200_000):
    """min ||A x - b||^2 + penalty ||x||^2 over the simplex, by accelerated projected gradient
    (FISTA) with step 1/L. A and b are already demeaned (this absorbs the intercept)."""
    AtA, Atb = A.T @ A, A.T @ b
    L = 2 * (np.linalg.eigvalsh(AtA).max() + penalty)
    x = np.full(A.shape[1], 1 / A.shape[1])
    z, t = x.copy(), 1.0
    for _ in range(max_iter):
        grad = 2 * (AtA @ z - Atb + penalty * z)
        x_new = project_to_simplex(z - grad / L)
        t_new = (1 + np.sqrt(1 + 4 * t * t)) / 2
        z = x_new + (t - 1) / t_new * (x_new - x)
        if np.max(np.abs(x_new - x)) < tol:
            return x_new
        x, t = x_new, t_new
    warnings.warn("simplex_ridge reached max_iter")
    return x


def simplex_ridge_slsqp(A, b, penalty):
    """Second route for V1: the same problem with scipy's SLSQP."""
    n = A.shape[1]
    res = minimize(lambda v: np.sum((A @ v - b) ** 2) + penalty * v @ v, np.full(n, 1 / n),
                   jac=lambda v: 2 * (A.T @ (A @ v - b) + penalty * v),
                   bounds=[(0, 1)] * n, constraints=[{"type": "eq", "fun": lambda v: v.sum() - 1}],
                   method="SLSQP", options={"ftol": 1e-15, "maxiter": 10_000})
    return res.x


def weight_problems(Y, n_co, T0):
    """The two demeaned least-squares problems and their penalties."""
    Yco = Y[:n_co]
    n_tr, T_post = Y.shape[0] - n_co, Y.shape[1] - T0
    sigma = np.std(np.diff(Yco[:, :T0], axis=1), ddof=1)        # noise in donor changes
    zeta_omega = (n_tr * T_post) ** 0.25 * sigma
    A_om, b_om = Yco[:, :T0].T, Y[n_co:, :T0].mean(axis=0)      # rows: pre periods
    A_la, b_la = Yco[:, :T0], Yco[:, T0:].mean(axis=1)          # rows: donors
    return [(A_om - A_om.mean(0), b_om - b_om.mean(), zeta_omega ** 2 * T0),
            (A_la - A_la.mean(0), b_la - b_la.mean(), (1e-6 * sigma) ** 2 * n_co)]


def sdid_weights(Y, n_co, T0, solver=simplex_ridge):
    (A1, b1, p1), (A2, b2, p2) = weight_problems(Y, n_co, T0)
    return solver(A1, b1, p1), solver(A2, b2, p2)


def tau_from(Y, n_co, T0, omega, lam):
    treated = Y[n_co:].mean(axis=0)
    synth = omega @ Y[:n_co]
    return (treated[T0:].mean() - lam @ treated[:T0]) - (synth[T0:].mean() - lam @ synth[:T0])


def sdid(Y, n_co, T0, jackknife=True):
    omega, lam = sdid_weights(Y, n_co, T0)
    out = {"tau": tau_from(Y, n_co, T0, omega, lam), "omega": omega, "lambda": lam}
    out["tau_did"] = tau_from(Y, n_co, T0, np.full(n_co, 1 / n_co), np.full(T0, 1 / T0))
    om_sc = simplex_ridge(Y[:n_co, :T0].T, Y[n_co:, :T0].mean(axis=0), 0.0)   # synthetic control
    out["tau_sc"] = (Y[n_co:].mean(0) - om_sc @ Y[:n_co])[T0:].mean()
    for key, wts in (("sdid", omega), ("did", np.full(n_co, 1 / n_co))):
        gap = Y[n_co:, :T0].mean(0) - wts @ Y[:n_co, :T0]
        out[f"rmse_{key}"] = np.sqrt(np.mean((gap - gap.mean()) ** 2))       # after level matching
    out["eff_donors"] = 1 / np.sum(omega ** 2)
    if jackknife:
        # Algorithm 3: leave one unit out, weights fixed (donor weights renormalised)
        n, taus = Y.shape[0], []
        for i in range(n):
            keep = np.arange(n) != i
            n_co_i = n_co - (i < n_co)
            om_i = omega[keep[:n_co]]
            if om_i.sum() == 0 or n_co_i == 0 or keep[n_co:].sum() == 0:
                continue
            taus.append(tau_from(Y[keep], n_co_i, T0, om_i / om_i.sum(), lam))
        taus = np.array(taus)
        out["se"] = np.sqrt((len(taus) - 1) / len(taus) * np.sum((taus - taus.mean()) ** 2))
    return out


# ---------------------------------------------------------------------------
# Verification (V1-V3)
# ---------------------------------------------------------------------------

def verify(Y, n_co, T0, res):
    problems = weight_problems(Y, n_co, T0)
    for name, (A, b, pen), x in zip(["omega", "lambda"], problems, [res["omega"], res["lambda"]]):
        x2 = simplex_ridge_slsqp(A, b, pen)
        f = lambda v: np.sum((A @ v - b) ** 2) + pen * v @ v  # noqa: E731
        print(f"  V1 {name}: FISTA vs SLSQP objective {f(x):.10f} vs {f(x2):.10f}; "
              f"max |weight diff| {np.max(np.abs(x - x2)):.1e}")
        assert f(x) <= f(x2) + 1e-8, f"V1 failed for {name}"
    tau_sl = tau_from(Y, n_co, T0, *sdid_weights(Y, n_co, T0, solver=simplex_ridge_slsqp))
    print(f"  V1 tau with SLSQP weights {tau_sl:.6f} vs FISTA {res['tau']:.6f}")

    tr, co = Y[n_co:], Y[:n_co]
    did_2x2 = (tr[:, T0:].mean() - tr[:, :T0].mean()) - (co[:, T0:].mean() - co[:, :T0].mean())
    print(f"  V2 DiD via weights {res['tau_did']:.8f} vs 2x2 means {did_2x2:.8f}")
    assert abs(res["tau_did"] - did_2x2) < 1e-12, "V2 failed"

    # V3: SDID = weighted two-way FE regression (unit weights x time weights; treated units
    # weighted 1/N_tr, post periods 1/T_post)
    n, T = Y.shape
    uw = np.r_[res["omega"], np.full(n - n_co, 1 / (n - n_co))]
    tw = np.r_[res["lambda"], np.full(T - T0, 1 / (T - T0))]
    W = np.outer(uw, tw).ravel()
    ui, ti = np.repeat(np.arange(n), T), np.tile(np.arange(T), n)
    D = ((ui >= n_co) & (ti >= T0)).astype(float)
    X = np.column_stack([np.eye(n)[ui], np.eye(T)[ti][:, 1:], D])
    keep = W > 0
    sw = np.sqrt(W[keep])
    beta = np.linalg.lstsq(X[keep] * sw[:, None], Y.ravel()[keep] * sw, rcond=None)[0][-1]
    print(f"  V3 SDID tau {res['tau']:.8f} vs weighted TWFE regression {beta:.8f}")
    assert abs(res["tau"] - beta) < 1e-8, "V3 failed"


# ---------------------------------------------------------------------------
# All checks
# ---------------------------------------------------------------------------

def main():
    d, interpolated, region = load()
    quarters = sorted(d.Quarter.unique())
    pre = [q for q in quarters if q < DROP_QUARTERS[0]]
    post = [q for q in quarters if q >= POST_START]
    fake_pre, fake_post = [q for q in pre if q < "2021 Q1"], [q for q in pre if q >= "2021 Q1"]
    print(f"  pre {pre[0]}-{pre[-1]} ({len(pre)} q); post {post[0]}-{post[-1]} ({len(post)} q)")
    names = d.drop_duplicates("lpa").set_index("lpa")["name"]

    rows, main_fits = [], {}

    def run(dd, y, pre_q, post_q, label, check, keep_fit=False):
        m, n_co, n_drop = outcome_matrix(dd, y, pre_q + post_q)
        r = sdid(m.values, n_co, len(pre_q))
        rows.append({"check": check, "outcome": label, "tau": r["tau"], "se": r["se"],
                     "tau_did": r["tau_did"], "tau_sc": r["tau_sc"], "rmse_sdid": r["rmse_sdid"],
                     "rmse_did": r["rmse_did"], "eff_donors": r["eff_donors"], "n_wales": n_co,
                     "n_england": len(m) - n_co, "n_dropped_missing": n_drop, "mde": 2.8 * r["se"]})
        if keep_fit:
            main_fits[y] = (r, m, n_co)

    for y, label in OUTCOMES:
        run(d, y, pre, post, label, "1 main", keep_fit=True)
        run(d[d.Quarter <= pre[-1]], y, fake_pre, fake_post, label,
            "2 placebo in time (fake post 2021 Q1-2023 Q3)")
        run(d[~d.lpa.isin(interpolated)], y, pre, post, label, "3 drop interpolated councils")
        # check 4 (fringe ratio >= 1) needs the LCM2021 England-Wales intensity: not rebuilt yet

    # annual major-dwelling grant rate (too few major decisions per Welsh quarter)
    d["year"] = d.Quarter.str[:4].astype(int)
    ann = d[d.year <= 2025].groupby(["lpa", "year", "country"], as_index=False)[["maj_dec", "maj_gr"]].sum()
    ann["mrate"] = ann.maj_gr / ann.maj_dec.where(ann.maj_dec > 0)
    ann["Quarter"] = ann.year.astype(str)
    run(ann, "mrate", [str(y) for y in range(2016, 2024)], ["2025"],
        "major dwelling grant rate (annual)", "1 main")
    run(ann[ann.year <= 2023], "mrate", [str(y) for y in range(2016, 2021)], ["2021", "2022", "2023"],
        "major dwelling grant rate (annual)", "2 placebo in time (fake post 2021-2023)")

    for reg in sorted(region.unique()):
        if reg == "London":
            continue
        sub = d[(d.country == "Wales") | (d.lpa.map(region) == reg)]
        if (sub.country == "England").any():
            run(sub, "grate", pre, post, "dwelling grant rate [primary]", f"5 region: {reg}")

    tab = pd.DataFrame(rows)

    # leave one donor out, weights re-fitted
    loo = []
    for y, label in OUTCOMES:
        r, m, n_co = main_fits[y]
        for i in range(n_co):
            keep = np.arange(len(m)) != i
            loo.append({"outcome": label, "dropped": names[m.index[i]],
                        "tau": sdid(m.values[keep], n_co - 1, len(pre), jackknife=False)["tau"]})
    loo = pd.DataFrame(loo)

    print("\nVerification, primary outcome:")
    r, m, n_co = main_fits["grate"]
    verify(m.values, n_co, len(pre), r)

    # V4: comparison with the pilot
    old = pd.read_csv(PILOT_DIR / "sdid_table.csv")
    old = old[~old.check.str.startswith("4 ")]
    cmp = tab.merge(old, on=["check", "outcome"], suffixes=("", "_pilot"), how="outer", indicator=True)
    assert (cmp._merge == "both").all(), cmp[cmp._merge != "both"][["check", "outcome", "_merge"]]
    cols = ["tau", "se", "tau_did", "tau_sc", "rmse_sdid", "rmse_did", "eff_donors"]
    diff = pd.DataFrame({c: (cmp[c] - cmp[f"{c}_pilot"]).abs() for c in cols})
    counts_same = all((cmp[c] == cmp[f"{c}_pilot"]).all() for c in ["n_wales", "n_england", "n_dropped_missing"])
    old_loo = pd.read_csv(PILOT_DIR / "sdid_loo.csv")
    lm = loo.merge(old_loo, on=["outcome", "dropped"], suffixes=("", "_pilot"), validate="one_to_one")
    print(f"\nV4 table ({len(cmp)} rows): max |diff| by column {diff.max().map('{:.1e}'.format).to_dict()}; "
          f"sample counts equal: {counts_same}")
    print(f"V4 leave-one-out ({len(lm)} of {len(old_loo)}): max |tau - pilot| {(lm.tau - lm.tau_pilot).abs().max():.1e}")
    worst = cmp.assign(d_tau=diff.tau).nlargest(3, "d_tau")[["check", "outcome", "tau", "tau_pilot"]]
    print(worst.to_string(index=False))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tab.to_csv(OUT_DIR / "sdid_table.csv", index=False)
    loo.to_csv(OUT_DIR / "sdid_loo.csv", index=False)
    pd.set_option("display.width", 220)
    print("\n" + tab[["check", "outcome", "tau", "se", "tau_did", "tau_sc", "eff_donors",
                      "n_wales", "n_england"]].round(4).to_string(index=False))
    print("\nleave-one-donor-out range:\n" + loo.groupby("outcome").tau.agg(["min", "max"]).round(4).to_string())
    # tau_sc (synthetic control, a comparison column) has no ridge penalty, so the solver
    # converges slowly; the pilot stopped at 50,000 iterations, this build at up to 200,000
    # (converged: same value as SLSQP). Differences up to ~3e-6 are explained; see notes.
    ok = (diff.drop(columns="tau_sc").max().max() < 1e-6 and diff.tau_sc.max() < 1e-5
          and counts_same and (lm.tau - lm.tau_pilot).abs().max() < 1e-6)
    print("\nV1-V4 passed (tau_sc within 1e-5: pilot under-converged)" if ok
          else "\nV4 NOT passed: explain before using")


if __name__ == "__main__":
    main()
