"""Check C1: the doubly robust Callaway-Sant'Anna estimator on simulated data.

Run from the Pipeline folder:  python -m pytest tests
"""

import sys
from pathlib import Path

import numpy as np
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from drdid import att_gt, bootstrap, dr_att, estimate, logit  # noqa: E402


def test_no_covariates_equals_2x2_means():
    rng = np.random.default_rng(1)
    dy = rng.normal(size=200)
    d = np.r_[np.ones(60), np.zeros(140)].astype(bool)
    assert np.isclose(dr_att(dy, d, None), dy[d].mean() - dy[~d].mean(), atol=1e-14)


def test_logit_matches_statsmodels():
    rng = np.random.default_rng(2)
    X = np.column_stack([np.ones(500), rng.normal(size=(500, 3))])
    d = (rng.random(500) < 1 / (1 + np.exp(-(X @ [-0.5, 1.0, -0.7, 0.3])))).astype(float)
    ours = logit(X, d)
    theirs = sm.Logit(d, X).fit(disp=0).params
    assert np.allclose(ours, theirs, atol=1e-8)


def simulate_panel(rng, n=3000, T=10, att=0.05):
    """Units with a covariate x that raises both the chance of early treatment and the
    outcome trend: unconditional DiD is biased, conditional DiD is not."""
    x = rng.normal(size=n)
    early = rng.random(n) < 1 / (1 + np.exp(-1.5 * x))
    G = np.where(early, 6, np.inf)                    # treated in period 6, or never in the data
    unit = rng.normal(size=n)
    t = np.arange(T)
    Y = unit[:, None] + 0.1 * t[None, :] + 0.08 * x[:, None] * t[None, :] + rng.normal(scale=0.1, size=(n, T))
    Y[np.ix_(G == 6, t >= 6)] += att
    return Y, G, x[:, None]


def test_dr_recovers_known_att_under_selection_on_x():
    rng = np.random.default_rng(3)
    Y, G, X = simulate_panel(rng)
    dr = estimate(Y, G, X, cohorts=[6], delta=0)["overall"]
    naive = estimate(Y, G, None, cohorts=[6], delta=0)["overall"]
    assert abs(dr - 0.05) < 0.01                     # about 3 simulation SEs
    assert abs(naive - 0.05) > 0.05                  # the unadjusted estimate is biased


def test_pre_periods_are_zero_under_conditional_parallel_trends():
    rng = np.random.default_rng(4)
    Y, G, X = simulate_panel(rng)
    cells, _ = att_gt(Y, G, X, cohorts=[6], delta=0)
    pre = [c["att"] for c in cells if c["e"] < -1]
    assert max(abs(a) for a in pre) < 0.01


def test_bootstrap_reproducible_with_seed():
    rng = np.random.default_rng(5)
    Y, G, X = simulate_panel(rng, n=400)
    a, _ = bootstrap(Y, G, X, [6], 5, np.random.default_rng(99), delta=0)
    b, _ = bootstrap(Y, G, X, [6], 5, np.random.default_rng(99), delta=0)
    assert np.array_equal(a, b)


# ---------------------------------------------------------------------------
# Check W1: unit weights
# ---------------------------------------------------------------------------

def test_equal_weights_reproduce_unweighted():
    rng = np.random.default_rng(6)
    Y, G, X = simulate_panel(rng, n=600)
    a = estimate(Y, G, X, [6], delta=0)["overall"]
    b = estimate(Y, G, X, [6], delta=0, W=np.ones(len(G)))["overall"]
    c = estimate(Y, G, X, [6], delta=0, W=np.full(len(G), 3.7))["overall"]
    assert np.isclose(a, b, atol=1e-12) and np.isclose(a, c, atol=1e-10)


def test_integer_weights_equal_duplicated_units():
    rng = np.random.default_rng(7)
    Y, G, X = simulate_panel(rng, n=500)
    W = rng.integers(1, 5, len(G)).astype(float)
    idx = np.repeat(np.arange(len(G)), W.astype(int))
    for kind in ["dr", "ipw", "or"]:
        weighted = estimate(Y, G, X, [6], delta=0, kind=kind, W=W)["overall"]
        duplicated = estimate(Y[idx], G[idx], X[idx], [6], delta=0, kind=kind)["overall"]
        assert np.isclose(weighted, duplicated, atol=1e-9), kind


def test_weighted_logit_matches_statsmodels_freq_weights():
    rng = np.random.default_rng(8)
    X = np.column_stack([np.ones(400), rng.normal(size=(400, 2))])
    d = (rng.random(400) < 1 / (1 + np.exp(-(X @ [0.2, 0.8, -0.5])))).astype(float)
    w = rng.integers(1, 6, 400).astype(float)
    ours = logit(X, d, w)
    theirs = sm.GLM(d, X, family=sm.families.Binomial(), freq_weights=w).fit().params
    assert np.allclose(ours, theirs, atol=1e-8)
