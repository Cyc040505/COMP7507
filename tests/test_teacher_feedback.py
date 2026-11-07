"""Presentation must remain faithful when the user leaves the guided presets."""
import unittest
import numpy as np
from src.modules import m4_product as m4, m3_network as m3
from src.modules.m4_presentation import presentation, story_guide
from test_final_integration import call


class TeacherFeedback(unittest.TestCase):
    def context(self, step):
        c=m4.recipe(step)
        incomes=m4.pd.to_numeric(m4.data_loader.load_gdp_year().query('year == 2023').set_index('country').gdp_per_capita, errors='coerce').to_dict()
        return dict(c, selection_state='Guided case',case_step=step,comparison_mode=c['mode'],gdp=incomes)

    def render(self,c):
        return presentation(c,m4.metrics(c['year']),m4.trade(),m4.names())

    def test_structure_has_same_full_denominator_values(self):
        c=self.context('structure'); title,fig,note=self.render(c)
        self.assertIn('Similar incomes',title)
        question,evidence,rca=story_guide(c,m4.metrics(2023),m4.names())
        self.assertIn('5.4%',evidence);self.assertIn('26.1%',evidence)
        self.assertIn('$12,509',evidence);self.assertIn('$13,788',evidence)
        for trace, country in zip(fig.data,c['countries']):
            expected=m4.metrics(2023).query('exporter == @country').set_index('hs2').reindex([v[1] for v in trace.customdata]).share*100
            np.testing.assert_allclose(trace.x,expected)
            self.assertEqual(trace.customdata[0][0],country)
        self.assertIn('GDP per person',note)

    def test_specialization_retains_ratio_and_its_baseline(self):
        title,fig,note=self.render(self.context('specialization'))
        self.assertIn('toys are more specialized',title)
        np.testing.assert_allclose(fig.data[0].x,[31.3646,2.5996],atol=.0001)
        np.testing.assert_allclose(fig.data[1].x,[2.140111,4.118182],atol=.00001)
        self.assertEqual(fig.layout.shapes[0].x0,1)
        self.assertIn('not an export-value multiple',note)

    def test_custom_selection_has_no_preset_claim(self):
        c=self.context('specialization')|dict(selection_state='Custom exploration',countries=['USA'],products=['27'])
        title,fig,note=self.render(c)
        self.assertNotIn('China',title);self.assertNotIn('toys',title)
        self.assertIn('One economy',title)
        self.assertEqual(len(fig.data),1)
        title,fig,note=self.render(c|dict(countries=[]))
        self.assertEqual(len(fig.data),0)
        self.assertIn('No valid comparison',title)

    def test_change_uses_real_endpoints_and_click_drills_into_original(self):
        c=self.context('change');title,fig,note=self.render(c)
        self.assertIn('below 1',title)
        self.assertEqual(fig.data[0].name,'2010');self.assertEqual(fig.data[1].name,'2023')
        r=call('M4-inspect.value',{'active-module.data':'M4','M4-comparison.data':c,
              'M4-case.data':m4.recipe('change'),'M4-story.clickData':{'points':[{'customdata':['MEX','87']}] }},'M4-story.clickData')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['response']['M4-focus']['value'],'MEX')
        self.assertEqual(r.json['response']['M4-inspect']['value'],'87')

    def test_m3_direction_and_country_are_not_stale(self):
        self.assertIn('exports going to Asia',m3.regional_takeaway('CHN',2023,'export'))
        title=m3.regional_takeaway('DEU',2024,'import')
        self.assertIn('Germany, 2024',title);self.assertIn('imports coming from Europe',title)
        self.assertNotIn('exports going',title)

    def test_m2_takeaway_tracks_comparison_and_empty_state(self):
        for country in ['JPN','USA']:
            r=call('M2-takeaway.children',{'active-module.data':'M2','M2-context.data':dict(year=2023,anchor='DEU',comparator=country,mode='gdp')},'M2-context.data')
            self.assertEqual(r.status_code,200)
            self.assertIn('2023',r.get_data(as_text=True))
            self.assertIn('Japan' if country=='JPN' else 'United States',r.get_data(as_text=True))
        r=call('M2-takeaway.children',{'active-module.data':'M2','M2-context.data':None},'M2-context.data')
        self.assertNotIn('Japan',r.get_data(as_text=True))

    def test_change_plots_both_shares_and_rca_from_each_year(self):
        from src.analytics.product import two_year_metrics
        c=self.context('change');title,fig,note=self.render(c)
        self.assertEqual(len(fig.data),4)
        self.assertEqual([t.xaxis for t in fig.data],['x','x','x2','x2'])
        for col,measure in [(0,'share'),(2,'rca')]:
            for j,endpoint in enumerate(['base','current']):
                expected=[getattr(two_year_metrics(m4.trade(),country,2023,2010,['87']).iloc[0],measure+'_'+endpoint)
                          * (100 if measure=='share' else 1) for country in c['countries']]
                np.testing.assert_allclose(fig.data[col+j].x,expected)
        self.assertEqual(fig.layout.shapes[0].xref,'x2')
        self.assertEqual(fig.layout.shapes[0].x0,1)
        self.assertEqual([t.showlegend for t in fig.data],[True,True,False,False])
        self.assertIn('0.288',fig.data[2].text[0]);self.assertIn('0.649',fig.data[3].text[0])

    def test_missing_income_does_not_assert_similarity(self):
        c=self.context('structure')|{'gdp':{}}
        title,fig,note=self.render(c)
        self.assertNotIn('Similar incomes',title)
        q,e,r=story_guide(c,m4.metrics(2023),m4.names())
        self.assertIn('cannot be verified',e)
        custom=self.context('specialization')|{'selection_state':'Custom exploration'}
        q,e,r=story_guide(custom,m4.metrics(2023),m4.names())
        self.assertNotIn('14.66',e)
        self.assertIn('current selection',e)

    def test_change_missing_endpoint_is_not_zero_or_growth_claim(self):
        c=self.context('change')
        frame=m4.trade()
        frame=frame[~(frame.year.eq(2010)&frame.exporter.eq('CHN')&frame.hs2.eq('87'))]
        title,fig,note=presentation(c,m4.metrics(2023),frame,m4.names())
        self.assertTrue(np.isnan(fig.data[0].x[0]))
        self.assertTrue(np.isnan(fig.data[2].x[0]))
        self.assertNotIn('rose',title)
        self.assertIn('Missing endpoints',note)

    def test_story_http_has_income_evidence_and_keeps_original_view_available(self):
        c=self.context('structure')
        values={'active-module.data':'M4','M4-comparison.data':c,'M4-presentation-mode.value':'key'}
        r=call('M4-story-title.children',values,'M4-comparison.data')
        self.assertEqual(r.status_code,200,r.data[:300])
        body=r.json['response']
        self.assertIn('$12,509',body['M4-story-evidence']['children'])
        self.assertEqual(body['M4-story-rca']['children'],'')
        r=call('M4-story-title.children',values|{'M4-presentation-mode.value':'full'},'M4-presentation-mode.value')
        self.assertEqual(r.json['response']['M4-full-analysis']['style']['display'],'grid')
        c=self.context('change')
        r=call('M4-story-title.children',values|{'M4-comparison.data':c},'M4-comparison.data')
        explanation=r.json['response']['M4-story-rca']['children']
        self.assertIn('divided by', explanation[0]['props']['aria-label'])
        self.assertIn('World benchmark', str(explanation))
        self.assertIn('not export amounts or product quality', str(explanation))
