"""T5/T6: EPC hedonic controls and a composition check for the pilot ring DiD.

Run from the Pipeline folder, after src/epc_extract.py:
    python src/gainsite_epc.py

Why (Gibbons, Mourato and Resende 2011, property-level hedonics with size and age): Price Paid
has type, tenure and new build but no floor area or age, so a price change near a gain site
could just mean bigger or older homes happened to sell there after registration.

Linkage (a simplified version of the Chi et al. 2021 rules): same postcode and agreeing
address number/name and flat number:
    numbered houses : EPC first address token = PAON (e.g. "24", "18A")
    named houses    : EPC address line 1 = PAON name
    flats           : EPC address starts "FLAT n" and contains every PAON word
For each sale, the latest certificate lodged on or before the sale date, else the earliest
after. Match rates are reported by ring and period, since a match rate that changed after
registration would itself bias the test.

2a pilot ring DiD on the matched sample, without then with floor area, rooms, age band, rating
2b outcome log price per m2;  2c composition: log floor area, share built 2012 or later.
Sale level; FE site x ring, site x quarter, type, tenure; SE clustered by site.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from gainsite_did import OUT_DIR, PILOT, WORK, load_sites  # noqa: E402

FLAT_WORDS = r"^(?:FLAT|APARTMENT|APT|UNIT|MAISONETTE)\b"


def clean(x):
    return (x.fillna("").str.upper().str.replace(r"[^A-Z0-9 ]", " ", regex=True)
            .str.replace(r"\s+", " ", regex=True).str.strip())


def load_epc(tag):
    epc = pd.read_csv(WORK / f"epc_near_sites_{tag}.csv.gz", dtype=str, keep_default_na=False)
    n0 = len(epc)
    epc["lodged"] = pd.to_datetime(epc.lodgement_date, errors="coerce")
    epc["floor_area"] = pd.to_numeric(epc.floor_area, errors="coerce")
    epc["rooms"] = pd.to_numeric(epc.rooms, errors="coerce")
    epc = epc[(epc.floor_area > 10) & (epc.floor_area < 1000) & epc.lodged.notna()].copy()
    a1 = clean(epc.address1)
    full = clean(epc.address1 + " " + epc.address2 + " " + epc.address3)
    num = a1.str.extract(r"^(\d+[A-Z]?)\b")[0]
    epc["k_num"] = np.where(num.notna() & ~a1.str.contains(FLAT_WORDS), epc.postcode + "|" + num.fillna(""), None)
    epc["k_name"] = epc.postcode + "|" + a1
    epc["flat"] = full.str.extract(r"^(?:FLAT|APARTMENT|APT|UNIT) (\w+)")[0]
    epc["full"] = full
    print(f"EPC certificates: {n0:,}; usable (floor area 10-1,000 m2, dated) {len(epc):,}")
    return epc


def link(x, epc):
    cols = ["cert_id", "lodged", "floor_area", "rooms", "age_band", "rating", "property_type"]
    x["k_num"] = np.where(x.paon.str.fullmatch(r"\d+[A-Z]?") & (x.saon == ""), x.pcds + "|" + x.paon, None)
    x["k_name"] = np.where(~x.paon.str.contains(r"\d") & (x.saon == ""), x.pcds + "|" + x.paon, None)
    x["flat"] = x.saon.str.extract(r"^(?:FLAT |APARTMENT |APT |UNIT )?(\w+)$")[0]
    m1 = x.dropna(subset=["k_num"])[["tid", "date", "k_num"]].merge(epc.dropna(subset=["k_num"])[["k_num"] + cols], on="k_num")
    m2 = x.dropna(subset=["k_name"])[["tid", "date", "k_name"]].merge(epc[["k_name"] + cols], on="k_name")
    fl = x[x.saon != ""].dropna(subset=["flat"])[["tid", "date", "pcds", "paon", "flat"]]
    e3 = epc.dropna(subset=["flat"])[["postcode", "flat", "full"] + cols].rename(columns={"postcode": "pcds"})
    m3 = fl.merge(e3, on=["pcds", "flat"])
    m3 = m3[[set(p.split()) <= set(f.split()) for p, f in zip(m3.paon, m3.full)]]
    m = pd.concat([m1.drop(columns="k_num"), m2.drop(columns="k_name"), m3[["tid", "date"] + cols]], ignore_index=True)
    m["before"] = m.lodged <= m.date
    m["gap"] = (m.date - m.lodged).dt.days.abs()
    m = m.sort_values(["tid", "before", "gap"], ascending=[True, False, True]).drop_duplicates("tid")
    x = x.merge(m[["tid"] + cols[1:]], on="tid", how="left")
    x["matched"] = x.floor_area.notna()
    return x


def main(tag="2026-10-12_rows"):
    s = load_sites(tag)
    pilot = s[s.urban_fringe & (s.cohort <= 2025)]
    epc = load_epc(tag)

    d = pd.read_parquet(WORK / "sales_resid.parquet")
    pcs = d[["pcds", "easting", "northing"]].drop_duplicates("pcds").reset_index(drop=True)
    tree = cKDTree(pcs[["easting", "northing"]].to_numpy())
    pairs = []
    for r in pilot.itertuples():
        idx = tree.query_ball_point([r.easting, r.northing], r=r.radius_m + 4000)
        xy = pcs.loc[idx, ["easting", "northing"]].to_numpy()
        de = np.clip(np.hypot(xy[:, 0] - r.easting, xy[:, 1] - r.northing) - r.radius_m, 0, None)
        pairs.append(pd.DataFrame({"ref": r.ref, "pcds": pcs.pcds.to_numpy()[idx], "d": de, "gq": r.gq}))
    pairs = pd.concat(pairs)
    x = d[d.pcds.isin(pairs.pcds.unique())].copy()
    addr = x.addr.str.split("|", expand=True)
    x["paon"], x["saon"] = clean(addr[1]), clean(addr[2])
    x = link(x, epc)

    z = x.merge(pairs, on="pcds")
    z = z[(z.d < 1000) | (z.d >= 2000)].copy()
    z["inner"] = (z.d < 1000).astype(int)
    z["e"] = z.q - z.gq
    z = z[z.e >= -20]
    z["post"] = (z.e >= 0).astype(int)
    z["ip"] = z.inner * z.post
    z["sr"], z["sq"] = z.ref + z.inner.astype(str), z.ref + "_" + z.q.astype(str)
    rate = z.drop_duplicates("tid").matched.mean()
    mm = pf.feols("matched ~ ip | sr + sq", data=z.assign(matched=z.matched.astype(int)), vcov={"CRV1": "ref"})
    print(f"match rate (sales near pilot sites): {rate:.1%} (pilot 93.9%); "
          f"change after registration within 1 km: {mm.coef()['ip']:.4f} (SE {mm.se()['ip']:.4f}; pilot -0.0070 (0.0046))")

    k = z[z.matched].copy()
    k["lfa"] = np.log(k.floor_area)
    k["lppsm"] = k.lp - k.lfa
    k["rooms_c"] = k.rooms.clip(upper=8).fillna(-1).astype(int).astype(str)
    k["new_stock"] = k.age_band.str.contains("2012|2022|2023|2024|2025|2026", regex=True).astype(int)
    for c in ["age_band", "rating"]:
        k[c] = k[c].replace("", "missing").fillna("missing")
    rows = []
    specs = [("2a-i Matched sample, pilot controls only (type, tenure, new)", "lp ~ ip + new | sr + sq + ptype + tenure"),
             ("2a-ii + log floor area, rooms, age band, energy rating",
              "lp ~ ip + new + lfa | sr + sq + ptype + tenure + rooms_c + age_band + rating"),
             ("2b Outcome: log price per m2 (+ same controls except area)",
              "lppsm ~ ip + new | sr + sq + ptype + tenure + rooms_c + age_band + rating"),
             ("2c-i Composition: log floor area of homes sold", "lfa ~ ip | sr + sq"),
             ("2c-ii Composition: share built 2012 or later", "new_stock ~ ip | sr + sq")]
    for label, fml in specs:
        mod = pf.feols(fml, data=k, vcov={"CRV1": "ref"})
        rows.append({"spec": label, "beta": float(mod.coef()["ip"]), "se": float(mod.se()["ip"]),
                     "n": mod._N, "sites": k.ref.nunique()})
    res = pd.DataFrame(rows)
    old = pd.read_csv(PILOT / "test2_epc.csv")
    m = res.merge(old, on="spec", suffixes=("", "_pilot"))
    pd.set_option("display.width", 200)
    print(m[["spec", "beta", "beta_pilot", "se", "se_pilot", "n", "n_pilot"]].round(7).to_string(index=False))
    res.to_csv(OUT_DIR / f"t5_epc_{tag}.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-10-12_rows")
