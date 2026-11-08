"""Presentation of M5's existing annual evidence as comparable country cards."""

import math

import plotly.graph_objects as go
from dash import dcc, html

from src import theme
from src.ids import mid

FOCUS_COUNTRIES = ("USA", "DEU", "CHN", "MEX", "NLD", "ITA")
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
        font={"family": theme.FONT},
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
        tickfont={"size": 10},
        fixedrange=True,
    )
    fig.update_yaxes(
        title=None, range=[0, ceiling], nticks=4, tickfont={"size": 10}, fixedrange=True
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
        font={"size": 10, "color": theme.MUTED},
        yanchor="bottom",
    )
    fig.add_vline(x=selected, line_color=theme.ACCENT_LINE, line_width=1, layer="below")
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
):
    """Use computed rows only; retain nulls, summary status and caller order."""
    if not rows:
        return [
            html.Div(
                [
                    html.H3("Choose a comparison"),
                    html.P(message or "Select one to four economies to begin."),
                ],
                className="m5-empty-card",
                role="status",
            )
        ] + [_hidden_graph(c) for c in FOCUS_COUNTRIES]

    maxima = [r["index"] for r in rows if finite(r.get("index"))]
    ceiling = max(100, math.ceil(max(maxima, default=100) / 50) * 50)
    summary_map = {r["country"]: r for r in summaries}
    children = []
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
            state = f"At/above baseline at window end · {window[1]}"
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
                            html.Strong(number(current.get("index"))),
                            html.Span(f"index in {selected}"),
                        ],
                        className="m5-country-index",
                    ),
                    html.P(
                        f"Nominal exports · {baseline} = 100",
                        className="m5-country-baseline",
                    ),
                    dcc.Graph(
                        id=cid("portrait-" + country),
                        figure=_figure(
                            series, country, window, baseline, event, selected, ceiling
                        ),
                        style={"height": "205px"},
                        config={"displayModeBar": False, "responsive": True},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("First observed return"),
                                    html.Strong(first_text),
                                ]
                            ),
                            html.Div(
                                [html.Span("Largest observed loss*"), html.Strong(loss)]
                            ),
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
    children += [_hidden_graph(c) for c in FOCUS_COUNTRIES if c not in countries]
    children.append(
        html.P(
            f"* Largest observed loss relative to {baseline} during {event}–{window[1]}. "
            "Recovery summaries use the full displayed window; large values and highlighted points use the inspected year.",
            className="m5-country-footnote",
        )
    )
    return children
