import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.modules import m5_time as m
import app


class TimeInterface(unittest.TestCase):
    def test_guided_and_custom_selection_follow_actual_inputs(self):
        guided = m.compute_view(
            ["CHN", "DEU", "MEX"], "87", 2019, 2020, [2016, 2024], "product", 2024
        )
        self.assertEqual(guided["preset_class"], "m5-presets vehicles")
        self.assertIn("3.00 percentage points", guided["implication"])
        custom = m.compute_view(
            ["DEU"], "87", 2019, 2020, [2016, 2024], "product", 2024
        )
        self.assertEqual(custom["preset_class"], "m5-presets custom")
        self.assertIn("DEU", custom["implication"])
        self.assertNotIn("CHN", custom["implication"])

    def test_uncertain_region_assignments_change_the_allowed_conclusion(self):
        view = m.compute_view(
            ["CHN", "DEU", "MEX"], "TOTAL", 2019, 2020, [2016, 2024], "intra", 2024
        )
        rows = {r["country"]: r for r in view["summary"]}
        # Reconstruct the bound from the downloadable year-level shares.
        for code in rows:
            series = {r["year"]: r for r in view["rows"] if r["country"] == code}
            self.assertAlmostEqual(
                rows[code]["region_change_min_pp"],
                100 * (series[2024]["intra_share"] - series[2019]["intra_upper"]),
                places=7,
            )
            self.assertAlmostEqual(
                rows[code]["region_change_max_pp"],
                100 * (series[2024]["intra_upper"] - series[2019]["intra_share"]),
                places=7,
            )
        self.assertLess(rows["CHN"]["region_change_min_pp"], 0)
        self.assertGreater(rows["CHN"]["region_change_max_pp"], 0)
        self.assertIn("unresolved for CHN, DEU", view["implication"])
        self.assertIn("MEX", view["implication"])
        self.assertIn("at least 0.73 pp", view["implication"])

    def test_real_figures_and_exports_share_the_same_values(self):
        v = m.compute_view(
            ["CHN", "MEX"], "87", 2019, 2020, [2016, 2024], "product", 2021
        )
        self.assertEqual(len(v["index"].data), 2)
        self.assertEqual(len(v["structure"].data), 2)
        base = next(r for r in v["rows"] if r["country"] == "CHN" and r["year"] == 2019)
        self.assertAlmostEqual(base["index"], 100)
        self.assertLess(base["product_share"], 1)
        self.assertEqual(base["product"], "87")
        self.assertIn("source_version", base)
        self.assertIn("region_coverage", base)
        self.assertTrue(v["summary"])

    def test_invalid_and_empty_controls_are_readable(self):
        v = m.compute_view([], "TOTAL", 2019, 2020, [2016, 2024], "intra", 2024)
        self.assertEqual(v["rows"], [])
        self.assertIn("Select", v["message"])
        v = m.compute_view(["CHN"], "TOTAL", 2021, 2020, [2016, 2024], "intra", 2024)
        self.assertEqual(v["rows"], [])
        self.assertIn("baseline", v["message"].lower())
        v = m.compute_view(
            ["CHN", "MEX", "USA", "DEU", "JPN"],
            "TOTAL",
            2019,
            2020,
            [2016, 2024],
            "intra",
            2024,
        )
        self.assertEqual(v["rows"], [])
        self.assertIn("4", v["message"])

    def test_reconciled_data_and_hash_are_required(self):
        p, r, manifest = m.inputs()
        self.assertFalse(p.attrs["demo"])
        self.assertEqual(len(r), 566165)
        self.assertEqual(manifest["source_version"], "BACI HS92 V202601")

    def test_comparison_colors_are_distinct_and_linked(self):
        v = m.compute_view(
            ["AUS", "BRA"], "87", 2019, 2020, [2016, 2024], "product", 2024
        )
        main = {t.name: t.line.color for t in v["index"].data}
        detail = {t.name: t.line.color for t in v["structure"].data}
        self.assertNotEqual(main["AUS"], main["BRA"])
        self.assertEqual(main, detail)

    def call(self, needle, values, changed):
        key = next(k for k in app.app.callback_map if needle in k)
        meta = app.app.callback_map[key]

        def payload(spec):
            return [
                dict(v, value=values.get(v["id"] + "." + v["property"])) for v in spec
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
                "changedPropIds": [changed],
            },
        )
        return res

    def test_http_render_hidden_and_download(self):
        values = {
            "active-module.data": "M5",
            "M5-countries.value": ["CHN", "MEX"],
            "M5-product.value": "87",
            "M5-baseline.value": 2019,
            "M5-event.value": 2020,
            "M5-window.value": [2016, 2024],
            "M5-metric.value": "intra",
            "M5-selected.data": 2021,
        }
        res = self.call("M5-index.figure", values, "active-module.data")
        self.assertEqual(res.status_code, 200, res.data[:500])
        rows = res.json["response"]["M5-rows"]["data"]
        download = self.call(
            "M5-download.data",
            {"M5-download-button.n_clicks": 1, "M5-rows.data": rows},
            "M5-download-button.n_clicks",
        )
        self.assertEqual(download.status_code, 200)
        self.assertIn(
            "region_coverage",
            download.json["response"]["M5-download"]["data"]["content"],
        )
        values["active-module.data"] = "M4"
        self.assertEqual(
            self.call("M5-index.figure", values, "active-module.data").status_code, 204
        )

    def test_explicit_m4_import(self):
        res = self.call(
            "M5-countries.value",
            {
                "active-module.data": "M5",
                "M5-import.n_clicks": 1,
                "M4-comparison.data": {"countries": ["CHN", "MEX"], "year": 2023},
                "M4-inspect.value": "87",
            },
            "M5-import.n_clicks",
        )
        self.assertEqual(res.status_code, 200, res.data[:500])
        self.assertEqual(res.json["response"]["M5-product"]["value"], "87")
        self.assertEqual(res.json["response"]["M5-countries"]["value"], ["CHN", "MEX"])


if __name__ == "__main__":
    unittest.main()
