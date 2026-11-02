"""Optional full source audit. Run with --source-root ../data; never needed by UI."""

import argparse, json, hashlib, sys, time
from pathlib import Path
import pandas as pd, numpy as np, duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.analytics.product import validate_trade

p = argparse.ArgumentParser()
p.add_argument("--source-root", type=Path, required=True)
p.add_argument("--out", type=Path, default=ROOT / "docs/M4_source_audit.json")
args = p.parse_args()
src = args.source_root.resolve()
t = time.perf_counter()
con = duckdb.connect()
con.execute("SET threads=4")
d = pd.read_parquet(ROOT / "data/processed/exporter_hs2_year.parquet")
validate_trade(d)
cc = pd.read_csv(src / "BACI/country_codes_V202601.csv")
con.register("cc", cc)
report = {
    "source_version": "BACI HS92 V202601",
    "years": [],
    "trade_rows": len(d),
    "reference_scope": "All BACI exporters retained; absent product cells not filled.",
}
for year in range(1995, 2025):
    f = src / f"BACI/BACI_HS92_Y{year}_V202601.csv"
    q = """select t AS year, country_iso3 AS exporter, substr(lpad(cast(k as varchar),6,'0'),1,2) AS hs2,sum(v) AS value from read_csv_auto(?) r left join cc on r.i=cc.country_code group by 1,2,3"""
    a = con.execute(q, [str(f)]).df()
    b = d[d.year.eq(year)]
    z = a.merge(
        b,
        on=["year", "exporter", "hs2"],
        how="outer",
        suffixes=("_raw", "_stored"),
        indicator=True,
    )
    assert z["_merge"].eq("both").all(), f"Key mismatch {year}"
    np.testing.assert_allclose(z.value_raw, z.value_stored, rtol=2e-10, atol=1e-7)
    report["years"].append(
        {
            "year": year,
            "keys": len(z),
            "max_relative_error": float(
                (
                    (z.value_raw - z.value_stored).abs()
                    / z.value_raw.where(z.value_raw.ne(0))
                ).max()
            ),
        }
    )
    print(f"{year}: {len(z)} product keys verified", flush=True)
g = pd.read_parquet(ROOT / "data/processed/gdp_year.parquet")
raw = pd.read_csv(src / "CHELEM/gdp_v202502.csv")
raw = raw[raw.indicator.eq("GDP-CAP")]
raw = raw.melt(
    id_vars=["country", "indicator"],
    value_vars=[f"v{y}" for y in range(1995, 2025)],
    var_name="year",
    value_name="raw",
)
raw["year"] = raw.year.str[1:].astype(int)
z = raw.merge(
    g[["year", "country", "gdp_per_capita"]],
    on=["year", "country"],
    how="left",
    validate="one_to_one",
)
a = pd.to_numeric(z.raw, errors="coerce")
b = pd.to_numeric(z.gdp_per_capita, errors="coerce")
np.testing.assert_allclose(a, b, equal_nan=True, rtol=1e-12)
report["gdp_cap_matched_rows"] = len(z)
report["seconds"] = round(time.perf_counter() - t, 2)
report["files"] = {
    n: hashlib.sha256((ROOT / "data/processed" / n).read_bytes()).hexdigest()
    for n in ["exporter_hs2_year.parquet", "gdp_year.parquet"]
}
args.out.write_text(json.dumps(report, indent=2))
print("Audit passed:", args.out)
