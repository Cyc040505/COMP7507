"""Behavior checks for the approved M5 country-card interface."""

import unittest

import test_m5_ui as legacy
from dash.development.base_component import Component

from src.modules import m5_time as m


def walk(node):
    if isinstance(node, Component):
        yield node
        yield from walk(getattr(node, "children", None))
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from walk(child)


def text(node):
    if isinstance(node, Component):
        return text(getattr(node, "children", None))
    if isinstance(node, (list, tuple)):
        return " ".join(text(child) for child in node)
    return "" if node is None else str(node)


class CountryPortraits(unittest.TestCase):
    call = legacy.TimeInterface.call

    def view(self, countries=None, selected=2024):
        view = m.compute_view(
            countries or ["CHN", "DEU", "MEX"],
            "87",
            2019,
            2020,
            [2016, 2024],
            "product",
            selected,
        )
        self.assertTrue(
            "portraits" in view, "M5 must expose the same-scale country cards"
        )
        return view

    def test_portraits_keep_input_order_shared_axes_and_export_values(self):
        v = self.view(["MEX", "CHN", "USA", "DEU"])
        cards = [
            n
            for n in walk(v["portraits"])
            if "m5-country-card" in str(getattr(n, "className", "")).split()
        ]
        self.assertEqual(
            [n.id for n in cards],
            [m.cid("card-" + c) for c in ["MEX", "CHN", "USA", "DEU"]],
        )
        figures = []
        for card, country in zip(cards, ["MEX", "CHN", "USA", "DEU"]):
            graph = next(
                n
                for n in walk(card)
                if getattr(n, "id", None) == m.cid("portrait-" + country)
            )
            figures.append(graph.figure)
            self.assertEqual(
                graph.figure.data[0].line.color, m.theme.country_color(country)
            )
            exported = [r["index"] for r in v["rows"] if r["country"] == country]
            self.assertEqual(list(graph.figure.data[0].y), exported)
        self.assertTrue(
            all(
                tuple(f.layout.yaxis.range) == tuple(figures[0].layout.yaxis.range)
                for f in figures
            )
        )
        self.assertTrue(all(f.layout.font.family == m.theme.FONT for f in figures))

    def test_inspected_values_and_full_window_recovery_are_distinguished(self):
        v = self.view(selected=2020)
        card = next(
            n
            for n in walk(v["portraits"])
            if getattr(n, "id", None) == m.cid("card-CHN")
        )
        content = text(card)
        self.assertIn("97.1", content)
        self.assertIn("2020", content)
        self.assertIn("2021", content)
        self.assertIn("2024", content)
        self.assertIn("2.67%", content)
        self.assertIn("−0.06 pp", content)

    def test_empty_view_retains_six_click_targets_and_explains_action(self):
        v = m.compute_view([], "TOTAL", 2019, 2020, [2016, 2024], "intra", 2024)
        self.assertTrue(
            "portraits" in v, "The new layout needs an actionable empty state"
        )
        ids = {
            getattr(n, "id", None)
            for n in walk(v["portraits"])
            if isinstance(getattr(n, "id", None), str)
        }
        self.assertTrue({m.cid("portrait-" + c) for c in m.FOCUS_COUNTRIES} <= ids)
        self.assertIn("Select one to four", text(v["portraits"]))
        self.assertNotIn("0.0%", text(v["portraits"]))

    def test_missing_observation_and_never_below_are_not_invented_losses(self):
        self.assertTrue(
            hasattr(m, "portrait_cards"), "A reusable portrait renderer is required"
        )
        rows = [
            {
                "country": "CHN",
                "year": y,
                "index": i,
                "value": None,
                "product_share": None,
                "intra_share": None,
                "intra_upper": None,
                "region_coverage": None,
            }
            for y, i in [(2019, 100), (2020, 110), (2021, None)]
        ]
        summary = [
            {
                "country": "CHN",
                "status": "endpoint_missing",
                "first_at_baseline": None,
                "minimum_index": 110,
            }
        ]
        cards = m.portrait_cards(
            ["CHN"], rows, summary, 2019, 2020, [2019, 2021], "product", "87", 2021
        )
        content = text(cards)
        self.assertIn("No observed loss", content)
        self.assertIn("No observed return", content)
        self.assertNotIn("−0.0%", content)
        graph = next(
            n for n in walk(cards) if getattr(n, "id", None) == m.cid("portrait-CHN")
        )
        self.assertIsNone(graph.figure.data[0].y[-1])
        self.assertFalse(graph.figure.data[0].connectgaps)

    def values(self):
        return {
            "active-module.data": "M5",
            "M5-window.value": [2016, 2024],
            "M5-selected.data": 2024,
            "M5-inspect-year.value": 2024,
        }

    def test_portrait_click_updates_both_selected_year_and_inspection_slider(self):
        v = self.values()
        v["M5-portrait-CHN.clickData"] = {"points": [{"x": 2020}]}
        res = self.call("M5-selected.data", v, "M5-portrait-CHN.clickData")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2020)
        self.assertEqual(res.json["response"]["M5-inspect-year"]["value"], 2020)

    def test_redrawing_a_portrait_does_not_reset_or_loop_selection(self):
        res = self.call("M5-selected.data", self.values(), "M5-portrait-CHN.clickData")
        # Dash 4 may return an empty multi-output response instead of HTTP 204.
        self.assertIn(res.status_code, (200, 204))
        if res.status_code == 200:
            self.assertEqual(res.json["response"], {})

    def test_slider_and_window_change_use_valid_observed_years(self):
        values = self.values()
        values["M5-inspect-year.value"] = 2021
        res = self.call("M5-selected.data", values, "M5-inspect-year.value")
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2021)
        values["M5-window.value"] = [2004, 2013]
        res = self.call("M5-selected.data", values, "M5-window.value")
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2013)
        self.assertEqual(res.json["response"]["M5-inspect-year"]["value"], 2013)


if __name__ == "__main__":
    unittest.main()
