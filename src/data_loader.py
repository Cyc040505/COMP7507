"""Data access layer.

Each loader prefers a pre-aggregated parquet table under ``data/processed/``
(produced offline by ``scripts/build_analytics.py``) and falls back to a small,
deterministic synthetic frame with the SAME schema when that artefact is missing.
Every returned frame carries ``df.attrs["demo"]`` (True for the fallback) so the
UI can label itself honestly.

Rules for contributors (see README "Module development conventions"):

* Loaders are ``lru_cache``-d and return **shared** frames — treat them as
  read-only; never mutate the returned DataFrame in place.
* Call loaders **only inside callbacks**, never at import time. The raw CEPII
  sources reach ~10 GB (``trade_chel`` alone is ~1.1 GB).
* CHELEM raw files store years as **wide columns** (``v1995 … v2024``); when the
  pipeline is written, select the year column at read time rather than after load.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from src import config

_SEED = 7507
_YEARS = list(range(config.YEAR_MIN, config.YEAR_MAX + 1))

# A small, fixed set of economies used only to synthesise demo frames.
_DEMO_COUNTRIES = [
    ("CHN", "China", "Asia"),
    ("USA", "United States", "America"),
    ("DEU", "Germany", "Europe"),
    ("JPN", "Japan", "Asia"),
    ("GBR", "United Kingdom", "Europe"),
    ("FRA", "France", "Europe"),
    ("IND", "India", "Asia"),
    ("BRA", "Brazil", "America"),
    ("CAN", "Canada", "America"),
    ("KOR", "South Korea", "Asia"),
    ("AUS", "Australia", "Oceania"),
    ("MEX", "Mexico", "America"),
    ("SGP", "Singapore", "Asia"),
    ("ZAF", "South Africa", "Africa"),
]
_CODES = [c[0] for c in _DEMO_COUNTRIES]

# Relative export scale per demo economy (rough), used to shape synthetic data.
_SIZE = {
    "CHN": 1.00, "USA": 0.85, "DEU": 0.70, "JPN": 0.50, "GBR": 0.45,
    "FRA": 0.45, "IND": 0.40, "BRA": 0.30, "CAN": 0.35, "KOR": 0.40,
    "AUS": 0.28, "MEX": 0.30, "SGP": 0.30, "ZAF": 0.12,
}

_HS2_SECTIONS = [
    "01", "10", "15", "24", "27", "29", "30", "39", "44", "52",
    "61", "62", "72", "84", "85", "87", "90", "94", "97",
]


# --- plumbing -----------------------------------------------------------------
def _finish(df: pd.DataFrame, demo: bool) -> pd.DataFrame:
    df.attrs["demo"] = bool(demo)
    return df


def _load(filename: str, demo_fn, **kwargs) -> pd.DataFrame:
    """Return the parquet analysis table if present, else the demo fallback."""
    path = config.processed_path(filename)
    if path.exists():
        return _finish(pd.read_parquet(path), False)
    return _finish(demo_fn(**kwargs), True)


# --- country metadata ---------------------------------------------------------
@lru_cache(maxsize=None)
def load_country_meta() -> pd.DataFrame:
    """ISO3 → display name / region. Columns: iso3, name, region."""
    return _load("country_meta.parquet", _demo_country_meta)


def _demo_country_meta() -> pd.DataFrame:
    return pd.DataFrame(_DEMO_COUNTRIES, columns=["iso3", "name", "region"])


# --- overview / time ----------------------------------------------------------
@lru_cache(maxsize=None)
def load_flow_year() -> pd.DataFrame:
    """Global export total per year. Columns: year, export_value (thousand USD)."""
    return _load("flow_year.parquet", _demo_flow_year)


def _demo_flow_year() -> pd.DataFrame:
    rng = np.random.default_rng(_SEED)
    values = 5_000_000.0 * (1.06 ** np.arange(len(_YEARS))) * (1 + rng.normal(0, 0.03, len(_YEARS)))
    return pd.DataFrame({"year": _YEARS, "export_value": values.round(1)})


@lru_cache(maxsize=None)
def load_country_year() -> pd.DataFrame:
    """Exporter total per year. Columns: year, country, export_value."""
    return _load("country_year.parquet", _demo_country_year)


def _demo_country_year() -> pd.DataFrame:
    rng = np.random.default_rng(_SEED + 1)
    rows = []
    for iso3, _, _ in _DEMO_COUNTRIES:
        for i, year in enumerate(_YEARS):
            value = 900_000 * _SIZE[iso3] * (1.055 ** i) * (1 + rng.normal(0, 0.05))
            rows.append((year, iso3, round(value, 1)))
    return pd.DataFrame(rows, columns=["year", "country", "export_value"])


# --- geography ----------------------------------------------------------------
@lru_cache(maxsize=None)
def load_country_pair_year() -> pd.DataFrame:
    """Bilateral value per year. Columns: year, exporter, importer, value."""
    return _load("country_pair_year.parquet", _demo_country_pair_year)


def _demo_country_pair_year() -> pd.DataFrame:
    rng = np.random.default_rng(_SEED + 2)
    rows = []
    for i, year in enumerate(_YEARS):
        for o in _CODES:
            for d in _CODES:
                if o == d:
                    continue
                value = 1000 * (1.05 ** i) * (0.5 + rng.random()) * _SIZE[o]
                rows.append((year, o, d, round(value, 1)))
    return pd.DataFrame(rows, columns=["year", "exporter", "importer", "value"])


@lru_cache(maxsize=None)
def load_geodist() -> pd.DataFrame:
    """Country-pair geography. Columns: iso_o, iso_d, dist, contig, comlang_off."""
    return _load("geodist.parquet", _demo_geodist)


def _demo_geodist() -> pd.DataFrame:
    rng = np.random.default_rng(_SEED + 5)
    rows = []
    for o in _CODES:
        for d in _CODES:
            same = o == d
            rows.append(
                (
                    o,
                    d,
                    round(5.0 if same else float(rng.uniform(200, 19_000)), 1),
                    int(not same and rng.random() < 0.15),
                    int(not same and rng.random() < 0.20),
                )
            )
    return pd.DataFrame(rows, columns=["iso_o", "iso_d", "dist", "contig", "comlang_off"])


# --- economy ------------------------------------------------------------------
@lru_cache(maxsize=None)
def load_gdp_year() -> pd.DataFrame:
    """GDP per country/year (CHELEM, reshaped wide→long).

    Columns: year, country, gdp, gdp_per_capita, population.
    """
    return _load("gdp_year.parquet", _demo_gdp_year)


def _demo_gdp_year() -> pd.DataFrame:
    rng = np.random.default_rng(_SEED + 4)
    gdp0 = {"CHN": 1.2e7, "USA": 1.6e7, "DEU": 3.4e6, "JPN": 4.5e6, "GBR": 2.9e6,
            "FRA": 2.6e6, "IND": 2.5e6, "BRA": 1.9e6, "CAN": 1.7e6, "KOR": 1.5e6,
            "AUS": 1.4e6, "MEX": 1.2e6, "SGP": 3.4e5, "ZAF": 3.5e5}
    pop0 = {"CHN": 1.4e6, "USA": 3.3e5, "DEU": 8.3e4, "JPN": 1.25e5, "GBR": 6.7e4,
            "FRA": 6.7e4, "IND": 1.4e6, "BRA": 2.1e5, "CAN": 3.8e4, "KOR": 5.2e4,
            "AUS": 2.6e4, "MEX": 1.3e5, "SGP": 6.0e3, "ZAF": 5.9e4}
    rows = []
    for iso3, _, _ in _DEMO_COUNTRIES:
        for i, year in enumerate(_YEARS):
            gdp = gdp0[iso3] * (1.05 ** i) * (1 + rng.normal(0, 0.02))
            pop = pop0[iso3] * (1.008 ** i)
            rows.append((year, iso3, round(gdp, 1), round(gdp / pop, 4), round(pop, 3)))
    return pd.DataFrame(rows, columns=["year", "country", "gdp", "gdp_per_capita", "population"])


# --- product structure --------------------------------------------------------
@lru_cache(maxsize=None)
def load_exporter_hs2_year() -> pd.DataFrame:
    """Exporter × HS2 × year value. Columns: year, exporter, hs2, value."""
    return _load("exporter_hs2_year.parquet", _demo_exporter_hs2_year)


def _demo_exporter_hs2_year() -> pd.DataFrame:
    rng = np.random.default_rng(_SEED + 3)
    rows = []
    for iso3, _, _ in _DEMO_COUNTRIES:
        for hs2 in _HS2_SECTIONS:
            for i, year in enumerate(_YEARS):
                value = 4000 * _SIZE[iso3] * (1.04 ** i) * (0.3 + rng.random())
                rows.append((year, iso3, hs2, round(value, 1)))
    return pd.DataFrame(rows, columns=["year", "exporter", "hs2", "value"])


@lru_cache(maxsize=None)
def load_country_pair_hs2_year() -> pd.DataFrame:
    """Exporter × importer × HS2 × year value.

    Columns: year, exporter, importer, hs2, value. Demo uses a trimmed HS2 set to
    keep the synthetic frame small.
    """
    return _load("country_pair_hs2_year.parquet", _demo_country_pair_hs2_year)


def _demo_country_pair_hs2_year() -> pd.DataFrame:
    rng = np.random.default_rng(_SEED + 6)
    hs2_subset = _HS2_SECTIONS[:8]
    rows = []
    for i, year in enumerate(_YEARS):
        for o in _CODES:
            for d in _CODES:
                if o == d:
                    continue
                for hs2 in hs2_subset:
                    value = 300 * (1.04 ** i) * (0.3 + rng.random()) * _SIZE[o]
                    rows.append((year, o, d, hs2, round(value, 1)))
    return pd.DataFrame(rows, columns=["year", "exporter", "importer", "hs2", "value"])


def is_demo() -> bool:
    """True while the app is running on synthetic fallback data."""
    return bool(load_country_meta().attrs.get("demo", True))
