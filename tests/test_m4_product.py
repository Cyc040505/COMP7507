import sys, unittest
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analytics.product import (
    year_metrics,
    validate_trade,
    product_set,
    income_peers,
    chapters,
)
from src.modules import m4_product as m
from src import data_loader
import app


class ProductTests(unittest.TestCase):
    def test_known_rca(self):
        f = pd.DataFrame(
            [
                (2020, "AAA", "01", 80.0),
                (2020, "AAA", "02", 20.0),
                (2020, "BBB", "01", 20.0),
                (2020, "BBB", "02", 80.0),
            ],
            columns=["year", "exporter", "hs2", "value"],
        )
        d = year_metrics(f, 2020)
        r = d[(d.exporter == "AAA") & (d.hs2 == "01")].iloc[0]
        self.assertAlmostEqual(r.share, 0.8)
        self.assertAlmostEqual(r.rca, 1.6)
        self.assertEqual(product_set(d, ["AAA"], ["01"]), ["01"])
        self.assertAlmostEqual(d[d.hs2 == "01"].iloc[0].rca, 1.6)

    def test_zero_missing_duplicates(self):
        f = pd.DataFrame(
            [
                (2020, "AAA", "01", 0.0),
                (2020, "AAA", "02", 10.0),
                (2020, "BBB", "02", 10.0),
            ],
            columns=["year", "exporter", "hs2", "value"],
        )
        d = year_metrics(f, 2020)
        self.assertEqual(d[d.hs2 == "01"].iloc[0].share, 0)
        self.assertTrue(pd.isna(d[d.hs2 == "01"].iloc[0].rca))
        self.assertTrue(d[(d.exporter == "BBB") & (d.hs2 == "01")].empty)
        with self.assertRaises(ValueError):
            validate_trade(pd.concat([f, f.iloc[:1]]))
        f.loc[0, "hs2"] = "1"
        with self.assertRaises(ValueError):
            validate_trade(f)

    def test_all_years_reconcile(self):
        d = m.trade()
        c = data_loader.load_country_year()
        w = data_loader.load_flow_year()
        self.assertFalse(d.attrs["demo"])
        a = d.groupby(["year", "exporter"]).value.sum().sort_index()
        b = c.set_index(["year", "country"]).export_value.sort_index()
        self.assertEqual(list(a.index), list(b.index))
        np.testing.assert_allclose(a, b, rtol=2e-12)
        np.testing.assert_allclose(
            d.groupby("year").value.sum(),
            w.set_index("year").sort_index().export_value,
            rtol=2e-12,
        )
        for year in range(1995, 2025):
            z = m.metrics(year)
            np.testing.assert_allclose(z.groupby("exporter").share.sum(), 1, atol=1e-12)
            self.assertTrue(np.isfinite(z.rca).all())
            totals = z.groupby("exporter").total.first()
            v = z.rca * z.total / totals.sum()
            np.testing.assert_allclose(v.groupby(z.hs2).sum(), 1, atol=1e-12)

    def test_income_scope(self):
        g = pd.DataFrame(
            [
                (2024, "AAA", "100"),
                (2024, "BBB", "149"),
                (2024, "CCC", "151"),
                (2024, "DDD", "NA"),
                (2023, "EEE", "110"),
            ],
            columns=["year", "country", "gdp_per_capita"],
        )
        self.assertEqual(
            income_peers(g, 2024, "AAA", ["AAA", "BBB", "CCC", "DDD", "EEE"])[0],
            ["AAA", "BBB"],
        )
        self.assertEqual(income_peers(g, 2024, "EEE", ["EEE"])[0], [])

    def test_figures(self):
        d = m.metrics(2024)
        codes = product_set(d, m.DEFAULTS)
        for metric in ["share", "rca"]:
            f = m.heat_figure(d, m.DEFAULTS, codes, metric)
            self.assertEqual(list(f.data[0].y), codes)
        self.assertIn("01", m.detail_figure(d, "CHN", "01").data[0].y)
        self.assertIn("SGP", m.eligible(d))
        self.assertIn("SWE", m.eligible(d))
        self.assertNotIn("S19", m.eligible(d))


class DashIntegration(unittest.TestCase):
    def call(self, needle, inputs, states=None, changed=None):
        key = next(k for k in app.app.callback_map if needle in k)
        meta = app.app.callback_map[key]
        values = inputs.copy()
        values.update(states or {})

        def payload(spec):
            return [
                {
                    "id": v["id"],
                    "property": v["property"],
                    "value": values.get(v["id"] + "." + v["property"]),
                }
                for v in spec
            ]

        outs = meta["output"]
        outs = outs if isinstance(outs, list) else [outs]
        output = [
            {"id": o.component_id, "property": o.component_property} for o in outs
        ]
        res = app.server.test_client().post(
            "/_dash-update-component",
            json={
                "output": key,
                "outputs": output if len(output) > 1 else output[0],
                "inputs": payload(meta["inputs"]),
                "state": payload(meta["state"]),
                "changedPropIds": [changed or list(inputs)[0]],
            },
        )
        self.assertEqual(res.status_code, 200, res.data.decode()[:600])
        return res.json["response"]

    def test_render_income_empty_click_download(self):
        base = {
            "global-filters.data": {"year": 2024, "country": "CHN", "product": "TOTAL"},
            "active-module.data": "M4",
            "M4-countries.value": m.DEFAULTS,
            "M4-products.value": [],
            "M4-metric.value": "share",
            "M4-mode.value": "selected",
        }
        z = self.call("M4-graph.figure", base, {"M4-focus.value": "CHN"})
        self.assertEqual(len(z["M4-focus"]["options"]), 3)
        self.assertEqual(z["M4-table"]["data"][0]["year"], 2024)
        r = self.call("M4-graph.figure", base | {"M4-metric.value": "rca"})
        self.assertEqual(
            z["M4-graph"]["figure"]["data"][0]["y"],
            r["M4-graph"]["figure"]["data"][0]["y"],
        )
        inc = self.call("M4-graph.figure", base | {"M4-mode.value": "income"})
        self.assertGreater(len(inc["M4-focus"]["options"]), 1)
        empty = self.call("M4-graph.figure", base | {"M4-countries.value": []})
        self.assertEqual(empty["M4-table"]["data"], [])
        sel = self.call(
            "M4-inspect.value",
            {
                "M4-graph.clickData": {"points": [{"customdata": ["DEU", "87"]}]},
                "M4-focus.options": z["M4-focus"]["options"],
                "global-filters.data": base["global-filters.data"],
                "active-module.data": "M4",
            },
            changed="M4-graph.clickData",
        )
        self.assertEqual(sel["M4-focus"]["value"], "DEU")
        self.assertEqual(sel["M4-inspect"]["value"], "87")
        without_custom = self.call(
            "M4-inspect.value",
            {
                "M4-graph.clickData": {"points": [{"x": "DEU", "y": "87"}]},
                "M4-focus.options": z["M4-focus"]["options"],
                "global-filters.data": base["global-filters.data"],
                "active-module.data": "M4",
            },
            changed="M4-graph.clickData",
        )
        self.assertEqual(without_custom["M4-focus"]["value"], "DEU")
        self.assertEqual(without_custom["M4-inspect"]["value"], "87")

        detail = self.call(
            "M4-detail.figure",
            {
                "M4-focus.value": "DEU",
                "M4-inspect.value": "87",
                "global-filters.data": base["global-filters.data"],
                "active-module.data": "M4",
            },
        )
        self.assertIn("DEU", str(detail["M4-detail-note"]))
        data = self.call(
            "M4-download.data",
            {"M4-download-button.n_clicks": 1},
            {"M4-table.data": z["M4-table"]["data"]},
        )
        self.assertIn("world_pct", data["M4-download"]["data"]["content"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
