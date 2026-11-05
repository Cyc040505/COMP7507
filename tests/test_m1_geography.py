import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analytics.geography import analyze, trade_by_partner, partner_frame
from src.modules.m1_geography import (
    _comparison_rows, _focus_subset, _geo_positions, _map_figure, _map_summary,
    _preserve_map_view, layout,
)


def _meta():
    return pd.DataFrame(
        [
            ("AAA", "Alpha", "Asia"),
            ("P1", "Partner One", "Asia"),
            ("P2", "Partner Two", "Europe"),
            ("P3", "Partner Three", "Europe"),
        ],
        columns=["iso3", "name", "region"],
    )


def _geodist():
    return pd.DataFrame(
        [
            ("AAA", "P1", 100.0, 90.0, 1, 0),
            ("AAA", "P2", 4000.0, 3800.0, 0, 1),
            ("AAA", "P3", 9000.0, 8800.0, 0, 0),
        ],
        columns=["iso_o", "iso_d", "dist", "distw", "contig", "comlang_off"],
    )


class GeographyTests(unittest.TestCase):
    def test_share_uses_selected_scope_denominator(self):
        pair = pd.DataFrame(
            [
                (2024, "AAA", "P1", 90.0),
                (2024, "AAA", "P2", 10.0),
                (2024, "AAA", "AAA", 999.0),
            ],
            columns=["year", "exporter", "importer", "value"],
        )
        res = analyze(pair, _geodist(), _meta(), "AAA", 2024)
        frame = res["frame"]
        self.assertNotIn("AAA", set(frame["partner"]))
        self.assertAlmostEqual(frame.set_index("partner").loc["P1", "share_pct"], 90.0)
        self.assertAlmostEqual(frame.set_index("partner").loc["P2", "share_pct"], 10.0)

    def test_hs2_filter_changes_denominator(self):
        pair = pd.DataFrame(
            [
                (2024, "AAA", "P1", "01", 80.0),
                (2024, "AAA", "P2", "01", 20.0),
                (2024, "AAA", "P1", "02", 999.0),
            ],
            columns=["year", "exporter", "importer", "hs2", "value"],
        )
        res = analyze(pair, _geodist(), _meta(), "AAA", 2024, hs2="01")
        frame = res["frame"]
        self.assertEqual(set(frame["partner"]), {"P1", "P2"})
        self.assertAlmostEqual(frame.set_index("partner").loc["P1", "share_pct"], 80.0)

    def test_metric_falls_back_to_available_column(self):
        pair = pd.DataFrame(
            [(2024, "AAA", "P1", 100.0)],
            columns=["year", "exporter", "importer", "value"],
        )
        geo = _geodist().drop(columns=["distw"])
        res = analyze(pair, geo, _meta(), "AAA", 2024, metric="distw")
        self.assertEqual(res["metric_used"], "dist")
        self.assertTrue(res["frame"].loc[0, "has_distance"])

    def test_missing_distance_is_kept_but_not_plotted(self):
        pair = pd.DataFrame(
            [
                (2024, "AAA", "P1", 60.0),
                (2024, "AAA", "P2", 40.0),
                (2024, "AAA", "P9", 30.0),
            ],
            columns=["year", "exporter", "importer", "value"],
        )
        res = analyze(pair, _geodist(), _meta(), "AAA", 2024)
        self.assertEqual(res["stats"]["n"], 3)
        self.assertEqual(res["stats"]["n_missing"], 1)
        self.assertAlmostEqual(res["stats"]["coverage"], 2 / 3)
        self.assertFalse(res["frame"].set_index("partner").loc["P9", "has_distance"])

    def test_spearman_negative_for_inverse_relation(self):
        rows = []
        geodist_rows = []
        for i, partner in enumerate([f"P{i}" for i in range(10)], 1):
            rows.append((2024, "AAA", partner, float(11 - i)))
            geodist_rows.append(("AAA", partner, float(i), float(i), 0, 0))
        pair = pd.DataFrame(rows, columns=["year", "exporter", "importer", "value"])
        geo = pd.DataFrame(
            geodist_rows,
            columns=["iso_o", "iso_d", "dist", "distw", "contig", "comlang_off"],
        )
        res = analyze(pair, geo, _meta(), "AAA", 2024)
        self.assertLess(res["stats"]["spearman"], -0.9)

    def test_exceptions_quartile_rule(self):
        rows = []
        geodist_rows = []
        # Shares decrease as distance grows, so the nearest low-share and the
        # farthest high-share cases can be constructed explicitly.
        values = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
        for i, partner in enumerate([f"P{n}" for n in range(1, 11)]):
            rows.append((2024, "AAA", partner, float(values[i])))
            geodist_rows.append(("AAA", partner, float(i + 1), float(i + 1), 0, 0))
        pair = pd.DataFrame(rows, columns=["year", "exporter", "importer", "value"])
        geo = pd.DataFrame(
            geodist_rows,
            columns=["iso_o", "iso_d", "dist", "distw", "contig", "comlang_off"],
        )
        res = analyze(pair, geo, _meta(), "AAA", 2024)
        kinds = {r["partner"]: r["kind"] for r in res["exceptions"]}
        self.assertEqual(kinds.get("P1"), "Near but weak")
        self.assertEqual(kinds.get("P10"), "Far but strong")

    def test_empty_selection(self):
        pair = pd.DataFrame(
            columns=["year", "exporter", "importer", "value"]
        )
        res = analyze(pair, _geodist(), _meta(), "AAA", 2024)
        self.assertEqual(res["stats"]["n"], 0)
        self.assertEqual(res["exceptions"], [])
        self.assertTrue(res["frame"].empty)


class GeographyMapTests(unittest.TestCase):
    def test_map_gestures_persist_for_same_exporter_and_reset_for_new_exporter(self):
        result = self._map_result()
        previous = _map_figure(result, "AAA", "top10").to_plotly_json()
        gesture = {"geo.projection.scale": 3, "geo.center.lon": 100, "geo.center.lat": 20}
        changed = _preserve_map_view(_map_figure(result, "AAA", "nearest10"), gesture, previous)
        self.assertEqual(changed.layout.geo.projection.scale, 3)
        self.assertEqual(changed.layout.geo.center.lon, 100)
        # A subsequent gesture can carry only the changed part of the view.
        updated = _preserve_map_view(_map_figure(result, "AAA", "all"),
                                     {"geo.center.lon": 110}, changed.to_plotly_json())
        self.assertEqual(updated.layout.geo.projection.scale, 3)
        self.assertEqual(updated.layout.geo.center.lon, 110)
        reset = _preserve_map_view(_map_figure(result, "BBB", "all"), gesture, previous)
        self.assertEqual(reset.layout.geo.projection.scale, 1)
        self.assertEqual(reset.layout.geo.center.lon, 0)

    def _map_result(self):
        pair = pd.DataFrame(
            [(2024, "AAA", "P1", 10.0), (2024, "AAA", "P2", 60.0),
             (2024, "AAA", "P3", 30.0)],
            columns=["year", "exporter", "importer", "value"],
        )
        return analyze(pair, _geodist(), _meta(), "AAA", 2024)

    def test_partner_country_fills_encode_share_without_marker_traces(self):
        result = self._map_result()
        for show in ("top10", "all"):
            figure = _map_figure(result, "AAA", show)
            partners = next(t for t in figure.data if t.name == "Trade partners")
            self.assertEqual(partners.type, "choropleth")
            self.assertEqual(dict(zip(partners.locations, partners.z)),
                             {"P1": 10.0, "P2": 60.0, "P3": 30.0})
            self.assertFalse(partners.reversescale)
            self.assertIn("share", partners.colorbar.title.text)
            self.assertFalse(any("markers" in (getattr(t, "mode", "") or "")
                                 for t in figure.data))

    def test_nearest_country_fills_reverse_distance_scale_and_ranking(self):
        result = self._map_result()
        figure = _map_figure(result, "AAA", "nearest10")
        partners = next(t for t in figure.data if t.name == "Trade partners")
        self.assertEqual(dict(zip(partners.locations, partners.z)),
                         {"P1": 90.0, "P2": 3800.0, "P3": 8800.0})
        self.assertTrue(partners.reversescale)  # Lower km values get the dark end.
        self.assertIn("km", partners.colorbar.title.text)
        summary = _map_summary(result, "AAA", "nearest10")
        ranking = next(c for c in summary if getattr(c, "className", "") == "m1-rank-list")
        self.assertEqual(ranking.children[0].children[0].children[0].children, "P1")
        self.assertEqual(ranking.children[0].children[0].children[1].children, "90 km")

    def test_small_economies_have_explicit_coordinates(self):
        positions = _geo_positions(["HKG", "SGP"])
        self.assertAlmostEqual(positions["lat"][0], 22.26667)
        self.assertAlmostEqual(positions["lon"][1], 103.85)

    def test_empty_scope_renders_without_partner_columns(self):
        pair = pd.DataFrame(columns=["year", "exporter", "importer", "value"])
        res = analyze(pair, _geodist(), _meta(), "AAA", 2024)
        self.assertTrue(_focus_subset(res["frame"], "top10").empty)
        self.assertEqual(_comparison_rows(res["frame"]), [])
        self.assertTrue(_map_summary(res, "AAA", "top10"))
        self.assertIn("No partners", _map_figure(res, "AAA", "top10").to_json())

    def test_display_filter_keeps_full_export_denominator(self):
        frame = pd.DataFrame({
            "partner": [f"P{i}" for i in range(12)],
            "name": [f"Partner {i}" for i in range(12)],
            "value": list(range(1, 13)),
            "share_pct": [v / 78 * 100 for v in range(1, 13)],
            "distance": list(range(1, 13)),
            "has_distance": [True] * 12,
        })
        subset = _focus_subset(frame, "top10")
        self.assertEqual(len(subset), 10)
        self.assertAlmostEqual(subset["share_pct"].sum(), 75 / 78 * 100)
        self.assertAlmostEqual(frame["share_pct"].sum(), 100)

    def test_default_exporter_is_available_on_initial_layout(self):
        def find(component, target):
            if getattr(component, "id", None) == target:
                return component
            children = getattr(component, "children", [])
            for child in children if isinstance(children, list) else [children]:
                found = find(child, target)
                if found is not None:
                    return found
            return None

        exporter = find(layout(), "M1-exporter")
        self.assertIn(exporter.value, {option["value"] for option in exporter.options})


if __name__ == "__main__":
    unittest.main()
