"""Annual, descriptive recovery analysis. No interpolation or changing denominators."""

from __future__ import annotations
import numpy as np
import pandas as pd

REGIONS = {"Africa", "America", "Asia", "Europe", "Pacific"}
TIMELINE_COLUMNS = [
    "year",
    "country",
    "value",
    "total",
    "product_share",
    "index",
    "intra_value",
    "known_value",
    "intra_share",
    "intra_upper",
    "region_coverage",
]


def validate(frame, keys, amount="value"):
    if not set(keys + [amount]).issubset(frame.columns):
        raise ValueError("Required data columns are missing.")
    if frame[keys + [amount]].isna().any().any() or frame.duplicated(keys).any():
        raise ValueError("Missing or duplicate analysis keys/amounts.")
    if not np.isfinite(frame[amount]).all() or frame[amount].lt(0).any():
        raise ValueError("Amounts must be finite and nonnegative.")


def aggregate_regions(edges, meta):
    """Retain all destination amounts; unknown origin never means zero internal trade."""
    validate(edges, ["year", "exporter", "importer", "hs2"])
    mapping = meta[["iso3", "region"]].drop_duplicates()
    if mapping.iso3.duplicated().any():
        raise ValueError("Conflicting region keys.")
    region = mapping.set_index("iso3").region
    d = edges.copy()
    origin, destination = d.exporter.map(region), d.importer.map(region)
    known = origin.isin(REGIONS) & destination.isin(REGIONS)
    d["known_value"] = d.value.where(known, 0.0)
    d["intra_value"] = d.value.where(known & origin.eq(destination), 0.0)
    d.loc[~origin.isin(REGIONS), ["intra_value", "known_value"]] = np.nan
    return d.groupby(["year", "exporter", "hs2"], as_index=False)[
        ["value", "known_value", "intra_value"]
    ].sum(min_count=1)


def build_timeline(products, regions, countries, product, baseline, start, end):
    """One row per chosen country and calendar year, including missing years."""
    if not start <= baseline <= end:
        raise ValueError("Baseline must be within the displayed window.")
    validate(products, ["year", "exporter", "hs2"])
    if not countries:
        return pd.DataFrame(columns=TIMELINE_COLUMNS)
    countries = list(dict.fromkeys(countries))
    d = products[products.exporter.isin(countries)]
    total = d.groupby(["year", "exporter"]).value.sum(min_count=1).rename("total")
    selected = d if product == "TOTAL" else d[d.hs2.eq(product)]
    values = (
        selected.groupby(["year", "exporter"]).value.sum(min_count=1).rename("value")
    )
    grid = pd.MultiIndex.from_product(
        [range(start, end + 1), countries], names=["year", "exporter"]
    )
    f = pd.concat([total, values], axis=1).reindex(grid).reset_index()
    f["product_share"] = (
        f.value / f.total.where(f.total.gt(0)) if product != "TOTAL" else np.nan
    )
    base = f[f.year.eq(baseline)].set_index("exporter").value
    f["index"] = f.value / f.exporter.map(base.where(base.gt(0))) * 100
    if regions is not None:
        validate(regions, ["year", "exporter", "hs2"])
        r = regions[regions.exporter.isin(countries)]
        if product != "TOTAL":
            r = r[r.hs2.eq(product)]
        r = r.groupby(["year", "exporter"])[
            ["value", "intra_value", "known_value"]
        ].sum(min_count=1)
        # This table must reconcile to the same product scope before computing shares.
        z = f.set_index(["year", "exporter"]).join(
            r.rename(columns={"value": "region_total"})
        )
        both = z.value.notna() & z.region_total.notna()
        if not np.allclose(
            z.loc[both, "value"], z.loc[both, "region_total"], rtol=2e-8, atol=1e-6
        ):
            raise ValueError("Regional amounts do not reconcile to trade totals.")
        f = z.reset_index().drop(columns="region_total")
    else:
        f["intra_value"] = np.nan
        f["known_value"] = np.nan
    denominator = f.value.where(f.value.gt(0))
    f["intra_share"] = f.intra_value / denominator
    f["region_coverage"] = f.known_value / denominator
    f["intra_upper"] = (
        f.intra_value + (f.value - f.known_value).clip(lower=0)
    ) / denominator
    return f.rename(columns={"exporter": "country"})[TIMELINE_COLUMNS]


def summarize_recovery(timeline, baseline, event, end):
    """Recovery horizon equals displayed end. Missing observations qualify timing."""
    if not baseline < event <= end:
        raise ValueError("Use baseline < event year <= window end.")
    records = []
    for c, d in timeline.groupby("country", sort=False):
        d = d.set_index("year").reindex(range(baseline, end + 1))
        post = d.loc[event:end, "index"]
        observed = post.dropna()
        losses = observed[observed.lt(100 - 1e-9)]
        # A pre-loss above-baseline observation is not a subsequent recovery.
        reached = (
            observed[(observed.index > losses.index[0]) & observed.ge(100 - 1e-9)]
            if len(losses)
            else observed.iloc[:0]
        )
        first = int(reached.index[0]) if len(reached) else None
        endpoint = post.get(end, np.nan)
        if pd.isna(d.loc[baseline, "index"]):
            status = "invalid_baseline"
        elif observed.empty:
            status = "no_observations"
        elif losses.empty:
            status = "never_below" if pd.notna(endpoint) else "endpoint_missing"
        elif first is None:
            status = "not_recovered" if post.notna().all() else "unobserved_incomplete"
        elif pd.isna(endpoint):
            status = "endpoint_missing"
        elif endpoint < 100 - 1e-9:
            status = "relapsed"
        else:
            status = "recovered"
        timing_complete = (
            bool(post.loc[event:first].notna().all())
            if first
            else bool(post.notna().all())
        )
        records.append(
            dict(
                country=c,
                status=status,
                first_at_baseline=first,
                timing_complete=timing_complete,
                observed_years=int(post.notna().sum()),
                expected_years=len(post),
                end_index=endpoint,
                minimum_index=observed.min() if len(observed) else np.nan,
                end_product_change_pp=(
                    d.loc[end, "product_share"] - d.loc[baseline, "product_share"]
                )
                * 100,
                end_intra_change_pp=(
                    d.loc[end, "intra_share"] - d.loc[baseline, "intra_share"]
                )
                * 100,
                end_region_coverage=d.loc[end, "region_coverage"],
                # Bound the change itself, allowing unknown destinations in either year.
                region_change_min_pp=(
                    d.loc[end, "intra_share"] - d.loc[baseline, "intra_upper"]
                )
                * 100,
                region_change_max_pp=(
                    d.loc[end, "intra_upper"] - d.loc[baseline, "intra_share"]
                )
                * 100,
            )
        )
    return pd.DataFrame(records)
