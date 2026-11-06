"""Independent raw-source examples for every main view; does not import UI code."""

import argparse, json
from pathlib import Path
import duckdb, pandas as pd

p = argparse.ArgumentParser()
p.add_argument("--source-root", type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
con = duckdb.connect()
con.execute("SET threads=4")
cc = pd.read_csv(a.source_root / "BACI/country_codes_V202601.csv")
con.register("cc", cc)
report = {}
annual = {}
for y in [2010, 2019, 2023, 2024]:
    path = a.source_root / f"BACI/BACI_HS92_Y{y}_V202601.csv"
    frame = con.execute(
        "SELECT a.country_iso3 exporter,b.country_iso3 importer,substr(lpad(cast(k as varchar),6,'0'),1,2) hs2,sum(v) value FROM read_csv_auto(?) r JOIN cc a ON r.i=a.country_code JOIN cc b ON r.j=b.country_code GROUP BY 1,2,3",
        [str(path)],
    ).df()
    annual[y] = frame
    report[str(y)] = {"world_thousand_USD": float(frame.value.sum())}
    c = frame.groupby("exporter").value.sum().sort_values(ascending=False)
    report[str(y)]["top10"] = dict(c.head(10))
    for code in ["CHN", "MEX"]:
        for hs in ["85", "95", "87"]:
            v = frame.loc[frame.exporter.eq(code) & frame.hs2.eq(hs), "value"].sum()
            share = v / c[code]
            worldshare = frame.loc[frame.hs2.eq(hs), "value"].sum() / frame.value.sum()
            report[str(y)][code + "_" + hs] = {
                "value": float(v),
                "share": float(share),
                "rca": float(share / worldshare),
            }
    print(y, "raw examples recalculated", flush=True)
d = annual[2023]
exports = d[d.exporter.eq("CHN")].groupby("importer").value.sum()
distance = pd.read_excel(a.source_root / "GEODIST/dist_cepii.xls")
km = float(
    distance.loc[distance.iso_o.eq("CHN") & distance.iso_d.eq("USA"), "dist"].iloc[0]
)
report["M1_CHN_USA_2023"] = {
    "distance_km": km,
    "share": float(exports["USA"] / exports.sum()),
}
for direction, col, partner in [
    ("export", "exporter", "importer"),
    ("import", "importer", "exporter"),
]:
    f = (
        d[d[col].eq("CHN") & d.hs2.eq("87")]
        .groupby(partner)
        .value.sum()
        .sort_values(ascending=False)
    )
    report["M3_" + direction] = {
        "total": float(f.sum()),
        "top10_coverage": float(f.head(10).sum() / f.sum()),
        "USA": float(f["USA"]),
        "USA_share": float(f["USA"] / f.sum()),
    }
raw = pd.read_csv(a.source_root / "CHELEM/gdp_v202502.csv")
for code in ["DEU", "JPN"]:
    g = float(
        raw.loc[raw.country.eq(code) & raw.indicator.eq("GDP-VAL"), "v2023"].iloc[0]
    )
    v = d.loc[d.exporter.eq(code), "value"].sum()
    report["M2_" + code] = {
        "gdp_million_USD": g,
        "export_thousand_USD": float(v),
        "export_gdp_ratio": float(v / (g * 1000)),
    }
report["M5_CHN_HS87_2024"] = {
    "index_2019_100": report["2024"]["CHN_87"]["value"]
    / report["2019"]["CHN_87"]["value"]
    * 100,
    "share": report["2024"]["CHN_87"]["share"],
}
(root / "docs/final_example_audit.json").write_text(json.dumps(report, indent=2))
