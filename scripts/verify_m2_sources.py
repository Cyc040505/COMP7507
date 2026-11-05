"""Audit M2 against official raw files without rebuilding shared analysis tables."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.modules import m2_economy as m
from src.analytics.economy import match_candidates


def sha(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(range(1995, 2024)))
    parser.add_argument("--out", type=Path, default=ROOT / "docs/M2_source_audit.json")
    args = parser.parse_args()
    source = args.source_root
    dictionary = source / "BACI/country_codes_V202601.csv"
    assert sha(dictionary) == sha(ROOT / "data/reference/m2_country_codes_V202601.csv")
    cc = pd.read_csv(dictionary)
    gdp = pd.read_parquet(ROOT / "data/processed/gdp_year.parquet")
    exports = pd.read_parquet(ROOT / "data/processed/country_year.parquet")
    raw = pd.read_csv(source / "CHELEM/gdp_v202502.csv")
    raw = raw.loc[raw.indicator.eq("GDP-VAL")].melt(
        id_vars=["country", "indicator"], value_vars=[f"v{y}" for y in args.years],
        var_name="year", value_name="raw_gdp",
    )
    raw["year"] = raw.year.str[1:].astype(int)
    joined = raw.merge(gdp, on=["country", "year"], how="left", validate="one_to_one")
    np.testing.assert_allclose(pd.to_numeric(joined.raw_gdp, errors="coerce"),
                               pd.to_numeric(joined.gdp, errors="coerce"),
                               rtol=1e-12, equal_nan=True)
    report = {"trade_source": "BACI HS92 V202601", "gdp_source": "CHELEM GDP-VAL V202502",
              "gdp_rows_checked": len(joined), "years": [], "default_2023": {},
              "historical_scope_policy": "BEL <=1998 and SDN <=2011 excluded conservatively; no territorial GDP remapping.",
              "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [
                  ROOT / "data/processed/country_year.parquet", ROOT / "data/processed/gdp_year.parquet",
                  ROOT / "data/reference/m2_country_codes_V202601.csv"]}}
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.register("cc", cc)
    for year in args.years:
        path = source / f"BACI/BACI_HS92_Y{year}_V202601.csv"
        totals = con.execute("""
            SELECT c.country_iso3 AS country, sum(r.v) AS raw_exports,
                   list(DISTINCT r.i) AS raw_codes
            FROM read_csv_auto(?) r LEFT JOIN cc c ON r.i=c.country_code
            GROUP BY c.country_iso3
        """, [str(path)]).df()
        stored = exports.loc[exports.year.eq(year)]
        checked = totals.merge(stored, on="country", how="outer", indicator=True, validate="one_to_one")
        assert checked._merge.eq("both").all(), f"Country keys differ in {year}"
        np.testing.assert_allclose(checked.raw_exports, checked.export_value, rtol=2e-10, atol=1e-7)
        rows = m.data_for_year(year)
        valid = rows[rows.valid]
        # Independent direct inequality, all eligible anchors (not only the six).
        checks = 0
        for mode in ["gdp", "export_value"]:
            for factor in [1.25, 1.5]:
                for a in valid.itertuples():
                    value = getattr(a, mode)
                    expected = set(valid.loc[(valid[mode] / value >= 1 / factor)
                                             & (valid[mode] / value <= factor)
                                             & valid.country.ne(a.country), "country"])
                    actual = set(match_candidates(rows, a.country, mode, factor).country)
                    assert actual == expected, (year, a.country, mode, factor)
                    checks += 1
        historic = checked[checked.country.isin(["BEL", "SDN"])][["country", "raw_codes"]]
        report["years"].append({"year": year, "export_country_keys": len(checked),
            "max_relative_export_error": float(((checked.raw_exports - checked.export_value).abs() / checked.raw_exports.abs()).max()),
            "eligible_pairs": len(valid), "matching_combinations_checked": checks,
            "historical_codes": [{"country": r.country, "raw_codes": [int(x) for x in r.raw_codes]} for r in historic.itertuples()]})
        if year == 2023:
            for code in ["DEU", "JPN"]:
                a = rows[rows.country.eq(code)].iloc[0]
                report["default_2023"][code] = {"gdp_million_usd": a.gdp, "exports_thousand_usd": a.export_value, "exports_gdp_ratio": a.export_gdp_ratio}
            report["default_2023"]["matches"] = {
                f"{mode}_{factor}": match_candidates(rows, "DEU", mode, factor).country.tolist()
                for mode in ["gdp", "export_value"] for factor in [1.25, 1.5]}
        print(f"{year}: {len(checked)} export totals, {len(valid)} valid pairs, {checks} matching combinations verified", flush=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Audit passed: {args.out}")


if __name__ == "__main__":
    main()
