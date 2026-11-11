"""Presentation variants must preserve the accepted analytical contracts."""
import unittest
from unittest.mock import patch
import numpy as np
from src.modules import m3_network as m
from test_final_integration import call


class M3Views(unittest.TestCase):
    def test_region_encodings_match_for_all_focal_economies_and_directions(self):
        for country in m.FOCUS:
            for direction in ['export', 'import']:
                fig = m.regional_comparison(country, 2023, direction)
                for code, trace in zip(['85', '87'], fig.data):
                    shares, low, high = m.regional(country, 2023, code, direction)
                    np.testing.assert_allclose(trace.x, [shares[r] * 100 for r in trace.y])
                    self.assertAlmostEqual(sum(trace.x), 100)
                    self.assertIn('Unknown', trace.y)
                    self.assertAlmostEqual(high-low, shares['Unknown'])

    def test_gravity_test_compares_home_region_with_largest_rival(self):
        from src.analytics.partners import REGIONS
        from src import data_loader
        meta = (data_loader.load_country_meta().drop_duplicates('iso3')
                .set_index('iso3'))
        for country in m.FOCUS:
            home = meta.loc[country, 'region']
            home = 'Oceania' if home == 'Pacific' else home
            for direction in ['export', 'import']:
                fig = m.gravity_test(country, 2023, direction)
                for code, trace in zip(['85', '87'], fig.data):
                    shares, _, _ = m.regional(country, 2023, code, direction)
                    others = {r: shares[r] for r in REGIONS
                              if r not in (home, 'Unknown')}
                    rival = max(others, key=others.get)
                    self.assertAlmostEqual(
                        float(trace.x[0]),
                        (shares[home] - others[rival]) * 100, places=6)
                    # The verdict must respect the unknown-region bound.
                    own, unk = shares[home], shares['Unknown']
                    if own > others[rival]:
                        self.assertIn('holds', trace.text[0])
                    elif own + unk < others[rival]:
                        self.assertIn('breaks', trace.text[0])
                    else:
                        self.assertIn('unclear', trace.text[0])

    def test_gravity_verdict_names_the_exception(self):
        self.assertIn('breaks for electronics', m.gravity_takeaway('USA', 2023, 'import'))
        self.assertIn('breaks for vehicles', m.gravity_takeaway('CHN', 2023, 'import'))
        self.assertIn('no exception', m.gravity_takeaway('MEX', 2023, 'export'))
        self.assertIn('Inconclusive', m.gravity_takeaway('DEU', 2023, 'import'))

    def test_no_data_never_becomes_zero_or_a_difference(self):
        original = m.regional
        with patch.object(m, 'regional', side_effect=lambda c,y,p,d: None if p == '85' else original(c,y,p,d)):
            fig = m.regional_comparison('CHN', 2023, 'export')
        self.assertTrue(all(np.isnan(v) for v in fig.data[0].x))
        self.assertEqual(sum(a.text == '—' for a in fig.layout.annotations), 6)
        with patch.object(m, 'regional', return_value=None):
            fig = m.regional_comparison('CHN', 2023, 'export')
            self.assertEqual(len(fig.data), 0)

    def test_light_map_preserves_all_geometry_hover_and_widths(self):
        for direction in ['export', 'import']:
            original = m.map_figure('CHN', m.partners('CHN',2023,'87',direction),direction,10,'RUS')
            light = m.light_map(original)
            self.assertEqual(len(original.data), len(light.data))
            for a,b in zip(original.data, light.data):
                for attr in ['lon','lat','locations','z','customdata','text','hovertemplate']:
                    if hasattr(a, attr):
                        self.assertEqual(str(getattr(a,attr)), str(getattr(b,attr)))
                if a.type == 'scattergeo':
                    self.assertEqual(a.line.width, b.line.width)
            self.assertEqual(original.layout.paper_bgcolor, m.theme.MAP_BG)
            self.assertEqual(light.layout.paper_bgcolor, '#ffffff')

    def test_selected_flow_and_its_partner_marker_share_one_highlight(self):
        def arcs(fig):
            return [t for t in fig.data if t.type == 'scattergeo'
                    and t.mode == 'lines' and t.hovertemplate]

        def markers(fig):
            return next(t for t in fig.data
                        if t.type == 'scattergeo' and 'markers' in (t.mode or ''))

        d = m.partners('CHN', 2023, '87', 'export')
        self.assertTrue(all(t.line.color == '#75b5c7'
                            for t in arcs(m.map_figure('CHN', d, 'export', 10, None))))
        fig = m.map_figure('CHN', d, 'export', 10, 'RUS')
        flows = arcs(fig)
        self.assertEqual([t.line.color for t in flows].count('#e5b878'), 1)
        self.assertEqual(flows[-1].line.color, '#e5b878')
        self.assertTrue(all(t.line.color == m.DIM_ARC for t in flows[:-1]))
        # Every partner dot carries the same colour as its own arc.
        codes = list(markers(fig).customdata)
        dot = dict(zip(codes, markers(fig).marker.color))
        arc = {t.customdata[0]: t.line.color for t in flows}
        self.assertEqual(dot['CHN'], '#e5b878')  # focal economy
        for code in codes[1:]:
            self.assertEqual(dot[code], arc[code])
        self.assertEqual(dot['RUS'], '#e5b878')
        self.assertEqual(dot['USA'], m.DIM_ARC)
        light = m.light_map(fig)
        self.assertTrue(all(t.line.color == m.DIM_ARC_LIGHT
                            for t in arcs(light)[:-1]))
        self.assertEqual(arcs(light)[-1].line.color, '#b27a2a')
        light_dot = dict(zip(markers(light).customdata, markers(light).marker.color))
        self.assertEqual(light_dot['RUS'], '#b27a2a')
        self.assertEqual(light_dot['USA'], m.DIM_ARC_LIGHT)

    def test_selected_partner_country_is_filled_in_the_arrow_amber(self):
        def fills(fig):
            return {t.locations[0]: t.colorscale[0][1]
                    for t in fig.data if t.type == 'choropleth' and len(t.locations) == 1}

        d = m.partners('CHN', 2023, '87', 'export')
        self.assertEqual(fills(m.map_figure('CHN', d, 'export', 10, None)), {'CHN': '#bd955c'})
        fig = m.map_figure('CHN', d, 'export', 10, 'RUS')
        self.assertEqual(fills(fig), {'CHN': '#bd955c', 'RUS': m.HIGHLIGHT})
        self.assertEqual(fills(m.light_map(fig))['RUS'], m.HIGHLIGHT_LIGHT)
        # A focal economy acting as a partner is filled the same way, otherwise
        # the highlight would depend on which row the partner came from.
        for partner in ['USA', 'DEU', 'MEX', 'NLD', 'ITA']:
            picked = m.map_figure('CHN', d, 'export', 10, partner)
            self.assertEqual(fills(picked).get(partner), m.HIGHLIGHT)
            self.assertEqual(fills(picked)['CHN'], '#bd955c')

    def test_flow_animation_targets_the_live_graph_id(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'assets' / 'm3_flow.js').read_text(
            encoding='utf-8'
        )
        self.assertIn('#M3-graph', source)
        self.assertEqual(m.cid('graph'), 'M3-graph')
        self.assertIn('path.js-line', source)
        self.assertIn('prefers-reduced-motion', source)

    def test_http_render_uses_grouped_regions_and_light_map(self):
        values = {'active-module.data':'M3', 'M3-selected.data':'RUS', **{
            'M3-'+k+'.value':v for k,v in dict(country='CHN',year=2023,product='87',direction='export',top=10,view='map').items()}}
        r = call('M3-graph.figure', values, 'M3-country.value')
        self.assertEqual(r.status_code,200,r.data[:300])
        response = r.json['response']
        self.assertEqual(response['M3-regions']['figure']['layout']['barmode'],'group')
        self.assertEqual(response['M3-graph']['figure']['layout']['paper_bgcolor'],'#ffffff')
