"""Plain-language views over the existing M4 metrics; no new denominators."""
import math
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src import theme
from src.analytics.product import label, two_year_metrics


def product_name(code):
    text = label(code)
    title = text.split(' · ', 1)[-1]
    return f'{title} (HS{code})'


def bars(fig, x, y, name, color, custom, row=None, col=None, suffix='%', digits=2, showlegend=True):
    trace = go.Bar(x=x, y=y, name=name, orientation='h', marker_color=color,
                   text=['—' if pd.isna(v) else f'{v:.{digits}f}{suffix}' for v in x],
                   legendgroup=name, showlegend=showlegend,
                   textposition='outside', cliponaxis=False, customdata=custom,
                   hovertemplate=name+'<br>%{y}<br>%{x:.3f}'+suffix+'<extra></extra>')
    fig.add_trace(trace, **({'row':row,'col':col} if row else {}))


RCA_GUIDE = (
    "RCA compares export shares: a product’s share in a country ÷ its share in world exports. "
    "1× = world benchmark; above 1× = more concentrated in that product. "
    "It is not an export-value multiple or a quality score."
)


def has_income_evidence(context):
    incomes = context.get('gdp', {})
    return all(isinstance(incomes.get(c), (int, float)) and math.isfinite(incomes[c])
               and incomes[c] > 0 for c in ['CHN', 'MEX'])


def story_guide(context, current, names):
    """Use the same filtered context as the figures, never a stale preset claim."""
    step = context.get('case_step') if context.get('selection_state') == 'Guided case' else 'custom'
    year, baseline = context.get('year', 2023), context.get('baseline', 2010)
    explanation = RCA_GUIDE if step in ['specialization', 'change'] or context.get('metric') == 'rca' else ''
    if step == 'structure':
        incomes = context.get('gdp', {})
        income_text = (f"{year} GDP per person: China ${incomes['CHN']:,.0f} · Mexico ${incomes['MEX']:,.0f}. "
                       if has_income_evidence(context) else "GDP per person unavailable; income similarity cannot be verified here. ")
        a = current[current.hs2.eq('87')].set_index('exporter')
        evidence = ''
        if {'CHN', 'MEX'} <= set(a.index):
            evidence = f"Vehicles & parts: {a.loc['CHN','share']:.1%} of China’s exports vs {a.loc['MEX','share']:.1%} of Mexico’s."
        return '01 / Do similar incomes mean similar export baskets?', income_text + evidence, explanation
    if step == 'specialization':
        a = current[current.exporter.eq('CHN')].set_index('hs2')
        evidence = f"China · {year}. Compare importance within China (left) with concentration relative to the world (right)."
        if {'85','95'} <= set(a.index):
            evidence += f" World export shares: electrical equipment {a.loc['85','world_share']:.2%}; toys, games & sports equipment {a.loc['95','world_share']:.2%}."
        return '02 / Is the largest export category also the most specialized?', evidence, explanation
    if step == 'change':
        return ('03 / If export share rises, is specialization above the world benchmark?',
                f'Vehicles & parts · {baseline} → {year}. Compare the share change on the left and RCA against 1× on the right. China and Mexico remain the same two cases.',
                explanation)
    return ('Explore / What does the current selection show?',
            f"{year} · {len(context.get('countries', []))} selected economies. Findings follow your current selection; preset conclusions are not carried over.", explanation)


def presentation(context, current, trade, names):
    countries = context.get('countries', [])
    products = context.get('products', [])
    year, baseline = context.get('year', 2023), context.get('baseline', 2010)
    step = context.get('case_step') if context.get('selection_state') == 'Guided case' else 'custom'
    if not countries or not products:
        return 'No valid comparison available', theme.empty_figure('Choose economies and products in Customize this comparison.'), 'Missing data are not treated as zero.'
    selected = current[current.exporter.isin(countries)]
    if step == 'specialization':
        a = selected[selected.exporter.eq('CHN')].set_index('hs2').reindex(['85','95'])
        fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=.13,
                            subplot_titles=['Share of China’s exports', 'Specialization relative to the world'])
        ys = [product_name(c) for c in ['85','95']]
        for col, vals, suffix in [(1,a.share*100,'%'), (2,a.rca,'×')]:
            bars(fig, vals.tolist(), ys, 'China', ['#7892ac', theme.ACCENT], [['CHN',c] for c in ['85','95']], 1,col,suffix)
            fig.update_xaxes(title_text='All-product export share (%)' if col==1 else 'Country share ÷ world share (×)',
                             range=[0,max(1, vals.max()*1.3)], row=1,col=col)
            fig.update_yaxes(autorange='reversed', row=1,col=col)
        fig.add_vline(x=1, line_dash='dot', line_color=theme.INK, row=1,col=2)
        fig.add_annotation(x=1, y=.5, xref='x2', yref='y2 domain', text='1× World benchmark', showarrow=False, xanchor='left', xshift=6, bgcolor='white', font=dict(size=12))
        supported = a.loc['85','share'] > a.loc['95','share'] and a.loc['95','rca'] > a.loc['85','rca']
        title = ('China: electrical equipment has the larger share; toys are more specialized' if supported else 'Compare product share with the world benchmark')
        note = 'Above 1×: the product takes a larger share of China’s exports than of world exports. This is RCA, not an export-value multiple or a technology score.'
        fig.update_layout(showlegend=False, height=365)
    elif step == 'change':
        fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=.13,
                            subplot_titles=['Share of each country’s exports', 'Specialization against the world benchmark'])
        data = [two_year_metrics(trade,c,year,baseline,['87']).iloc[0] for c in countries]
        ys = [names.get(c,c) for c in countries]
        for col, measure, suffix in [(1, 'share', '%'), (2, 'rca', '×')]:
            for endpoint, title_year, color in [('base',baseline,'#7892ac'),('current',year,theme.ACCENT)]:
                vals = [getattr(r, measure+'_'+endpoint)*(100 if measure=='share' else 1) for r in data]
                bars(fig, vals, ys, str(title_year), color, [[c,'87'] for c in countries],
                     1, col, suffix, digits=2 if measure=='share' else 3, showlegend=col==1)
            all_values = [getattr(r,measure+'_'+e)*(100 if measure=='share' else 1)
                          for r in data for e in ['base','current'] if pd.notna(getattr(r,measure+'_'+e))]
            upper = max(1, max(all_values, default=0)*1.2)
            fig.update_xaxes(title_text='All-product export share (%)' if measure=='share' else 'RCA (× world share)',
                             range=[0,upper], ticksuffix=suffix, row=1,col=col)
            fig.update_yaxes(autorange='reversed',row=1,col=col)
        fig.add_vline(x=1,line_dash='dot',line_color=theme.INK,row=1,col=2)
        fig.add_annotation(x=1,y=.5,xref='x2',yref='y2 domain',text='1× World benchmark',
                           showarrow=False,xanchor='left',xshift=6,bgcolor='white',font=dict(size=12))
        chn = next((r for c,r in zip(countries,data) if c=='CHN'),None)
        supported = chn is not None and not chn.missing_endpoint and chn.share_current>chn.share_base and chn.rca_current<1
        title = (f'China’s vehicle export share rose; RCA was below 1× in {year}' if supported else 'Vehicles and parts: compare share and specialization in two years')
        note = ('Each year uses its own all-product and world export totals. '
                'Two observations are not a continuous trend. Missing endpoints remain unknown. '
                'Full analysis retains all chapters and the optional dumbbell chart.')
        fig.update_layout(height=375,barmode='group')
    else:
        if step == 'structure' and '87' in products:
            products = ['87'] + [p for p in products if p != '87']
        metric = context.get('metric','share')
        factor, suffix = (100,'%') if metric == 'share' else (1,'×')
        fig = go.Figure()
        for c in countries:
            a = selected[selected.exporter.eq(c)].set_index('hs2').reindex(products)
            bars(fig, (a[metric]*factor).tolist(), [product_name(p) for p in products],names.get(c,c),theme.country_color(c),[[c,p] for p in products],suffix=suffix)
        title = 'Compare the selected export baskets'
        if step == 'structure' and '87' in products and {'CHN','MEX'} <= set(countries):
            a = selected[selected.hs2.eq('87')].set_index('exporter')
            if a.loc['MEX','share'] > a.loc['CHN','share']:
                title = "Similar incomes, different export baskets" if has_income_evidence(context) else "Different export baskets: compare China and Mexico"
            idx = products.index('87')
            fig.add_shape(type='rect',xref='paper',x0=0,x1=1,y0=idx-.46,y1=idx+.46,line_width=0,fillcolor='rgba(212,161,91,.14)',layer='below')
        note = ('Income means GDP per person; similar does not mean identical. ' if context.get('comparison_mode')=='income' else '') + 'Shares use all-product exports, not just the displayed chapters. Click a bar to inspect the product in Full analysis.'
        if metric == 'rca':
            fig.add_vline(x=1,line_dash='dot',line_color=theme.INK)
            note += ' 1× marks the world benchmark; above 1× indicates relative specialization.'
        if len(countries)<2:
            title = 'One economy selected — no cross-country comparison'
        fig.update_layout(height=max(420,100+len(products)*max(50,len(countries)*20)),barmode='group',
                          xaxis_title='Share of all-product exports (%)' if metric=='share' else 'Country share ÷ world share (×)',yaxis_autorange='reversed')
    fig.update_layout(template=theme.PLOT_TEMPLATE, margin=dict(l=20,r=70,t=75,b=60),
                      font=dict(size=13,color=theme.INK),legend=dict(orientation='h',y=1.12,x=0),bargap=.32)
    if step == 'change':
        fig.update_layout(legend=dict(orientation='h', y=1.3, x=0), margin=dict(t=80))
    fig.update_xaxes(rangemode='tozero',fixedrange=True)
    fig.update_yaxes(automargin=True,fixedrange=True)
    return title, fig, f'{year} · '+note
