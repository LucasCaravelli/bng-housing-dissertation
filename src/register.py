"""Clean one pull of Natural England's Biodiversity Gain Site Register.

Run from the Pipeline folder:
    python3 src/register.py 2026-11-06_BNG_Register
    python3 src/register.py BNG_Register_snapshot_2026-10-12

Inputs (read-only) in RAW_ROOT/RawData-BNG/<pull folder>:
    bng_sites_raw.json                 paginated /bng/api/all download
    bng_sites_by_reference.json        sites fetched one by one from /bng/api/search/<ref>
    bng_site_<ref>_from_browser.json   /search/<ref> responses copied from the browser
    download_meta.json                 record count reported by the API
Only the first is required; the others exist for the 6 Nov 2026 pull.

Outputs in PROCESSED_DIR/bng:
    register_sites_<date>.csv          one row per gain site
    register_allocations_<date>.csv    one row per development allocated to a site

Decision rules and checks are pre-specified in notes/register.md.
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

# config.py sits one folder up from src/; add it to the import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

REGISTER_DIR = config.RAW_ROOT / "RawData-BNG"
OUT_DIR = config.PROCESSED_DIR / "bng"
OLD_DIR = config.RAW_ROOT / "ProcessedData" / "bng"  # pilot outputs, for check C7

SOURCE_API = "api_all"
SOURCE_BYREF = "api_search_by_ref"
SOURCE_BROWSER = "browser_copy"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def pull_date(folder):
    """Pull date from the folder name, e.g. '2026-11-06_BNG_Register' -> '2026-11-06'."""
    match = re.search(r"\d{4}-\d{2}-\d{2}", Path(folder).name)
    if not match:
        raise ValueError(f"No date in folder name: {folder}")
    return match.group(0)


def base_reference(ref):
    """'BGS-140125001 - 05/11/2026 14:33 ' -> 'BGS-140125001'."""
    return str(ref).split(" - ")[0].strip()


def reference_date(ref):
    """Date encoded in BGS-DDMMYY###: the day the registration application was submitted."""
    return pd.to_datetime(base_reference(ref)[4:10], format="%d%m%y")


def empty(x):
    return x is None or (isinstance(x, str) and x.strip() in ("", "None"))


def iso_date(x):
    """API timestamp -> 'YYYY-MM-DD', or None if empty."""
    return None if empty(x) else pd.to_datetime(x).date().isoformat()


# ---------------------------------------------------------------------------
# OS grid reference -> British National Grid
# ---------------------------------------------------------------------------
# The first letter picks a 500 km square, the second a 100 km square inside it.
# Both use a 5 x 5 letter grid (A-Z without I), read row by row from the north-west.
# Offsets below are in units of 100 km.

FIRST_LETTER = {"S": (0, 0), "T": (5, 0), "N": (0, 5), "O": (5, 5), "H": (0, 10), "J": (5, 10)}
GRID_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def second_letter_offset(letter):
    position = GRID_LETTERS.index(letter)
    row, col = divmod(position, 5)  # row 0 is the northern row
    return col, 4 - row


def gridref_to_bng(gridref):
    """'SU378910' -> (437850.0, 191050.0, 6): easting and northing of the square's centre,
    plus the number of digits. Returns (None, None, 0) if the reference is empty."""
    if empty(gridref):
        return None, None, 0
    gr = gridref.replace(" ", "").upper()
    letters, digits = gr[:2], gr[2:]
    if letters[0] not in FIRST_LETTER or letters[1] not in GRID_LETTERS:
        raise ValueError(f"Bad grid letters: {gridref!r}")
    # letters alone are allowed (centre of the 100 km square; gr_digits = 0 flags it)
    if (digits and not digits.isdigit()) or len(digits) % 2 or len(digits) > 10:
        raise ValueError(f"Bad grid digits: {gridref!r}")

    e500, n500 = FIRST_LETTER[letters[0]]
    e100, n100 = second_letter_offset(letters[1])
    half = len(digits) // 2
    square = 10 ** (5 - half)  # side of the square the reference describes, in metres
    east_in = int(digits[:half]) * square if half else 0
    north_in = int(digits[half:]) * square if half else 0
    easting = (e500 + e100) * 100_000 + east_in + square / 2
    northing = (n500 + n100) * 100_000 + north_in + square / 2
    return easting, northing, len(digits)


# ---------------------------------------------------------------------------
# Records -> rows
# ---------------------------------------------------------------------------

def to_all_layout(rec):
    """/search/<ref> uses a different layout from /all: baseline habitats in `habitats`
    (a dict), created/enhanced ones in `improvements` (a dict), responsible bodies as plain
    strings, and no status. Convert to the /all layout; infer status (decision rule 4)."""
    rec = dict(rec)
    habitats = []
    for key in ("habitats", "improvements"):
        value = rec.pop(key, None)
        if isinstance(value, dict):
            habitats.append(value)
        elif isinstance(value, list):
            habitats.extend(value)
    rec["habitats"] = habitats
    rec["responsibleBodies"] = [b if isinstance(b, dict) else {"body": b}
                                for b in rec.get("responsibleBodies") or []]
    if "gainSiteStatus" in rec:
        raise ValueError(f"{rec['referenceNumber']}: /search record already has a status")
    rec["gainSiteStatus"] = "Registered" if empty(rec.get("removalDate")) else "Internally Removed"
    rec["_status_inferred"] = True
    return rec


def habitat_area(rec, habitat_type):
    """Total hectares of area habitat of one type ('Baseline' or 'CreatedOrEnhanced').
    Hedgerows and watercourses are linear and not included."""
    total = 0.0
    for block in rec.get("habitats") or []:
        if block.get("type") != habitat_type:
            continue
        for area in block.get("areas") or []:
            if area.get("unit") != "Hectares":  # check C8
                raise ValueError(f"{rec['referenceNumber']}: area unit {area.get('unit')!r}")
            total += area.get("size") or 0
    return round(total, 4)


def site_row(rec, source):
    easting, northing, digits = gridref_to_bng(rec.get("gridReference"))
    allocations = rec.get("allocations") or []
    lpas = sorted({a["localPlanningAuthority"] for a in allocations if a.get("localPlanningAuthority")})
    amend_dates = [a["amendmentDate"] for a in rec.get("amendments") or [] if a.get("amendmentDate")]
    return {
        "base_ref": base_reference(rec["referenceNumber"]),
        "reference": rec["referenceNumber"].strip(),
        "ref_date": reference_date(rec["referenceNumber"]).date().isoformat(),
        "works_start": iso_date(rec.get("startDate")),
        "end_date": iso_date(rec.get("endDate")),
        "removal_date": iso_date(rec.get("removalDate")),
        "status": rec.get("gainSiteStatus"),
        "status_inferred": rec.get("_status_inferred", False),
        "site_ha": pd.to_numeric(rec.get("siteSize"), errors="coerce"),
        "gridref": rec.get("gridReference"),
        "gr_digits": digits,
        "easting": easting,
        "northing": northing,
        "n_alloc": len(allocations),
        "alloc_lpas": "; ".join(lpas) if lpas else None,
        "created_ha": habitat_area(rec, "CreatedOrEnhanced"),
        "baseline_ha": habitat_area(rec, "Baseline"),
        "n_amend": len(rec.get("amendments") or []),
        "last_amendment": iso_date(max(amend_dates)) if amend_dates else None,
        "extract_date": iso_date(rec.get("extractDate")),
        "source": source,
    }


def allocation_rows(rec):
    keep = ["developerReference", "localPlanningAuthority", "planningReference", "projectName",
            "areaUnits", "hedgerowUnits", "watercoursesUnits"]
    return [{"base_ref": base_reference(rec["referenceNumber"]), **{k: a.get(k) for k in keep}}
            for a in rec.get("allocations") or []]


# ---------------------------------------------------------------------------
# One pull
# ---------------------------------------------------------------------------

def drop_duplicate_versions(records):
    """Decision rule 2: if a site appears twice in the paginated file, keep the version
    without the timestamp suffix, after checking the two agree (check C3)."""
    by_base = {}
    for rec in records:
        by_base.setdefault(base_reference(rec["referenceNumber"]), []).append(rec)

    kept, dropped = [], []
    for base, versions in by_base.items():
        if len(versions) == 1:
            kept.append(versions[0])
            continue
        for field in ("siteSize", "gridReference", "gainSiteStatus"):
            values = {str(v.get(field)) for v in versions}
            if len(values) > 1:
                raise ValueError(f"C3 failed: {base} versions disagree on {field}: {values}")
        plain = [v for v in versions if " - " not in v["referenceNumber"]]
        if len(plain) != 1:
            raise ValueError(f"{base}: expected one untimestamped version, found {len(plain)}")
        kept.append(plain[0])
        dropped += [v["referenceNumber"] for v in versions if v is not plain[0]]
    return kept, dropped


def load_pull(folder):
    """Read every source in a pull folder. Returns {source: [records]} and the API metadata."""
    raw = json.loads((folder / "bng_sites_raw.json").read_text())
    sources = {SOURCE_API: raw}

    byref_path = folder / "bng_sites_by_reference.json"
    sources[SOURCE_BYREF] = json.loads(byref_path.read_text()) if byref_path.exists() else []
    sources[SOURCE_BROWSER] = [json.loads(p.read_text())
                               for p in sorted(folder.glob("bng_site_*_from_browser.json"))]

    meta_path = folder / "download_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return sources, meta


def build(folder):
    folder = REGISTER_DIR / folder
    date = pull_date(folder)
    sources, meta = load_pull(folder)
    n_records = {s: len(r) for s, r in sources.items()}

    # C1: everything the API counted is accounted for
    if "api_total_count" in meta:
        accounted = sum(n_records.values())
        if accounted != meta["api_total_count"]:
            raise ValueError(f"C1 failed: {accounted} records in folder, API counted "
                             f"{meta['api_total_count']}. Decide how to fill the gap (rule 5).")

    api_records, dropped = drop_duplicate_versions(sources[SOURCE_API])
    records = [(r, SOURCE_API) for r in api_records]
    records += [(to_all_layout(r), SOURCE_BYREF) for r in sources[SOURCE_BYREF]]
    records += [(to_all_layout(r), SOURCE_BROWSER) for r in sources[SOURCE_BROWSER]]

    # C4: no site in more than one source (precedence would hide a conflict)
    seen = {}
    for rec, source in records:
        base = base_reference(rec["referenceNumber"])
        if base in seen:
            raise ValueError(f"C4 failed: {base} in both {seen[base]} and {source}")
        seen[base] = source

    sites = pd.DataFrame([site_row(r, s) for r, s in records]).sort_values("base_ref")
    allocations = pd.DataFrame([row for r, _ in records for row in allocation_rows(r)])
    sites = sites.reset_index(drop=True)

    run_checks(sites, allocations)
    report(sites, allocations, n_records, dropped, date)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sites.to_csv(OUT_DIR / f"register_sites_{date}.csv", index=False)
    allocations.to_csv(OUT_DIR / f"register_allocations_{date}.csv", index=False)
    compare_with_old(sites, date)
    return sites, allocations


# ---------------------------------------------------------------------------
# Checks and comparison with the pilot file
# ---------------------------------------------------------------------------

def run_checks(sites, allocations):
    # C5: reference format (dates already parsed in site_row, which raises if bad)
    bad = sites.loc[~sites.base_ref.str.fullmatch(r"BGS-\d{9}"), "base_ref"]
    assert bad.empty, f"C5 failed: {bad.tolist()}"
    assert sites.base_ref.is_unique

    # C6: located points fall in the English part of the GB grid
    located = sites.dropna(subset=["easting"])
    outside = located[~located.easting.between(80_000, 660_000) | ~located.northing.between(0, 660_000)]
    assert outside.empty, f"C6 failed: {outside[['base_ref', 'gridref']].to_dict('records')}"

    # C8: allocation table matches the per-site counts
    assert len(allocations) == sites.n_alloc.sum(), "C8 failed: allocation rows != sum of n_alloc"


def report(sites, allocations, n_records, dropped, date):
    print(f"\nPull {date}")
    print(f"  records per source: {n_records}")
    print(f"  duplicate versions dropped: {dropped}")
    print(f"  unique sites: {len(sites)}  by source: {sites.source.value_counts().to_dict()}")
    print(f"  status: {sites.status.value_counts().to_dict()}  "
          f"(inferred for {int(sites.status_inferred.sum())})")
    no_grid = sites.loc[sites.easting.isna(), ["base_ref", "status"]].to_dict("records")
    print(f"  no grid reference: {no_grid}")
    print(f"  grid digits: {sites.gr_digits.value_counts().sort_index().to_dict()}")
    print(f"  ref_date range: {sites.ref_date.min()} to {sites.ref_date.max()}")
    gap = (pd.to_datetime(sites.ref_date) - pd.to_datetime(sites.works_start)).dt.days
    print(f"  works start -> registration, days: n={gap.notna().sum()}, "
          f"median={gap.median():.0f}, IQR={gap.quantile(.25):.0f} to {gap.quantile(.75):.0f}, "
          f"negative={int((gap < 0).sum())}")
    print(f"  allocations: {len(allocations)} rows on {int((sites.n_alloc > 0).sum())} sites; "
          f"missing planning reference: {int(allocations.planningReference.map(empty).sum())}")


def compare_with_old(sites, date):
    """C7: compare with the pilot output for the same pull."""
    old_path = OLD_DIR / f"bng_sites_clean_{date}.csv"
    if not old_path.exists():
        print(f"  C7: no pilot file {old_path.name}")
        return
    old = pd.read_csv(old_path).rename(columns={
        "ref_date_ddmmyy": "ref_date", "works_start_date": "works_start",
        "size": "site_ha", "created_area": "created_ha"})
    new_set, old_set = set(sites.base_ref), set(old.base_ref)
    print(f"  C7 vs {old_path.name}: {len(old)} pilot rows; "
          f"only in new {sorted(new_set - old_set)}; only in pilot {sorted(old_set - new_set)}")

    both = sites.merge(old, on="base_ref", suffixes=("", "_old"), validate="one_to_one")
    for col in ["reference", "ref_date", "works_start", "status", "site_ha",
                "easting", "northing", "gr_digits", "n_alloc", "created_ha"]:
        new_v, old_v = both[col], both[f"{col}_old" if col != "reference" else "ref"]
        if col == "reference":
            new_v, old_v = new_v.str.strip(), old_v.astype(str).str.strip()
        if pd.api.types.is_numeric_dtype(new_v) and pd.api.types.is_numeric_dtype(old_v):
            same = (new_v - old_v).abs().lt(1e-6) | (new_v.isna() & old_v.isna())
        else:
            same = (new_v.astype(str) == old_v.astype(str)) | (new_v.isna() & old_v.isna())
        diff = both.loc[~same, "base_ref"].tolist()
        print(f"    {col:12s} differs on {len(diff)} sites" + (f": {diff[:10]}" if diff else ""))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "2026-11-06_BNG_Register")
