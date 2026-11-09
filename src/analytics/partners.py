"""Shared bilateral scope: full partners first, presentation limits last."""

from functools import lru_cache
import pandas as pd
import duckdb
from src import config, data_loader

FOCUS = ["USA", "DEU", "CHN", "MEX", "NLD", "ITA"]
REGIONS = ["Africa", "America", "Asia", "Europe", "Oceania", "Unknown"]


def region(value):
    return "Oceania" if value == "Pacific" else value if value in REGIONS else "Unknown"


@lru_cache(maxsize=256)
def flows(year, product="TOTAL"):
    file = (
        "country_pair_year.parquet"
        if product == "TOTAL"
        else "country_pair_hs2_year.parquet"
    )
    path = config.processed_path(file)
    if product != "TOTAL":
        compact = config.processed_path("country_pair_hs2_focus_year.parquet")
        if compact.exists():
            path = compact
    if not path.exists():
        raise FileNotFoundError(
            f"Missing real bilateral data: {file}. Run the data preparation step."
        )
    with duckdb.connect() as con:
        q = "SELECT * FROM read_parquet(?) WHERE year=?"
        params = [str(path), int(year)]
        if product != "TOTAL":
            q += " AND hs2=?"
            params.append(product)
        return con.execute(q, params).df()


@lru_cache(maxsize=256)
def partners(country, year, product="TOTAL", direction="export"):
    if country not in FOCUS:
        raise ValueError("Select one of the six focal economies.")
    d = flows(year, product)
    origin, dest = (
        ("exporter", "importer") if direction == "export" else ("importer", "exporter")
    )
    d = (
        d[d[origin].eq(country)]
        .groupby(dest, as_index=False)
        .value.sum()
        .rename(columns={dest: "partner"})
    )
    total = d.value.sum()
    d["share"] = d.value / total if total > 0 else float("nan")
    meta = data_loader.load_country_meta().drop_duplicates("iso3").set_index("iso3")
    d["name"] = d.partner.map(meta.name).fillna(d.partner)
    d["region"] = d.partner.map(meta.region).map(region)
    return d.sort_values(["value", "partner"], ascending=[False, True]).reset_index(
        drop=True
    )


MATRIX_COLUMNS = 12


@lru_cache(maxsize=64)
def matrix_columns(year, product="TOTAL", direction="export"):
    """Partners ranked by the highest share they hold in any focal economy.

    A partner earns a column by dominating at least one focal economy's trade in
    the current scope, not by having ranked in one fixed snapshot. Ordering by
    that peak share makes the matrix read as a descending importance gradient.
    """
    peak, total = {}, {}
    for c in FOCUS:
        p = partners(c, year, product, direction)
        if p.empty or p.value.sum() <= 0:
            continue
        for partner, share in zip(p.partner, p.share):
            partner, share = str(partner), float(share)
            peak[partner] = max(peak.get(partner, 0.0), share)
            total[partner] = total.get(partner, 0.0) + share
    ranked = sorted(peak, key=lambda c: (-peak[c], -total[c], c))
    return ranked[:MATRIX_COLUMNS]


def matrix(year, product, direction):
    columns = matrix_columns(year, product, direction)
    rows = []
    for c in FOCUS:
        p = partners(c, year, product, direction)
        if p.empty or p.value.sum() <= 0:
            rows.append([float("nan")] * (len(columns) + 1))
            continue
        s = p.set_index("partner").share
        # Exhaustive source scope confirms absent bilateral cells have no recorded flow.
        rows.append(
            [float(s.get(k, 0)) * 100 for k in columns]
            + [p.loc[~p.partner.isin(columns), "share"].sum() * 100]
        )
    return columns + ["Other"], rows


def regional(country, year, product, direction):
    d = partners(country, year, product, direction)
    if d.empty or d.value.sum() <= 0:
        return None
    s = d.groupby("region").share.sum().reindex(REGIONS, fill_value=0)
    home = region(
        data_loader.load_country_meta()
        .drop_duplicates("iso3")
        .set_index("iso3")
        .region.get(country)
    )
    low = float(s[home]) if home != "Unknown" else None
    return s, low, (low + float(s["Unknown"]) if low is not None else None)
