"""Were gain sites already bird-rich? Richness 0-1 km vs 2-4 km around future gain sites,
2015-2023, for the same observer effort (PPML, site FE). Descriptive, not causal.

Run from the Pipeline folder, after src/ebird_species.py:
    python src/ebird_selection.py

Specification and reading rules: notes/ebird_selection.md.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from ebird_counts import OUT, OUT_WORK  # noqa: E402

SIMILAR = 0.049          # +/-5% in log points


def load():
    p = pd.read_parquet(OUT_WORK / "selection_pairs_2015_2023.parquet")
    r = pd.read_parquet(OUT_WORK / "richness_2015_2023.parquet")
    d = p.merge(r, left_on="SAMPLING EVENT IDENTIFIER", right_on="id", how="left", validate="many_to_one")
    assert d.richness.notna().all()
    d["inner"] = (d.d_edge < 1000).astype(int)
    d["inner500"] = (d.d_edge < 500).astype(int)
    d["log_dur"] = np.log(d.duration)
    d["log_dist"] = np.log1p(d.distance)
    d["obs_bin"] = np.where(d.observers >= 3, "3+", d.observers.astype(int).astype(str))
    d["traveling"] = (d["PROTOCOL NAME"] == "Traveling").astype(int)
    hour = pd.to_numeric(d["TIME OBSERVATIONS STARTED"].str[:2], errors="coerce")
    d["hour_bin"] = pd.cut(hour, [-1, 7, 10, 14, 24], labels=["<08", "08-11", "11-15", "15+"]).astype(str)
    d["month"], d["year"] = d.date.dt.month.astype(str), d.date.dt.year.astype(str)
    return d


def fit(d, y, x, effort=True):
    controls = " + log_dur + log_dist + C(obs_bin) + traveling" if effort else ""
    fe = "ref + month + year + hour_bin" if effort else "ref + month + year"
    m = pf.fepois(f"{y} ~ {x}{controls} | {fe}", data=d, vcov={"CRV1": "ref"})
    b, se = float(m.coef()[x]), float(m.se()[x])
    return {"beta": b, "se": se, "lo95": b - 1.96 * se, "hi95": b + 1.96 * se,
            "pct": 100 * (np.exp(b) - 1), "sites": d.ref.nunique(), "rows": m._N,
            "inner_rows": int(d[x].sum())}


def reading(r):
    if r["lo95"] > 0:
        return "richer near future sites"
    if r["hi95"] < 0:
        return "poorer near future sites"
    return "similar (within +/-5%)" if (r["lo95"] > -SIMILAR and r["hi95"] < SIMILAR) else "inconclusive"


def main():
    d = load()
    n_inner = d[(d.inner == 1) & d.date.dt.year.between(2018, 2023)].groupby("ref").size()
    main_sites = n_inner[n_inner >= 10].index
    print(f"pairs {len(d):,}; sites with >= 10 inner checklists 2018-23: {len(main_sites)} (feasibility: 124)")
    m = d[d.ref.isin(main_sites)]
    both = d.groupby("ref").inner.agg(["min", "max"])
    all_sites = d[d.ref.isin(both[(both["min"] == 0) & (both["max"] == 1)].index)]

    desc = m.groupby("inner")[["richness", "fbi", "duration", "distance", "observers", "traveling"]].mean()
    print("\nmain sample means (0 = 2-4 km, 1 = 0-1 km):\n" + desc.round(2).to_string())

    rows = []
    for label, data, y, x, eff in [
            ("1 Main: richness, 0-1 km vs 2-4 km, effort controls", m, "richness", "inner", True),
            ("2 No effort controls", m, "richness", "inner", False),
            ("3 0-500 m vs 2-4 km", m[(m.inner500 == 1) | (m.inner == 0)], "richness", "inner500", True),
            ("4 All sites with checklists in both rings", all_sites, "richness", "inner", True),
            ("5 Farmland Bird Index species", m, "fbi", "inner", True)]:
        r = {"spec": label, **fit(data, y, x, eff)}
        r["reading"] = reading(r)
        rows.append(r)
    tab = pd.DataFrame(rows)

    # second route for the main spec: statsmodels GLM Poisson with explicit dummies
    g = smf.glm("richness ~ inner + log_dur + log_dist + C(obs_bin) + traveling + C(ref) + C(month) + C(year) + C(hour_bin)",
                data=m, family=sm.families.Poisson()).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(m.ref)[0]})
    print(f"\nsecond route (statsmodels GLM): beta {g.params['inner']:.7f} vs pyfixest {tab.beta[0]:.7f}; "
          f"|diff| {abs(g.params['inner'] - tab.beta[0]):.1e}")
    assert abs(g.params["inner"] - tab.beta[0]) < 1e-6, "second route disagrees"

    pd.set_option("display.width", 200)
    print("\n" + tab[["spec", "beta", "se", "lo95", "hi95", "pct", "sites", "rows", "inner_rows", "reading"]]
          .round(4).to_string(index=False))
    OUT.mkdir(parents=True, exist_ok=True)
    tab.to_csv(OUT / "selection_richness.csv", index=False)
    desc.to_csv(OUT / "selection_means.csv")


if __name__ == "__main__":
    main()
