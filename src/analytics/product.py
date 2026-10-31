"""Pure M4 calculations. Presentation filters never define reference totals."""

from functools import lru_cache
import json
from pathlib import Path
import numpy as np
import pandas as pd

REFERENCE = Path(__file__).resolve().parents[2] / "data/reference/hs92_chapters.json"


@lru_cache(maxsize=1)
def chapters():
    return {r["hs2"]: r["name"] for r in json.loads(REFERENCE.read_text())["chapters"]}


# Readable display labels; the UN HS1992 reference title remains available in hover.
SHORT = {
    "27": "Mineral fuels & oils",
    "84": "Machinery & mechanical appliances",
    "85": "Electrical machinery & equipment",
    "87": "Vehicles & parts (excl. rail)",
    "94": "Furniture, bedding & lighting",
    "95": "Toys, games & sports equipment",
    "61": "Knitted apparel & accessories",
    "62": "Other apparel & accessories",
    "03": "Fish & aquatic invertebrates",
    "16": "Meat & seafood preparations",
    "15": "Animal & vegetable fats and oils",
    "23": "Food residues & animal feed",
    "30": "Pharmaceutical products",
    "39": "Plastics & articles",
    "71": "Precious stones & metals",
    "90": "Optical, medical & measuring instruments",
    "72": "Iron & steel",
    "73": "Articles of iron or steel",
    "29": "Organic chemicals",
    "88": "Aircraft & spacecraft",
}


def label(code):
    title = SHORT.get(code, chapters().get(code, "Unmapped chapter"))
    return f"{code} · {title}"


def validate_trade(frame):
    required = {"year", "exporter", "hs2", "value"}
    if not required.issubset(frame.columns):
        raise ValueError(
            "Missing product-table fields: "
            + ", ".join(sorted(required - set(frame.columns)))
        )
    if frame[list(required)].isna().any().any():
        raise ValueError(
            "Product table has missing keys or amounts; investigate before analysis."
        )
    if frame.duplicated(["year", "exporter", "hs2"]).any():
        raise ValueError("Product table has duplicate year/exporter/HS2 keys.")
    if not frame.hs2.astype(str).str.fullmatch(r"\d{2}").all():
        raise ValueError(
            "HS2 must be a two-digit string; do not infer chapters from unpadded HS6."
        )
    if set(frame.hs2) - set(chapters()):
        raise ValueError(
            "Product table contains chapters absent from the HS1992 reference."
        )
    if not np.isfinite(frame.value).all() or (frame.value < 0).any():
        raise ValueError("Trade values must be finite and non-negative.")


def year_metrics(frame, year):
    """Keep unrecorded cells absent. All observed exporters remain in world totals."""
    d = frame.loc[frame.year.eq(year), ["exporter", "hs2", "value"]].copy()
    if d.empty:
        return pd.DataFrame(
            columns=["exporter", "hs2", "value", "total", "share", "world_share", "rca"]
        )
    d["total"] = d.groupby("exporter").value.transform("sum")
    world = d.groupby("hs2").value.sum()
    grand = world.sum()
    d["share"] = d.value / d.total.where(d.total.gt(0))
    d["world_share"] = d.hs2.map(world / grand if grand > 0 else world * np.nan)
    d["rca"] = d.share / d.world_share.where(d.world_share.gt(0))
    return d


def product_set(metrics, countries, requested=None):
    available = set(metrics.hs2)
    if requested:
        return sorted(set(requested) & available)
    d = metrics[metrics.exporter.isin(countries)].sort_values(
        ["value", "hs2"], ascending=[False, True]
    )
    codes = set(d.groupby("exporter", sort=False).head(5).hs2)
    # Common rows, independent of the displayed metric and focus cell.
    sums = d.groupby("hs2").value.sum()
    return sorted(codes, key=lambda p: (-sums.get(p, 0), p))


def income_peers(gdp, year, anchor, eligible, factor=1.5, limit=6):
    """Contemporaneous nominal GDP per capita within [anchor/factor, anchor*factor].

    This is a transparent comparison heuristic, not an official income grouping.
    """
    if gdp.duplicated(["year", "country"]).any():
        raise ValueError("GDP table has duplicate year/country keys.")
    g = gdp.loc[
        gdp.year.eq(year) & gdp.country.isin(eligible), ["country", "gdp_per_capita"]
    ].copy()
    g["income"] = pd.to_numeric(g.gdp_per_capita, errors="coerce")
    g = g[np.isfinite(g.income) & g.income.gt(0)]
    a = g.loc[g.country.eq(anchor), "income"]
    if a.empty:
        return [], g, None
    base = float(a.iloc[0])
    g["ratio"] = g.income / base
    g = g[g.ratio.between(1 / factor, factor)].copy()
    g["distance"] = np.abs(np.log(g.ratio))
    g = g.sort_values(["distance", "country"]).head(limit)
    return g.country.tolist(), g, base
