"""Figures for the report and the write-up (PNG for viewing, PDF for LaTeX).

Run from the Pipeline folder, after the design scripts:
    python src/figures.py

Every figure is drawn from saved results (data/processed/...) or the rebuilt inputs; no
estimate is computed here except the planning SDID trajectory (fig_s6), which re-fits the
weights from src/sdid.py.

Colours: the reference palette's first three categorical slots (blue, orange, aqua: validated
all-pairs for maps and scatters), its blue sequential ramp for magnitude, neutral greys for
context. Aqua is below 3:1 contrast on the surface, so every figure has a legend or labels.
Outputs: output/figures/<name>.png and .pdf
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.patches import Circle, Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

PROC = config.PROCESSED_DIR
FIG = config.REPO_ROOT / "output" / "figures"
GRID_WORK = config.WORK_ROOT / "intensity"
LAD_FILE = next((config.RAW_ROOT / "RawData-BNG").glob("LAD_MAY_2025_UK_BGC*.gpkg"))
PARKS_FILE = config.RAW_ROOT / "RawData-BNG" / "National_Parks_England.gpkg"

# palette (reference instance, light mode)
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e7e6e2"
NEUTRAL = "#f0efec"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.titlesize": 10, "axes.titlelocation": "left", "axes.titlecolor": INK,
    "legend.frameon": False, "lines.linewidth": 1.5,
})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight", dpi=300)  # dpi for rasterised map layers
    plt.close(fig)
    print(f"  wrote {name}")


def note(fig, text, y=-0.02):
    fig.text(0.01, y, text, fontsize=7, color=INK2, va="top", wrap=True)


def england_lads():
    lad = gpd.read_file(LAD_FILE, columns=["LAD25CD", "LAD25NM"])
    return lad[lad.LAD25CD.str.startswith("E")].rename(columns={"LAD25CD": "code", "LAD25NM": "name"})


def parks():
    from intensity_grid import PARK_CODES
    p = gpd.read_file(PARKS_FILE, columns=["name"])
    p["code"] = p["name"].map(PARK_CODES)
    return p


def map_axes(ax):
    ax.set_axis_off()
    ax.set_aspect("equal")


def scale_bar(ax, x, y, km, label=None):
    ax.plot([x, x + km * 1000], [y, y], color=INK, lw=2, solid_capstyle="butt")
    ax.text(x + km * 500, y + 0.012 * (ax.get_ylim()[1] - ax.get_ylim()[0]), label or f"{km} km",
            ha="center", va="bottom", fontsize=7, color=INK)


def interval_points(ax, x, b, se, color, label=None, z=1.96, ms=4.5, offset=0.0):
    x = np.asarray(x, float) + offset
    ax.errorbar(x, b, yerr=z * np.asarray(se), fmt="o", ms=ms, color=color, ecolor=color,
                elinewidth=1, capsize=0, label=label, zorder=3)


# ===========================================================================
# Supply side
# ===========================================================================

def fig_s1_intensity_map():
    r = pd.read_csv(PROC / "intensity" / "intensity_lpa2025.csv")
    lad = england_lads().merge(r[["code", "intensity", "main_sample"]], on="code", how="left")
    pk = parks()
    bins = np.quantile(r.loc[r.main_sample, "intensity"], np.linspace(0, 1, 7))   # real min .. max
    cmap = ListedColormap(SEQ[:6])
    norm = BoundaryNorm(bins, cmap.N)
    fig, ax = plt.subplots(figsize=(6.4, 7.2))
    main = lad[lad.main_sample == True]  # noqa: E712
    other = lad[lad.main_sample != True]  # noqa: E712
    other.plot(ax=ax, color=GRID, edgecolor=SURFACE, linewidth=0.3, rasterized=True)
    main.plot(ax=ax, column="intensity", cmap=cmap, norm=norm, edgecolor=SURFACE, linewidth=0.3, rasterized=True)
    pk.plot(ax=ax, color="#b3b2ad", edgecolor=SURFACE, linewidth=0.3, rasterized=True)
    map_axes(ax)
    handles = [Patch(facecolor=SEQ[i], label=f"{bins[i]:.2f}-{bins[i + 1]:.2f}") for i in range(6)]
    handles += [Patch(facecolor=GRID, label="Excluded: urban / London councils"),
                Patch(facecolor="#b3b2ad", label="Excluded: national parks")]
    ax.legend(handles=handles, loc="upper left", fontsize=7.5, title="BNG intensity (sextiles,\nmain sample)",
              title_fontsize=8, bbox_to_anchor=(0.0, 0.98))
    ax.set_title("Supply: BNG intensity by planning authority (2025 boundaries)")
    note(fig, "Intensity = share of developable land within 500 m of settlements (built-up patches >= 10 ha) that has "
              "Medium or higher statutory-metric distinctiveness (Living England 2022-23). Main sample: 205 councils "
              "outside London with developable fringe >= settlement area. Source: rebuilt score, identical to the pilot.")
    save(fig, "fig_s1_intensity_map")


def fig_s2_intensity_method():
    """How the score is built, on one council: settlements, the 0-500 m zone, habitat value."""
    from intensity_grid import NCOL, NROW, RES, X0, Y1
    from intensity_score import rings, settlements
    r = pd.read_csv(PROC / "intensity" / "intensity_lpa2025.csv")
    units = pd.read_csv(GRID_WORK / "units_50m.csv")
    cand = r[r.main_sample & r.code.isin(units[units.area_ha_raster.between(25_000, 45_000)].code)]
    pick = cand.iloc[(cand.intensity - cand.intensity.median()).abs().argsort()].iloc[0]
    uid = int(units.loc[units.code == pick.code, "unit_id"].iloc[0])
    unit_r = np.load(GRID_WORK / "units_50m.npy", mmap_mode="r")
    rows, cols = np.nonzero(unit_r == uid)
    pad = 60                                                   # 3 km margin so rings are right at the edge
    r0, r1 = max(rows.min() - pad, 0), min(rows.max() + pad, NROW)
    c0, c1 = max(cols.min() - pad, 0), min(cols.max() + pad, NCOL)
    cls = np.load(GRID_WORK / "habitat_50m.npy", mmap_mode="r")[r0:r1, c0:c1].copy()
    inside = np.asarray(unit_r[r0:r1, c0:c1]) == uid
    codes = json.loads((GRID_WORK / "habitat_classes.json").read_text())
    xw = pd.read_csv(config.REPO_ROOT / "inputs" / "le_distinctiveness_crosswalk.csv")
    settle, _ = settlements(cls == codes["Built-up Areas and Gardens"], 40)
    ring = rings(settle)
    dev = np.zeros(256, bool)
    med = np.zeros(256, bool)
    for _, row in xw.iterrows():
        k = codes[row.le_class]
        dev[k] = row.developable == 1
        med[k] = (row.developable == 1) and (row.distinctiveness_main >= 4)
    layer = np.zeros(cls.shape, np.uint8)                      # 0 other
    zone = np.isin(ring, [1, 2]) & dev[cls]
    layer[zone & ~med[cls]] = 1                                 # zone, Low
    layer[zone & med[cls]] = 2                                  # zone, Medium+
    layer[settle] = 3                                           # settlement
    layer[~inside] = 4                                          # outside the council
    cmap = ListedColormap([NEUTRAL, ORANGE, BLUE, INK2, SURFACE])
    extent = [X0 + c0 * RES, X0 + c1 * RES, Y1 - r1 * RES, Y1 - r0 * RES]
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    ax.imshow(layer, cmap=cmap, vmin=-0.5, vmax=4.5, extent=extent, interpolation="nearest")
    lad = england_lads()
    lad[lad.code == pick.code].boundary.plot(ax=ax, color=INK, linewidth=0.8)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    map_axes(ax)
    scale_bar(ax, extent[0] + 0.05 * (extent[1] - extent[0]), extent[2] + 0.04 * (extent[3] - extent[2]), 5)
    handles = [Patch(facecolor=INK2, label="Settlement (built-up patch >= 10 ha)"),
               Patch(facecolor=BLUE, label="0-500 m zone: Medium+ habitat (costly under BNG)"),
               Patch(facecolor=ORANGE, label="0-500 m zone: Low habitat (cheap)"),
               Patch(facecolor=NEUTRAL, label="Other land in the council")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, fontsize=7.5)
    median = r.loc[r.main_sample, "intensity"].median()
    ax.set_title(f"How intensity is measured: {pick['name']} (intensity {pick.intensity:.2f}; "
                 f"main-sample median {median:.2f})")
    note(fig, "Intensity = blue / (blue + orange) area. 50 m grid; distance bands from a Euclidean distance "
              "transform; water, coast and built-up land excluded from the zone.", y=-0.07)
    save(fig, "fig_s2_intensity_method")


def quarter_x(q):
    q = pd.Series(q)
    return q.str[:4].astype(int) + (q.str[-1].astype(int) - 1) / 4


def bng_lines(ax, labels=True):
    ax.axvspan(2023.75, 2024.5, color=GRID, alpha=0.6, lw=0, zorder=0)
    for x, lab in [(2024.1, "BNG majors"), (2024.25, "BNG small sites")]:
        ax.axvline(x, color=INK2, lw=0.8, ls=(0, (2, 2)), zorder=1)


def fig_s3_planning_event_study():
    e = pd.read_csv(PROC / "intensity" / "event_study_coefs.csv")
    e = e[(e["sample"] == "main") & (e.scale == "per_lpa")]
    outs = [("log(1+dwelling decisions)", "Dwelling decisions (log)"),
            ("dwelling grant rate", "Dwelling grant rate"),
            ("log(1+householder decisions) [placebo]", "Householder decisions (log), placebo")]
    fig, axs = plt.subplots(3, 1, figsize=(7.2, 7.4), sharex=True)
    for ax, (key, title) in zip(axs, outs):
        x = e[e.outcome == key]
        bng_lines(ax)
        ax.axhline(0, color=INK2, lw=0.8)
        interval_points(ax, quarter_x(x.quarter), x.b, x.se, BLUE, ms=3.5)
        ax.set_title(title)
        ax.set_ylabel("coef. per SD of intensity")
    axs[-1].set_xticks(range(2015, 2027))
    axs[0].annotate("reference 2023 Q3", xy=(2023.5, 0), xytext=(2020.6, 0.045), fontsize=7, color=INK2,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    fig.suptitle("Supply: event study by BNG intensity (205 councils, LPA and quarter FE)", x=0.01, ha="left",
                 fontsize=10.5, color=INK)
    fig.tight_layout()
    note(fig, "Points: intensity x quarter coefficients, 95% CIs (SE clustered by LPA). Grey band: 2023 Q4-2024 Q2 "
              "(fee rise, BNG transition; dropped from the DiD). Dashed: BNG for major (12 Feb 2024) and small sites "
              "(2 Apr 2024). High-intensity councils were 2-5% below in 2015-21 and caught up before BNG.")
    save(fig, "fig_s3_planning_event_study")


def fig_s4_robustness():
    t = pd.read_csv(PROC / "intensity" / "robustness_table.csv")
    t = t[~t.check.str.startswith("11")]
    order = list(dict.fromkeys(t.check))
    outs = [("log(1+dwelling decisions)", "Dwelling decisions (log)"),
            ("dwelling grant rate", "Dwelling grant rate"),
            ("log(1+householder decisions) [placebo]", "Householder (placebo)")]
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 6.8), sharey=True)
    y = np.arange(len(order))[::-1]
    for ax, (key, title) in zip(axs, outs):
        x = t[t.outcome == key].set_index("check").reindex(order)
        ax.axvline(0, color=INK2, lw=0.8)
        main = np.array([c.startswith("1 ") for c in order])
        col = np.where(main, ORANGE, BLUE)
        for yi, (b, se, c) in enumerate(zip(x.beta, x.se, col)):
            if np.isnan(b):
                continue
            ax.errorbar(b, y[yi], xerr=1.96 * se, fmt="o", ms=4, color=c, ecolor=c, elinewidth=1, capsize=0)
        ax.set_title(title)
        ax.set_xlabel("beta per SD of intensity x Post")
        ax.grid(axis="y", visible=False)
    axs[0].set_yticks(y)
    axs[0].set_yticklabels(order, fontsize=7.5)
    fig.suptitle("Supply: pre-registered robustness checks (95% CIs, SE clustered by LPA)", x=0.01, ha="left",
                 fontsize=10.5, color=INK)
    fig.tight_layout()
    note(fig, "Orange: baseline (205 councils). Check 5 uses the corrected first step (pilot value 0.0285 had a "
              "rank-deficiency rounding error). Check 11 (leave one region out) is summarised in the report table.")
    save(fig, "fig_s4_robustness")


def fig_s5_grant_rates():
    p = pd.read_csv(PROC / "planning" / "panel_england_lpa2025_quarter.csv")
    nat = p.groupby("Quarter")[["grant_major", "dec_major", "grant_minor", "dec_minor", "grant_hh", "dec_hh"]].sum()
    x = quarter_x(nat.index)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for lo, hi, lab in [(2022.0, 2023.5, "pre"), (2025.0, 2026.5, "post")]:
        ax.axvspan(lo, hi, color=NEUTRAL, lw=0, zorder=0)
        ax.text((lo + hi) / 2, 92.5, lab, ha="center", fontsize=7.5, color=INK2)
    bng_lines(ax)
    series = [("major", "Major dwellings (10+)", BLUE), ("minor", "Minor dwellings (1-9)", ORANGE),
              ("hh", "Householder (BNG-exempt)", AQUA)]
    for k, lab, c in series:
        y = 100 * nat[f"grant_{k}"] / nat[f"dec_{k}"]
        ax.plot(x, y, color=c, lw=1.6, label=lab)
        ax.text(x.iloc[-1] + 0.1, y.iloc[-1], lab.split(" (")[0], fontsize=7.5, color=INK, va="center")
    ax.set_xlim(2015, 2028.2)
    ax.set_ylim(64, 94)
    ax.set_ylabel("% of decisions granted")
    ax.set_xticks(range(2015, 2027))
    ax.legend(loc="lower left", fontsize=7.5, ncol=3)
    ax.set_title("Supply: national grant rates by application type (England, quarterly)")
    note(fig, "Pre (2022 Q1-2023 Q2) to post (2025 Q1-2026 Q2): major 80.0 -> 84.5%, minor 71.5 -> 74.6%, "
              "householder 89.7 -> 90.3%. Descriptive: the post window also follows the Dec 2024 NPPF.")
    save(fig, "fig_s5_grant_rates")


def fig_s6_wales_sdid():
    import sdid as S
    d, _, _ = S.load()
    q = sorted(d.Quarter.unique())
    pre = [x for x in q if x < S.DROP_QUARTERS[0]]
    post = [x for x in q if x >= S.POST_START]
    m, n_co, _ = S.outcome_matrix(d, "grate", pre + post)
    Y, T0 = m.values, len(pre)
    r = S.sdid(Y, n_co, T0, jackknife=False)
    tr = Y[n_co:].mean(0)
    syn = r["omega"] @ Y[:n_co]
    syn = syn + (tr[:T0] - syn[:T0]).mean()
    wal = Y[:n_co].mean(0)
    wal = wal + (tr[:T0] - wal[:T0]).mean()
    # break the lines across the dropped quarters (2023 Q4-2024 Q2) instead of joining them
    x = np.r_[quarter_x(pd.Series(pre)), np.nan, quarter_x(pd.Series(post))]
    gap = lambda v: np.r_[v[:T0], np.nan, v[T0:]]  # noqa: E731
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axs[0]
    bng_lines(ax)
    ax.plot(x, 100 * gap(tr), color=BLUE, label="England councils (mean)")
    ax.plot(x, 100 * gap(syn), color=ORANGE, label="Synthetic Wales (SDID weights, level-matched)")
    ax.plot(x, 100 * gap(wal), color=AQUA, ls=(0, (3, 2)), label="Wales, equal weights (DiD), level-matched")
    ax.set_ylabel("dwelling grant rate (%)")
    ax.set_title("Supply: England vs Welsh donor councils")
    ax.legend(fontsize=7.5, loc="lower left")
    ax2 = axs[1]
    tab = pd.read_csv(PROC / "sdid" / "sdid_table.csv")
    rows = tab[(tab.outcome == "dwelling grant rate [primary]")].set_index("check")
    labels = ["1 main", "2 placebo in time (fake post 2021 Q1-2023 Q3)", "3 drop interpolated councils"]
    short = ["Main (post 2024 Q3+)", "Placebo in time (2021-23)", "Drop interpolated"]
    yy = np.arange(len(labels))[::-1]
    for yi, lab in zip(yy, labels):
        b, se = rows.loc[lab, "tau"], rows.loc[lab, "se"]
        c = ORANGE if lab.startswith("2") else BLUE
        ax2.errorbar(100 * b, yi, xerr=196 * se, fmt="o", ms=4.5, color=c, ecolor=c, elinewidth=1)
    ax2.axvline(0, color=INK2, lw=0.8)
    ax2.set_yticks(yy)
    ax2.set_yticklabels(short)
    ax2.set_xlabel("SDID tau, pp of grant rate (95% CI)")
    ax2.set_title("Placebo larger than the estimate")
    ax2.grid(axis="y", visible=False)
    fig.tight_layout()
    note(fig, "Welsh grant rates fell from ~80% to ~65% in 2016-23 while England's held near 75%; reweighting donors "
              "cannot remove the divergence. Verdict: Wales is not a usable comparison group for planning outcomes.")
    save(fig, "fig_s6_wales_sdid")


# ===========================================================================
# Demand side
# ===========================================================================

def demand_sites():
    s = pd.read_csv(PROC / "bng" / "gainsite_context_2026-11-06_sites.csv")
    s["treat"] = pd.to_datetime(s.treat)
    return s


def fig_d1_sites_map():
    s = demand_sites()
    lad = england_lads()
    fig, ax = plt.subplots(figsize=(6.4, 7.2))
    lad.plot(ax=ax, color=NEUTRAL, edgecolor=SURFACE, linewidth=0.3, rasterized=True)
    for yr, c in [(2024, BLUE), (2025, ORANGE), (2026, AQUA)]:
        x = s[s.cohort == yr]
        ax.scatter(x.easting, x.northing, s=11, color=c, edgecolor=SURFACE, linewidth=0.4,
                   label=f"Registered {yr} ({len(x)})", zorder=3)
    map_axes(ax)
    ax.legend(loc="upper left", fontsize=7.5, title=f"Gain sites ({len(s)})", title_fontsize=8, markerscale=1.4)
    ax.set_title("Demand: registered biodiversity gain sites (6 Nov 2026 register)")
    note(fig, "Points: grid references (no site boundaries are published); year = reference date (application "
              f"submitted). {int(s.urban_fringe.sum())} sites are 'urban fringe' (>= 10% built-up within 1 km). "
              "Price data end Jun 2026, so 2026 sites act only as later-registered controls.")
    save(fig, "fig_d1_sites_map")


def fig_d2_ring_design():
    from intensity_grid import RES, X0, Y1
    s = demand_sites()
    t1 = s[s.urban_fringe & (s.cohort <= 2025)]
    pc = pd.read_parquet(config.WORK_ROOT / "gainsites" / "pc_index.parquet")
    cells = pd.read_parquet(config.WORK_ROOT / "gainsites" / "site_cells_2026-11-06_sites.parquet")
    inner_n = cells[cells.ring.isin(["0-500m", "500m-1km"])].groupby("ref").n.sum()
    pick = t1.assign(n=t1.ref.map(inner_n)).sort_values("n").iloc[len(t1) // 2]   # a typical site
    dx = np.hypot(pc.easting - pick.easting, pc.northing - pick.northing) - pick.radius_m
    near = pc[dx < 4300].assign(d=np.clip(dx[dx < 4300], 0, None))
    codes = json.loads((GRID_WORK / "habitat_classes.json").read_text())
    half = int((pick.radius_m + 4500) // RES)
    rc, cc = int((Y1 - pick.northing) // RES), int((pick.easting - X0) // RES)
    hab = np.load(GRID_WORK / "habitat_50m.npy", mmap_mode="r")[rc - half:rc + half, cc - half:cc + half]
    built = (np.asarray(hab) == codes["Built-up Areas and Gardens"]).astype(float)
    built[built == 0] = np.nan
    ext = [X0 + (cc - half) * RES, X0 + (cc + half) * RES, Y1 - (rc + half) * RES, Y1 - (rc - half) * RES]
    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    ax.imshow(built, cmap=ListedColormap([GRID]), extent=ext, interpolation="nearest", zorder=0)
    groups = [(near.d < 1000, BLUE, "0-1 km: treated ring"), ((near.d >= 1000) & (near.d < 2000), MUTED, "1-2 km: buffer (dropped)"),
              ((near.d >= 2000) & (near.d < 4000), ORANGE, "2-4 km: comparison ring")]
    for mask, c, lab in groups:
        ax.scatter(near.easting[mask], near.northing[mask], s=3, color=c, label=lab, zorder=2, linewidths=0)
    for rad, ls in [(pick.radius_m, "-"), (pick.radius_m + 1000, "-"), (pick.radius_m + 2000, (0, (3, 2))),
                    (pick.radius_m + 4000, "-")]:
        ax.add_patch(Circle((pick.easting, pick.northing), rad, fill=False, ec=INK, lw=0.8, ls=ls, zorder=3))
    ax.add_patch(Circle((pick.easting, pick.northing), pick.radius_m, color=AQUA, zorder=4))
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    map_axes(ax)
    scale_bar(ax, ext[0] + 400, ext[2] + 400, 2)
    h, l = ax.get_legend_handles_labels()
    h += [Patch(facecolor=AQUA, label="Gain site (disc of its area)"), Patch(facecolor=GRID, label="Built-up land")]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, fontsize=7.5, markerscale=3)
    ax.set_title(f"Demand: the ring design around one urban-fringe site ({pick.base_ref}, registered "
                 f"{pick.treat:%b %Y})")
    note(fig, "Dots: postcodes with any sale 2018-26. Distance is from the implied site edge (circle of the site's "
              "area). Ring DiD: 0-1 km vs 2-4 km prices, before vs after registration, within each site.", y=-0.08)
    save(fig, "fig_d2_ring_design")


def fig_d3_stacked_event_study():
    e = pd.read_csv(PROC / "gainsites" / "t2_event_study_2026-11-06_sites.csv")
    e = pd.concat([e, pd.DataFrame({"halfyear": [-1], "beta": [0.0], "se": [0.0]})]).sort_values("halfyear")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.axvspan(-0.5, e.halfyear.max() + 0.5, color=NEUTRAL, lw=0, zorder=0)
    ax.axhline(0, color=INK2, lw=0.8)
    interval_points(ax, e.halfyear, 100 * e.beta, 100 * e.se, BLUE)
    ax.set_xticks(e.halfyear)
    ax.set_xticklabels([f"{int(h)}" for h in e.halfyear])
    ax.set_xlabel("half-years since registration (reference: -1)")
    ax.set_ylabel("price effect within 1 km (%)")
    ax.set_title("Demand: event study, later-registered sites as controls (423 sites)")
    note(fig, "Stacked clean-control DiD (inner 0-1 km ring; FE stack x site and stack x quarter; weights = sales; "
              "SE clustered by site); 95% CIs. Shaded: after registration. Joint pre-trend test p = 0.39.")
    save(fig, "fig_d3_stacked_event_study")


def demand_estimates():
    tag = "2026-11-06_sites"
    G = PROC / "gainsites"
    rows = []
    t1 = pd.read_csv(G / f"t1_ring_did_{tag}.csv").iloc[0]
    rows.append(("Ring / stacked (sales-weighted)", "Ring DiD, urban fringe (71 sites)", t1.beta, t1.se))
    lab = {"1a": "Later sites as controls (155 treated)", "1b": "Later sites: ring DDD",
           "1c": "Later sites: urban fringe only", "1d": "Later sites: urban fringe, ring DDD",
           "1f": "Later sites: timing = works start", "1g": "Later sites: existing homes only"}
    for r in pd.read_csv(G / f"t2_stacked_{tag}.csv").itertuples():
        if r.spec[:2] in lab:
            rows.append(("Ring / stacked (sales-weighted)", lab[r.spec[:2]], r.beta, r.se))
    ep = pd.read_csv(G / f"t5_epc_{tag}.csv").set_index("spec")
    rows.append(("EPC hedonic", "Ring DiD + floor area, rooms, age, rating", ep.iloc[1].beta, ep.iloc[1].se))
    rows.append(("EPC hedonic", "Ring DiD, price per m2", ep.iloc[2].beta, ep.iloc[2].se))
    sd = pd.read_csv(G / f"t4_sdid_{tag}.csv").iloc[0]
    rows.append(("Synthetic DiD", "SDID, mean of 40 donor draws (64 sites)", sd.tau_mean_40_draws,
                 float(np.hypot(sd.se, sd.tau_sd_40_draws))))
    cs = pd.read_csv(G / f"cs_drdid_{tag}.csv").iloc[0]
    cw = pd.read_csv(G / f"cs_drdid_weighted_{tag}.csv").iloc[0]
    rows.append(("Callaway-Sant'Anna DR", "CS doubly robust, covariates (355 sites)", cs.att, cs.se_boot))
    rows.append(("Callaway-Sant'Anna DR", "CS doubly robust, sales-weighted", cw.att, cw.se_boot))
    return pd.DataFrame(rows, columns=["group", "label", "beta", "se"])


def fig_d4_estimates():
    t = demand_estimates()
    pct = lambda b: 100 * (np.exp(b) - 1)  # noqa: E731
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    ax.axvspan(-3, 3, color=NEUTRAL, lw=0, zorder=0)
    ax.axvline(0, color=INK2, lw=0.8)
    colours = {"Ring / stacked (sales-weighted)": BLUE, "EPC hedonic": BLUE, "Synthetic DiD": AQUA,
               "Callaway-Sant'Anna DR": ORANGE}
    y = np.arange(len(t))[::-1]
    for yi, r in zip(y, t.itertuples()):
        lo, hi, b = pct(r.beta - 1.96 * r.se), pct(r.beta + 1.96 * r.se), pct(r.beta)
        c = colours[r.group]
        ax.plot([lo, hi], [yi, yi], color=c, lw=1.2, solid_capstyle="round")
        ax.plot(b, yi, "o", ms=5, color=c, mec=SURFACE, mew=0.8, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(t.label, fontsize=7.8)
    ax.set_xlabel("effect on existing-home prices within 1 km of a gain site (%, 95% CI)")
    ax.grid(axis="y", visible=False)
    ax.text(0, y.max() + 0.9, "+/-3% equivalence band", ha="center", fontsize=7.5, color=INK2)
    ax.set_ylim(-0.8, y.max() + 1.4)
    handles = [Line2D([], [], marker="o", color=c, lw=1.2, label=g) for g, c in
               [("Ring / stacked / EPC (sales-weighted)", BLUE), ("Synthetic DiD", AQUA),
                ("Callaway-Sant'Anna doubly robust (site-level)", ORANGE)]]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, -0.13), ncol=3, fontsize=7.5)
    ax.set_title("Demand: every estimate of the gain-site price effect (423-site register)")
    note(fig, "TOST (90% CI inside +/-3%) passes for the ring DiD, the stacked DiD and works-start timing; the "
              "site-level CS estimates are too imprecise to test equivalence. SDID SE combines placebo SE and "
              "donor-draw SD.", y=-0.09)
    save(fig, "fig_d4_estimates")


def fig_d5_cs_event_study():
    e = pd.read_csv(PROC / "gainsites" / "cs_event_study_2026-11-06_sites.csv")
    e = e[e.spec.str.startswith("Main")]
    e = pd.concat([e, pd.DataFrame({"e": [-2], "att": [0.0], "se_boot": [0.0]})]).sort_values("e")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.axvspan(-1.5, -0.5, color="#d6d5d0", lw=0, zorder=0)
    ax.axvspan(-0.5, e.e.max() + 0.5, color=NEUTRAL, lw=0, zorder=0)
    ax.axhline(0, color=INK2, lw=0.8)
    interval_points(ax, e.e, 100 * e.att, 100 * e.se_boot, ORANGE)
    top = ax.get_ylim()[1]
    ax.text(-1, top * 0.93, "anticipation", ha="center", fontsize=7, color=INK2)
    ax.text((e.e.max() - 0.5) / 2, top * 0.93, "after registration", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(e.e)
    ax.set_xlabel("half-years since registration (base: -2; grey: anticipation half-year)")
    ax.set_ylabel("ATT, inner-minus-outer price gap (%)")
    ax.set_title("Demand: Callaway-Sant'Anna doubly robust event study (355 sites)")
    note(fig, "Not-yet-treated sites as controls; covariates: site area, built-up share, woodland habitat, IMD 2025, "
              "2018-19 price level. 95% CIs from a 499-rep site bootstrap. Pre-trend test p = 0.46.")
    save(fig, "fig_d5_cs_event_study")


def fig_b1_ebird():
    t = pd.read_csv(PROC / "ebird" / "selection_richness.csv")
    short = ["All species, 0-1 km vs 2-4 km", "  without effort controls", "  0-500 m vs 2-4 km",
             "  all 298 sites with lists in both rings", "Farmland Bird Index species"]
    pct = lambda b: 100 * (np.exp(b) - 1)  # noqa: E731
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    ax.axvline(0, color=INK2, lw=0.8)
    y = np.arange(len(t))[::-1]
    for yi, r in zip(y, t.itertuples()):
        c = AQUA if "Farmland" in r.spec else BLUE
        ax.plot([pct(r.lo95), pct(r.hi95)], [yi, yi], color=c, lw=1.2)
        ax.plot(pct(r.beta), yi, "o", ms=5, color=c, mec=SURFACE, mew=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(short, fontsize=7.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("difference in species per checklist, same effort (%, 95% CI)")
    ax.set_title("Biodiversity: were gain sites already bird-rich before BNG? (eBird 2015-23)")
    note(fig, "PPML, site FE, effort controls (duration, distance, observers, protocol, start hour), month and year FE; "
              "124 well-surveyed sites (spec 4: 298). Descriptive. The 2-4 km ring includes towns.", y=-0.06)
    save(fig, "fig_b1_ebird_selection")


def main():
    for f in [fig_s1_intensity_map, fig_s2_intensity_method, fig_s3_planning_event_study, fig_s4_robustness,
              fig_s5_grant_rates, fig_s6_wales_sdid, fig_d1_sites_map, fig_d2_ring_design,
              fig_d3_stacked_event_study, fig_d4_estimates, fig_d5_cs_event_study, fig_b1_ebird]:
        f()


if __name__ == "__main__":
    which = sys.argv[1:] or None
    if which:
        for name in which:
            globals()[name]()
    else:
        main()
