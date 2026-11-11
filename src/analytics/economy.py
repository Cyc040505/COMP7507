"""M2 same-year scale comparisons. BACI: thousand USD; CHELEM: million USD.

No imputation, geographic remapping, or mutation of the shared loader frames.
"""

import numpy as np
import pandas as pd

FOCUS_COUNTRIES = ("USA", "DEU", "CHN", "MEX", "NLD", "ITA")
MODES = {"gdp": "GDP", "export_value": "exports"}
# Explicit BACI entities, not a prefix-based country filter.
SPECIAL_CODES = {490, 697, 711}  # Other Asia nes, Europe EFTA nes, SACU


def country_names(reference):
    # Modern entries precede historical aliases for BEL, DEU and SDN in BACI.
    rows = reference.drop_duplicates("country_iso3", keep="first")
    return rows.set_index("country_iso3").country_name.to_dict()


def prepare_year(exports, gdp, reference, year):
    """Outer-join observed source entities and retain an auditable exclusion reason.

    A source entity with no row in either input is outside this year's universe.
    Historical territorial mismatches are excluded rather than joined to a GDP
    series for a different territory. The original shared tables remain intact.
    """
    if year not in range(1995, 2024):
        raise ValueError("M2 requires a historical year from 1995 to 2023.")
    if exports.attrs.get("demo") or gdp.attrs.get("demo"):
        raise ValueError("M2 requires real BACI and CHELEM tables; demo data cannot support findings.")
    for data, cols in [(exports, ["export_value"]), (gdp, ["gdp"])]:
        if not {"year", "country", *cols}.issubset(data.columns):
            raise ValueError("An M2 source table has missing columns.")
        if data.duplicated(["year", "country"]).any():
            raise ValueError("Duplicate country/year keys in an M2 source table.")
    e = exports.loc[exports.year.eq(year), ["country", "export_value"]]
    g = gdp.loc[gdp.year.eq(year), ["country", "gdp"]]
    if e.empty or g.empty:
        raise ValueError(f"Missing source data for {year}; M2 does not substitute another year.")
    rows = e.merge(g, on="country", how="outer", validate="one_to_one")
    names = country_names(reference)
    eligible = set(reference.loc[~reference.country_code.isin(SPECIAL_CODES), "country_iso3"])
    rows["name"] = rows.country.map(names).fillna(rows.country).fillna("Unidentified entity")
    for col in ["gdp", "export_value"]:
        rows[col] = pd.to_numeric(rows[col], errors="coerce")
    rows["exclusion"] = ""
    rows.loc[~rows.country.isin(eligible), "exclusion"] = "Not an eligible BACI country/economy"
    historical = ((rows.country.eq("BEL") & (year <= 1998))
                  | (rows.country.eq("SDN") & (year <= 2011)))
    rows.loc[historical, "exclusion"] = "Historical trade/GDP territorial scope mismatch"
    for col, label in [("gdp", "GDP"), ("export_value", "exports")]:
        missing = ~np.isfinite(rows[col])
        invalid = rows[col].le(0) & ~missing
        for mask, reason in [(missing, f"Missing/non-finite {label}"), (invalid, f"Non-positive {label}")]:
            existing = rows.exclusion.ne("")
            # GDP and trade problems are both visible; entity exclusions take priority.
            numeric = rows.exclusion.str.startswith(("Missing", "Non-positive"))
            rows.loc[mask & (~existing | numeric), "exclusion"] = (
                rows.loc[mask & (~existing | numeric), "exclusion"]
                .map(lambda s: f"{s}; {reason}" if s else reason)
            )
    rows["valid"] = rows.exclusion.eq("")
    rows["year"] = year
    rows["gdp_billion_usd"] = rows.gdp / 1000
    rows["exports_billion_usd"] = rows.export_value / 1_000_000
    rows["export_gdp_ratio"] = np.nan
    mask = rows.valid
    rows.loc[mask, "export_gdp_ratio"] = rows.loc[mask, "export_value"] / (rows.loc[mask, "gdp"] * 1000)
    return rows.sort_values(["name", "country"]).reset_index(drop=True)


def match_candidates(rows, anchor, mode="gdp", factor=1.25):
    """Full eligible pool, one dimension, inclusive symmetric multiplicative bounds."""
    if mode not in MODES or factor not in (1.25, 1.5):
        raise ValueError("Choose similar GDP/exports and a 1.25× or 1.5× window.")
    valid = rows[rows.valid]
    a = valid[valid.country.eq(anchor)]
    result = valid.iloc[:0].copy()
    if a.empty:
        result["matching_ratio"] = pd.Series(dtype=float)
        return result
    ratios = valid[mode] / float(a.iloc[0][mode])
    keep = ratios.between(1 / factor, factor, inclusive="both") & valid.country.ne(anchor)
    result = valid.loc[keep].copy()
    result["matching_ratio"] = ratios.loc[keep]
    result["_distance"] = np.abs(np.log(result.matching_ratio))
    return result.sort_values(["_distance", "country"]).drop(columns="_distance")


def display_candidates(rows):
    """Year-specific union of all six anchors' widest one-dimensional pools.

    Display-only: do not change the matching rules or exported source universe.
    Invalid anchors never contribute a range or a plotted point.
    """
    valid = rows[rows.valid]
    keep = valid.country.isin(FOCUS_COUNTRIES)
    anchors = valid[valid.country.isin(FOCUS_COUNTRIES)]
    for anchor in anchors.itertuples():
        for measure in MODES:
            keep |= (valid[measure] / getattr(anchor, measure)).between(1 / 1.5, 1.5, inclusive="both")
    return valid.loc[keep].copy()


def evidence_frame(rows, anchor, comparator, mode, factor):
    """Download includes the full source universe, matches, and exclusion reasons."""
    peers = match_candidates(rows, anchor, mode, factor)
    out = rows.copy()
    out["is_match"] = out.country.isin(peers.country)
    out["is_anchor"] = out.country.eq(anchor)
    out["is_comparator"] = out.country.eq(comparator)
    out["anchor"] = anchor
    out["comparator"] = comparator
    out["matching_dimension"] = mode
    out["factor"] = factor
    out["matching_ratio"] = out.country.map(peers.set_index("country").matching_ratio)
    for key in ("gdp_anchor_100", "exports_anchor_100", "export_gdp_gap_pp"):
        out[key] = np.nan
    a = rows[rows.valid & rows.country.eq(anchor)]
    if not a.empty:
        a = a.iloc[0]
        out.loc[out.valid, "gdp_anchor_100"] = 100 * out.loc[out.valid, "gdp"] / a.gdp
        out.loc[out.valid, "exports_anchor_100"] = 100 * out.loc[out.valid, "export_value"] / a.export_value
        out.loc[out.valid, "export_gdp_gap_pp"] = 100 * (out.loc[out.valid, "export_gdp_ratio"] - a.export_gdp_ratio)
    out["trade_source"] = "BACI HS92 V202601"
    out["gdp_source"] = "CHELEM GDP-VAL V202502"
    return out.rename(columns={"gdp": "gdp_million_current_usd", "export_value": "exports_thousand_current_usd"})
