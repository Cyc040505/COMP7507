"""Offline pre-aggregation pipeline (DuckDB).

Turns the ~10 GB of raw CEPII sources under ``data/`` into compact analysis tables
under ``data/processed/``. Run once, offline, from the project root:

    python scripts/build_analytics.py            # build everything
    python scripts/build_analytics.py --only gdp # build one dataset
    python scripts/build_analytics.py --help

This script is intentionally NOT run automatically by the app; the app reads the
produced parquet files (see ``src/data_loader.py``) and falls back to demo data
until they exist. Set ``config.DATA_READY = True`` once tables are built.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ``import src`` work when run as a script from the project root.
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src import config  # noqa: E402

BACI_GLOB = str(config.BACI_DIR / "BACI_HS92_Y*_V*.csv")
BACI_COUNTRY = str(config.BACI_DIR / "country_codes_V202601.csv")
GDP_CSV = str(config.CHELEM_DIR / "gdp_v202502.csv")
GEO_XLS = str(config.GEODIST_DIR / "geo_cepii.xls")
DIST_XLS = str(config.GEODIST_DIR / "dist_cepii.xls")

# Small hand-built crosswalk for the ~23 BACI codes that don't match CEPII ISO3
# directly (historical entities / code variants). Extend as needed.
ISO3_CROSSWALK: dict[str, str] = {
    # "ROM": "ROU",  # example — populate during data integration (task T1)
}


def _con():
    import duckdb

    return duckdb.connect()


def build_flow_country(con) -> None:
    """flow_year + country_year from the 30 BACI files."""
    con.execute(f"""
        CREATE OR REPLACE TABLE flows AS
        SELECT
            t AS year,
            i AS exporter_code,
            j AS importer_code,
            substr(CAST(k AS VARCHAR), 1, 2) AS hs2,
            v AS value
        FROM read_csv_auto('{BACI_GLOB}', header=true, union_by_name=true)
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE cc AS
        SELECT CAST(country_code AS INTEGER) AS code, country_iso3 AS iso3, country_name AS name
        FROM read_csv_auto('{BACI_COUNTRY}', header=true)
    """)

    con.execute(f"""
        COPY (
            SELECT year, SUM(value) AS export_value
            FROM flows GROUP BY year ORDER BY year
        ) TO '{config.processed_path("flow_year.parquet")}' (FORMAT PARQUET)
    """)

    con.execute(f"""
        COPY (
            SELECT f.year, cc.iso3 AS country, SUM(f.value) AS export_value
            FROM flows f JOIN cc ON f.exporter_code = cc.code
            GROUP BY f.year, cc.iso3
        ) TO '{config.processed_path("country_year.parquet")}' (FORMAT PARQUET)
    """)

    con.execute(f"""
        COPY (
            SELECT f.year, eo.iso3 AS exporter, ed.iso3 AS importer, SUM(f.value) AS value
            FROM flows f
            JOIN cc eo ON f.exporter_code = eo.code
            JOIN cc ed ON f.importer_code = ed.code
            GROUP BY f.year, eo.iso3, ed.iso3
        ) TO '{config.processed_path("country_pair_year.parquet")}' (FORMAT PARQUET)
    """)

    con.execute(f"""
        COPY (
            SELECT f.year, cc.iso3 AS exporter, f.hs2, SUM(f.value) AS value
            FROM flows f JOIN cc ON f.exporter_code = cc.code
            GROUP BY f.year, cc.iso3, f.hs2
        ) TO '{config.processed_path("exporter_hs2_year.parquet")}' (FORMAT PARQUET)
    """)

    con.execute(f"""
        COPY (
            SELECT f.year, eo.iso3 AS exporter, ed.iso3 AS importer, f.hs2, SUM(f.value) AS value
            FROM flows f
            JOIN cc eo ON f.exporter_code = eo.code
            JOIN cc ed ON f.importer_code = ed.code
            GROUP BY f.year, eo.iso3, ed.iso3, f.hs2
        ) TO '{config.processed_path("country_pair_hs2_year.parquet")}' (FORMAT PARQUET)
    """)


def build_gdp(con) -> None:
    """CHELEM gdp wide → long: gdp / gdp_per_capita / population per year."""
    # The file keys on (country, indicator, vYYYY...). Unpivot the year columns,
    # then pivot the indicators back into columns.
    con.execute(f"""
        CREATE OR REPLACE TABLE gdp_long AS
        UNPIVOT (SELECT * FROM read_csv_auto('{GDP_CSV}', header=true))
        ON COLUMNS(* EXCLUDE (country, indicator))
        INTO NAME yr VALUE value
    """)
    con.execute(f"""
        COPY (
            SELECT
                CAST(replace(yr, 'v', '') AS INTEGER) AS year,
                country,
                MAX(CASE WHEN indicator = 'GDP-VAL' THEN value END)      AS gdp,
                MAX(CASE WHEN indicator = 'GDP-CAP' THEN value END)      AS gdp_per_capita,
                MAX(CASE WHEN indicator = 'POP' THEN value END)          AS population
            FROM gdp_long
            WHERE regexp_matches(yr, '^v[0-9]{{4}}$')
            GROUP BY year, country
        ) TO '{config.processed_path("gdp_year.parquet")}' (FORMAT PARQUET)
    """)


def build_geodist(con) -> None:
    """geodist + country_meta from the GeoDist spreadsheets."""
    con.execute(f"""
        COPY (
            SELECT iso_o, iso_d, dist, distw, distcap, contig, comlang_off
            FROM read_xlsx('{DIST_XLS}', header=true, all_varchar=true)
        ) TO '{config.processed_path("geodist.parquet")}' (FORMAT PARQUET)
    """)
    con.execute(f"""
        COPY (
            SELECT iso3, country AS name, continent AS region
            FROM read_xlsx('{GEO_XLS}', header=true, all_varchar=true)
            WHERE iso3 IS NOT NULL
        ) TO '{config.processed_path("country_meta.parquet")}' (FORMAT PARQUET)
    """)


BUILDERS = {
    "flows": build_flow_country,
    "gdp": build_gdp,
    "geodist": build_geodist,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="CEPII offline pre-aggregation (DuckDB).")
    parser.add_argument(
        "--only",
        choices=sorted(BUILDERS),
        help="Build a single dataset instead of all.",
    )
    args = parser.parse_args()

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    con = _con()
    targets = [args.only] if args.only else list(BUILDERS)
    try:
        for name in targets:
            print(f"[build] {name} ...")
            BUILDERS[name](con)
            print(f"[build] {name} done")
    finally:
        con.close()

    print(f"[build] outputs written to {config.PROCESSED_DIR}")
    print("[build] set src/config.py DATA_READY = True to serve real tables.")


if __name__ == "__main__":
    main()
