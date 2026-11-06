"""Reconcile a BACI HS92 V202601 redistribution and build only M5 inputs.

The original CEPII download was unavailable. This does not claim a fresh audit of
official CSVs or an independent validation of bilateral allocations.
"""

import argparse
from pathlib import Path
import sys, json, hashlib, urllib.request, datetime
import pandas as pd
import numpy as np
import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.analytics.time_change import aggregate_regions

BASE = "https://github.com/phbelov/world-trade-app/releases/download/data-v1/"
FILES = [
    "dims-baci-hs92-202601-countries.parquet",
    "cube-baci-hs92-202601-bilateral.parquet",
    "cube-baci-hs92-202601-bilateral_hs2.parquet",
]
DIGESTS = [
    "138a5ded9aa25b59890f29f93791d55090f2180cc25c573fcd4d4b31a6014bce",
    "a95669d80e4a3698f24eef9aa6f3d370cae2219fb36bdab1799144b5c66c524d",
    "8c236bd9d35105427c3348911e61cb45e520177821a09efaaf0cfef0f1fba892",
]


def build(source, output):
    output.mkdir(parents=True, exist_ok=True)
    for n, digest in zip(FILES, DIGESTS):
        if hashlib.sha256((source / n).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Release asset digest mismatch: {n}")
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='2GB'")
    dims = pd.read_parquet(source / FILES[0])
    if dims.code.duplicated().any() or dims.iso3.isna().any():
        raise ValueError("Invalid source country mapping.")
    con.register("dims", dims)
    meta = pd.read_parquet(output / "country_meta.parquet")
    expected = pd.read_parquet(output / "exporter_hs2_year.parquet")
    rows = []
    max_error = 0.0
    counts = []
    for year in range(1995, 2025):
        d = con.execute(
            """SELECT year, a.iso3 AS exporter, b.iso3 AS importer,
            hs2, value_usd / 1000. AS value FROM read_parquet(?) e
            LEFT JOIN dims a ON e.exporter=a.code LEFT JOIN dims b ON e.importer=b.code
            WHERE year=?""",
            [str(source / FILES[2]), year],
        ).df()
        if not d.hs2.str.fullmatch(r"\d{2}").all():
            raise ValueError("Invalid HS2")
        z = aggregate_regions(d, meta)
        target = expected[expected.year.eq(year)]
        match = z.merge(
            target,
            on=["year", "exporter", "hs2"],
            how="outer",
            indicator=True,
            suffixes=("_source", "_project"),
        )
        if not match["_merge"].eq("both").all():
            raise ValueError(f"Key mismatch {year}")
        np.testing.assert_allclose(
            match.value_source, match.value_project, rtol=2e-8, atol=1e-6
        )
        max_error = max(
            max_error,
            float(
                (
                    (match.value_source - match.value_project).abs()
                    / match.value_project.where(match.value_project.ne(0))
                ).max()
            ),
        )
        counts.append(
            dict(year=year, bilateral_product_rows=len(d), product_keys=len(z))
        )
        rows.append(z)
        print(f"{year}: {len(d):,} bilateral product rows reconciled", flush=True)
    result = pd.concat(rows, ignore_index=True)
    for keys, name, value in [
        (["year", "exporter"], "country_year.parquet", "export_value")
    ]:
        sums = result.groupby(keys).value.sum().sort_index()
        other = (
            pd.read_parquet(output / name)
            .rename(columns={"country": "exporter"})
            .set_index(keys)[value]
            .sort_index()
        )
        if not sums.index.equals(other.index):
            raise ValueError("Country keys mismatch")
        np.testing.assert_allclose(sums, other, rtol=2e-8, atol=1e-6)
    np.testing.assert_allclose(
        result.groupby("year").value.sum(),
        pd.read_parquet(output / "flow_year.parquet").sort_values("year").export_value,
        rtol=2e-8,
    )
    # The separate all-product bilateral cube must agree with its HS2 marginal.
    mismatch = con.execute(
        """WITH a AS (
        SELECT year,exporter,importer,sum(value_usd) v FROM read_parquet(?) GROUP BY ALL
        ), b AS (SELECT year,exporter,importer,value_usd v FROM read_parquet(?))
        SELECT count(*) FROM a FULL OUTER JOIN b USING(year,exporter,importer)
        WHERE a.v IS NULL OR b.v IS NULL OR abs(a.v-b.v)>0.001+2e-8*abs(b.v)
        """,
        [str(source / FILES[2]), str(source / FILES[1])],
    ).fetchone()[0]
    if mismatch:
        raise ValueError(f"Bilateral-key discrepancies: {mismatch}")
    pairs = con.execute(
        """SELECT e.year,a.iso3 exporter,b.iso3 importer,value_usd/1000. value
        FROM read_parquet(?) e LEFT JOIN dims a ON e.exporter=a.code LEFT JOIN dims b ON e.importer=b.code""",
        [str(source / FILES[1])],
    ).df()
    if (
        pairs[["year", "exporter", "importer"]].isna().any().any()
        or pairs.duplicated(["year", "exporter", "importer"]).any()
    ):
        raise ValueError("Invalid bilateral keys")
    p = pairs.groupby(["year", "exporter"]).value.sum().sort_index()
    np.testing.assert_allclose(
        p, result.groupby(["year", "exporter"]).value.sum().sort_index(), rtol=2e-8
    )
    result.to_parquet(output / "m5_region_hs2_year.parquet", index=False)
    pairs.to_parquet(output / "country_pair_year.parquet", index=False)
    manifest = {
        "source_version": "BACI HS92 V202601",
        "years": [1995, 2024],
        "source_type": "Third-party redistribution; not an independent official-CSV audit",
        "source_repository": "https://github.com/phbelov/world-trade-app",
        "source_release": "data-v1",
        "upstream": "https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
        "license": "CEPII Etalab 2.0; attribution retained",
        "unit": "thousand current USD; release value_usd divided by 1000",
        "region_definition": "Fixed project country_meta regions: Africa/America/Asia/Europe/Pacific. No/unmapped remains unknown.",
        "partner_allocation_limit": "Matching exporter-product marginals does not independently audit partner allocation.",
        "max_product_relative_error": max_error,
        "keys_reconciled": len(result),
        "bilateral_keys_reconciled": len(pairs),
        "project_inputs_sha256": {
            n: hashlib.sha256((output / n).read_bytes()).hexdigest()
            for n in [
                "exporter_hs2_year.parquet",
                "country_year.parquet",
                "flow_year.parquet",
                "country_meta.parquet",
            ]
        },
        "checks": counts,
        "files": [
            {
                "file": n,
                "url": BASE + n,
                "sha256": hashlib.sha256((source / n).read_bytes()).hexdigest(),
            }
            for n in FILES
        ],
        "output_sha256": hashlib.sha256(
            (output / "m5_region_hs2_year.parquet").read_bytes()
        ).hexdigest(),
        "downloaded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (output / "m5_source_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf8"
    )
    print(f"PASS: {len(result):,} product keys; max relative error {max_error:.3g}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--download", action="store_true")
    p.add_argument("--source-dir", type=Path, default=ROOT / "data/sources/m5")
    p.add_argument("--output-dir", type=Path, default=ROOT / "data/processed")
    a = p.parse_args()
    a.source_dir.mkdir(parents=True, exist_ok=True)
    if a.download:
        for n in FILES:
            if not (a.source_dir / n).exists():
                urllib.request.urlretrieve(BASE + n, a.source_dir / n)
    build(a.source_dir, a.output_dir)
