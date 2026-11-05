import unittest
from pathlib import Path
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analytics.time_change import (
    aggregate_regions,
    build_timeline,
    summarize_recovery,
)


class TimeCalculations(unittest.TestCase):
    def sample(self):
        return pd.DataFrame(
            [
                (y, "AAA", p, v)
                for y, a, b in [
                    (2019, 20, 80),
                    (2020, 16, 64),
                    (2021, 33, 77),
                    (2022, 18, 72),
                ]
                for p, v in [("01", a), ("02", b)]
            ],
            columns=["year", "exporter", "hs2", "value"],
        )

    def test_fixed_product_denominator_and_recovery_relapse(self):
        f = build_timeline(self.sample(), None, ["AAA"], "01", 2019, 2019, 2022)
        np.testing.assert_allclose(f["index"], [100, 80, 165, 90])
        np.testing.assert_allclose(f.product_share, [0.2, 0.2, 0.3, 0.2])
        r = summarize_recovery(f, 2019, 2020, 2022).iloc[0]
        self.assertEqual(r.first_at_baseline, 2021)
        self.assertEqual(r.status, "relapsed")
        self.assertAlmostEqual(r.end_index, 90)

    def test_missing_year_is_not_zero_or_exact_recovery_time(self):
        d = self.sample()
        d = d[d.year.ne(2021)].copy()
        d["value"] = d.value.astype(float)
        d.loc[d.year.eq(2022), "value"] *= 1.3
        f = build_timeline(d, None, ["AAA"], "TOTAL", 2019, 2019, 2022)
        self.assertTrue(pd.isna(f.loc[f.year.eq(2021), "index"].iloc[0]))
        r = summarize_recovery(f, 2019, 2020, 2022).iloc[0]
        self.assertFalse(r.timing_complete)
        self.assertEqual(r.first_at_baseline, 2022)

    def test_zero_baseline_and_absent_product_are_unknown(self):
        d = self.sample()
        d.loc[d.year.eq(2019) & d.hs2.eq("01"), "value"] = 0
        f = build_timeline(d, None, ["AAA"], "01", 2019, 2019, 2022)
        self.assertTrue(f["index"].isna().all())
        self.assertEqual(
            summarize_recovery(f, 2019, 2020, 2022).iloc[0].status, "invalid_baseline"
        )
        z = build_timeline(d, None, ["AAA"], "99", 2019, 2019, 2022)
        self.assertTrue(z.value.isna().all())

    def test_no_decline_is_not_called_recovery(self):
        d = self.sample()
        d.loc[d.year.eq(2020), "value"] *= 2
        d.loc[d.year.eq(2022), "value"] *= 2
        f = build_timeline(d, None, ["AAA"], "TOTAL", 2019, 2019, 2022)
        self.assertEqual(
            summarize_recovery(f, 2019, 2020, 2022).iloc[0].status, "never_below"
        )

    def test_above_baseline_before_a_later_loss_is_not_a_recovery(self):
        d = self.sample()
        d["value"] = d.value.astype(float)
        for year, multiplier in [(2020, 1.5), (2021, 0.5), (2022, 1.3)]:
            d.loc[d.year.eq(year), "value"] *= multiplier
        f = build_timeline(d, None, ["AAA"], "TOTAL", 2019, 2019, 2022)
        r = summarize_recovery(f, 2019, 2020, 2022).iloc[0]
        self.assertEqual(r.first_at_baseline, 2022)
        self.assertEqual(r.status, "recovered")
        d.loc[d.year.eq(2022), "value"] *= 0.5
        f = build_timeline(d, None, ["AAA"], "TOTAL", 2019, 2019, 2022)
        self.assertEqual(
            summarize_recovery(f, 2019, 2020, 2022).iloc[0].status, "not_recovered"
        )

    def test_unknown_region_retains_total_and_bounds(self):
        edges = pd.DataFrame(
            [
                (2020, "AAA", "BBB", "01", 40),
                (2020, "AAA", "CCC", "01", 30),
                (2020, "AAA", "XXX", "01", 30),
                (2020, "XXX", "BBB", "01", 20),
            ],
            columns=["year", "exporter", "importer", "hs2", "value"],
        )
        meta = pd.DataFrame(
            [("AAA", "Asia"), ("BBB", "Asia"), ("CCC", "Europe"), ("XXX", "No")],
            columns=["iso3", "region"],
        )
        z = aggregate_regions(edges, meta)
        a = z[z.exporter.eq("AAA")].iloc[0]
        self.assertEqual(a.value, 100)
        self.assertEqual(a.known_value, 70)
        self.assertEqual(a.intra_value, 40)
        self.assertTrue(pd.isna(z[z.exporter.eq("XXX")].iloc[0].intra_value))
        product = edges.groupby(["year", "exporter", "hs2"], as_index=False).value.sum()
        f = build_timeline(product, z, ["AAA"], "01", 2020, 2020, 2020).iloc[0]
        self.assertAlmostEqual(f.intra_share, 0.4)
        self.assertAlmostEqual(f.intra_upper, 0.7)
        self.assertAlmostEqual(f.region_coverage, 0.7)

    def test_duplicate_keys_and_bad_windows_rejected(self):
        with self.assertRaises(ValueError):
            build_timeline(
                pd.concat([self.sample(), self.sample()]),
                None,
                ["AAA"],
                "01",
                2019,
                2019,
                2022,
            )
        with self.assertRaises(ValueError):
            build_timeline(self.sample(), None, ["AAA"], "01", 2019, 2021, 2020)
        f = build_timeline(self.sample(), None, ["AAA"], "TOTAL", 2019, 2019, 2022)
        with self.assertRaises(ValueError):
            summarize_recovery(f, 2019, 2018, 2022)

    def test_empty_selection_and_total_product_share(self):
        f = build_timeline(self.sample(), None, [], "TOTAL", 2019, 2019, 2022)
        self.assertTrue(f.empty)
        f = build_timeline(self.sample(), None, ["AAA"], "TOTAL", 2019, 2019, 2022)
        self.assertTrue(f.product_share.isna().all())

    def test_identical_metadata_rows_do_not_multiply_trade(self):
        e = pd.DataFrame(
            [(2020, "AAA", "AAA", "01", 10)],
            columns=["year", "exporter", "importer", "hs2", "value"],
        )
        m = pd.DataFrame([("AAA", "Asia"), ("AAA", "Asia")], columns=["iso3", "region"])
        self.assertEqual(aggregate_regions(e, m).iloc[0].intra_value, 10)
        m.loc[1, "region"] = "Europe"
        with self.assertRaises(ValueError):
            aggregate_regions(e, m)


if __name__ == "__main__":
    unittest.main()
