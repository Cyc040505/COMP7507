"""Regression checks for meaningful visual/interaction semantics, not CSS pixels."""

import unittest
from dash.development.base_component import Component
from test_final_integration import call
from src.modules import m3_network as m3, m4_product as m4, m5_time as m5


class VisualContracts(unittest.TestCase):
    def test_hs_codes_are_categories_not_continuous_numbers(self):
        data = m4.metrics(2023)
        for metric in ["share", "rca"]:
            fig = m4.heat_figure(
                data,
                ["CHN", "MEX"],
                ["27", "29", "39", "84", "85", "87", "90", "95"],
                metric,
            )
            self.assertEqual(fig.layout.yaxis.type, "category")
        self.assertEqual(
            m4.detail_figure(data, "CHN", "95").layout.yaxis.type, "category"
        )

    def test_m3_reset_restores_case_and_clears_partner(self):
        response = call("M3-year.value", {"M3-reset.n_clicks": 1}, "M3-reset.n_clicks")
        self.assertEqual(response.status_code, 200)
        r = response.get_json()["response"]
        for key, value in [
            ("country", "CHN"),
            ("year", 2023),
            ("product", "87"),
            ("direction", "export"),
            ("top", 10),
            ("view", "map"),
        ]:
            self.assertEqual(r["M3-" + key]["value"], value)
        self.assertIsNone(r["M3-selected"]["data"])

    def test_m3_complete_scope_and_coverage_match_export_records(self):
        rows = m3.figures("CHN", 2023, "87", "export", 10, "map", None)[-1]
        response = call(
            "M3-kpis.children",
            {"M3-records.data": rows, "M3-top.value": 10},
            "M3-records.data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("208 partners", response.get_data(as_text=True))
        self.assertIn("50.5%", response.get_data(as_text=True))
        self.assertIn("49.5%", response.get_data(as_text=True))

    def test_m3_claim_respects_unknown_region_bounds(self):
        result = m3.figures("CHN", 2023, "87", "export", 10, "map", None)
        self.assertIn("lower same-region share", result[4])
        self.assertIn("48.3%", result[4])
        self.assertIn("42.0%", result[4])

    def test_responsive_time_graphs_have_intrinsic_height(self):
        found = {}

        def walk(c):
            if isinstance(c, (tuple, list)):
                for child in c:
                    walk(child)
            elif isinstance(c, Component):
                if getattr(c, "id", None) in ["M5-index", "M5-structure"]:
                    found[c.id] = c.style
                walk(getattr(c, "children", None))

        walk(m5.layout())
        self.assertEqual(len(found), 2)
        for style in found.values():
            self.assertGreaterEqual(int(style["height"][:-2]), 330)

    def test_map_polish_keeps_capitals_directions_and_amount_widths(self):
        import math

        for direction in ["export", "import"]:
            rows = m3.partners("CHN", 2023, "87", direction)
            fig = m3.map_figure("CHN", rows, direction, 10, None)
            routes = [
                t
                for t in fig.data
                if t.type == "scattergeo"
                and t.customdata is not None
                and t.mode == "lines"
            ]
            self.assertEqual(len(routes), 10)
            for t in routes:
                partner = t.customdata[0]
                a, b = ("CHN", partner) if direction == "export" else (partner, "CHN")
                for key in ["lon", "lat"]:
                    self.assertAlmostEqual(
                        getattr(t, key)[0], m3.positions().loc[a, key]
                    )
                    self.assertAlmostEqual(
                        getattr(t, key)[-1], m3.positions().loc[b, key]
                    )
                value = float(rows.loc[rows.partner.eq(partner), "value"].iloc[0])
                self.assertAlmostEqual(
                    t.line.width, 1 + 5 * math.sqrt(value / rows.head(10).value.max())
                )
