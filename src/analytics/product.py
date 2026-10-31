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
    "31": "Fertilizers",
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


@lru_cache(maxsize=1)
def income_policy():
    return json.loads((REFERENCE.parent / "m4_income_policy.json").read_text())


def income_allowed(year):
    policy = income_policy()
    return policy["comparison_min_year"] <= year <= policy["comparison_max_year"]


def candidate_pool(country_year, selectable):
    """Union of annual Top10 after explicit metadata eligibility, not S-prefix filtering."""
    d = country_year[country_year.country.isin(selectable)].copy()
    d["rank"] = d.groupby("year").export_value.rank(method="min", ascending=False)
    return sorted(d.loc[d["rank"].le(10), "country"].unique())


def two_year_metrics(frame, country, year, baseline, products):
    """Outer alignment preserves absent endpoints; no synthetic zeros or forward fills."""
    pieces = []
    for y, suffix in [(baseline, "base"), (year, "current")]:
        all_metrics = year_metrics(frame, y)
        d = (
            all_metrics[all_metrics.exporter.eq(country)]
            .set_index("hs2")[["value", "share", "world_share", "rca"]]
            .reindex(products)
        )
        # World shares remain known even when the focus economy has no record.
        world = all_metrics.drop_duplicates("hs2").set_index("hs2").world_share
        d["world_share"] = world.reindex(products)
        pieces.append(d.add_suffix("_" + suffix))
    d = pieces[0].join(pieces[1], how="outer").reindex(products).copy()
    d.index.name = "hs2"
    d["change_pp"] = (d.share_current - d.share_base) * 100
    d["baseline"] = baseline
    d["year"] = year
    d["country"] = country
    d["missing_endpoint"] = d.share_base.isna() | d.share_current.isna()
    return d.reset_index()


def spread_finding(metrics, countries, products):
    """Only the displayed product scope can contribute to a displayed finding."""
    if len(countries) < 2 or not products:
        return None
    a = metrics[metrics.exporter.isin(countries) & metrics.hs2.isin(products)]
    a = (
        a.pivot(index="hs2", columns="exporter", values="share")
        .reindex(columns=countries)
        .dropna()
    )
    if a.empty:
        return None
    spread = a.max(axis=1) - a.min(axis=1)
    p = spread.idxmax()
    return {
        "hs2": p,
        "high": a.loc[p].idxmax(),
        "low": a.loc[p].idxmin(),
        "high_share": float(a.loc[p].max()),
        "low_share": float(a.loc[p].min()),
        "spread_pp": float(spread[p] * 100),
    }
