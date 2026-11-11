"""Two-year composition must preserve denominators, nulls and region bounds."""

import unittest

import test_m5_ui as legacy
from src.modules import m5_time as m
from src.m5_structure import composition_figure, comparison_summary


class StructureComposition(unittest.TestCase):
    call = legacy.TimeInterface.call

    def test_product_stacks_match_exported_shares_and_total_100(self):
        v = m.compute_view(["MEX", "CHN"], "85", 2019, 2020, [2016, 2023], "product", 2023)
        fig = v["structure"]
        self.assertEqual([t.type for t in fig.data], ["bar", "bar"])
        self.assertEqual(len(fig.data[0].x), 4)
        for i, custom in enumerate(fig.data[0].customdata):
            country, year = custom[:2]
            row = next(r for r in v["rows"] if r["country"] == country and r["year"] == year)
            self.assertAlmostEqual(fig.data[0].x[i], row["product_share"] * 100)
            self.assertAlmostEqual(sum(t.x[i] for t in fig.data), 100)
        self.assertEqual([tuple(c[:2]) for c in fig.data[0].customdata],
                         [("MEX", 2019), ("MEX", 2023), ("CHN", 2019), ("CHN", 2023)])
        self.assertEqual(tuple(fig.layout.xaxis.range), (0, 100))
        self.assertIn("2023", v["implication"])
        self.assertIn("lost", v["implication"])

    def test_region_unknown_is_separate_and_change_keeps_bounds(self):
        rows = [dict(country="CHN", year=y, intra_share=lo,
                     intra_upper=hi, region_coverage=coverage)
                for y, lo, hi, coverage in [(2019, .4, .5, .9), (2023, .45, .52, .93)]]
        fig = composition_figure(rows, ["CHN"], "TOTAL", "intra", 2019, 2023)
        self.assertEqual(len(fig.data), 3)
        self.assertAlmostEqual(fig.data[1].x[0], 50)
        self.assertAlmostEqual(fig.data[2].x[1], 7)
        for i in (0, 1):
            self.assertAlmostEqual(sum(t.x[i] for t in fig.data), 100)
        import pandas as pd
        summary = comparison_summary(pd.DataFrame({"country": ["CHN"]}), rows, 2019, 2023)
        self.assertAlmostEqual(summary.region_change_min_pp.iloc[0], -5)
        self.assertAlmostEqual(summary.region_change_max_pp.iloc[0], 12)

    def test_missing_years_are_empty_not_zero_or_full_other_products(self):
        fig = composition_figure([dict(country="CHN", year=2019, product_share=.3)],
                                 ["CHN"], "85", "product", 2019, 2023)
        self.assertIsNone(fig.data[0].x[1])
        self.assertIsNone(fig.data[1].x[1])
        self.assertIn("No data", str(fig.layout.annotations))

    def test_same_year_is_not_duplicated_and_total_product_is_not_100_percent(self):
        fig = composition_figure([dict(country="CHN", year=2019, product_share=.3)],
                                 ["CHN"], "85", "product", 2019, 2019)
        self.assertEqual(len(fig.data[0].x), 1)
        empty = composition_figure([], ["CHN"], "TOTAL", "product", 2019, 2023)
        self.assertFalse(empty.data)

    def test_structure_click_uses_year_not_percentage(self):
        result = self.call("M5-selected.data", {
            "active-module.data": "M5", "M5-window.value": [2016, 2024],
            "M5-selected.data": 2024, "M5-inspect-year.value": 2024,
            "M5-structure.clickData": {"points": [{"x": 31.36,
                "customdata": ["CHN", 2023, 31.36, 31.36, 31.36]}]},
        }, "M5-structure.clickData")
        self.assertEqual(result.json["response"]["M5-inspect-year"]["value"], 2023)

    def test_six_countries_get_room_and_selected_year_drives_explanation(self):
        v = m.compute_view(list(m.FOCUS_COUNTRIES), "85", 2019, 2020,
                           [2016, 2024], "product", 2023)
        self.assertEqual(len(v["structure"].data[0].x), 12)
        self.assertGreater(v["structure"].layout.height, 500)
        self.assertIn("2023", v["implication"])

    def test_change_chart_matches_exact_product_changes_and_is_centered(self):
        v = m.compute_view(["CHN", "DEU", "MEX"], "85", 2019, 2020,
                           [2016, 2023], "product", 2023)
        figure = v["structure_change"]
        summary = {r["country"]: r for r in v["summary"]}
        for country, amount in zip(["CHN", "DEU", "MEX"], figure.data[0].x):
            self.assertAlmostEqual(amount, summary[country]["end_product_change_pp"])
        self.assertGreater(figure.data[0].x[0], 0)
        self.assertLess(figure.data[0].x[2], 0)
        self.assertEqual(figure.layout.xaxis.range[0], -figure.layout.xaxis.range[1])

    def test_region_change_range_preserves_uncertainty(self):
        v = m.compute_view(["CHN", "MEX"], "TOTAL", 2019, 2020,
                           [2016, 2024], "intra", 2024)
        trace = v["structure_change"].data[0]
        rows = {(r["country"], r["year"]): r for r in v["rows"]}
        for amount, base, custom in zip(trace.x, trace.base, trace.customdata):
            self.assertEqual(base, 0)
            expected = 100 * (rows[custom[0], 2024]["intra_share"] - rows[custom[0], 2019]["intra_share"])
            self.assertAlmostEqual(amount, expected)
        self.assertLess(trace.customdata[0][3], 0)
        self.assertGreater(trace.customdata[0][4], 0)

    def test_region_range_is_explicit_and_not_styled_as_a_solid_change(self):
        v = m.compute_view(["CHN", "MEX"], "TOTAL", 2019, 2020,
                           [2016, 2024], "intra", 2024)
        fig = v["structure_change"]
        self.assertIn(fig.data[0].marker.pattern.shape, (None, ""))
        labels = [a.text for a in fig.layout.annotations]
        self.assertNotIn("Overall direction uncertain", labels)
        self.assertNotIn("Increase supported", labels)
        self.assertNotIn("Decrease supported", labels)
        self.assertIn("Possible overall change", fig.data[0].hovertemplate)
        self.assertTrue(any("possible overall range" in t for t in labels))

    def test_local_layout_has_both_visible_charts(self):
        from dash.development.base_component import Component
        def walk(node):
            if isinstance(node, Component):
                yield node
                yield from walk(getattr(node, "children", None))
            elif isinstance(node, (list, tuple)):
                for child in node:
                    yield from walk(child)
        nodes = list(walk(m.layout()))
        pair = next(n for n in nodes if getattr(n, "className", "") == "m5-structure-pair")
        ids = {getattr(n, "id", None) for n in walk(pair)}
        self.assertTrue({"M5-structure", "M5-structure-change"} <= ids)


if __name__ == "__main__":
    unittest.main()
