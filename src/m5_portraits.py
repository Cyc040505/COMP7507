"""Presentation of M5's existing annual evidence as comparable country cards."""

import math

import plotly.graph_objects as go
from dash import dcc, html

from src import theme
from src.ids import mid

FOCUS_COUNTRIES = ("USA", "DEU", "CHN", "MEX", "NLD", "ITA")
# Match M4's base_style without coupling the two modules' analytical code.
PLOT_FONT = "Segoe UI, system-ui, sans-serif"
NAMES = {
    "USA": "United States",
    "DEU": "Germany",
    "CHN": "China",
    "MEX": "Mexico",
    "NLD": "Netherlands",
    "ITA": "Italy",
}


def cid(name):
    return mid("M5", name)


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def number(value, digits=1):
    return f"{value:,.{digits}f}" if finite(value) else "—"


def _hidden_graph(country):
    # Fixed input IDs also remain mounted in empty/error states. No visible
    # placeholder series is drawn, and remounts do not change the selected year.
    return html.Div(
        dcc.Graph(
            id=cid("portrait-" + country),
            figure={"data": [], "layout": {"height": 1}},
            config={"displayModeBar": False},
        ),
        style={"display": "none"},
        **{"aria-hidden": "true"},
    )


def _figure(series, country, window, baseline, event, selected, ceiling):
    fig = go.Figure(
        go.Scatter(
            x=[r["year"] for r in series],
            y=[r.get("index") for r in series],
            customdata=[[r.get("value")] for r in series],
            mode="lines+markers",
            connectgaps=False,
            line={"color": theme.country_color(country), "width": 2.5},
            marker={
                "color": theme.country_color(country),
                "size": [8 if r["year"] == selected else 4 for r in series],
            },
            name=country,
            hovertemplate=(
                f"<b>{NAMES[country]}</b> · %{{x}}<br>Index: %{{y:.1f}}"
                "<br>Exports: %{customdata[0]:,.0f} thousand USD<extra></extra>"
            ),
        )
    )
    theme.style_figure(fig, height=205)
    start, end = window
    fig.update_layout(
        margin={"l": 37, "r": 15, "t": 28, "b": 32},
        font={"family": PLOT_FONT, "size": 12},
        showlegend=False,
        hovermode="closest",
        clickmode="event",
        dragmode=False,
        uirevision=f"M5-portrait-{country}-{start}-{end}-{baseline}",
    )
    ticks = sorted({start, baseline, end})
    fig.update_xaxes(
        title=None,
        range=[start - 0.25, end + 0.25],
        tickmode="array",
        tickvals=ticks,
        tickfont={"size": 12},
        fixedrange=True,
    )
    fig.update_yaxes(
        title=None, range=[0, ceiling], nticks=4, tickfont={"size": 12}, fixedrange=True
    )
    fig.add_hline(y=100, line_color=theme.MUTED, line_width=1, line_dash="dot")
    fig.add_vrect(
        x0=event - 0.12,
        x1=event + 0.12,
        fillcolor=theme.ACCENT_SOFT,
        opacity=0.8,
        line_width=0,
        layer="below",
    )
    fig.add_annotation(
        x=event,
        y=1.02,
        xref="x",
        yref="paper",
        text=str(event),
        showarrow=False,
        font={"size": 12, "color": theme.MUTED},
        yanchor="bottom",
    )
    fig.add_vline(x=selected, line_color=theme.ACCENT_LINE, line_width=1, layer="below")
    return fig


def _bar_figure(series, country, window, baseline, event, selected, ceiling):
    # A clicked baseline/event still leaves the endpoint visible for comparison.
    years = sorted({baseline, event, selected})
    if len(years) < 3:
        years = sorted(set(years) | {window[1]})
    by_year = {r["year"]: r for r in series}
    values = [by_year.get(y, {}).get("index") for y in years]
    color = theme.country_color(country)
    fig = go.Figure(
        go.Bar(
            x=values,
            y=[str(y) for y in years],
            orientation="h",
            customdata=[[y, by_year.get(y, {}).get("value")] for y in years],
            marker={
                "color": [theme.LINE if y == baseline else color for y in years],
                "opacity": [1 if y in (baseline, selected) else 0.45 for y in years],
                "line": {
                    "color": theme.ACCENT,
                    "width": [1.5 if y == selected else 0 for y in years],
                },
            },
            text=[number(v) if finite(v) else "" for v in values],
            textposition="outside",
            cliponaxis=False,
            name=country,
            hovertemplate=(
                f"<b>{NAMES[country]}</b> · %{{customdata[0]}}"
                "<br>Index: %{x:.1f}<br>Exports: %{customdata[1]:,.0f} thousand USD<extra></extra>"
            ),
        )
    )
    theme.style_figure(fig, height=205)
    fig.update_layout(
        margin={"l": 43, "r": 12, "t": 28, "b": 32},
        font={"family": PLOT_FONT, "size": 12},
        showlegend=False,
        bargap=0.4,
        clickmode="event",
        dragmode=False,
        uirevision=f"M5-bars-{country}-{baseline}-{event}-{selected}-{window[1]}",
    )
    fig.update_xaxes(
        title=None,
        range=[0, ceiling * 1.12],
        fixedrange=True,
        dtick=50 if ceiling <= 200 else 100,
        tickfont={"size": 12},
    )
    fig.update_yaxes(
        title=None,
        type="category",
        categoryorder="array",
        categoryarray=[str(y) for y in years],
        autorange="reversed",
        fixedrange=True,
        showgrid=False,
        tickfont={"size": 12},
    )
    fig.add_vline(x=100, line_color=theme.MUTED, line_dash="dot", line_width=1)
    fig.add_annotation(
        x=100,
        y=1.08,
        xref="x",
        yref="paper",
        text=f"{baseline} = 100",
        showarrow=False,
        font={"size": 12, "color": theme.MUTED},
    )
    for year, value in zip(years, values):
        if not finite(value):
            fig.add_annotation(
                x=0,
                y=str(year),
                text="No data",
                showarrow=False,
                xanchor="left",
                font={"size": 12, "color": theme.MUTED},
            )
    return fig


def portrait_cards(
    countries,
    rows,
    summaries,
    baseline,
    event,
    window,
    metric,
    product,
    selected,
    *,
    message=None,
    chart_type="line",
    show_graph=True,
):
    """Use computed rows only; retain nulls, summary status and caller order."""
    if not rows:
        return [
            html.Div(
                [
                    html.H3("Choose a comparison"),
                    html.P(message or "Select one to six economies to begin."),
                ],
                className="m5-empty-card",
                role="status",
            )
        ] + ([_hidden_graph(c) for c in FOCUS_COUNTRIES] if show_graph else [])

    maxima = [r["index"] for r in rows if finite(r.get("index"))]
    ceiling = max(100, math.ceil(max(maxima, default=100) / 50) * 50)
    summary_map = {r["country"]: r for r in summaries}
    children = [
        html.P(
            f"Nominal exports · {baseline} = 100 · Inspect {selected}",
            className="m5-chart-caption",
        )
    ]
    for country in countries:
        series = [r for r in rows if r["country"] == country]
        current = next((r for r in series if r["year"] == selected), {})
        base = next((r for r in series if r["year"] == baseline), {})
        s = summary_map.get(country, {})
        minimum = s.get("minimum_index")
        loss = (
            "Insufficient data"
            if not finite(minimum)
            else "No observed loss"
            if minimum >= 100 - 1e-9
            else f"−{100 - minimum:.1f}%"
        )
        first = s.get("first_at_baseline")
        first_text = str(int(first)) if finite(first) else "No observed return"
        if metric == "product":
            value = current.get("product_share")
            label = "Product share"
            share = f"{100 * value:.2f}%" if finite(value) else "—"
            if finite(value) and finite(base.get("product_share")):
                delta = 100 * (value - base["product_share"])
                note = (
                    f"{'−' if delta < 0 else '+'}{abs(delta):.2f} pp versus {baseline}"
                )
            else:
                note = (
                    "Select an HS2 chapter."
                    if product == "TOTAL"
                    else "Comparable product share unavailable."
                )
        else:
            lo, hi = current.get("intra_share"), current.get("intra_upper")
            label = "Same-region share"
            share = (
                f"{100 * lo:.1f}–{100 * hi:.1f}%" if finite(lo) and finite(hi) else "—"
            )
            coverage = current.get("region_coverage")
            note = (
                f"Known-region coverage · {100 * coverage:.1f}%"
                if finite(coverage)
                else "Region or coverage unavailable."
            )
        state = (
            s.get("status_label")
            or str(s.get("status", "Unavailable")).replace("_", " ").capitalize()
        )
        if s.get("status") == "recovered":
            state = f"At/above baseline · {window[1]}"
        elif s.get("status") == "relapsed":
            state = f"Below baseline again · {window[1]}"
        current_index = current.get("index")
        is_bar = chart_type == "bar"
        headline = (
            (f"{current_index - 100:+.1f}%" if finite(current_index) else "—")
            if is_bar
            else number(current_index)
        )
        children.append(
            html.Article(
                [
                    html.Header(
                        [
                            html.H3(NAMES[country]),
                            html.Span(country, className="m5-country-code"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Strong(headline),
                            html.Span(
                                f"vs {baseline} · {selected}"
                                if is_bar
                                else f"index in {selected}"
                            ),
                        ],
                        className="m5-country-index",
                    ),
                    dcc.Graph(
                        id=cid("portrait-" + country),
                        figure=(_bar_figure if is_bar else _figure)(
                            series, country, window, baseline, event, selected, ceiling
                        ),
                        style={"height": "205px"},
                        config={"displayModeBar": False, "responsive": True},
                    ) if show_graph else None,
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("First observed return"),
                                    html.Strong(first_text),
                                ]
                            ),
                            html.Div([html.Span("Max. loss*"), html.Strong(loss)]),
                        ],
                        className="m5-country-facts",
                    ),
                    html.Div(
                        [html.Span(label), html.Strong(share)],
                        className="m5-country-share",
                    ),
                    html.P(note, className="m5-country-note"),
                    html.P(state, className="m5-country-status"),
                ],
                id=cid("card-" + country),
                className="m5-country-card",
                style={"--country-color": theme.country_color(country)},
            )
        )
    if show_graph:
        children += [_hidden_graph(c) for c in FOCUS_COUNTRIES if c not in countries]
    children.append(
        html.P(
            f"* Max. observed loss vs {baseline} · {event}–{window[1]}. "
            f"Recovery status uses {window[1]}; highlighted values use {selected}.",
            className="m5-country-footnote",
        )
    )
    return children
