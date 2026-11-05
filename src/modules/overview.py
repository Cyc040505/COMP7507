"""Global nominal exports and focal-economy world shares; local year control."""

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, dash_table
from src import data_loader, components, theme, config
from src.analytics.partners import FOCUS
from src.analytics.economy import SPECIAL_CODES
from src.ids import ACTIVE_MODULE, mid
from src.module_base import guard_active

MODULE_ID = "M0"
NAV_LABEL = "0  Overview"
ORDER = 0


def cid(k):
    return mid(MODULE_ID, k)


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
                    components.field(
                        "Analysis year",
                        dcc.Dropdown(
                            id=cid("year"),
                            options=list(range(1995, 2025)),
                            value=2023,
                            clearable=False,
                        ),
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
                    components.card("Global export value", dcc.Graph(id=cid("total"))),
                    components.card(
                        "Share of complete world exports", dcc.Graph(id=cid("share"))
                    ),
                ],
                className="m0-charts",
            ),
            components.card(
                "What the evidence shows",
                html.Div(id=cid("finding"), className="m3-note"),
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
    total.add_vline(x=year, line_dash="dot")
    total.update_layout(
        height=420,
        yaxis_title="Trillion current USD",
        xaxis_title="Year",
        margin=dict(t=20, b=90),
        xaxis=dict(tickmode="array", tickvals=[1995, 2000, 2010, 2020, 2024]),
    )
    valid = c[c.country.isin(eligible())]
    top = (
        valid[valid.year.eq(year)].sort_values("export_value", ascending=False).head(10)
    )
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
            xaxis_range=[0, float(top.share.max()) * 1.2],
            yaxis_showgrid=False,
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
        fig.add_vline(x=year, line_dash="dot")
        fig.update_layout(
            yaxis_title="World export share (%)",
            xaxis_title="Year",
            xaxis=dict(tickmode="array", tickvals=[1995, 2000, 2010, 2020, 2024]),
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
    finding = f'{year}: global merchandise exports ${float(w.loc[w.year.eq(year),"export_value"].iloc[0])/1e9:.2f}T; six focal economies account for {six:.2f}%. {ever} distinct recorded economies entered the annual Top10 during 1995–2024. Historical entities follow BACI codes and are not silently reassigned.'
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
        return figures(year, view)
