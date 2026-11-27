"""National grant rates before and after BNG (descriptive; validation target 3).

Run from the Pipeline folder, after src/planning_panel.py:
    python src/pilot1_rates.py

Two routes to the England totals: the raw PS2 rows (as in the pilot, development
corporations included) and the new 306-unit panel (development corporations excluded).
Definitions and checks are pre-specified in notes/pilot1_rates.md.
"""

import sys
from pathlib import Path

import pandas as pd

# src/ for planning_panel, the Pipeline folder for config
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from planning_panel import PS1_FILE, PS2_FILE, VARIABLES, load_england  # noqa: E402

PANEL = config.PROCESSED_DIR / "planning" / "panel_england_lpa2025_quarter.csv"

WINDOWS = {
    "pre": ("2022 Q1", "2023 Q2"),
    "anticipation": ("2023 Q3", "2024 Q1"),
    "transition": ("2024 Q2", "2024 Q4"),
    "post": ("2025 Q1", "2026 Q2"),
}
TYPES = {"major": "Major dwellings", "minor": "Minor dwellings", "hh": "Householder"}

# Pilot 1 summary, section C (Planning/output/pilot1/pilot1_summary.txt)
TARGETS = {
    ("major", "pre"): 80.0, ("major", "anticipation"): 78.9, ("major", "transition"): 82.2,
    ("major", "post"): 84.5,
    ("minor", "pre"): 71.5, ("minor", "anticipation"): 70.0, ("minor", "transition"): 72.2,
    ("minor", "post"): 74.6,
    ("hh", "pre"): 89.7, ("hh", "anticipation"): 88.4, ("hh", "transition"): 89.0,
    ("hh", "post"): 90.3,
}
# Pilot's computed England totals for 2026 Q2 (check R3)
TOTALS_2026Q2 = {"received_total": 78_706, "decided_total": 74_484,
                 "granted_total": 65_211, "dec_hh": 37_712}


def national(df):
    """England totals by quarter: sum over every row (min_count=1 keeps a missing
    quarter missing rather than zero)."""
    return df.groupby("Quarter")[list(VARIABLES)].sum(min_count=1).sort_index()


def window_rates(nat):
    """Mean of quarterly rates (pilot definition) and pooled rate, per type and window."""
    rows = []
    for t in TYPES:
        quarterly = 100 * nat[f"grant_{t}"] / nat[f"dec_{t}"]
        for w, (a, b) in WINDOWS.items():
            inside = nat.index.to_series().between(a, b)
            rows.append({
                "type": t, "window": w, "n_quarters": int(inside.sum()),
                "mean_of_quarters": quarterly[inside].mean(),
                "pooled": 100 * nat.loc[inside, f"grant_{t}"].sum() / nat.loc[inside, f"dec_{t}"].sum(),
            })
    return pd.DataFrame(rows).set_index(["type", "window"])


def main():
    raw = load_england()          # PS1 + PS2 rows, 2015 Q1-2026 Q2, all authorities
    panel = pd.read_csv(PANEL)
    nat_raw, nat_panel = national(raw), national(panel)

    pilot = window_rates(nat_raw)       # route 1
    new = window_rates(nat_panel)       # route 2

    # R1: pilot route reproduces the targets to 0.1 pp (they are printed to one decimal)
    target = pd.Series(TARGETS).rename_axis(["type", "window"])
    gap1 = (pilot.mean_of_quarters.round(1) - target).abs()
    assert (gap1 < 0.05).all(), f"R1 failed:\n{gap1[gap1 >= 0.05]}"

    # R2: dropping development corporations moves no rate by 0.1 pp or more
    gap2 = (pilot.mean_of_quarters - new.mean_of_quarters).abs()
    assert (gap2 < 0.1).all(), f"R2 failed:\n{gap2[gap2 >= 0.1]}"

    # R3: 2026 Q2 England totals
    for v, expected in TOTALS_2026Q2.items():
        got = nat_raw.loc["2026 Q2", v]
        assert got == expected, f"R3 failed: {v} {got} != {expected}"

    table = pd.DataFrame({
        "target": target,
        "pilot_route": pilot.mean_of_quarters,
        "panel_route": new.mean_of_quarters,
        "pooled_panel": new.pooled,
        "n_quarters": new.n_quarters,
    }).round(2)
    print("\nGrant rates (%), England; window rate = mean of quarterly rates unless 'pooled'")
    print(table.to_string())
    print(f"\nlargest |pilot route - panel route|: {gap2.max():.3f} pp")
    print(f"largest |mean of quarters - pooled| (panel): "
          f"{(new.mean_of_quarters - new.pooled).abs().max():.3f} pp")

    # Other Pilot 1 numbers quoted in FINDINGS section 5 (reported, not tested)
    yoy = 100 * nat_raw.dec_minor.pct_change(4)
    print("\nminor-dwelling decisions, % change on a year earlier:")
    print(yoy.loc["2024 Q3":"2025 Q2"].round(1).to_string())
    year = nat_raw.index.str[:4]
    annual = nat_raw.groupby(year).dec_major.sum()
    print(f"\nmajor-dwelling decisions per year: 2019 {annual['2019']:,.0f}; 2025 {annual['2025']:,.0f}")
    print(f"(inputs: {PS1_FILE.name}, {PS2_FILE.name}, {PANEL.name})")

    out = config.PROCESSED_DIR / "planning" / "pilot1_grant_rates.csv"
    table.to_csv(out)
    print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
