"""Offline pre-aggregation pipeline (DuckDB).

Two-layer design so it is safe to re-run incrementally:

    raw sources ──► staging table (persisted, scanned ONCE per build)
                              │
                              └────► 7 analysis parquet tables (cheap, re-materialisable)

Staging tables live in a small on-disk DuckDB library (``data/processed/analytics.duckdb``).
They are created/refreshed once; every analysis-table build reads staging, never the
~10 GB raw CSVs. This is what lets each module re-run just the table(s) it depends on
without re-loading raw data. Run from the project root:

    python scripts/build_analytics.py                # build/refresh all staging + tables
    python scripts/build_analytics.py --only gdp     # materialise one analysis table
    python scripts/build_analytics.py --force        # re-scan raw sources into staging

``--only`` values are the individual analysis tables (see ``TABLES`` below). Staging is
always (re)built unless its source marker still matches the raw files on disk, so the 10 GB
BACI scan happens at most once per source revision. This script is intentionally NOT run
automatically by the app; the app reads the produced parquet files (see
``src/data_loader.py``) and falls back to demo data until they exist. Set
``config.DATA_READY = True`` once tables are built.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas

# Make ``import src`` work when run as a script from the project root.
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src import config  # noqa: E402

BACI_GLOB = str(config.BACI_DIR / "BACI_HS92_Y*_V*.csv")
BACI_COUNTRY = str(config.BACI_DIR / "country_codes_V202601.csv")
GDP_CSV = str(config.CHELEM_DIR / "gdp_v202502.csv")
BOP_CSV = str(config.CHELEM_DIR / "bop_v202502.csv")
BOP_INDIC_CSV = str(config.CHELEM_DIR / "bop_indic_v202502.csv")
TRADE_CHIEL_CSV = str(config.CHELEM_DIR / "trade_chel_v202502.csv")
TRADE_GTAP_CSV = str(config.CHELEM_DIR / "trade_gtap_v202502.csv")
TRADE_INDIC_CSV = str(config.CHELEM_DIR / "trade_indic_v202502.csv")
TRADE_ISIC_CSV = str(config.CHELEM_DIR / "trade_isic_V202502.csv")
GEO_XLS = str(config.GEODIST_DIR / "geo_cepii.xls")
DIST_XLS = str(config.GEODIST_DIR / "dist_cepii.xls")

# Small hand-built crosswalk for the ~23 BACI codes that don't match CEPII ISO3
# directly (historical entities / code variants). Extend as needed.
ISO3_CROSSWALK: dict[str, str] = {
    # "ROM": "ROU",  # example — populate during data integration (task T1)
}

# On-disk DuckDB library that holds the persisted staging tables.
DB_PATH = str(config.PROCESSED_DIR / "analytics.duckdb")
# Marker file recording which raw-source revision the current staging reflects.
STAGING_MARKER = config.PROCESSED_DIR / ".staging_marker.json"


def _con():
    import duckdb

    return duckdb.connect(DB_PATH)


def _read_xls(path: str):
    """Read a legacy OLE2 .xls (BIFF) into a pandas DataFrame via xlrd.

    These GeoDist files predate OOXML, so DuckDB's zip-based ``read_xlsx`` cannot
    open them; pandas with the xlrd engine is the correct reader.
    """
    import pandas

    return pandas.read_excel(path, header=0, engine="xlrd", dtype=str)


def _stage_from_pandas(con, table_name: str, path: str, cols: list[str]) -> None:
    """Read a legacy .xls via pandas and persist it as a DuckDB staging table."""
    df = _read_xls(path)
    # Coerce the known numeric distance/flag columns; keep text columns as-is.
    numeric = {"dist", "distw", "distcap", "contig", "comlang_off"}
    for c in cols:
        if c in numeric:
            df[c] = pandas.to_numeric(df[c], errors="coerce")
    for c in ("iso_o", "iso_d"):
        df[c] = df[c].astype("string")
    con.register(table_name, df)
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM {table_name}")
    con.unregister(table_name)


# ---------------------------------------------------------------------------
# Staging layer (raw → analytics.duckdb tables). The expensive 8.2 GB BACI scan
# lives here; everything downstream reads these persistent tables, not the CSVs.
# ---------------------------------------------------------------------------

def _stage_all(con, revision: str) -> None:
    """Scan raw sources once and refresh every persistent staging table."""
    print("[staging] scanning raw sources → " + Path(DB_PATH).name)

    # BACI: the single expensive step (year, exporter, importer, hs2, value).
    con.execute(f"""
        CREATE OR REPLACE TABLE staging_baci AS
        SELECT
            t AS year,
            i AS exporter_code,
            j AS importer_code,
            substr(CAST(k AS VARCHAR), 1, 2) AS hs2,
            v AS value
        FROM read_csv_auto('{BACI_GLOB}', header=true, union_by_name=true)
    """)
    # BACI: country_code (INT) → iso3/name. Tiny, cheap.
    con.execute(f"""
        CREATE OR REPLACE TABLE staging_country AS
        SELECT
            CAST(country_code AS INTEGER) AS code,
            country_iso3                  AS iso3,
            country_name                  AS name
        FROM read_csv_auto('{BACI_COUNTRY}', header=true)
    """)
    # CHELEM gdp wide → long (one row per country × year-col). Cheap.
    con.execute(f"""
        CREATE OR REPLACE TABLE staging_gdp_long AS
        SELECT country, indicator, yr, value
        FROM (
            UNPIVOT (
                SELECT * FROM read_csv_auto('{GDP_CSV}', header=true)
            )
            ON COLUMNS(* EXCLUDE (country, indicator))
            INTO NAME yr VALUE value
        )
    """)
    # GeoDist. The dist/geo files are *legacy* OLE2 .xls (BIFF), not OOXML .xlsx,
    # so DuckDB's read_xlsx (zip-based) cannot open them. Read via pandas/xlrd and
    # hand the frames to DuckDB as registered tables instead.
    _stage_from_pandas(con, "staging_geodist", DIST_XLS, [
        "iso_o", "iso_d", "dist", "distw", "distcap", "contig", "comlang_off",
    ])
    meta = _read_xls(GEO_XLS)
    meta = meta[meta["iso3"].notnull()].rename(
        columns={"country": "name", "continent": "region"}
    )[["iso3", "name", "region"]]
    meta["region"] = meta["region"].astype("string")
    con.register("meta", meta)
    con.execute("CREATE OR REPLACE TABLE staging_country_meta AS SELECT * FROM meta")
    con.unregister("meta")

    # Record which raw revision we just scanned so the next run can skip staging.
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_MARKER.write_text(
        json.dumps({"revision": revision}, indent=2), encoding="utf-8"
    )
    print("[staging] done (marker written)")


def _raw_revision() -> str:
    """Stable hash of the raw-source *fingerprints* (names + mtime + size).

    This intentionally does NOT read the ~10 GB files; it only stat()'s them, so
    detecting "raw data changed" is cheap. Re-running without touching sources is a
    no-op on staging; editing a raw file bumps the revision and forces a re-stage.
    """
    import glob
    import os

    names = sorted(
        set(glob.glob(str(config.BACI_DIR / "BACI_HS92_Y*_V*.csv")))
        | {str(p) for p in [BACI_COUNTRY, GDP_CSV, BOP_CSV, BOP_INDIC_CSV,
                            TRADE_CHIEL_CSV, TRADE_GTAP_CSV, TRADE_INDIC_CSV,
                            TRADE_ISIC_CSV, GEO_XLS, DIST_XLS]}
    )
    parts = []
    for name in names:
        try:
            st = os.stat(name)
            parts.append(f"{name}|{st.st_mtime_ns}|{st.st_size}")
        except FileNotFoundError:
            parts.append(f"{name}|missing")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def _staging_revision() -> str | None:
    """Revision currently recorded in the marker file, or None if absent."""
    if not STAGING_MARKER.exists():
        return None
    try:
        return json.loads(STAGING_MARKER.read_text(encoding="utf-8")).get("revision")
    except (json.JSONDecodeError, OSError):
        return None


def _ensure_staging(revision: str, force: bool) -> None:
    """Stage raw sources unless the marker already records ``revision``.

    With ``force`` we always re-scan; otherwise a matching revision means the
    persistent staging tables are already current and we skip the expensive work.
    Staging is a whole-library operation (every builder reads from it), so it is
    refreshed all-or-nothing here, not per table.
    """
    if not force and _staging_revision() == revision:
        print("[staging] current (marker matches raw revision) — skipping scan")
        return
    con = _con()
    try:
        _stage_all(con, revision)
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Analysis layer (analytics.duckdb → data/processed/*.parquet). Each of these
# is cheap because it reads the persistent staging tables, not raw CSVs.
# ---------------------------------------------------------------------------

def _mat_flow_year(con) -> None:
    con.execute(f"""
        COPY (
            SELECT year, SUM(value) AS export_value
            FROM staging_baci GROUP BY year ORDER BY year
        ) TO '{config.processed_path("flow_year.parquet")}' (FORMAT PARQUET)
    """)


def _mat_country_year(con) -> None:
    con.execute(f"""
        COPY (
            SELECT b.year, c.iso3 AS country, SUM(b.value) AS export_value
            FROM staging_baci b JOIN staging_country c ON b.exporter_code = c.code
            GROUP BY b.year, c.iso3
        ) TO '{config.processed_path("country_year.parquet")}' (FORMAT PARQUET)
    """)


def _mat_country_pair_year(con) -> None:
    con.execute(f"""
        COPY (
            SELECT b.year, eo.iso3 AS exporter, ed.iso3 AS importer, SUM(b.value) AS value
            FROM staging_baci b
            JOIN staging_country eo ON b.exporter_code = eo.code
            JOIN staging_country ed ON b.importer_code = ed.code
            GROUP BY b.year, eo.iso3, ed.iso3
        ) TO '{config.processed_path("country_pair_year.parquet")}' (FORMAT PARQUET)
    """)


def _mat_exporter_hs2_year(con) -> None:
    con.execute(f"""
        COPY (
            SELECT b.year, c.iso3 AS exporter, b.hs2, SUM(b.value) AS value
            FROM staging_baci b JOIN staging_country c ON b.exporter_code = c.code
            GROUP BY b.year, c.iso3, b.hs2
        ) TO '{config.processed_path("exporter_hs2_year.parquet")}' (FORMAT PARQUET)
    """)


def _mat_country_pair_hs2_year(con) -> None:
    con.execute(f"""
        COPY (
            SELECT b.year, eo.iso3 AS exporter, ed.iso3 AS importer, b.hs2, SUM(b.value) AS value
            FROM staging_baci b
            JOIN staging_country eo ON b.exporter_code = eo.code
            JOIN staging_country ed ON b.importer_code = ed.code
            GROUP BY b.year, eo.iso3, ed.iso3, b.hs2
        ) TO '{config.processed_path("country_pair_hs2_year.parquet")}' (FORMAT PARQUET)
    """)


def _mat_gdp_year(con) -> None:
    con.execute(f"""
        COPY (
            SELECT
                CAST(replace(yr, 'v', '') AS INTEGER) AS year,
                country,
                MAX(CASE WHEN indicator = 'GDP-VAL' THEN value END) AS gdp,
                MAX(CASE WHEN indicator = 'GDP-CAP' THEN value END) AS gdp_per_capita,
                MAX(CASE WHEN indicator = 'POP'     THEN value END) AS population
            FROM staging_gdp_long
            WHERE regexp_matches(yr, '^v[0-9]{{4}}$')
            GROUP BY year, country
        ) TO '{config.processed_path("gdp_year.parquet")}' (FORMAT PARQUET)
    """)


def _mat_geodist(con) -> None:
    con.execute(f"""
        COPY (
            SELECT iso_o, iso_d, dist, distw, distcap, contig, comlang_off
            FROM staging_geodist
        ) TO '{config.processed_path("geodist.parquet")}' (FORMAT PARQUET)
    """)


def _mat_country_meta(con) -> None:
    con.execute(f"""
        COPY (
            SELECT iso3, name, region
            FROM staging_country_meta
        ) TO '{config.processed_path("country_meta.parquet")}' (FORMAT PARQUET)
    """)


@dataclass(frozen=True)
class TableSpec:
    """One analysis parquet table and the staging table(s) it depends on.

    ``materialise`` reads only from persistent staging (never raw CSVs), which is
    what makes ``--only`` cheap: it re-materialises a single output without
    re-scanning the 8.2 GB BACI sources.
    """
    key: str
    output: str                       # filename under data/processed/
    staging_dep: tuple[str, ...]      # staging table names this output reads
    materialise: object = field(default=None, repr=False)  # fn(con) -> None


TABLES: dict[str, TableSpec] = {
    spec.key: spec
    for spec in [
        TableSpec("flow_year", "flow_year.parquet",
                  ("staging_baci",), _mat_flow_year),
        TableSpec("country_year", "country_year.parquet",
                  ("staging_baci", "staging_country"), _mat_country_year),
        TableSpec("country_pair_year", "country_pair_year.parquet",
                  ("staging_baci", "staging_country"), _mat_country_pair_year),
        TableSpec("exporter_hs2_year", "exporter_hs2_year.parquet",
                  ("staging_baci", "staging_country"), _mat_exporter_hs2_year),
        TableSpec("country_pair_hs2_year", "country_pair_hs2_year.parquet",
                  ("staging_baci", "staging_country"), _mat_country_pair_hs2_year),
        TableSpec("gdp_year", "gdp_year.parquet",
                  ("staging_gdp_long",), _mat_gdp_year),
        TableSpec("geodist", "geodist.parquet",
                  ("staging_geodist",), _mat_geodist),
        TableSpec("country_meta", "country_meta.parquet",
                  ("staging_country_meta",), _mat_country_meta),
    ]
}


def main() -> None:
    parser = argparse.ArgumentParser(description="CEPII offline pre-aggregation (DuckDB).")
    parser.add_argument(
        "--only",
        choices=sorted(TABLES),
        help="Materialise a single analysis table instead of all eight.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scan the raw sources into staging even if the revision marker matches.",
    )
    args = parser.parse_args()

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Staging: refresh once (or reuse when the marker already matches).
    revision = _raw_revision()
    _ensure_staging(revision, args.force)

    # 2) Analysis: materialise the requested table(s) from persistent staging.
    keys = [args.only] if args.only else list(TABLES)
    con = _con()
    try:
        for key in keys:
            spec = TABLES[key]
            print(f"[build] {key} ← {', '.join(spec.staging_dep)}")
            spec.materialise(con)
            print(f"[build] {key} done → {config.processed_path(spec.output).name}")
    finally:
        con.close()

    print(f"[build] {len(keys)} table(s) written to {config.PROCESSED_DIR}")
    print("[build] set src/config.py DATA_READY = True to serve real tables.")


if __name__ == "__main__":
    main()
