"""Behavior checks for the approved M5 country-card interface."""

import unittest

import plotly.graph_objects as go
import test_m5_ui as legacy
from dash.development.base_component import Component

from src.modules import m4_product as m4
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
        reference_font = m4.base_style(go.Figure(), 205).layout.font
        self.assertTrue(
            all(
                f.layout.font.family == reference_font.family
                and f.layout.font.size == reference_font.size
                for f in figures + [v["index"]]
            )
        )

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
        self.assertIn("Select one to six", text(v["portraits"]))
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

    def test_five_and_six_economies_keep_complete_linked_evidence(self):
        for size in (5, 6):
            countries = list(m.FOCUS_COUNTRIES)[:size]
            for metric in ("product", "intra"):
                with self.subTest(size=size, metric=metric):
                    v = m.compute_view(
                        countries, "87", 2019, 2020, [2016, 2024], metric, 2024
                    )
                    self.assertEqual(len(v["rows"]), size * 9)
                    self.assertEqual(len(v["summary"]), size)
                    self.assertEqual([t.name for t in v["index"].data], countries)
                    self.assertEqual(len({t.line.dash for t in v["index"].data}), size)
                    structure = v["structure"]
                    self.assertEqual(len(structure.data), 2 if metric == "product" else 3)
                    self.assertEqual([r[0] for r in structure.data[0].customdata],
                                     [c for c in countries for _ in range(2)])
                    cards = [
                        n
                        for n in walk(v["portraits"])
                        if "m5-country-card" in str(getattr(n, "className", "")).split()
                    ]
                    self.assertEqual(
                        [n.id for n in cards], [m.cid("card-" + c) for c in countries]
                    )
                    figures = [
                        n.figure
                        for card in cards
                        for n in walk(card)
                        if getattr(n, "id", "").startswith("M5-portrait-")
                    ]
                    self.assertEqual(
                        len({tuple(f.layout.yaxis.range) for f in figures}), 1
                    )

    def test_six_economy_m4_handoff_preserves_all_countries(self):
        countries = list(reversed(m.FOCUS_COUNTRIES))
        res = self.call(
            "M5-countries.value",
            {
                "active-module.data": "M5",
                "M5-import.n_clicks": 1,
                "M4-comparison.data": {"countries": countries, "year": 2023},
                "M4-inspect.value": "87",
            },
            "M5-import.n_clicks",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json["response"]
        self.assertEqual(data["M5-countries"]["value"], countries)
        self.assertEqual(data["M5-window"]["value"], [2016, 2023])

    def test_multicountry_path_updates_inspected_year(self):
        values = self.values()
        values["M5-index.clickData"] = {"points": [{"x": 2020}]}
        res = self.call("M5-selected.data", values, "M5-index.clickData")
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2020)
        self.assertEqual(res.json["response"]["M5-inspect-year"]["value"], 2020)

    def test_recovery_path_click_updates_selected_year_and_dropdown(self):
        v = self.values()
        v["M5-index.clickData"] = {"points": [{"x": 2020}]}
        res = self.call("M5-selected.data", v, "M5-index.clickData")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2020)
        self.assertEqual(res.json["response"]["M5-inspect-year"]["value"], 2020)

    def test_bar_mode_preserves_evidence_and_shared_zero_based_scale(self):
        countries = list(m.FOCUS_COUNTRIES)
        line = self.view(countries)
        bars = m.compute_view(
            countries, "87", 2019, 2020, [2016, 2024], "product", 2024, chart_type="bar"
        )
        self.assertEqual(line["rows"], bars["rows"])
        self.assertEqual(line["summary"], bars["summary"])
        graphs = [
            n
            for n in walk(bars["portraits"])
            if getattr(n, "id", "").startswith("M5-portrait-")
        ]
        self.assertEqual(len(graphs), 6)
        self.assertEqual(len({tuple(n.figure.layout.xaxis.range) for n in graphs}), 1)
        for graph in graphs:
            trace = graph.figure.data[0]
            self.assertEqual(trace.type, "bar")
            self.assertEqual(graph.figure.layout.xaxis.range[0], 0)
            self.assertEqual([r[0] for r in trace.customdata], [2019, 2020, 2024])
            country = graph.id.removeprefix("M5-portrait-")
            observed = {
                r["year"]: r["index"] for r in bars["rows"] if r["country"] == country
            }
            for value, custom in zip(trace.x, trace.customdata):
                self.assertEqual(value, observed[custom[0]])

    def test_structure_point_updates_inspected_year(self):
        values = self.values()
        values["M5-structure.clickData"] = {"points": [{"x": 2020}]}
        res = self.call("M5-selected.data", values, "M5-structure.clickData")
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2020)

    def test_country_bar_uses_custom_year_and_shared_line_remains_linked(self):
        values = self.values()
        values["M5-portrait-CHN.clickData"] = {
            "points": [{"x": 97.1, "y": "2020", "customdata": [2020, 2666000000]}]}
        res = self.call("M5-selected.data", values, "M5-portrait-CHN.clickData")
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2020)
        self.assertEqual(res.json["response"]["M5-inspect-year"]["value"], 2020)

    def test_bar_years_are_unique_and_missing_values_stay_missing(self):
        rows = [
            {"country": "CHN", "year": y, "index": i}
            for y, i in [(2019, 100), (2020, 90), (2021, None)]
        ]
        for selected in (2019, 2020, 2021):
            cards = m.portrait_cards(
                ["CHN"],
                rows,
                [],
                2019,
                2020,
                [2019, 2021],
                "product",
                "87",
                selected,
                chart_type="bar",
            )
            graph = next(
                n for n in walk(cards) if getattr(n, "id", None) == "M5-portrait-CHN"
            )
            trace = graph.figure.data[0]
            self.assertEqual([r[0] for r in trace.customdata], [2019, 2020, 2021])
            self.assertIsNone(trace.x[-1])
            self.assertIn("No data", str(graph.figure.layout.annotations))

    def test_recovery_has_shared_line_before_country_bars(self):
        nodes = list(walk(m.layout()))
        ids = {getattr(n, "id", None) for n in nodes}
        self.assertIn("M5-index", ids)
        self.assertNotIn("M5-chart-type", ids)
        self.assertNotIn("M5-recovery-table", ids)
        self.assertTrue({"M5-portrait-" + c for c in m.FOCUS_COUNTRIES} <= ids)
        self.assertNotIn("Overlay country recovery lines", text(m.layout()))
        panel = next(n for n in nodes if getattr(n, "id", None) == "M5-recovery-panel")
        ordered = [getattr(n, "id", None) for n in walk(panel)]
        self.assertLess(ordered.index("M5-recovery-title"), ordered.index("M5-index"))
        self.assertLess(ordered.index("M5-index"), ordered.index("M5-portraits"))
        self.assertLess(ordered.index("M5-portraits"), ordered.index("M5-finding"))

    def test_http_comparison_graph_keeps_year_and_all_annual_rows(self):
        values = {
            "active-module.data": "M5",
            "M5-countries.value": list(m.FOCUS_COUNTRIES),
            "M5-product.value": "87",
            "M5-baseline.value": 2019,
            "M5-event.value": 2020,
            "M5-window.value": [2016, 2024],
            "M5-metric.value": "product",
            "M5-selected.data": 2021,
        }
        rows = None
        for year in (2021, 2020, 2024):
            values["M5-selected.data"] = year
            res = self.call("M5-index.figure", values, "M5-selected.data")
            self.assertEqual(res.status_code, 200)
            data = res.json["response"]
            current = [{k: v for k, v in row.items() if k != "selected_year"}
                       for row in data["M5-rows"]["data"]]
            self.assertEqual(len(current), 54)
            if rows is not None:
                self.assertEqual(current, rows)
            rows = current
            self.assertEqual(data["M5-detail-year"]["children"], str(year))
            self.assertEqual(
                data["M5-inspect-year"]["options"],
                [{"label": str(y), "value": y} for y in range(2016, 2025)],
            )
            cards = data["M5-portraits"]["children"]
            graphs = [
                child
                for card in cards
                if card.get("type") == "Article"
                for child in card["props"]["children"]
                if child and child.get("type") == "Graph"
            ]
            self.assertEqual(len(graphs), 6)
            self.assertEqual({g["props"]["figure"]["data"][0]["type"] for g in graphs}, {"bar"})
            figure = data["M5-index"]["figure"]
            self.assertEqual([trace["name"] for trace in figure["data"]], list(m.FOCUS_COUNTRIES))
            self.assertEqual({trace["type"] for trace in figure["data"]}, {"scatter"})

    def test_recovery_results_keep_country_order_without_individual_graphs(self):
        v = m.compute_view(["MEX", "CHN"], "87", 2019, 2020, [2016, 2024],
                           "product", 2024, show_country_charts=False)
        cards = [n for n in walk(v["portraits"]) if type(n).__name__ == "Article"]
        self.assertEqual([n.id for n in cards], ["M5-card-MEX", "M5-card-CHN"])
        self.assertFalse(any(type(n).__name__ == "Graph" for n in walk(v["portraits"])))
        self.assertIn("280.6", text(cards[1]))
        self.assertIn("2021", text(cards[1]))
        self.assertIn("2022", text(cards[0]))

    def test_empty_recovery_results_have_no_hidden_graphs(self):
        v = m.compute_view([], "TOTAL", 2019, 2020, [2016, 2024], "intra", 2024,
                           show_country_charts=False)
        self.assertFalse(any(type(n).__name__ == "Graph" for n in walk(v["portraits"])))
        self.assertIn("Select one to six", text(v["portraits"]))

    def test_redrawing_comparison_graph_does_not_reset_or_loop_selection(self):
        res = self.call("M5-selected.data", self.values(), "M5-index.clickData")
        # Dash 4 may return an empty multi-output response instead of HTTP 204.
        self.assertIn(res.status_code, (200, 204))
        if res.status_code == 200:
            self.assertEqual(res.json["response"], {})

    def test_year_dropdown_and_window_change_use_valid_observed_years(self):
        year_control = next(
            n for n in walk(m.layout()) if getattr(n, "id", None) == "M5-inspect-year"
        )
        self.assertEqual(type(year_control).__name__, "Dropdown")
        self.assertFalse(year_control.clearable)
        self.assertFalse(any(type(n).__name__ == "Slider" for n in walk(m.layout())))
        values = self.values()
        values["M5-inspect-year.value"] = 2021
        res = self.call("M5-selected.data", values, "M5-inspect-year.value")
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2021)
        values["M5-window.value"] = [2004, 2013]
        res = self.call("M5-selected.data", values, "M5-window.value")
        self.assertEqual(res.json["response"]["M5-selected"]["data"], 2013)
        self.assertEqual(res.json["response"]["M5-inspect-year"]["value"], 2013)

    def test_major_sections_keep_graphs_and_their_conclusions_together(self):
        nodes = list(walk(m.layout()))
        by_id = {getattr(n, "id", None): n for n in nodes if getattr(n, "id", None)}
        self.assertIn("M5-section", by_id)
        for panel_id, graph_id, evidence_id, conclusion_id in [
            (
                "M5-recovery-panel",
                "M5-index",
                "M5-finding",
                "M5-recovery-interpretation",
            ),
            (
                "M5-structure-panel",
                "M5-structure",
                "M5-implication",
                "M5-structure-interpretation",
            ),
        ]:
            panel_nodes = list(walk(by_id[panel_id]))
            ids = [getattr(n, "id", None) for n in panel_nodes]
            self.assertLess(ids.index(graph_id), ids.index(evidence_id))
            self.assertLess(ids.index(evidence_id), ids.index(conclusion_id))
        ids = [getattr(n, "id", None) for n in nodes if getattr(n, "id", None)]
        self.assertEqual(len(ids), len(set(ids)))
        # Three cases share a single selection across the two major chart views.
        for key in m.CASES:
            self.assertEqual(ids.count(m.cid(key)), 1)

    def test_major_section_navigation_only_changes_panel_visibility(self):
        for section in ("recovery", "structure"):
            res = self.call(
                "M5-recovery-panel.style",
                {"active-module.data": "M5", "M5-section.value": section},
                "M5-section.value",
            )
            self.assertEqual(res.status_code, 200)
            data = res.json["response"]
            self.assertEqual(set(data), {"M5-recovery-panel", "M5-structure-panel"})
            self.assertEqual(
                data["M5-recovery-panel"]["style"]["display"],
                "flex" if section == "recovery" else "none",
            )
            self.assertEqual(
                data["M5-structure-panel"]["style"]["display"],
                "flex" if section == "structure" else "none",
            )

    def test_recovery_conclusion_explains_returns_separately_from_structure(self):
        v = self.view(list(m.FOCUS_COUNTRIES))
        self.assertIn("recovery_interpretation", v)
        self.assertIn("2021", v["recovery_interpretation"])
        self.assertIn("2022", v["recovery_interpretation"])
        self.assertNotIn("percentage points", v["recovery_interpretation"])
        self.assertIn("share", v["structure_interpretation"].lower())
        self.assertIn("3.00 percentage points", v["implication"])

    def test_questions_are_inside_each_chart_before_the_data(self):
        nodes = list(walk(m.layout()))
        by_id = {getattr(n, "id", None): n for n in nodes if getattr(n, "id", None)}
        self.assertNotIn("M5-guide", set(by_id))
        for section, graph in [("recovery", "index"), ("structure", "structure")]:
            ids = [getattr(n, "id", None) for n in walk(by_id[f"M5-{section}-panel"])]
            self.assertLess(
                ids.index(f"M5-{section}-question"), ids.index(f"M5-{section}-title")
            )
            self.assertLess(ids.index(f"M5-{section}-title"), ids.index(f"M5-{graph}"))

    def test_section_questions_and_titles_follow_scope_and_evidence(self):
        vehicles = self.view()
        self.assertIn("2019", vehicles["recovery_question"])
        self.assertIn("vehicle", vehicles["recovery_question"].lower())
        self.assertIn("different years", vehicles["recovery_title"])
        self.assertIn("HS87", vehicles["structure_question"])
        crisis = m.compute_view(
            ["CHN", "DEU", "MEX"], "TOTAL", 2007, 2008, [2004, 2013], "intra", 2013
        )
        self.assertIn("2007", crisis["recovery_question"])
        self.assertNotIn("2019", crisis["recovery_question"])
        self.assertIn("region", crisis["structure_question"].lower())
        self.assertNotIn("HS87", crisis["structure_question"])
        pandemic = m.compute_view(
            ["CHN", "DEU", "MEX"], "TOTAL", 2019, 2020, [2016, 2024], "intra", 2024
        )
        self.assertNotIn("different years", pandemic["recovery_title"])


if __name__ == "__main__":
    unittest.main()
