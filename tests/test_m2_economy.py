"""M2 numerical boundaries, source integrity, and actual Dash callback requests."""

import io
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import app
from src import data_loader
from src.analytics.economy import prepare_year, match_candidates, evidence_frame
from src.modules import m2_economy as m


def sample():
    # Lower/upper boundaries have deliberately very different exports.
    g = pd.DataFrame({"country": ["DEU", "JPN", "IND", "USA", "SWE", "SGP", "ZZZ"],
                      "gdp": [100, 80, 125, 150, 50, 0, 100], "year": 2023})
    e = pd.DataFrame({"country": g.country, "export_value": [100_000, 400_000, 10_000, 100_000, 125_000, 1, 100_000], "year": 2023})
    return e, g


class EconomyMath(unittest.TestCase):
    def test_dimension_not_intersection_and_inclusive_boundaries(self):
        rows = prepare_year(*sample(), m.reference(), 2023)
        self.assertEqual(set(match_candidates(rows, "DEU", "gdp", 1.25).country), {"JPN", "IND"})
        self.assertEqual(set(match_candidates(rows, "DEU", "export_value", 1.25).country), {"USA", "SWE"})
        self.assertEqual(set(match_candidates(rows, "DEU", "gdp", 1.5).country), {"JPN", "IND", "USA"})

    def test_units_and_over_100_percent_are_valid(self):
        rows = prepare_year(*sample(), m.reference(), 2023).set_index("country")
        self.assertEqual(rows.loc["DEU", "gdp_billion_usd"], .1)
        self.assertEqual(rows.loc["DEU", "exports_billion_usd"], .1)
        self.assertEqual(rows.loc["DEU", "export_gdp_ratio"], 1)
        self.assertEqual(rows.loc["JPN", "export_gdp_ratio"], 5)
        self.assertTrue(rows.loc["JPN", "valid"])

    def test_zero_negative_nan_infinity_and_no_imputation(self):
        e, g = sample()
        g.loc[g.country.eq("JPN"), "gdp"] = -1
        g.loc[g.country.eq("IND"), "gdp"] = np.nan
        e["export_value"] = e.export_value.astype(float)
        e.loc[e.country.eq("USA"), "export_value"] = np.inf
        e = e[~e.country.eq("SWE")]
        rows = prepare_year(e, g, m.reference(), 2023).set_index("country")
        self.assertEqual(set(rows[rows.valid].index), {"DEU"})
        self.assertIn("Non-positive", rows.loc["JPN", "exclusion"])
        self.assertIn("Missing", rows.loc["SWE", "exclusion"])
        self.assertTrue(pd.isna(rows.loc["SWE", "export_value"]))
        self.assertTrue(rows.loc[~rows.valid, "export_gdp_ratio"].isna().all())

    def test_identity_is_dictionary_based_not_prefix_based(self):
        e, g = sample()
        g.loc[g.country.eq("SGP"), "gdp"] = 100
        rows = prepare_year(e, g, m.reference(), 2023).set_index("country")
        self.assertTrue(rows.loc["SGP", "valid"])
        self.assertTrue(rows.loc["SWE", "valid"])
        self.assertFalse(rows.loc["ZZZ", "valid"])

    def test_historical_territories(self):
        for year, excluded in [(1998, {"BEL", "SDN"}), (1999, {"SDN"}), (2011, {"SDN"}), (2012, set())]:
            e = pd.DataFrame({"year": year, "country": ["BEL", "SDN"], "export_value": [100., 100.]})
            g = pd.DataFrame({"year": year, "country": ["BEL", "SDN"], "gdp": [100., 100.]})
            rows = prepare_year(e, g, m.reference(), year)
            self.assertEqual(set(rows.loc[~rows.valid, "country"]), excluded)

    def test_no_match_and_invalid_anchor_do_not_widen(self):
        rows = prepare_year(*sample(), m.reference(), 2023)
        self.assertTrue(match_candidates(rows, "SWE", "gdp", 1.25).empty)
        self.assertTrue(match_candidates(rows, "SGP", "gdp", 1.5).empty)
        self.assertTrue(match_candidates(rows, "XXX", "gdp", 1.5).empty)

    def test_reject_duplicates_demo_and_outside_years(self):
        e, g = sample()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            prepare_year(pd.concat([e, e.iloc[:1]]), g, m.reference(), 2023)
        with self.assertRaisesRegex(ValueError, "1995 to 2023"):
            prepare_year(e, g, m.reference(), 2024)
        with self.assertRaisesRegex(ValueError, "Missing source"):
            prepare_year(e, g, m.reference(), 1995)
        e.attrs["demo"] = True
        with self.assertRaisesRegex(ValueError, "demo"):
            prepare_year(e, g, m.reference(), 2023)

    def test_no_mutation_of_shared_frames(self):
        e, g = data_loader.load_country_year(), data_loader.load_gdp_year()
        before_e, before_g = e.copy(deep=True), g.copy(deep=True)
        m.data_for_year(2023)
        pd.testing.assert_frame_equal(e, before_e)
        pd.testing.assert_frame_equal(g, before_g)

    def test_default_real_case_and_four_pools(self):
        rows = m.data_for_year(2023)
        expected = {("gdp", 1.25): {"JPN", "IND"}, ("gdp", 1.5): {"JPN", "IND", "GBR", "FRA"},
                    ("export_value", 1.25): {"USA"}, ("export_value", 1.5): {"USA"}}
        for (mode, factor), codes in expected.items():
            self.assertEqual(set(match_candidates(rows, "DEU", mode, factor).country), codes)
        a = rows.set_index("country")
        self.assertAlmostEqual(a.loc["DEU", "gdp"], 4456081.017)
        self.assertAlmostEqual(a.loc["JPN", "gdp"], 4212944.753)
        self.assertAlmostEqual(a.loc["DEU", "export_gdp_ratio"], .352672565, places=7)

    def test_figure_band_and_reference_lines(self):
        rows = m.data_for_year(2023)
        for mode in ["gdp", "export_value"]:
            peers = match_candidates(rows, "DEU", mode, 1.25)
            fig = m.scatter_figure(rows, "DEU", peers.iloc[0].country, mode, 1.25)
            self.assertEqual(fig.layout.xaxis.type, "log")
            self.assertEqual(fig.layout.yaxis.type, "log")
            self.assertEqual(len(fig.layout.shapes), 4)
            self.assertEqual(fig.layout.shapes[-1].yref if mode == "gdp" else fig.layout.shapes[-1].xref, "y domain" if mode == "gdp" else "x domain")
            for shape, trace, ratio in zip(fig.layout.shapes[:3], fig.data[:3], [.1, .5, 1]):
                self.assertEqual(float(shape.name.removeprefix("m2-ratio-")), ratio)
                self.assertEqual(shape.xref, "x domain")
                self.assertEqual(shape.yref, "y domain")
                self.assertEqual(list(trace.x), [None])
            self.assertEqual(sum(len(t.x) for t in fig.data[3:]), int(rows.valid.sum()))


class EconomyCallbacks(unittest.TestCase):
    def test_layout_has_no_nested_child_lists(self):
        from dash.development.base_component import Component
        def visit(component):
            if not isinstance(component, Component):
                return
            children = getattr(component, "children", None)
            if isinstance(children, (list, tuple)):
                self.assertFalse(any(isinstance(c, (list, tuple)) for c in children), type(component).__name__)
                for child in children:
                    visit(child)
            else:
                visit(children)
        visit(m.layout())

    def request(self, needle="M2-graph.figure", changes=None, changed="active-module.data", expect=200):
        values = {"active-module.data": "M2", "M2-year.value": 2023, "M2-anchor.value": "DEU",
                  "M2-mode.value": "gdp", "M2-factor.value": 1.25, "M2-comparator.value": "JPN",
                  "M2-graph.clickData": None}
        values.update(changes or {})
        key = next(k for k in app.app.callback_map if needle in k)
        spec = app.app.callback_map[key]
        outs = spec["output"] if isinstance(spec["output"], list) else [spec["output"]]
        out = [{"id": o.component_id, "property": o.component_property} for o in outs]
        def items(which):
            return [{**i, "value": values.get(f"{i['id']}.{i['property']}")} for i in spec[which]]
        response = app.server.test_client().post("/_dash-update-component", json={
            "output": key, "outputs": out if len(out) > 1 else out[0],
            "inputs": items("inputs"), "state": items("state"), "changedPropIds": [changed],
        })
        self.assertEqual(response.status_code, expect, response.data.decode()[:1500])
        return response.json["response"] if expect == 200 else None

    def test_default_cards_table_finding_and_context_agree(self):
        z = self.request()
        self.assertEqual(z["M2-comparator"]["value"], "JPN")
        self.assertEqual(len(z["M2-cards"]["children"]), 2)
        self.assertIn("2023", z["M2-finding"]["children"])
        self.assertIn("Japan", z["M2-finding"]["children"])
        self.assertEqual(len(z["M2-table"]["data"]), 2)
        self.assertEqual(z["M2-context"]["data"]["comparator"], "JPN")

    def test_zoom_preserved_for_comparison_but_reset_for_new_filters(self):
        context = self.request()["M2-context"]["data"]
        inputs = {"M2-context.data": context,
                  "M2-graph.relayoutData": {"xaxis.range[0]": 2, "xaxis.range[1]": 4,
                                            "yaxis.range[0]": 1, "yaxis.range[1]": 3},
                  "M2-comparator.value": "IND"}
        result = self.request(changes=inputs, changed="M2-comparator.value")
        axes = result["M2-graph"]["figure"]["layout"]
        self.assertEqual(axes["xaxis"]["range"], [2, 4])
        self.assertEqual(axes["yaxis"]["range"], [1, 3])
        self.assertFalse(axes["xaxis"]["autorange"])
        for change in [{"M2-year.value": 2010}, {"M2-factor.value": 1.5}, {"M2-mode.value": "export_value"}]:
            z = self.request(changes={**inputs, **change})
            self.assertTrue(z["M2-graph"]["figure"]["layout"]["xaxis"]["autorange"])
        z = self.request(changes={**inputs, "M2-graph.relayoutData": {"xaxis.autorange": True, "yaxis.autorange": True}})
        self.assertTrue(z["M2-graph"]["figure"]["layout"]["xaxis"]["autorange"])

    def test_switch_dimension_replaces_ineligible_comparator(self):
        z = self.request(changes={"M2-mode.value": "export_value"}, changed="M2-mode.value")
        self.assertEqual(z["M2-comparator"]["value"], "USA")
        self.assertIn("closest current match", z["M2-match-status"]["children"])
        self.assertIn("USA", z["M2-finding"]["children"])

    def test_year_change_updates_all_evidence(self):
        z = self.request(changes={"M2-year.value": 2010}, changed="M2-year.value")
        context = z["M2-context"]["data"]
        self.assertEqual(context["year"], 2010)
        self.assertIn("2010", z["M2-finding"]["children"])
        expected = match_candidates(m.data_for_year(2010), "DEU", "gdp", 1.25)
        self.assertEqual([o["value"] for o in z["M2-comparator"]["options"]], expected.country.tolist())

    def test_no_match_has_no_stale_card_or_finding(self):
        z = self.request(changes={"M2-anchor.value": "USA"}, changed="M2-anchor.value")
        self.assertIsNone(z["M2-comparator"]["value"])
        self.assertTrue(z["M2-comparator"]["disabled"])
        self.assertIn("has not been widened", z["M2-match-status"]["children"])
        self.assertNotIn("Japan", z["M2-finding"]["children"])

    def test_missing_and_nonpositive_anchors(self):
        e, g = sample()
        g.loc[g.country.eq("DEU"), "gdp"] = 0
        with patch.object(data_loader, "load_country_year", return_value=e), patch.object(data_loader, "load_gdp_year", return_value=g):
            z = self.request(changes={"M2-anchor.value": "DEU"})
            self.assertIn("Non-positive GDP", z["M2-match-status"]["children"])
            self.assertEqual(z["M2-cards"]["children"], [])

    def test_missing_file_or_demo_cannot_generate_findings(self):
        e, _ = sample()
        e.attrs["demo"] = True
        with patch.object(data_loader, "load_country_year", return_value=e):
            z = self.request()
        self.assertTrue(z["M2-export"]["disabled"])
        self.assertIsNone(z["M2-context"]["data"])
        self.assertIn("No finding", z["M2-finding"]["children"])
        with patch.object(m, "reference", side_effect=FileNotFoundError("missing dictionary")):
            z = self.request()
        self.assertIn("missing dictionary", z["M2-scope"]["children"])

    def test_click_only_selects_current_matches_and_does_not_filter_pool(self):
        z = self.request(changes={"M2-graph.clickData": {"points": [{"customdata": ["IND"]}]}}, changed="M2-graph.clickData")
        self.assertEqual(z["M2-comparator"]["value"], "IND")
        self.assertEqual(len(z["M2-table"]["data"]), 2)
        z = self.request(changes={"M2-graph.clickData": {"points": [{"customdata": ["CHN"]}]}}, changed="M2-graph.clickData")
        self.assertEqual(z["M2-comparator"]["value"], "JPN")
        z = self.request(changes={"M2-year.value": 2010, "M2-graph.clickData": {"points": [{"customdata": ["IND"]}]}}, changed="M2-year.value")
        self.assertNotEqual(z["M2-comparator"]["value"], "IND")

    def test_csv_contains_same_values_and_complete_exclusions(self):
        z = self.request()
        context = z["M2-context"]["data"]
        result = self.request("M2-download.data", {"M2-context.data": context, "M2-export.n_clicks": 1}, changed="M2-export.n_clicks")
        csv = pd.read_csv(io.StringIO(result["M2-download"]["data"]["content"]))
        rows = m.data_for_year(2023)
        self.assertEqual(len(csv), len(rows))
        self.assertEqual(set(csv[csv.is_match].country), {"JPN", "IND"})
        self.assertEqual(csv[csv.is_comparator].country.tolist(), ["JPN"])
        self.assertTrue(csv[~csv.valid].exclusion.notna().all())
        a = csv[csv.country.eq("JPN")].iloc[0]
        self.assertAlmostEqual(a.export_gdp_ratio, a.exports_thousand_current_usd / (a.gdp_million_current_usd * 1000))

    def test_six_anchors_global_candidates_and_hidden_module_guard(self):
        for code in m.FOCUS_COUNTRIES:
            z = self.request(changes={"M2-anchor.value": code})
            self.assertEqual(z["M2-context"]["data"]["anchor"], code)
            self.assertEqual([o["value"] for o in z["M2-anchor"]["options"]], list(m.FOCUS_COUNTRIES))
        for code in ["JPN", "IND", "XXX", None]:
            z = self.request(changes={"M2-anchor.value": code})
            self.assertIsNone(z["M2-context"]["data"])
            self.assertIn("six focus countries", z["M2-scope"]["children"])
            self.assertTrue(z["M2-export"]["disabled"])
        z = self.request()
        self.assertEqual({o["value"] for o in z["M2-comparator"]["options"]}, {"JPN", "IND"})
        self.request("M2-download.data", {"M2-export.n_clicks": 1, "M2-context.data": {"anchor": "JPN"}}, expect=204)
        self.request(changes={"active-module.data": "M4"}, expect=204)


if __name__ == "__main__":
    unittest.main()
