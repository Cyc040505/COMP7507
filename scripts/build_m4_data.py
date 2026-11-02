"""Rebuild only M4 inputs from official local files; never rewrite other modules' tables."""

import argparse, sys
from pathlib import Path
import duckdb, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.analytics.product import validate_trade

p = argparse.ArgumentParser()
p.add_argument("--source-root", type=Path, required=True)
p.add_argument("--output-dir", type=Path, default=ROOT / "data/processed")
a = p.parse_args()
source = a.source_root.resolve()
a.output_dir.mkdir(parents=True, exist_ok=True)
cc = pd.read_csv(source / "BACI/country_codes_V202601.csv")
con = duckdb.connect()
con.execute("SET threads=4")
con.register("codes", cc)
frames = []
for year in range(1995, 2025):
    f = source / f"BACI/BACI_HS92_Y{year}_V202601.csv"
    frames.append(
        con.execute(
            """select t AS year,country_iso3 AS exporter,substr(lpad(cast(k as varchar),6,'0'),1,2) AS hs2,sum(v) AS value from read_csv_auto(?) f left join codes c on f.i=c.country_code group by 1,2,3""",
            [str(f)],
        ).df()
    )
d = pd.concat(frames, ignore_index=True)
validate_trade(d)
d.to_parquet(a.output_dir / "exporter_hs2_year.parquet", index=False)
g = pd.read_csv(source / "CHELEM/gdp_v202502.csv")
g = g[g.indicator.isin(["GDP-VAL", "GDP-CAP", "POP"])]
years = [f"v{y}" for y in range(1995, 2025)]
g = g.melt(
    id_vars=["country", "indicator"],
    value_vars=years,
    var_name="year",
    value_name="number",
)
g["year"] = g.year.str[1:].astype(int)
g["number"] = pd.to_numeric(g.number, errors="coerce")
if g.duplicated(["year", "country", "indicator"]).any():
    raise ValueError("Duplicate CHELEM indicator keys")
g = (
    g.pivot(index=["year", "country"], columns="indicator", values="number")
    .rename(
        columns={"GDP-VAL": "gdp", "GDP-CAP": "gdp_per_capita", "POP": "population"}
    )
    .reset_index()
)
g.columns.name = None
g.to_parquet(a.output_dir / "gdp_year.parquet", index=False)
print(f"Built {len(d):,} trade rows and {len(g):,} GDP rows under {a.output_dir}")
