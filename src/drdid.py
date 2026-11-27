"""Doubly robust Callaway-Sant'Anna estimator for a unit x period panel.

Callaway and Sant'Anna (2021): estimate ATT(g,t) for each treatment cohort g and period t
against units not yet treated, then aggregate. Each ATT(g,t) uses the doubly robust (DR)
2x2 estimator of Sant'Anna and Zhao (2020, "traditional" panel version):

    ATT = mean_T[dY - m(X)]  -  sum_C w_i [dY_i - m(X_i)] / sum_C w_i,   w_i = p(X_i) / (1 - p(X_i))

dY = Y_t - Y_b (b = base period), m(X) = OLS prediction of dY from the comparison units,
p(X) = logit probability of being in cohort g rather than the comparison group. It is
consistent if either p or m is correctly specified. With no covariates it is the 2x2
difference of mean changes.

Kept free of project paths so it can be unit-tested on simulated data (tests/test_drdid.py).
"""

import numpy as np

TRIM = 0.995


def logit(X, d, w=None, max_iter=100, tol=1e-10):
    """Logistic regression by Newton-Raphson; X includes the intercept column; optional
    unit weights w (frequency-weight interpretation). Under (quasi-)separation the
    coefficients grow until max_iter and p goes to 0/1; such controls are then trimmed."""
    w = np.ones(len(d)) if w is None else w
    beta = np.zeros(X.shape[1])
    for _ in range(max_iter):
        p = 1 / (1 + np.exp(-np.clip(X @ beta, -35, 35)))
        grad = X.T @ (w * (d - p))
        hess = X.T @ (X * (w * p * (1 - p))[:, None])
        step = np.linalg.lstsq(hess, grad, rcond=None)[0]
        beta += step
        if np.max(np.abs(step)) < tol:
            break
    return beta


def dr_att(dy, d, X=None, kind="dr", u=None):
    """2x2 ATT for treated (d = 1) vs comparison (d = 0). kind: 'dr', 'ipw' or 'or'.
    u: optional unit weights, used in the logit, the outcome regression and both means."""
    d = d.astype(bool)
    n = len(dy)
    u = np.ones(n) if u is None else np.asarray(u, float)
    Z = np.ones((n, 1)) if X is None else np.column_stack([np.ones(n), X])
    if kind in ("dr", "or"):
        su = np.sqrt(u[~d])
        coef = np.linalg.lstsq(Z[~d] * su[:, None], dy[~d] * su, rcond=None)[0]   # weighted OLS
        m = Z @ coef
    else:
        m = np.zeros(n)
    resid = dy - m
    att_treated = np.sum(u[d] * resid[d]) / np.sum(u[d])
    if kind == "or":
        return float(att_treated)
    if X is None:
        w = u.copy()
    else:
        p = 1 / (1 + np.exp(-np.clip(Z @ logit(Z, d.astype(float), u), -35, 35)))
        w = u * p / (1 - p)
        w[(~d) & (p > TRIM)] = 0.0                 # trim controls with extreme scores
    att_control = np.sum(w[~d] * resid[~d]) / np.sum(w[~d])
    return float(att_treated - att_control)


def att_gt(Y, G, X, cohorts, delta=1, min_treated=5, min_control=10, kind="dr", W=None):
    """All ATT(g,t). Y: units x periods (NaN = not observed); G: first treated period
    (np.inf if never within the data); universal base b = g - 1 - delta.
    Returns a list of dicts (g, t, e, att, n_treated, n_control) and skipped cells."""
    T = Y.shape[1]
    out, skipped = [], []
    for g in cohorts:
        b = g - 1 - delta
        if b < 0:
            continue
        for t in range(T):
            if t == b:
                continue
            treated = G == g
            control = (G > max(t, b) + delta) & (G != g)
            ok = ~np.isnan(Y[:, t]) & ~np.isnan(Y[:, b])
            tr, co = treated & ok, control & ok
            if tr.sum() < min_treated or co.sum() < min_control:
                skipped.append((g, t, int(tr.sum()), int(co.sum())))
                continue
            keep = tr | co
            dy = Y[keep, t] - Y[keep, b]
            att = dr_att(dy, tr[keep], None if X is None else X[keep], kind=kind,
                         u=None if W is None else W[keep])
            out.append({"g": g, "t": t, "e": t - g, "att": att,
                        "n_treated": int(tr.sum()), "n_control": int(co.sum())})
    return out, skipped


def aggregate(cells, G, e_min=-8, e_max=3, W=None):
    """Overall post ATT (t >= g) and event-time averages, weighted by cohort size (the
    summed unit weights of the cohort when W is given)."""
    W = np.ones(len(G)) if W is None else W
    size = {g: float(np.sum(W[G == g])) for g in {c["g"] for c in cells}}
    post = [c for c in cells if c["e"] >= 0]
    w = np.array([size[c["g"]] for c in post])
    overall = float(np.sum(w * np.array([c["att"] for c in post])) / w.sum()) if post else np.nan
    event = {}
    for e in range(e_min, e_max + 1):
        cs = [c for c in cells if c["e"] == e]
        if cs:
            we = np.array([size[c["g"]] for c in cs])
            event[e] = float(np.sum(we * np.array([c["att"] for c in cs])) / we.sum())
    return overall, event


def estimate(Y, G, X, cohorts, delta=1, kind="dr", W=None):
    cells, skipped = att_gt(Y, G, X, cohorts, delta=delta, kind=kind, W=W)
    overall, event = aggregate(cells, G, W=W)
    return {"overall": overall, "event": event, "cells": cells, "skipped": skipped}


def bootstrap(Y, G, X, cohorts, reps, rng, delta=1, kind="dr", W=None):
    """Unit (cluster) bootstrap: resample units with replacement (with their weights),
    re-estimate everything."""
    n = Y.shape[0]
    overall, events = [], []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        r = estimate(Y[idx], G[idx], None if X is None else X[idx], cohorts, delta=delta, kind=kind,
                     W=None if W is None else W[idx])
        overall.append(r["overall"])
        events.append(r["event"])
    return np.array(overall), events
