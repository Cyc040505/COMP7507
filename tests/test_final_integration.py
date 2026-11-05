"""Final-source invariants and callback contracts, independent of Top-N rendering."""

import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import pandas as pd
from src import data_loader as dl, config
from src.analytics import partners as p
from src.modules import m3_network as m, overview, m1_geography as g
from src.analytics.geography import analyze, spearman_rho
import app


def call(needle, values, changed):
    key = next(k for k in app.app.callback_map if needle in k)
    meta = app.app.callback_map[key]
    payload = lambda spec: [
        dict(v, value=values.get(v["id"] + "." + v["property"])) for v in spec
    ]
    outs = meta["output"]
    outs = outs if isinstance(outs, list) else [outs]
    output = [dict(id=o.component_id, property=o.component_property) for o in outs]
    return app.server.test_client().post(
        "/_dash-update-component",
        json={
            "output": key,
            "outputs": output if len(output) > 1 else output[0],
            "inputs": payload(meta["inputs"]),
            "state": payload(meta["state"]),
            "changedPropIds": [changed],
        },
    )


class FinalIntegration(unittest.TestCase):
    def test_all_country_and_world_totals_reconcile_to_official_pairs(self):
        b = dl.load_country_pair_year().groupby(["year", "exporter"]).value.sum()
        c = dl.load_country_year().set_index(["year", "country"]).export_value
        joined = pd.concat([b.rename("actual"), c.rename("expected")], axis=1)
        self.assertFalse(joined.isna().any().any())
        np.testing.assert_allclose(
            joined.actual, joined.expected, rtol=2e-10, atol=1e-6
        )
        w = dl.load_flow_year().set_index("year").export_value
        np.testing.assert_allclose(
            b.groupby("year").sum().sort_index(), w.sort_index(), rtol=2e-10
        )

    def test_direction_and_denominators(self):
        source = p.flows(2023, "87")
        for direction, column, partnercol in [
            ("export", "exporter", "importer"),
            ("import", "importer", "exporter"),
        ]:
            out = p.partners("CHN", 2023, "87", direction).set_index("partner")
            independent = (
                source[source[column].eq("CHN")].groupby(partnercol).value.sum()
            )
            np.testing.assert_allclose(
                out.value.sort_index(), independent.sort_index(), rtol=1e-12
            )
            self.assertAlmostEqual(out.share.sum(), 1)
            for top in [5, 10, 20]:
                view = m.figures("CHN", 2023, "87", direction, top, "map", "USA")
                np.testing.assert_allclose(
                    list(view[1].data[0].x), out.share.iloc[:top] * 100
                )
                self.assertEqual(len(view[-1]), len(out))
        self.assertNotAlmostEqual(
            p.partners("CHN", 2023, "87", "import").value.sum(),
            p.partners("CHN", 2023, "87", "export").value.sum(),
        )

    def test_matrix_fixed_columns_and_region_sums(self):
        expected = None
        for year, product, direction in [
            (2010, "TOTAL", "export"),
            (2023, "85", "export"),
            (2024, "87", "import"),
        ]:
            columns, rows = p.matrix(year, product, direction)
            if expected is None:
                expected = columns
            self.assertEqual(columns, expected)
            np.testing.assert_allclose(np.sum(rows, axis=1), 100, rtol=1e-12)
            for country in p.FOCUS:
                for product in ["85", "87"]:
                    shares, low, high = p.regional(country, year, product, direction)
                    self.assertAlmostEqual(shares.sum(), 1)
                    self.assertGreaterEqual(high, low)
                    self.assertAlmostEqual(high - low, shares["Unknown"])
        self.assertEqual(columns[-1], "Other")

    def test_zero_scope_does_not_invent_shares(self):
        with patch.object(
            p,
            "partners",
            return_value=pd.DataFrame(columns=["partner", "value", "share", "region"]),
        ):
            self.assertIsNone(p.regional("CHN", 2023, "87", "export"))
            self.assertTrue(np.isnan(p.matrix(2023, "87", "export")[1]).all())

    def test_m3_http_render_and_click_focus_rules(self):
        values = {
            "active-module.data": "M3",
            **{
                "M3-" + k + ".value": v
                for k, v in dict(
                    country="CHN",
                    year=2023,
                    product="87",
                    direction="export",
                    top=10,
                    view="map",
                ).items()
            },
        }
        r = call("M3-graph.figure", values, "active-module.data")
        self.assertEqual(r.status_code, 200, r.data[:300])
        self.assertIn("50.5%", r.json["response"]["M3-scope"]["children"])
        for source, point, expected in [
            ("graph", {"location": "USA"}, "USA"),
            ("graph", {"location": "JPN"}, None),
            ("graph", {"customdata": "USA"}, None),
            ("ranking", {"customdata": "USA"}, None),
        ]:
            r = call(
                "M3-country.value",
                {
                    "active-module.data": "M3",
                    "M3-view.value": "map",
                    f"M3-{source}.clickData": {"points": [point]},
                },
                f"M3-{source}.clickData",
            )
            self.assertEqual(r.status_code, 200, r.data[:300])
            response = r.json["response"]
            self.assertEqual(response.get("M3-country", {}).get("value"), expected)
            if expected is None:
                self.assertEqual(
                    response["M3-selected"]["data"],
                    point.get("location") or point["customdata"],
                )
        values["active-module.data"] = "M2"
        self.assertEqual(
            call("M3-graph.figure", values, "active-module.data").status_code, 204
        )

    def test_m3_export_matches_plotted_records(self):
        rows = m.figures("MEX", 2024, "85", "import", 5, "matrix", None)[-1]
        r = call(
            "M3-download.data",
            {"M3-export.n_clicks": 1, "M3-records.data": rows},
            "M3-export.n_clicks",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(
            "thousand current USD", r.json["response"]["M3-download"]["data"]["content"]
        )

    def test_m1_full_sample_and_linked_highlight(self):
        res = analyze(
            p.flows(2023),
            dl.load_geodist(),
            dl.load_country_meta(),
            "CHN",
            2023,
            metric="dist",
        )
        before = res["stats"]["spearman"]
        selected = "JPN"
        for show in ["top10", "nearest10", "all"]:
            self.assertEqual(res["stats"]["spearman"], before)
            self.assertIn(
                selected, list(g.ranking_figure(res, show, selected).data[0].y)
            )
            self.assertEqual(
                list(g._map_figure(res, "CHN", show, selected).data[-1].locations),
                [selected],
            )
        f = g.scatter_figure(res, selected)
        i = list(f.data[0].customdata).index(selected)
        self.assertTrue(
            all(
                color != f.data[0].marker.color[i]
                for j, color in enumerate(f.data[0].marker.color)
                if j != i
            )
        )
        vals = {
            "active-module.data": "M1",
            "M1-year.value": 2023,
            "M1-exporter.value": "CHN",
            "M1-product.value": "87",
            "M1-dist-metric.value": "dist",
            "M1-show.value": "top10",
            "M1-selected.data": "JPN",
        }
        self.assertEqual(
            call("M1-finding.children", vals, "M1-product.value").status_code, 200
        )
        for source, point in [
            ("map", {"location": "JPN"}),
            ("scatter", {"customdata": "JPN"}),
            ("ranking", {"customdata": "JPN"}),
        ]:
            r = call(
                "M1-selected.data",
                {
                    "active-module.data": "M1",
                    f"M1-{source}.clickData": {"points": [point]},
                },
                f"M1-{source}.clickData",
            )
            self.assertEqual(r.json["response"]["M1-selected"]["data"], "JPN")

    def test_m0_full_trends_and_year_ranking(self):
        for year in [2010, 2023, 2024]:
            total, top, text = overview.figures(year, "ranking")
            _, six, _ = overview.figures(year, "six")
            self.assertEqual(len(total.data[0].x), 30)
            self.assertEqual(len(six.data), 6)
            c = dl.load_country_year()
            w = dl.load_flow_year().set_index("year").export_value[year]
            for code, value in zip(top.data[0].y, top.data[0].x):
                expected = (
                    c[c.country.eq(code) & c.year.eq(year)].export_value.iloc[0]
                    / w
                    * 100
                )
                self.assertAlmostEqual(value, expected)
            self.assertIn(str(year), text)

    def test_compact_inputs_match_audited_hashes(self):
        import hashlib, json

        manifest = json.loads(
            config.processed_path("m5_source_manifest.json").read_text()
        )
        for file, expected in manifest["bilateral_inputs_sha256"].items():
            self.assertEqual(
                hashlib.sha256(config.processed_path(file).read_bytes()).hexdigest(),
                expected,
            )

    def test_m3_rejects_non_focal_country(self):
        with self.assertRaises(ValueError):
            p.partners("JPN", 2023, "87")
        values = {
            "active-module.data": "M3",
            **{
                "M3-" + k + ".value": v
                for k, v in dict(
                    country="JPN",
                    year=2023,
                    product="87",
                    direction="export",
                    top=10,
                    view="map",
                ).items()
            },
        }
        r = call("M3-graph.figure", values, "M3-country.value")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["response"]["M3-records"]["data"], [])
        self.assertIn("valid focal economy", r.json["response"]["M3-scope"]["children"])

    def test_missing_real_table_fails_closed(self):
        with patch.object(
            config,
            "processed_path",
            return_value=Path("/tmp/comp7507-no-such-input.parquet"),
        ):
            with self.assertRaises(FileNotFoundError):
                dl._load("missing", lambda: pd.DataFrame({"value": [123]}))
