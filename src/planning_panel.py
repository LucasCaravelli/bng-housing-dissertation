"""Planning applications and decisions by LPA and quarter, on 2025 LPA boundaries.

Run from the Pipeline folder:
    python3 src/planning_panel.py

England: MHCLG PS1/PS2 open-data tables (release to June 2026), 2015 Q1 to 2026 Q2.
Councils merged in 2019-23 are summed into their 2025 successor, so every unit has one
continuous series. National park authorities are their own units. Development
corporations are dropped.

Wales: Development Management Quarterly Survey (DMQS), 36 releases, 2016 Q1 to 2026 Q1.
Each release covers five financial-year quarters; the latest release of each quarter is kept.

Outputs in PROCESSED_DIR/planning:
    panel_england_lpa2025_quarter.csv   one row per 2025 unit x quarter
    units_england_lpa2025.csv           the 306 units (code, name, type, notes)
    panel_wales_lpa_quarter.csv         one row per Welsh authority x quarter

Decision rules and checks are pre-specified in notes/planning_panel.md.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# config.py sits one folder up from src/; add it to the import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

MHCLG_DIR = config.RAW_ROOT / "RawData-Planning" / "2026-10-29_MHCLG"
PS1_FILE = MHCLG_DIR / "PS1_data_-_open_data_table__202606_.csv"
PS2_FILE = MHCLG_DIR / "PS2_data_-_open_data_table__202606_.csv"
LAD_FILE = next((config.RAW_ROOT / "RawData-BNG").glob("LAD_MAY_2025_UK_BGC*.gpkg"))
OLD_PANEL = config.RAW_ROOT / "ProcessedData" / "planning" / "panel_lpa2025_quarter.csv"
OUT_DIR = config.PROCESSED_DIR / "planning"

WALES_DIR = config.RAW_ROOT / "RawData-Planning" / "2026-10-29_Wales_DMQS"
OLD_WALES = config.RAW_ROOT / "ProcessedData" / "planning" / "wales_dmqs_lpa_quarter.csv"
WALES_FIRST, WALES_LAST = "2016 Q1", "2026 Q1"
# DMQS names: Dtrm = decided, Appd = granted, Refd = refused, Recd = received;
# MajDw = major dwellings, MinDw = minor dwellings, MinHou = householder
WALES_VARS = ["DtrmMajDw", "AppdMajDw", "RefdMajDw", "DtrmMinDw", "AppdMinDw", "RefdMinDw",
              "DtrmMinHou", "AppdMinHou", "RecdMajDw", "RecdMinDw", "RecdMinHou", "RecdTot", "DtrmTot"]
RELEASE_MONTHS = {"january-march": 1, "april-june": 2, "july-september": 3, "october-december": 4}

FIRST_QUARTER, LAST_QUARTER = "2015 Q1", "2026 Q2"

# Short name -> (source file, MHCLG column). "(all)" columns include applications with
# Performance Agreements / extensions of time; "PAs only" counts those separately.
VARIABLES = {
    "received_total": ("PS1", "Applications received"),
    "decided_total_ps1": ("PS1", "Applications decided"),
    "decided_total": ("PS2", "Total decisions; grand total (all)"),
    "granted_total": ("PS2", "Total granted; grand total (all)"),
    "dec_major": ("PS2", "Total decisions; major dwellings (all)"),
    "grant_major": ("PS2", "Total granted; major dwellings (all)"),
    "pa_major": ("PS2", "Total decisions; major dwellings (PAs only)"),
    "dec26to52_major": ("PS2", "Total decided within 26 to 52 weeks; major dwellings (excluding PAs)"),
    "dec52plus_major": ("PS2", "Total decided beyond 52 weeks; major dwellings (excluding PAs)"),
    "dec_minor": ("PS2", "Total decisions; minor dwellings (all)"),
    "grant_minor": ("PS2", "Total granted; minor dwellings (all)"),
    "pa_minor": ("PS2", "Total decisions; minor dwellings (PAs only)"),
    "dec26to52_minor": ("PS2", "Total decided within 26 to 52 weeks; minor dwellings (excluding PAs)"),
    "dec52plus_minor": ("PS2", "Total decided beyond 52 weeks; minor dwellings (excluding PAs)"),
    "dec_hh": ("PS2", "Total decisions; (other) householder developments (all)"),
    "grant_hh": ("PS2", "Total granted; (other) householder developments (all)"),
    "pa_hh": ("PS2", "Total decisions; (other) householder developments (PAs only)"),
}
VARS = list(VARIABLES)

# 2019-23 council mergers: 2025 successor -> predecessor codes (rule 4)
MERGERS = {
    "E06000058": ["E06000028", "E06000029", "E07000048"],              # BCP, 2019
    "E06000059": ["E07000049", "E07000050", "E07000051", "E07000052",
                  "E07000053"],                                       # Dorset, 2019
    "E07000244": ["E07000205", "E07000206"],                          # East Suffolk, 2019
    "E07000245": ["E07000201", "E07000204"],                          # West Suffolk, 2019
    "E06000060": ["E07000004", "E07000005", "E07000006", "E07000007"],  # Buckinghamshire, 2020
    "E06000061": ["E07000150", "E07000152", "E07000153", "E07000156"],  # North Northants, 2021
    "E06000062": ["E07000151", "E07000154", "E07000155"],              # West Northants, 2021
    "E06000063": ["E07000026", "E07000028", "E07000029"],              # Cumberland, 2023
    "E06000064": ["E07000027", "E07000030", "E07000031"],              # Westmorland and Furness, 2023
    "E06000065": ["E07000163", "E07000164", "E07000165", "E07000166",
                  "E07000167", "E07000168", "E07000169"],              # North Yorkshire, 2023
    "E06000066": ["E07000187", "E07000188", "E07000189", "E07000190",
                  "E07000191", "E07000246"],                          # Somerset, 2023 (via SW&T 2019)
}
TO_2025 = {old: new for new, olds in MERGERS.items() for old in olds}

# Councils that lost part of their planning area to a development corporation (rule 5)
DC_HOSTS = {
    **dict.fromkeys(["E09000025", "E09000030", "E09000012", "E09000031"], "E51000001"),  # LLDC
    **dict.fromkeys(["E09000009", "E09000005", "E09000013"], "E51000002"),               # OPDC
    **dict.fromkeys(["E07000107", "E07000109"], "E51000003"),                            # Ebbsfleet
    "E06000002": "E51000006",                                                            # Middlesbrough DC
    "E06000001": "E51000007",                                                            # Hartlepool DC
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def read_mhclg(path):
    """The open-data CSVs have title rows above the header and are cp1252-encoded.
    Find the header row (first cell 'Region') rather than hard-coding it (rule 1)."""
    peek = pd.read_csv(path, header=None, nrows=15, encoding="cp1252", low_memory=False)
    header_row = int(peek.index[peek[0].astype(str).str.strip() == "Region"][0])
    df = pd.read_csv(path, header=header_row, encoding="cp1252", low_memory=False, na_values=[".."])
    df = df[df["Quarter"].astype(str).str.fullmatch(r"\d{4} Q[1-4]")]
    df = df[df["Quarter"].between(FIRST_QUARTER, LAST_QUARTER)].copy()  # 'YYYY Qn' sorts as text
    assert not df.duplicated(["LPACD", "Quarter"]).any(), f"E1 failed: duplicate rows in {path.name}"
    return df


def english_councils_2025():
    """English LAD codes and names from the May 2025 boundary file (attribute table only)."""
    with sqlite3.connect(f"file:{LAD_FILE}?mode=ro", uri=True) as con:
        table = con.execute("select table_name from gpkg_contents").fetchone()[0]
        lad = pd.read_sql(f'select LAD25CD as code, LAD25NM as name from "{table}"', con)
    return lad[lad.code.str.startswith("E")].reset_index(drop=True)


def load_england():
    """PS1 and PS2 joined on code x quarter, with short variable names (rule 7)."""
    files = {"PS1": read_mhclg(PS1_FILE), "PS2": read_mhclg(PS2_FILE)}
    keys = ["LPACD", "Quarter"]
    parts = {}
    for src, df in files.items():
        cols = {mhclg: short for short, (s, mhclg) in VARIABLES.items() if s == src}
        part = df[keys + ["LPANM"] + list(cols)].rename(columns=cols)
        for v in cols.values():
            part[v] = pd.to_numeric(part[v], errors="coerce")
        parts[src] = part

    both = parts["PS2"].merge(parts["PS1"].drop(columns="LPANM"), on=keys, how="outer", indicator=True)
    one_sided = both[both._merge != "both"][keys + ["_merge"]]
    print(f"  PS1/PS2 rows in one file only: {len(one_sided)}"
          + (f"\n{one_sided.to_string()}" if len(one_sided) else ""))
    return both.drop(columns="_merge")


# ---------------------------------------------------------------------------
# Checks on the raw codes
# ---------------------------------------------------------------------------

def check_codes(raw, councils):
    # E2: every code is a known kind of authority
    known = set(councils.code) | set(TO_2025)
    other = raw.loc[~raw.LPACD.isin(known) & ~raw.LPACD.str[:3].isin(["E26", "E51"]), ["LPACD", "LPANM"]]
    assert other.empty, f"E2 failed: {other.drop_duplicates().to_dict('records')}"
    assert raw.LPACD.str.startswith("E26").groupby(raw.LPACD).any().sum() == 10, "expected 10 parks"

    # E3: predecessors stop the quarter before the successor starts, and never overlap
    q = pd.PeriodIndex(raw.Quarter.str.replace(" ", ""), freq="Q")
    span = pd.DataFrame({"code": raw.LPACD, "q": q}).groupby("code").q.agg(["min", "max"])
    for new, olds in MERGERS.items():
        succ_start = span.loc[new, "min"]
        for old in olds:
            end = span.loc[old, "max"]
            # Taunton Deane and West Somerset handed over to Somerset West and Taunton in
            # 2019, which itself became part of Somerset in 2023
            ok = end + 1 == succ_start or (old in ("E07000190", "E07000191")
                                           and end + 1 == span.loc["E07000246", "min"])
            assert ok, f"E3 failed: {old} ends {end}, successor {new} starts {succ_start}"


# ---------------------------------------------------------------------------
# Aggregation to 2025 units
# ---------------------------------------------------------------------------

def aggregate(raw):
    p = raw[~raw.LPACD.str.startswith("E51")].copy()  # rule 5
    p["code"] = p.LPACD.map(TO_2025).fillna(p.LPACD)

    groups = p.groupby(["code", "Quarter"])
    loose = groups[VARS].sum(min_count=1)             # partial sums allowed (pilot rule)
    complete = groups[VARS].count().eq(groups.size(), axis=0)
    strict = loose.where(complete)                    # rule 6: missing if any predecessor missing
    strict["n_predecessors"] = groups.LPACD.nunique()

    # E5: totals are conserved by the aggregation (checked on the loose sums)
    raw_tot = p.groupby("Quarter")[VARS].sum()
    agg_tot = loose.groupby(level="Quarter").sum()
    assert (raw_tot - agg_tot).abs().max().max() < 1e-9, "E5 failed: totals not conserved"

    partial = (loose.notna() & ~complete)
    return strict.reset_index(), loose.reset_index(), partial


def build_units(raw, councils):
    parks = (raw[raw.LPACD.str.startswith("E26")].sort_values("Quarter")
             .groupby("LPACD").LPANM.last().reset_index()
             .rename(columns={"LPACD": "code", "LPANM": "name"}))
    units = pd.concat([councils.assign(type="council"), parks.assign(type="national park")],
                      ignore_index=True)
    dc = raw[raw.LPACD.str.startswith("E51")].groupby("LPACD").agg(
        name=("LPANM", "last"), first=("Quarter", "min"), last=("Quarter", "max"))
    units["dc_note"] = units.code.map(
        lambda c: (f"part of area under {dc.loc[DC_HOSTS[c], 'name']} "
                   f"{dc.loc[DC_HOSTS[c], 'first']} to {dc.loc[DC_HOSTS[c], 'last']}")
        if c in DC_HOSTS else None)
    return units


# ---------------------------------------------------------------------------
# Checks on the output, report, comparison with the pilot
# ---------------------------------------------------------------------------

def check_panel(panel, units):
    # E4: balanced, 306 units x 46 quarters
    n_q = len(pd.period_range(FIRST_QUARTER.replace(" ", ""), LAST_QUARTER.replace(" ", ""), freq="Q"))
    assert len(units) == 306 and panel.code.nunique() == 306, f"E4 failed: {panel.code.nunique()} units"
    assert set(panel.code) == set(units.code), "E4 failed: panel and unit list differ"
    assert len(panel) == 306 * n_q and panel.Quarter.nunique() == n_q, "E4 failed: not balanced"

    # E6: logical bounds
    assert (panel[VARS].fillna(0) >= 0).all().all(), "E6 failed: negative counts"
    for g, d in [("grant_major", "dec_major"), ("grant_minor", "dec_minor"),
                 ("grant_hh", "dec_hh"), ("granted_total", "decided_total")]:
        bad = panel[panel[g] > panel[d]]
        assert bad.empty, f"E6 failed: {g} > {d} in {len(bad)} rows"


def report(raw, panel, partial):
    dc = raw[raw.LPACD.str.startswith("E51")]
    print(f"  development corporation rows dropped: {len(dc)}; their share of decisions: "
          f"major {dc.dec_major.sum() / raw.dec_major.sum():.2%}, minor "
          f"{dc.dec_minor.sum() / raw.dec_minor.sum():.2%}")
    miss = panel[VARS].isna().sum()
    print(f"  missing cells: {miss[miss > 0].to_dict() or 'none'}")
    n_partial = partial.sum()
    print(f"  cells set missing by the strict rule: {n_partial[n_partial > 0].to_dict() or 'none'}")

    year = panel.Quarter.str[:4]
    rates = pd.DataFrame({k: panel.groupby(year)[f"grant_{k}"].sum() / panel.groupby(year)[f"dec_{k}"].sum()
                          for k in ["major", "minor", "hh"]})
    print("  national grant rates by year (%):")
    print((100 * rates).round(1).T.to_string())


def compare_with_old(panel, loose):
    """E7: same cells and values as the pilot (pilot used partial sums, so compare both)."""
    if not OLD_PANEL.exists():
        print("  E7: no pilot panel")
        return
    # the pilot file carries both code2025 and a lookup 'code'; keep code2025
    old = pd.read_csv(OLD_PANEL).drop(columns="code").rename(columns={"code2025": "code"})
    old = old.rename(columns={mhclg: short for short, (_, mhclg) in VARIABLES.items()})
    keys = ["code", "Quarter"]
    cells_new, cells_old = set(map(tuple, panel[keys].values)), set(map(tuple, old[keys].values))
    print(f"  E7 vs pilot: {len(old)} pilot rows; cells only in new: {len(cells_new - cells_old)}, "
          f"only in pilot: {len(cells_old - cells_new)}")
    for label, new in [("strict (main)", panel), ("partial sums (pilot rule)", loose)]:
        m = new.merge(old, on=keys, suffixes=("", "_old"), validate="one_to_one")
        diffs = {}
        for v in VARS:
            same = (m[v] - m[f"{v}_old"]).abs().lt(1e-9) | (m[v].isna() & m[f"{v}_old"].isna())
            if (~same).any():
                diffs[v] = int((~same).sum())
        print(f"    {label}: variables with differing cells: {diffs or 'none'}")


# ---------------------------------------------------------------------------
# Wales (DMQS)
# ---------------------------------------------------------------------------

def fy_to_calendar(year, quarter):
    """Financial-year quarter -> calendar quarter (rule 2).
    ('2016-17', 'Q1') -> '2016 Q2' (Apr-Jun 2016); ('2015-16', 'Q4') -> '2016 Q1'."""
    first_year, q = int(year[:4]), int(quarter[1])
    if q == 4:
        return f"{first_year + 1} Q1"
    return f"{first_year} Q{q + 1}"


def release_order(path):
    """'dmqs_2023_july-september.ods' -> 20233, so releases sort in publication order."""
    year, months = path.stem.split("_", 2)[1:]
    return int(year) * 10 + RELEASE_MONTHS[months]


def load_wales():
    files = sorted(WALES_DIR.glob("dmqs_*.ods"), key=release_order)
    assert len(files) == 36, f"W1 failed: {len(files)} releases"
    parts = []
    for f in files:
        d = pd.read_excel(f, sheet_name="Data", engine="odf")
        is_data = (d.Year.astype(str).str.fullmatch(r"\d{4}-\d{2}")
                   & d.Quarter.astype(str).str.fullmatch(r"Q[1-4]"))      # rule 1
        d = d[is_data]
        missing = [v for v in WALES_VARS if v not in d.columns]
        assert len(d) == 125 and not missing, f"W1 failed: {f.name} rows {len(d)}, missing {missing}"
        d = d[["Authority", "Year", "Quarter"] + WALES_VARS].copy()
        d["release"] = release_order(f)
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


def welsh_council_codes():
    with sqlite3.connect(f"file:{LAD_FILE}?mode=ro", uri=True) as con:
        table = con.execute("select table_name from gpkg_contents").fetchone()[0]
        lad = pd.read_sql(f'select LAD25CD as code, LAD25NM as name from "{table}"', con)
    return lad[lad.code.str.startswith("W")]


def build_wales():
    long = load_wales()
    long["Quarter"] = [fy_to_calendar(y, q) for y, q in zip(long.Year, long.Quarter)]
    for v in WALES_VARS:
        long[v] = pd.to_numeric(long[v], errors="coerce")

    # cells revised between releases (reported)
    n_values = long.groupby(["Authority", "Quarter"])[WALES_VARS].nunique()
    revised = (n_values > 1).sum()

    # rule 3: latest release wins
    panel = (long.sort_values("release").drop_duplicates(["Authority", "Quarter"], keep="last")
             .drop(columns="Year").sort_values(["Authority", "Quarter"]).reset_index(drop=True))
    panel = panel[panel.Quarter.between(WALES_FIRST, WALES_LAST)]

    # rule 5: council codes by name
    panel["type"] = panel.Authority.str.endswith("NPA").map({True: "national park", False: "council"})
    panel["name"] = panel.Authority.str.replace(r"\s+(CBC|CC|NPA)$", "", regex=True)
    codes = welsh_council_codes()
    panel = panel.merge(codes, on="name", how="left", validate="many_to_one")
    councils = panel[panel.type == "council"]
    assert councils.code.notna().all() and councils.name.nunique() == 22 == codes.code.nunique(), \
        f"W5 failed: unmatched {sorted(councils.loc[councils.code.isna(), 'name'].unique())}"

    check_wales(panel)
    report_wales(panel, revised)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT_DIR / "panel_wales_lpa_quarter.csv", index=False)
    print(f"  wrote {len(panel)} rows: {panel.Authority.nunique()} authorities x "
          f"{panel.Quarter.nunique()} quarters")
    compare_wales(panel)
    return panel


def check_wales(panel):
    n_q = len(pd.period_range(WALES_FIRST.replace(" ", ""), WALES_LAST.replace(" ", ""), freq="Q"))
    assert panel.Authority.nunique() == 25 and panel.Quarter.nunique() == n_q == 41, "W2 failed"
    assert len(panel) == 25 * n_q, "W2 failed: not balanced"
    assert (panel[WALES_VARS].fillna(0) >= 0).all().all(), "W4 failed: negative counts"
    for kind in ["MajDw", "MinDw", "MinHou"]:
        bad = panel[panel[f"Appd{kind}"] > panel[f"Dtrm{kind}"]]
        assert bad.empty, f"W4 failed: granted > decided for {kind} in {len(bad)} rows"


def report_wales(panel, revised):
    print(f"  cells revised between releases: {revised[revised > 0].to_dict() or 'none'}")
    miss = panel[WALES_VARS].isna().sum()
    print(f"  missing cells: {miss[miss > 0].to_dict() or 'none'}")
    for kind in ["MajDw", "MinDw"]:
        gap = panel[f"Dtrm{kind}"] - panel[f"Appd{kind}"] - panel[f"Refd{kind}"]
        print(f"  {kind}: decided != granted + refused in {int((gap != 0).sum())} rows")
    year = panel.Quarter.str[:4]
    rates = pd.DataFrame({k: panel.groupby(year)[f"Appd{k}"].sum() / panel.groupby(year)[f"Dtrm{k}"].sum()
                          for k in ["MajDw", "MinDw", "MinHou"]})
    print("  Welsh grant rates by year (%):")
    print((100 * rates).round(1).T.to_string())


def compare_wales(panel):
    """W6: same cells and values as the pilot file."""
    if not OLD_WALES.exists():
        print("  W6: no pilot file")
        return
    old = pd.read_csv(OLD_WALES).rename(columns={"Quarter_cal": "Quarter"})
    # the pilot kept the DMQS '-' marker as text; this build reads it as missing
    for v in WALES_VARS:
        text = pd.to_numeric(old[v], errors="coerce").isna() & old[v].notna()
        if text.any():
            print(f"  pilot {v}: text values read as missing: {old.loc[text, v].value_counts().to_dict()}")
        old[v] = pd.to_numeric(old[v], errors="coerce")
    keys = ["Authority", "Quarter"]
    m = panel.merge(old, on=keys, suffixes=("", "_old"), how="outer", indicator=True)
    print(f"  W6 vs pilot: {len(old)} pilot rows; only in new {int((m._merge == 'left_only').sum())}, "
          f"only in pilot {int((m._merge == 'right_only').sum())}")
    m = m[m._merge == "both"]
    diffs = {}
    for v in WALES_VARS:
        same = (m[v] - m[f"{v}_old"]).abs().lt(1e-9) | (m[v].isna() & m[f"{v}_old"].isna())
        if (~same).any():
            diffs[v] = int((~same).sum())
    same_release = (m.release == m.release_old).all()
    print(f"    variables with differing cells: {diffs or 'none'}; same source release: {same_release}")


def main():
    print("\nEngland")
    raw = load_england()
    councils = english_councils_2025()
    check_codes(raw, councils)
    panel, loose, partial = aggregate(raw)
    units = build_units(raw, councils)
    panel = panel.merge(units[["code", "name", "type"]], on="code", how="left", validate="many_to_one")
    check_panel(panel, units)
    report(raw, panel, partial)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT_DIR / "panel_england_lpa2025_quarter.csv", index=False)
    units.to_csv(OUT_DIR / "units_england_lpa2025.csv", index=False)
    print(f"  wrote {len(panel)} rows: {panel.code.nunique()} units x {panel.Quarter.nunique()} quarters")
    compare_with_old(panel, loose)

    print("\nWales")
    build_wales()


if __name__ == "__main__":
    main()
