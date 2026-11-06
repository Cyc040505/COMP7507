"""Build/audit official BACI bilateral allocations and regional tables, without network."""

from pathlib import Path
import sys, argparse, json, hashlib
import duckdb, pandas as pd, numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.analytics.time_change import aggregate_regions

p = argparse.ArgumentParser()
p.add_argument("--source-root", type=Path, required=True)
a = p.parse_args()
out = ROOT / "data/processed"
out.mkdir(exist_ok=True, parents=True)
cc = pd.read_csv(a.source_root / "BACI/country_codes_V202601.csv")
g = pd.read_excel(a.source_root / "GEODIST/geo_cepii.xls").drop_duplicates("iso3")
mapping = g.set_index("iso3").continent
meta = pd.read_parquet(out / "country_meta.parquet")
meta["region"] = (
    meta.iso3.map(mapping)
    .replace({"Pacific": "Oceania", "No": "Unknown"})
    .fillna("Unknown")
)
meta.to_parquet(out / "country_meta.parquet", index=False)
expected = pd.read_parquet(out / "exporter_hs2_year.parquet")
con = duckdb.connect()
con.execute("SET threads=4")
con.register("cc", cc)
checks = []
regions = []
pair_parts = []
sources = []
import pyarrow as pa, pyarrow.parquet as pq

writer = None
for year in range(1995, 2025):
    raw = a.source_root / f"BACI/BACI_HS92_Y{year}_V202601.csv"
    d = con.execute(
        "SELECT t AS year,a.country_iso3 exporter,b.country_iso3 importer,substr(lpad(cast(k as varchar),6,'0'),1,2) hs2,sum(v) value FROM read_csv_auto(?) r LEFT JOIN cc a ON r.i=a.country_code LEFT JOIN cc b ON r.j=b.country_code GROUP BY 1,2,3,4",
        [str(raw)],
    ).df()
    assert not d.isna().any().any()
    assert not d.duplicated(["year", "exporter", "importer", "hs2"]).any()
    product = d.groupby(["year", "exporter", "hs2"], as_index=False).value.sum()
    z = product.merge(
        expected[expected.year.eq(year)],
        on=["year", "exporter", "hs2"],
        how="outer",
        indicator=True,
        suffixes=("_raw", "_stored"),
    )
    assert z["_merge"].eq("both").all()
    np.testing.assert_allclose(z.value_raw, z.value_stored, rtol=2e-10, atol=1e-7)
    # Also compare every bilateral allocation against the shared aggregate source.
    old = a.source_root / "processed/country_pair_hs2_year.parquet"
    if old.exists():
        stored = con.execute(
            "SELECT * FROM read_parquet(?) WHERE year=?", [str(old), year]
        ).df()
        b = d.merge(
            stored,
            on=["year", "exporter", "importer", "hs2"],
            how="outer",
            indicator=True,
            suffixes=("_raw", "_stored"),
        )
        assert b["_merge"].eq("both").all()
        np.testing.assert_allclose(b.value_raw, b.value_stored, rtol=2e-10, atol=1e-7)
    table = pa.Table.from_pandas(d, preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(
            out / "country_pair_hs2_year.parquet", table.schema, compression="zstd"
        )
    writer.write_table(table)
    regions.append(aggregate_regions(d, meta))
    pair_parts.append(
        d.groupby(["year", "exporter", "importer"], as_index=False).value.sum()
    )
    checks.append(
        {"year": year, "bilateral_product_rows": len(d), "product_keys": len(z)}
    )
    sources.append(
        {"file": raw.name, "sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}
    )
    print(year, "verified", len(d), flush=True)
writer.close()
pd.concat(regions, ignore_index=True).to_parquet(
    out / "m5_region_hs2_year.parquet", index=False
)
pd.concat(pair_parts, ignore_index=True).to_parquet(
    out / "country_pair_year.parquet", index=False
)
sha = lambda f: hashlib.sha256((out / f).read_bytes()).hexdigest()
con.execute(
    "COPY (SELECT * FROM read_parquet(?) WHERE exporter IN ('USA','DEU','CHN','MEX','NLD','ITA') OR importer IN ('USA','DEU','CHN','MEX','NLD','ITA')) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
    [
        str(out / "country_pair_hs2_year.parquet"),
        str(out / "country_pair_hs2_focus_year.parquet"),
    ],
)
manifest = {
    "source_version": "BACI HS92 V202601",
    "source_type": "Official local annual CSVs; all bilateral HS2 allocations independently reaggregated",
    "years": [1995, 2024],
    "unit": "thousand current USD",
    "region_definition": "GEODIST continents; Pacific→Oceania; unknown retained",
    "checks": checks,
    "files": sources,
    "project_inputs_sha256": {
        f: sha(f)
        for f in [
            "exporter_hs2_year.parquet",
            "country_meta.parquet",
            "country_year.parquet",
            "flow_year.parquet",
        ]
    },
    "output_sha256": sha("m5_region_hs2_year.parquet"),
}
manifest["bilateral_inputs_sha256"] = {
    f: sha(f)
    for f in ["country_pair_year.parquet", "country_pair_hs2_focus_year.parquet"]
}
manifest["focus_scope"] = (
    "Complete worldwide inbound and outbound HS2 flows for USA DEU CHN MEX NLD ITA; no Top-N filter."
)
(out / "m5_source_manifest.json").write_text(json.dumps(manifest, indent=2))
print("Official source audit complete")
