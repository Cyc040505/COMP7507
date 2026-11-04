"""Pure M1 calculations: distance vs partner export share.

Presentation filters (year / exporter / product / distance metric) never define
reference totals. The partner share denominator is always the exporter's total
exports inside the selected year and product scope, and only the export direction
is used (imports are never added).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_METRIC = "distw"

METRIC_LABELS = {
    "dist": "Simple distance",
    "distw": "Weighted distance",
    "distcap": "Capital distance",
}

_DISTANCE_CANDIDATES = ("dist", "distw", "distcap")


def _pick_metric(geodist: pd.DataFrame, requested: str) -> str:
    """Resolve the distance column to use.

    Real GeoDist tables carry ``dist``, ``distw`` and ``distcap``. The demo
    fallback only carries ``dist``, so a requested ``distw`` gracefully falls
    back to ``dist`` rather than producing a broken figure.
    """
    if requested in geodist.columns:
        return requested
    for candidate in _DISTANCE_CANDIDATES:
        if candidate in geodist.columns:
            return candidate
    raise ValueError("GeoDist table has no usable distance column.")


def trade_by_partner(
    pair: pd.DataFrame,
    exporter: str,
    year,
    hs2: str | None = None,
) -> pd.DataFrame:
    """Aggregate bilateral exports to one row per partner for one scope."""
    d = pair.loc[(pair["exporter"] == exporter) & (pair["year"] == year)].copy()
    if hs2 is not None:
        d = d.loc[d["hs2"].astype(str) == hs2]
    # Self-trade is not a partner relationship; keep only cross-border rows.
    d = d.loc[d["importer"] != exporter]
    if d.empty:
        return pd.DataFrame(columns=["partner", "value"])
    out = (
        d.groupby("importer", as_index=False)["value"].sum()
        .rename(columns={"importer": "partner"})
    )
    return out


def attach_geography(
    trade: pd.DataFrame,
    geodist: pd.DataFrame,
    exporter: str,
    metric: str = DEFAULT_METRIC,
) -> tuple[pd.DataFrame, str]:
    """Left-join GeoDist onto partner rows; missing geometry stays in the frame."""
    metric_used = _pick_metric(geodist, metric)
    g = geodist.loc[geodist["iso_o"] == exporter].copy()
    g = g.drop_duplicates(["iso_o", "iso_d"])

    keep = ["iso_d", metric_used]
    for aux in ("contig", "comlang_off"):
        if aux in g.columns:
            keep.append(aux)
    g = g[keep]

    out = trade.merge(g, left_on="partner", right_on="iso_d", how="left")
    out["distance"] = pd.to_numeric(out[metric_used], errors="coerce")
    out["has_distance"] = out["distance"].notna() & (out["distance"] > 0)
    for aux in ("contig", "comlang_off"):
        if aux not in out.columns:
            out[aux] = np.nan
    return out, metric_used


def partner_frame(
    pair: pd.DataFrame,
    geodist: pd.DataFrame,
    meta: pd.DataFrame,
    exporter: str,
    year,
    hs2: str | None = None,
    metric: str = DEFAULT_METRIC,
) -> tuple[pd.DataFrame, str]:
    """Build the analysis frame: partner, value, distance, share and aux flags."""
    trade = trade_by_partner(pair, exporter, year, hs2=hs2)
    if trade.empty:
        return trade, _pick_metric(geodist, metric)

    out, metric_used = attach_geography(trade, geodist, exporter, metric)

    total = float(out["value"].sum())
    out["share_pct"] = np.where(total > 0, out["value"] / total * 100.0, np.nan)

    names = meta.drop_duplicates("iso3").set_index("iso3")
    if "name" in names.columns:
        out["name"] = out["partner"].map(names["name"]).fillna(out["partner"])
    else:
        out["name"] = out["partner"]
    if "region" in names.columns:
        out["region"] = out["partner"].map(names["region"])
    else:
        out["region"] = None
    return out, metric_used


def spearman_rho(frame: pd.DataFrame) -> float | None:
    """Spearman correlation between log(distance) and partner share."""
    valid = frame.loc[frame["has_distance"] & frame["share_pct"].notna()]
    if len(valid) < 2:
        return None
    # Rank-based correlation without a scipy dependency: rank both series and
    # take the ordinary (Pearson) correlation of the ranks.
    dist_rank = pd.Series(np.log(valid["distance"]), index=valid.index).rank()
    share_rank = valid["share_pct"].rank()
    return float(dist_rank.corr(share_rank))


def summarize(frame: pd.DataFrame, metric_used: str) -> dict:
    """Descriptive statistics for the current selection."""
    n = int(len(frame))
    valid = frame.loc[frame["has_distance"] & frame["share_pct"].notna()]
    n_missing = int((~frame["has_distance"]).sum())
    n_zero = int((frame["share_pct"] == 0).sum())
    total = float(frame["value"].sum()) if n else 0.0
    coverage = (n - n_missing) / n if n else 0.0

    if n and not valid.empty:
        wavg = float(np.average(valid["distance"], weights=valid["value"]))
    else:
        wavg = None

    top = None
    top3_share = None
    if n:
        ordered = frame.sort_values("value", ascending=False)
        top = ordered.iloc[0]
        top3_share = float(ordered.head(3)["share_pct"].sum())

    rho = spearman_rho(frame)

    return {
        "n": n,
        "n_missing": n_missing,
        "n_zero": n_zero,
        "coverage": coverage,
        "total": total,
        "weighted_distance": wavg,
        "spearman": rho,
        "top_partner": top["partner"] if top is not None else None,
        "top_name": top["name"] if top is not None else None,
        "top_share": float(top["share_pct"]) if top is not None else None,
        "top3_share": top3_share,
        "metric_used": metric_used,
    }


def exceptions(
    frame: pd.DataFrame,
    top_n: int = 40,
    limit_per_side: int = 5,
) -> list[dict]:
    """Return near-but-weak and far-but-strong partners among meaningful flows.

    Only the ``top_n`` partners by export value are eligible, which keeps the
    list free of economically irrelevant micro-partners. Within that pool,
    ``near`` = distance at or below the 25th percentile and ``far`` = distance at
    or above the 75th percentile; ``weak`` / ``strong`` is measured against the
    median partner share. Each side is capped at ``limit_per_side``.
    """
    meaningful = frame.sort_values("value", ascending=False).head(top_n)
    valid = meaningful.loc[
        meaningful["has_distance"] & meaningful["share_pct"].notna()
    ].copy()
    if len(valid) < 4:
        return []

    near_cut = float(valid["distance"].quantile(0.25))
    far_cut = float(valid["distance"].quantile(0.75))
    median_share = float(valid["share_pct"].median())

    near_low = valid[
        (valid["distance"] <= near_cut) & (valid["share_pct"] < median_share)
    ].sort_values(["share_pct", "distance"])
    far_high = valid[
        (valid["distance"] >= far_cut) & (valid["share_pct"] > median_share)
    ].sort_values("share_pct", ascending=False)

    rows: list[dict] = []
    for kind, subset in (("Near but weak", near_low), ("Far but strong", far_high)):
        for r in subset.head(limit_per_side).itertuples(index=False):
            rows.append(
                {
                    "kind": kind,
                    "partner": r.partner,
                    "name": r.name,
                    "distance": round(float(r.distance), 1),
                    "value": round(float(r.value), 3),
                    "share_pct": round(float(r.share_pct), 3),
                    "contig": "Yes" if r.contig == 1 else ("No" if r.contig == 0 else ""),
                    "comlang_off": "Yes" if r.comlang_off == 1 else ("No" if r.comlang_off == 0 else ""),
                }
            )
    return rows


def loglog_trend(frame: pd.DataFrame) -> tuple[float, float] | None:
    """Ordinary least-squares fit of log10(share) on log10(distance).

    Used only to draw a descriptive reference line; it is not a gravity model and
    is never presented as a causal estimate.
    """
    valid = frame.loc[
        frame["has_distance"]
        & frame["share_pct"].notna()
        & (frame["share_pct"] > 0)
    ]
    if len(valid) < 2:
        return None
    x = np.log10(valid["distance"])
    y = np.log10(valid["share_pct"])
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def analyze(
    pair: pd.DataFrame,
    geodist: pd.DataFrame,
    meta: pd.DataFrame,
    exporter: str,
    year,
    hs2: str | None = None,
    metric: str = DEFAULT_METRIC,
) -> dict:
    """Run the full M1 computation for one selection."""
    frame, metric_used = partner_frame(
        pair, geodist, meta, exporter, year, hs2=hs2, metric=metric
    )
    if frame.empty:
        return {
            "frame": frame,
            "metric_used": metric_used,
            "stats": {
                "n": 0,
                "n_missing": 0,
                "n_zero": 0,
                "coverage": 0.0,
                "total": 0.0,
                "weighted_distance": None,
                "spearman": None,
                "top_partner": None,
                "top_name": None,
                "top_share": None,
                "top3_share": None,
                "metric_used": metric_used,
            },
            "exceptions": [],
        }
    return {
        "frame": frame,
        "metric_used": metric_used,
        "stats": summarize(frame, metric_used),
        "exceptions": exceptions(frame),
    }
