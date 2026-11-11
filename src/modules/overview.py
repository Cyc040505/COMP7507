"""Global nominal exports and focal-economy world shares; local year control."""

import math

import pandas as pd
import plotly.graph_objects as go
from dash import (
    Input,
    Output,
    State,
    ClientsideFunction,
    ctx,
    dcc,
    html,
    dash_table,
    no_update,
)
from src import data_loader, components, theme, config
from src.analytics.partners import FOCUS
from src.analytics.economy import SPECIAL_CODES
from src.ids import ACTIVE_MODULE, mid
from src.module_base import guard_active

MODULE_ID = "M0"
NAV_LABEL = "0  Overview"
ORDER = 0

YEAR_MIN, YEAR_MAX = 1995, 2024
STEP_MS = 700
PLAY_LABEL = "▶ Play"
PAUSE_LABEL = "❚❚ Pause"

FOCUS_NAMES = {
    "USA": "United States",
    "DEU": "Germany",
    "CHN": "China",
    "MEX": "Mexico",
    "NLD": "Netherlands",
    "ITA": "Italy",
}


def cid(k):
    return mid(MODULE_ID, k)


def tint(hex_color, alpha):
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def country_tag(iso3):
    """A coloured chip carrying the country name and its ISO3 code."""
    color = theme.country_color(iso3)
    return html.Span(
        [
            html.Span(className="m0-tag-dot", style={"background": color}),
            html.Span(FOCUS_NAMES.get(iso3, iso3)),
            html.Span(f"({iso3})", className="m0-tag-code"),
        ],
        className="m0-tag",
        style={"background": tint(color, 0.1), "borderColor": tint(color, 0.38)},
    )


def pattern_row(label, codes, note):
    return html.Div(
        [
            html.Span(label, className="m0-pattern-label"),
            html.Span([country_tag(c) for c in codes], className="m0-tag-row"),
            html.Span(note, className="m0-pattern-note"),
        ],
        className="m0-pattern",
    )


def eligible():
    ref = pd.read_csv(config.DATA_DIR / "reference/m2_country_codes_V202601.csv")
    return set(ref.loc[~ref.country_code.isin(SPECIAL_CODES), "country_iso3"].dropna())


def layout():
    return html.Div(
        className="module-inner m0",
        children=[
            components.module_intro(
                "Global growth, changing export shares",
                "How has the scale of world trade changed—and which economies account for it?",
            ),
            dcc.Download(id=cid("download")),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Analysis year", htmlFor=cid("year")),
                            html.Div(
                                [
                                    html.Button(
                                        PLAY_LABEL,
                                        id=cid("play"),
                                        className="m0-play",
                                        title="Step through every year automatically",
                                        **{"aria-label": "Play years automatically"},
                                    ),
                                    html.Span(f"{YEAR_MIN}", className="m0-year-edge"),
                                    dcc.Slider(
                                        id=cid("year"),
                                        min=YEAR_MIN,
                                        max=YEAR_MAX,
                                        step=1,
                                        value=YEAR_MIN,
                                        marks=None,
                                        tooltip={"placement": "top"},
                                        allow_direct_input=False,
                                    ),
                                    html.Span(f"{YEAR_MAX}", className="m0-year-edge"),
                                    dcc.Interval(
                                        id=cid("step"),
                                        interval=STEP_MS,
                                        n_intervals=0,
                                        disabled=True,
                                    ),
                                    dcc.Store(id=cid("playing"), data=False),
                                    dcc.Store(id=cid("auto-year"), data=None),
                                ],
                                className="m0-year-row",
                            ),
                        ],
                        className="control-field m0-year",
                    ),
                    dcc.RadioItems(
                        id=cid("view"),
                        options=[
                            {"label": "Annual Top10", "value": "ranking"},
                            {"label": "Six-economy world shares", "value": "six"},
                        ],
                        value="ranking",
                        className="radio-row",
                    ),
                ],
                className="m0-controls",
            ),
            html.Div(
                [
                    components.card(
                        "Global export value",
                        dcc.Graph(
                            id=cid("total"), responsive=True, style={"height": "420px"}
                        ),
                    ),
                    components.card(
                        "Share of complete world exports",
                        [
                            dcc.Graph(
                                id=cid("share"),
                                responsive=True,
                                style={"height": "420px"},
                            ),
                            dcc.Store(id=cid("tween")),
                        ],
                    ),
                ],
                className="m0-charts",
            ),
            components.card(
                "What the evidence shows",
                [
                    html.Div(id=cid("finding"), className="m3-note"),
                    html.Div(
                        [
                            pattern_row(
                                "Consistently dominant",
                                ["USA", "DEU"],
                                "Top 3 in every year, 1995–2024.",
                            ),
                            pattern_row(
                                "Fastest riser",
                                ["CHN"],
                                "6th in 1995 → 1st since 2005; world share 4.5% → 15.7%.",
                            ),
                            pattern_row(
                                "Stable shares",
                                ["MEX", "NLD", "ITA"],
                                "Each stayed inside a 2 pp band across 1995–2024.",
                            ),
                        ],
                        className="m0-patterns",
                    ),
                ],
                extra_class="m0-finding",
            ),
            html.Details(
                [
                    html.Summary("Annual Top10 evidence & full data"),
                    dash_table.DataTable(
                        id=cid("table"),
                        columns=[
                            {"name": c, "id": c}
                            for c in [
                                "country",
                                "export_thousand_USD",
                                "world_share_pct",
                            ]
                        ],
                        page_size=10,
                        style_table={"overflowX": "auto"},
                    ),
                    html.Button(
                        "Download all years and country shares", id=cid("export")
                    ),
                ]
            ),
            html.P(
                "Current-dollar values include price and exchange-rate effects. Rising nominal exports need not mean a rising world share. The six focal economies are case studies, not a representative global sample."
            ),
        ],
    )


def figures(year, view):
    w = data_loader.load_flow_year().sort_values("year")
    c = data_loader.load_country_year().copy()
    c["share"] = c.export_value / c.year.map(w.set_index("year").export_value) * 100
    total = go.Figure(
        go.Scatter(
            x=w.year,
            y=w.export_value / 1e9,
            mode="lines",
            name="Global exports",
            line={"color": theme.ACCENT, "width": 2.7},
            hovertemplate="%{x}: $%{y:.2f}T<extra></extra>",
        )
    )
    total.add_vline(
        x=year,
        line_dash="dot",
        line_color="#9aabbc",
        line_width=1.5,
        annotation_text=str(year),
        annotation_position="top left",
    )
    total.update_layout(
        height=420,
        yaxis_title="Trillion current USD",
        xaxis_title="Year",
        margin=dict(t=20, b=90),
        xaxis=dict(tickmode="array", tickvals=[1995, 2000, 2010, 2020, 2024], range=[1995, 2024], fixedrange=True),
        yaxis=dict(
            range=[
                math.floor(float(w.export_value.min()) / 1e9) - 0.6,
                math.ceil(float(w.export_value.max()) / 1e9) + 0.6,
            ],
            fixedrange=True,
        ),
        dragmode=False,
    )
    valid = c[c.country.isin(eligible())]
    top = (
        valid[valid.year.eq(year)].sort_values("export_value", ascending=False).head(10)
    )
    # One fixed horizontal scale keeps bars comparable between years and lets
    # the ranking tween without the axis rescaling mid-animation.
    yearly_peak = valid.groupby("year").share.max()
    share_ceiling = float(yearly_peak.max()) if yearly_peak.notna().any() else 1.0
    if view == "ranking":
        fig = go.Figure(
            go.Bar(
                x=top.share,
                y=top.country,
                orientation="h",
                marker_color=[theme.country_color(k) for k in top.country],
                text=[f"{v:.2f}%" for v in top.share],
                textposition="outside",
                cliponaxis=False,
            )
        )
        fig.update_layout(
            yaxis_autorange="reversed",
            xaxis_title="World export share (%)",
            yaxis_showgrid=False,
            xaxis=dict(range=[0, share_ceiling * 1.2], fixedrange=True),
            yaxis=dict(fixedrange=True),
        )
    else:
        fig = go.Figure()
        for country in FOCUS:
            d = c[c.country.eq(country)].sort_values("year")
            fig.add_trace(
                go.Scatter(
                    x=d.year,
                    y=d.share,
                    name=country,
                    line={"color": theme.country_color(country)},
                    hovertemplate="%{x}: %{y:.2f}%<extra>" + country + "</extra>",
                )
            )
        fig.add_vline(
            x=year,
            line_dash="dot",
            line_color="#9aabbc",
            line_width=1.5,
            annotation_text=str(year),
            annotation_position="top left",
        )
        fig.update_layout(
            yaxis_title="World export share (%)",
            xaxis_title="Year",
            xaxis=dict(tickmode="array", tickvals=[1995, 2000, 2010, 2020, 2024], range=[1995, 2024], fixedrange=True),
            yaxis=dict(fixedrange=True),
            dragmode=False,
        )
    fig.update_layout(
        height=420,
        margin=dict(t=20, b=90),
        legend={"orientation": "h", "y": -0.22, "yanchor": "top", "x": 0},
    )
    ever = (
        valid.sort_values("export_value", ascending=False)
        .groupby("year")
        .head(10)
        .country.nunique()
    )
    six = c[c.country.isin(FOCUS) & c.year.eq(year)].share.sum()
    finding = f'{year}: global merchandise exports ${float(w.loc[w.year.eq(year),"export_value"].iloc[0])/1e9:.2f}T; six focal economies account for {six:.2f}%. {ever} distinct recorded economies entered the annual Top10 during 1995–2024.'
    return total, fig, finding


def evidence():
    w = data_loader.load_flow_year().set_index("year").export_value
    c = data_loader.load_country_year().copy()
    c["world_total_thousand_USD"] = c.year.map(w)
    c["world_share_pct"] = c.export_value / c.world_total_thousand_USD * 100
    c["ranking_eligible"] = c.country.isin(eligible())
    c["focal_economy"] = c.country.isin(FOCUS)
    return c.rename(columns={"export_value": "export_thousand_USD"})


def register_callbacks(app):
    @app.callback(
        Output(cid("table"), "data"),
        Input(cid("year"), "value"),
        Input(ACTIVE_MODULE, "data"),
    )
    def table(year, active):
        guard_active(MODULE_ID, active)
        c = evidence()
        c = (
            c[c.year.eq(year) & c.ranking_eligible]
            .sort_values("export_thousand_USD", ascending=False)
            .head(10)
        )
        return (
            c[["country", "export_thousand_USD", "world_share_pct"]]
            .round(4)
            .to_dict("records")
        )

    @app.callback(
        Output(cid("download"), "data"),
        Input(cid("export"), "n_clicks"),
        State(cid("year"), "value"),
        prevent_initial_call=True,
    )
    def export(n, year):
        return dcc.send_data_frame(
            evidence().assign(selected_year=year).to_csv,
            "M0_world_shares.csv",
            index=False,
        )

    @app.callback(
        Output(cid("total"), "figure"),
        Output(cid("share"), "figure"),
        Output(cid("finding"), "children"),
        Input(cid("year"), "value"),
        Input(cid("view"), "value"),
        Input(ACTIVE_MODULE, "data"),
    )
    def update(year, view, active):
        guard_active(MODULE_ID, active)
        total, fig, finding = figures(year, view)
        return total, fig, finding

    @app.callback(
        Output(cid("year"), "value"),
        Output(cid("playing"), "data"),
        Output(cid("auto-year"), "data"),
        Output(cid("play"), "children"),
        Output(cid("play"), "className"),
        Output(cid("step"), "disabled"),
        Input(cid("play"), "n_clicks"),
        Input(cid("step"), "n_intervals"),
        Input(cid("year"), "value"),
        State(cid("playing"), "data"),
        State(cid("auto-year"), "data"),
        prevent_initial_call=True,
    )
    def playback(n_clicks, ticks, year, playing, auto_year):
        trigger = ctx.triggered_id
        idle = (no_update, False, no_update, PLAY_LABEL, "m0-play", True)

        if trigger == cid("play"):
            if playing:
                return idle
            # Starting playback from the final year restarts the sequence.
            start = int(year) if year is not None and year < YEAR_MAX else YEAR_MIN
            return start, True, start, PAUSE_LABEL, "m0-play on", False

        if trigger == cid("step"):
            if not playing or year is None:
                return idle
            if auto_year is not None and year != auto_year:
                return idle
            nxt = int(year) + 1
            if nxt > YEAR_MAX:
                return idle
            return nxt, no_update, nxt, no_update, no_update, no_update

        if playing and auto_year is not None and year != auto_year:
            return idle
        return (no_update,) * 6

    app.clientside_callback(
        ClientsideFunction(namespace="m0", function_name="tween_ranking"),
        Output(cid("tween"), "data"),
        Input(cid("share"), "figure"),
        Input(cid("view"), "value"),
    )
