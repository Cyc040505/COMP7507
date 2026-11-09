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

    def test_http_toggle_keeps_records_findings_and_matrix(self):
        values = {'active-module.data':'M3', 'M3-selected.data':'RUS', **{
            'M3-'+k+'.value':v for k,v in dict(country='CHN',year=2023,product='87',direction='export',top=10,view='map').items()}}
        def render(extra):
            r = call('M3-graph.figure',values | extra,'M3-region-view.value')
            self.assertEqual(r.status_code,200,r.data[:300])
            return r.json['response']
        old = render({'M3-region-view.value':'composition','M3-map-palette.value':'dark'})
        new = render({'M3-region-view.value':'compare','M3-map-palette.value':'light'})
        for key in ['M3-records','M3-finding','M3-scope','M3-detail','M3-ranking']:
            self.assertEqual(old[key],new[key])
        self.assertEqual(old['M3-regions']['figure']['layout']['barmode'],'stack')
        self.assertEqual(new['M3-regions']['figure']['layout']['barmode'],'group')
        values['M3-view.value']='matrix'
        self.assertEqual(render({'M3-map-palette.value':'dark'})['M3-graph'],
                         render({'M3-map-palette.value':'light'})['M3-graph'])
