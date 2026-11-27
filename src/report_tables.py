"""Results tables for the report, written straight from the saved results files so that no
number is retyped by hand.

Run from the Pipeline folder, after the design scripts:
    python src/report_tables.py
Output: output/tables/tables.md (Markdown tables, one section per design)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

P = config.PROCESSED_DIR
OUT = config.REPO_ROOT / "output" / "tables"
TAG = "2026-11-06_sites"


def md(df):
    return df.to_markdown(index=False)


def fmt(b, se, p=None, digits=4):
    if np.isnan(b):
        return "-"
    s = f"{b:+.{digits}f} ({se:.{digits}f})"
    if p is None or np.isnan(p):
        return s
    return s + (" p<0.01" if p < 0.01 else f" p={p:.2f}")


def pct_ci(b, se, z=1.96):
    return f"{100 * (np.exp(b) - 1):+.1f}% [{100 * (np.exp(b - z * se) - 1):+.1f}, {100 * (np.exp(b + z * se) - 1):+.1f}]"


def supply():
    out = []
    b = pd.read_csv(P / "intensity" / "did_baseline.csv")
    t = pd.DataFrame({"Outcome": b.outcome,
                      "beta per SD (SE, pyfixest)": [fmt(x, s) for x, s in zip(b.beta, b.se_pyfixest_default)],
                      "SE, pilot convention": b.se_pilot_correction.round(4), "p": b.p.round(3),
                      "LPAs": b.n_lpa, "Obs": b.n_obs})
    out.append(("Table S1. Intensity DiD, baseline (205 councils, 2015 Q1-2026 Q2 excl. 2023 Q4-2024 Q2)", md(t)))

    r = pd.read_csv(P / "intensity" / "robustness_table.csv")
    keep = r[~r.check.str.startswith("11")]
    w = keep.assign(cell=[fmt(x, s, p, 3) for x, s, p in zip(keep.beta, keep.se, keep.p)]) \
        .pivot(index="check", columns="outcome", values="cell").reindex(keep.check.unique()).fillna("-").reset_index()
    w = w[["check", "log(1+dwelling decisions)", "dwelling grant rate", "log(1+householder decisions) [placebo]"]]
    w.columns = ["Check", "Dwelling decisions (log)", "Dwelling grant rate", "Householder (placebo)"]
    loro = r[r.check.str.startswith("11")].groupby("outcome").beta.agg(["min", "max"])
    w.loc[len(w)] = ["11 leave one region out (range)"] + [
        f"{loro.loc[o, 'min']:+.3f} to {loro.loc[o, 'max']:+.3f}" for o in
        ["log(1+dwelling decisions)", "dwelling grant rate", "log(1+householder decisions) [placebo]"]]
    out.append(("Table S2. Robustness: beta per SD of intensity x Post (SE clustered by LPA)", md(w)))

    pt = pd.read_csv(P / "intensity" / "pretrend_tests.csv")
    pt = pt[pt.scale == "per_lpa"][["sample", "outcome", "slope_per_year", "se", "p"]].round(4)
    out.append(("Table S3. Pre-BNG linear differential trend (2015 Q1-2023 Q3, per year per SD)", md(pt)))

    g = pd.read_csv(P / "planning" / "pilot1_grant_rates.csv")
    g = g[g.window.isin(["pre", "post"])].pivot(index="type", columns="window", values="pilot_route").round(2)
    g["change (pp)"] = (g["post"] - g["pre"]).round(2)
    g = g.reset_index()[["type", "pre", "post", "change (pp)"]]
    g["type"] = g["type"].map({"major": "Major dwellings", "minor": "Minor dwellings", "hh": "Householder"})
    out.append(("Table S4. National grant rates (%), pre 2022 Q1-2023 Q2 vs post 2025 Q1-2026 Q2 (descriptive)", md(g)))

    s = pd.read_csv(P / "sdid" / "sdid_table.csv")
    s = s[s.check.isin(["1 main", "2 placebo in time (fake post 2021 Q1-2023 Q3)", "3 drop interpolated councils"])]
    s = s[["check", "outcome", "tau", "se", "tau_did", "eff_donors", "n_wales", "n_england"]].round(4)
    out.append(("Table S5. SDID, English councils vs Welsh donors (jackknife SE; see the two-cluster caveat)", md(s)))
    return out


def demand():
    out = []
    G = P / "gainsites"
    rows = []
    t1 = pd.read_csv(G / f"t1_ring_did_{TAG}.csv").iloc[0]
    rows.append(["Ring DiD, urban fringe 2024-25", int(t1.sites), t1.beta, t1.se])
    for r in pd.read_csv(G / f"t2_stacked_{TAG}.csv").itertuples():
        rows.append([f"Stacked: {r.spec}", int(r.treated_sites), r.beta, r.se])
    ep = pd.read_csv(G / f"t5_epc_{TAG}.csv")
    for r in ep.itertuples():
        rows.append([f"EPC: {r.spec}", int(r.sites), r.beta, r.se])
    sd = pd.read_csv(G / f"t4_sdid_{TAG}.csv")
    a = sd.iloc[0]
    rows.append(["SDID, pseudo-site donors, seed 7", int(a.n_treated), a.tau, a.se])
    rows.append(["SDID, mean of 40 donor draws (SE: placebo and draw SD combined)", int(a.n_treated),
                 a.tau_mean_40_draws, float(np.hypot(a.se, a.tau_sd_40_draws))])
    t = pd.DataFrame(rows, columns=["Design / spec", "Sites (treated)", "beta", "SE"])
    t["% effect [95% CI]"] = [pct_ci(b, s) for b, s in zip(t.beta, t.SE)]
    t[["beta", "SE"]] = t[["beta", "SE"]].round(4)
    out.append(("Table D1. Gain-site price effects, sales-weighted designs (423-site register)", md(t)))

    cs = pd.read_csv(G / f"cs_drdid_{TAG}.csv")
    cw = pd.read_csv(G / f"cs_drdid_weighted_{TAG}.csv")
    c = pd.concat([cs, cw], ignore_index=True)
    c = c[["spec", "att", "se_boot", "ci90_lo", "ci90_hi", "equivalent_3pct", "pretrend_p", "treated_sites", "n_sites"]]
    c[["att", "se_boot", "ci90_lo", "ci90_hi", "pretrend_p"]] = c[["att", "se_boot", "ci90_lo", "ci90_hi", "pretrend_p"]].round(3)
    out.append(("Table D2. Callaway-Sant'Anna doubly robust (site x half-year; bootstrap B = 499)", md(c)))

    tost = pd.read_csv(G / f"tost_existing_{TAG}.csv").round(4)
    out.append(("Table D3. Equivalence (TOST) against +/-3% (+/-0.0296 log points), 90% CI", md(tost)))
    return out


def biodiversity():
    e = pd.read_csv(P / "ebird" / "selection_richness.csv")
    e["% [95% CI]"] = [pct_ci(b, s) for b, s in zip(e.beta, e.se)]
    e = e[["spec", "beta", "se", "% [95% CI]", "sites", "rows", "reading"]].round(4)
    return [("Table B1. Bird species per checklist near future gain sites vs 2-4 km, 2015-23 (PPML, site FE)", md(e))]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = []
    for title, body in supply() + demand() + biodiversity():
        parts.append(f"### {title}\n\n{body}\n")
    (OUT / "tables.md").write_text("\n".join(parts))
    print(f"wrote {OUT / 'tables.md'} ({len(parts)} tables)")


if __name__ == "__main__":
    main()
