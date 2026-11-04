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

    def test_two_year_missing_and_same_year_world(self):
        from src.analytics.product import (
            two_year_metrics,
            spread_finding,
            income_allowed,
        )

        f = pd.DataFrame(
            [
                (2010, "AAA", "01", 10.0),
                (2010, "BBB", "02", 90.0),
                (2023, "AAA", "01", 30.0),
                (2023, "AAA", "02", 20.0),
                (2023, "BBB", "02", 50.0),
            ],
            columns=["year", "exporter", "hs2", "value"],
        )
        d = two_year_metrics(f, "AAA", 2023, 2010, ["01", "02"])
        absent = d[d.hs2 == "02"].iloc[0]
        self.assertTrue(absent.missing_endpoint)
        self.assertTrue(pd.isna(absent.change_pp))
        self.assertAlmostEqual(absent.world_share_base, 0.9)
        known = d[d.hs2 == "01"].iloc[0]
        self.assertAlmostEqual(known.share_base, 1)
        self.assertAlmostEqual(known.share_current, 0.6)
        self.assertAlmostEqual(known.rca_base, 10)
        self.assertAlmostEqual(known.rca_current, 2)
        self.assertTrue(income_allowed(2023))
        self.assertFalse(income_allowed(2024))
        finding = spread_finding(year_metrics(f, 2023), ["AAA", "BBB"], ["02"])
        self.assertEqual(finding["hs2"], "02")

    def test_highlight_preserves_data_and_ranking(self):
        d = m.metrics(2023)
        a = m.detail_figure(d, "RUS", "27")
        b = m.detail_figure(d, "RUS", "31")
        self.assertEqual(list(a.data[0].y), list(b.data[0].y))
        for old, new in zip(a.data, b.data):
            np.testing.assert_allclose(old.x, new.x, equal_nan=True)
            self.assertEqual(old.marker.color, new.marker.color)
        codes = list(b.data[0].y)
        index = codes.index("31")
        self.assertEqual(b.data[0].marker.opacity[index], 1)
        self.assertEqual(b.layout.shapes[0].y0, index - 0.46)
        self.assertIn("<b>", b.layout.yaxis.ticktext[index])
        added = m.detail_figure(d, "RUS", "01")
        self.assertIn("01", added.data[0].y)
        self.assertEqual(added.data[0].marker.opacity[-1], 1)

    def test_two_year_highlight_keeps_missing_endpoints(self):
        from src.analytics.product import two_year_metrics

        f = pd.DataFrame(
            [(2010, "AAA", "01", 10.0), (2023, "AAA", "02", 20.0)],
            columns=["year", "exporter", "hs2", "value"],
        )
        rows = two_year_metrics(f, "AAA", 2023, 2010, ["01", "02"])
        fig = m.comparison_figure(rows, 2010, 2023, "01")
        self.assertEqual(fig.data[0].marker.opacity[0], 1)
        self.assertTrue(pd.isna(fig.data[1].x[0]))
        self.assertTrue(rows.missing_endpoint.all())


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

    def inputs(self, step="structure", **changes):
        r = m.recipe(step)
        values = {
            "M4-filters.data": {"year": 2023, "country": "CHN", "product": "TOTAL"},
            "active-module.data": "M4",
            "M4-countries.value": r["countries"],
            "M4-products.value": r["products"],
            "M4-metric.value": r["metric"],
            "M4-mode.value": r["mode"],
            "M4-pool.value": "focus",
            "M4-factor.value": 1.25,
            "M4-case.data": r,
            "M4-baseline.value": 2010,
            "M4-detail-view.value": r["view"],
        }
        values.update(changes)
        return values

    def test_guided_income_and_sensitivity(self):
        z = self.call("M4-graph.figure", self.inputs())
        c = z["M4-comparison"]["data"]
        self.assertEqual(c["selection_state"], "Guided case")
        self.assertEqual(c["countries"], ["CHN", "MEX"])
        self.assertEqual(c["sensitivity"]["1.25"], c["sensitivity"]["1.5"])
        self.assertTrue(z["M4-countries"]["disabled"])
        self.assertIn("similar nominal GDP", z["M4-conclusion"]["children"])
        self.assertTrue(all(r["gdp_cap"] > 0 for r in z["M4-table"]["data"]))

    def test_forecast_exclusion_does_not_substitute_year(self):
        z = self.call(
            "M4-graph.figure",
            self.inputs(
                **{
                    "M4-filters.data": {
                        "year": 2024,
                        "country": "CHN",
                        "product": "TOTAL",
                    }
                }
            ),
        )
        self.assertEqual(z["M4-comparison"]["data"]["countries"], [])
        self.assertEqual(z["M4-comparison"]["data"]["year"], 2024)
        self.assertIn("no previous-year GDP", z["M4-scope"]["children"])
        manual = self.call(
            "M4-graph.figure",
            self.inputs(
                **{
                    "M4-filters.data": {
                        "year": 2024,
                        "country": "CHN",
                        "product": "TOTAL",
                    },
                    "M4-mode.value": "selected",
                }
            ),
        )
        self.assertEqual(len(manual["M4-focus"]["options"]), 2)

    def test_custom_scope_and_empty(self):
        z = self.call("M4-graph.figure", self.inputs(**{"M4-products.value": ["85"]}))
        self.assertEqual(z["M4-comparison"]["data"]["case_step"], "custom")
        self.assertIn("HS85", z["M4-evidence"]["children"])
        self.assertNotIn("HS27", z["M4-evidence"]["children"])
        self.assertEqual(z["M4-graph"]["figure"]["data"][0]["y"], ["85"])
        empty = self.call(
            "M4-graph.figure",
            self.inputs(**{"M4-mode.value": "selected", "M4-countries.value": []}),
        )
        self.assertEqual(empty["M4-table"]["data"], [])

    def test_no_false_difference_for_equal_or_incomparable_baskets(self):
        from unittest.mock import patch

        values = self.inputs(
            **{
                "M4-mode.value": "selected",
                "M4-countries.value": ["CHN", "USA"],
                "M4-products.value": ["01", "02"],
            }
        )
        for rows, phrase in [
            (
                [
                    (2023, "CHN", "01", 10.0),
                    (2023, "CHN", "02", 10.0),
                    (2023, "USA", "01", 10.0),
                    (2023, "USA", "02", 10.0),
                ],
                "below 0.05",
            ),
            (
                [(2023, "CHN", "01", 10.0), (2023, "USA", "02", 10.0)],
                "No displayed chapter",
            ),
        ]:
            frame = pd.DataFrame(rows, columns=["year", "exporter", "hs2", "value"])
            with patch.object(m, "metrics", return_value=year_metrics(frame, 2023)):
                result = self.call("M4-graph.figure", values)
                self.assertIn(phrase, result["M4-evidence"]["children"])
                self.assertNotIn(
                    "export baskets differ", result["M4-conclusion"]["children"]
                )

    def test_local_controls_and_no_global_console(self):
        result = self.call(
            "M4-case.data",
            {"active-module.data": "M4", "M4-step-specialization.n_clicks": 1},
            changed="M4-step-specialization.n_clicks",
        )
        self.assertEqual(result["M4-case"]["data"]["product"], "95")
        case = result["M4-case"]["data"]
        settings = self.call(
            "M4-countries.options",
            {"active-module.data": "M4", "M4-case.data": case},
            changed="M4-case.data",
        )
        self.assertEqual(settings["M4-year"]["value"], 2023)
        self.assertEqual(settings["M4-anchor"]["value"], "CHN")
        local = self.call(
            "M4-filters.data", {"M4-year.value": 2024, "M4-anchor.value": "MEX"}
        )
        self.assertEqual(local["M4-filters"]["data"], {"year": 2024, "country": "MEX"})
        layout = app.server.test_client().get("/_dash-layout").get_data(as_text=True)
        for control in [
            "global-year",
            "global-country",
            "global-product",
            "global-indicator",
        ]:
            self.assertNotIn('"id":"' + control + '"', layout)
        for meta in app.app.callback_map.values():
            outputs = meta["output"]
            outputs = outputs if isinstance(outputs, list) else [outputs]
            if any(str(o.component_id).startswith("M4-") for o in outputs):
                self.assertFalse(
                    any(i["id"] == "global-filters" for i in meta["inputs"])
                )

    def test_specialization_click_and_two_year_export(self):
        z = self.call("M4-graph.figure", self.inputs("specialization"))
        self.assertIn("HS95", z["M4-evidence"]["children"])
        self.assertIn("smaller export share", z["M4-conclusion"]["children"])
        c = z["M4-comparison"]["data"]
        selected = self.call(
            "M4-inspect.value",
            {
                "M4-graph.clickData": {"points": [{"x": "CHN", "y": "95"}]},
                "M4-comparison.data": c,
                "M4-case.data": m.recipe("specialization"),
                "active-module.data": "M4",
            },
            changed="M4-graph.clickData",
        )
        self.assertEqual(selected["M4-focus"]["value"], "CHN")
        self.assertEqual(selected["M4-inspect"]["value"], "95")
        changed = self.call("M4-graph.figure", self.inputs("change"))["M4-comparison"][
            "data"
        ]
        detail_inputs = {
            "M4-focus.value": "CHN",
            "M4-inspect.value": "87",
            "M4-comparison.data": changed,
            "M4-detail-view.value": "change",
            "M4-baseline.value": 2010,
            "active-module.data": "M4",
        }
        detail = self.call("M4-detail.figure", detail_inputs)
        row = next(r for r in detail["M4-detail-table"]["data"] if r["hs2"] == "87")
        self.assertAlmostEqual(row["change_pp"], 5.399088 - 2.082040, places=3)
        self.assertLess(row["current_rca"], 1)
        self.assertFalse(row["missing_endpoint"])
        self.assertEqual(row["baseline"], 2010)
        self.assertEqual(row["reference_scope"], changed["reference_scope"])
        invalid = self.call(
            "M4-detail.figure", detail_inputs | {"M4-baseline.value": 2023}
        )
        self.assertEqual(invalid["M4-detail-table"]["data"], [])
        data = self.call(
            "M4-detail-download.data",
            {"M4-detail-download-button.n_clicks": 1},
            {"M4-detail-table.data": detail["M4-detail-table"]["data"]},
        )
        self.assertIn("current_rca", data["M4-detail-download"]["data"]["content"])
        heat = self.call(
            "M4-download.data",
            {"M4-download-button.n_clicks": 1},
            {"M4-table.data": z["M4-table"]["data"]},
        )
        self.assertIn("income_factor", heat["M4-download"]["data"]["content"])

    def test_six_country_scope_rejects_stale_browser_selections(self):
        z = self.call("M4-graph.figure", self.inputs(**{
            "M4-mode.value": "selected", "M4-countries.value": ["RUS", "CHN", "SGP"],
            "M4-pool.value": "all",
        }))
        self.assertEqual(z["M4-comparison"]["data"]["countries"], ["CHN"])
        self.assertIn("Outside the six project cases", z["M4-scope"]["children"])
        z = self.call("M4-graph.figure", self.inputs(**{
            "M4-filters.data": {"year": 2023, "country": "RUS"},
            "M4-pool.value": "all",
        }))
        self.assertEqual(z["M4-comparison"]["data"]["countries"], [])

    def test_anchor_only_does_not_widen_or_claim_comparison(self):
        z = self.call("M4-graph.figure", self.inputs(**{
            "M4-filters.data": {"year": 2023, "country": "USA"},
        }))
        self.assertEqual(z["M4-comparison"]["data"]["countries"], ["USA"])
        self.assertIn("Only the anchor qualifies", z["M4-scope"]["children"])
        self.assertNotIn("export baskets differ", z["M4-conclusion"]["children"])

    def test_m5_handoff_uses_actual_comparison_and_inspected_product(self):
        for step, product in [("structure", "85"), ("specialization", "95"), ("change", "87")]:
            z = self.call("M4-graph.figure", self.inputs(step))
            comparison = z["M4-comparison"]["data"]
            selected = self.call("M4-inspect.value", {
                "M4-comparison.data": comparison, "M4-case.data": m.recipe(step),
                "active-module.data": "M4",
            }, changed="M4-case.data")
            self.assertEqual(comparison["countries"], ["CHN", "MEX"])
            self.assertEqual(comparison["year"], 2023)
            self.assertEqual(selected["M4-inspect"]["value"], product)
            # Reference still includes worldwide exporters outside the six cases.
            row = next(r for r in z["M4-table"]["data"] if r["country"] == "CHN" and r["hs2"] == product)
            world = m.trade().query("year == 2023")
            expected = world.loc[world.hs2.eq(product), "value"].sum() / world.value.sum() * 100
            self.assertAlmostEqual(row["world_pct"], expected, places=5)

    def test_hidden_module_does_not_render(self):
        key = next(k for k in app.app.callback_map if "M4-graph.figure" in k)
        callback = app.app.callback_map[key]["callback"].__wrapped__
        from dash.exceptions import PreventUpdate

        with self.assertRaises(PreventUpdate):
            callback(
                {},
                "M0",
                [],
                [],
                "share",
                "selected",
                "overview",
                1.25,
                {},
                2010,
                "world",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
