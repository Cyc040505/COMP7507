"""M3: six focal economies, worldwide partners and explicit flow direction."""

from functools import lru_cache
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dcc, html, no_update, dash_table
from src import config, theme, components, data_loader
from src.analytics.partners import FOCUS, REGIONS, partners, regional, matrix
from src.analytics.product import chapters, label
from src.ids import ACTIVE_MODULE, mid
from src.module_base import guard_active

MODULE_ID = "M3"
NAV_LABEL = "M3  Network & Partners"
ORDER = 3
COLORS = ["#95613e", "#d38b27", "#21799b", "#725ca1", "#48866d", "#9ca3af"]


def cid(k):
    return mid(MODULE_ID, k)


def field(title, widget):
    return html.Div(
        [html.Label(title, htmlFor=widget.id), widget], className="m3-field"
    )


@lru_cache(maxsize=1)
def positions():
    return pd.read_csv(config.DATA_DIR / "reference/capitals.csv").set_index("iso3")


def layout():
    return html.Div(
        className="module-inner m3",
        children=[
            html.P("PARTNERS / M3", className="m3-eyebrow"),
            html.H2("Regional ties or global reach?"),
            html.P(
                "Start with China’s vehicle exports in 2023. Compare destinations with electronics, then reverse the direction."
            ),
            dcc.Store(id=cid("selected")),
            dcc.Store(id=cid("records")),
            dcc.Download(id=cid("download")),
            html.Div(
                [
                    field(
                        "Focal economy",
                        dcc.Dropdown(
                            id=cid("country"),
                            options=FOCUS,
                            value="CHN",
                            clearable=False,
                        ),
                    ),
                    field(
                        "Year",
                        dcc.Dropdown(
                            id=cid("year"),
                            options=list(range(1995, 2025)),
                            value=2023,
                            clearable=False,
                        ),
                    ),
                    field(
                        "Product",
                        dcc.Dropdown(
                            id=cid("product"),
                            options=[{"label": "All products", "value": "TOTAL"}]
                            + [{"label": label(p), "value": p} for p in chapters()],
                            value="87",
                            clearable=False,
                        ),
                    ),
                    field(
                        "Direction",
                        dcc.Dropdown(
                            id=cid("direction"),
                            options=[
                                {"label": "Exports → partners", "value": "export"},
                                {"label": "Imports ← partners", "value": "import"},
                            ],
                            value="export",
                            clearable=False,
                        ),
                    ),
                    field(
                        "Displayed partners",
                        dcc.Dropdown(
                            id=cid("top"),
                            options=[5, 10, 20],
                            value=10,
                            clearable=False,
                        ),
                    ),
                ],
                className="m3-controls",
            ),
            html.Div(id=cid("scope"), className="m3-note"),
            dcc.RadioItems(
                id=cid("view"),
                options=[
                    {"label": "World map", "value": "map"},
                    {"label": "Six-economy partner matrix", "value": "matrix"},
                ],
                value="map",
                className="radio-row",
            ),
            components.card(
                "01 / Locate the trade links",
                dcc.Graph(
                    id=cid("graph"),
                    className="graph-interactive",
                    config={"displaylogo": False, "topojsonURL": "/assets/"},
                ),
            ),
            html.P(
                "Capital locations identify economies; curves are schematic connections, not transport routes. Arrowheads point toward the importer. Click a focal economy to switch; other partners only select a detail."
            ),
            html.Div(
                [
                    components.card(
                        "02 / Compare partner shares", dcc.Graph(id=cid("ranking"))
                    ),
                    components.card(
                        "03 / Compare product destinations",
                        dcc.Graph(id=cid("regions")),
                    ),
                ],
                className="m3-pair",
            ),
            html.Div(id=cid("detail"), className="m3-note"),
            components.verification_panel(
                "Partner concentration may differ across products.",
                "",
                "Regional shares describe destinations, not trade preferences adjusted for region size; no causal inference.",
                evidence_id=cid("finding"),
                conclusion_id=cid("limits"),
            ),
            html.Details(
                [
                    html.Summary("Scope, methods & data"),
                    html.P(
                        "BACI HS92 V202601; nominal merchandise trade, thousand current USD. Shares use all partners before Top-N. Unknown regions remain in the denominator. The matrix uses the fixed union of six economies’ 2023 all-product Top5 partners; Other includes remaining partners and is not Unknown. Blank rows mean no observed total. Zero cells mean no recorded flow in the complete selected source, not proof of structural absence."
                    ),
                    dash_table.DataTable(
                        id=cid("table"),
                        columns=[
                            {"name": c, "id": c}
                            for c in ["partner", "name", "value", "share", "region"]
                        ],
                        page_size=10,
                        sort_action="native",
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "textAlign": "left",
                            "padding": "8px",
                            "fontSize": 12,
                        },
                    ),
                    html.P(
                        "Value = thousand current USD; share = fraction of all partners."
                    ),
                    html.Button("Download current partner data", id=cid("export")),
                ]
            ),
        ],
    )


def map_figure(country, d, direction, top, selected):
    pos = positions()
    fig = go.Figure()
    codes = data_loader.load_country_meta().iso3.drop_duplicates().tolist()
    fig.add_trace(
        go.Choropleth(
            locations=codes,
            z=[0] * len(codes),
            colorscale=[[0, "#f0f2f4"], [1, "#f0f2f4"]],
            showscale=False,
            hovertemplate="%{location}<extra>Partner</extra>",
            marker_line_color="white",
        )
    )
    fig.add_trace(
        go.Choropleth(
            locations=FOCUS,
            z=[1] * 6,
            colorscale=[[0, "#d5e4f3"], [1, "#d5e4f3"]],
            showscale=False,
            customdata=FOCUS,
            hovertemplate="%{location}<extra>Focal economy</extra>",
            marker_line_color="white",
        )
    )
    shown = d.head(top)
    maxv = float(shown.value.max()) if len(shown) else 1
    if country in pos.index:
        for r in shown.itertuples():
            if r.partner not in pos.index:
                continue
            a, b = (
                (country, r.partner) if direction == "export" else (r.partner, country)
            )

            # Great-circle interpolation, with an explicit tangent arrowhead near destination.
            def xyz(code):
                la, lo = np.radians([pos.loc[code, "lat"], pos.loc[code, "lon"]])
                return np.array(
                    [np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]
                )

            u, v = xyz(a), xyz(b)
            omega = np.arccos(np.clip(np.dot(u, v), -1, 1))
            t = np.linspace(0, 1, 40)
            pts = (
                np.outer(1 - t, u) + np.outer(t, v)
                if abs(np.sin(omega)) < 1e-8
                else (
                    np.outer(np.sin((1 - t) * omega), u)
                    + np.outer(np.sin(t * omega), v)
                )
                / np.sin(omega)
            )
            lat = np.degrees(np.arctan2(pts[:, 2], np.hypot(pts[:, 0], pts[:, 1])))
            lon = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
            color = "#d56a24" if r.partner == selected else "#247c99"
            width = 1 + 5 * math.sqrt(r.value / maxv)
            text = f"{a} → {b}<br>{r.value:,.0f} thousand USD<br>{r.share:.2%} of all partners"
            fig.add_trace(
                go.Scattergeo(
                    lon=lon,
                    lat=lat,
                    mode="lines",
                    line={"width": width, "color": color},
                    customdata=[r.partner] * 40,
                    text=[text] * 40,
                    hovertemplate="%{text}<extra></extra>",
                    showlegend=False,
                )
            )
            k = 34
            dx = ((lon[k] - lon[k - 2] + 180) % 360) - 180
            dy = lat[k] - lat[k - 2]
            norm = max(np.hypot(dx, dy), 1e-6)
            dx /= norm
            dy /= norm
            fig.add_trace(
                go.Scattergeo(
                    lon=[
                        lon[k] - 4 * dx + 2 * dy,
                        lon[k],
                        lon[k] - 4 * dx - 2 * dy,
                    ],
                    lat=[
                        lat[k] - 4 * dy - 2 * dx,
                        lat[k],
                        lat[k] - 4 * dy + 2 * dx,
                    ],
                    mode="lines",
                    line={"width": 2.5, "color": color},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        codes = [country] + [p for p in shown.partner if p in pos.index]
        fig.add_trace(
            go.Scattergeo(
                lon=[pos.loc[p, "lon"] for p in codes],
                lat=[pos.loc[p, "lat"] for p in codes],
                text=[c if c in [country, selected] else "" for c in codes],
                hovertext=codes,
                customdata=codes,
                mode="markers+text",
                textposition="top center",
                marker={
                    "size": [11] + [6] * (len(codes) - 1),
                    "color": [theme.country_color(country)]
                    + ["#d56a24" if p == selected else "#247c99" for p in codes[1:]],
                },
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            )
        )
    for fraction in [0.25, 1]:
        fig.add_trace(
            go.Scattergeo(
                lon=[None],
                lat=[None],
                mode="lines",
                line={"width": 1 + 5 * math.sqrt(fraction), "color": "#247c99"},
                name=f"${maxv*fraction/1e6:.1f}bn",
            )
        )
    fig.update_geos(
        projection_type="natural earth",
        showland=True,
        landcolor="#f0f2f4",
        showocean=True,
        oceancolor="#f9fbfd",
        showcountries=True,
        countrycolor="white",
        showframe=False,
    )
    fig.update_layout(
        height=510,
        margin=dict(l=0, r=0, t=15, b=10),
        legend={"orientation": "h", "title": "Flow amount (line width)"},
        uirevision="world",
    )
    return fig


def figures(country, year, product, direction, top, view, selected):
    d = partners(country, year, product, direction)
    total = d.value.sum()
    shown = d.head(top)
    if view == "map":
        fig = map_figure(country, d, direction, top, selected)
    else:
        cols, rows = matrix(year, product, direction)
        fig = go.Figure(
            go.Heatmap(
                x=cols,
                y=FOCUS,
                z=rows,
                zmin=0,
                zmax=100,
                colorscale="Blues",
                colorbar={"title": "Share %"},
                hovertemplate="%{y} / %{x}: %{z:.2f}%<extra></extra>",
            )
        )
        fig.update_layout(
            height=460,
            margin=dict(t=20, b=90),
            xaxis_tickangle=-45,
            yaxis_autorange="reversed",
        )
    rank = go.Figure(
        go.Bar(
            x=(shown.share * 100).tolist(),
            y=shown.partner.tolist(),
            customdata=shown.partner.tolist(),
            orientation="h",
            marker_color=[
                "#d56a24" if p == selected else "#247c99" for p in shown.partner
            ],
            text=[f"{v:.1%}" for v in shown.share],
            textposition="auto",
            hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
        )
    )
    rank.update_layout(
        height=400,
        margin=dict(l=45, r=20, t=15, b=40),
        xaxis_title="Share of all partners (%)",
        yaxis_autorange="reversed",
    )
    reg = go.Figure()
    summaries = []
    for code in ["85", "87"]:
        r = regional(country, year, code, direction)
        if r is not None:
            summaries.append((code, r))
    for i, region in enumerate(REGIONS):
        reg.add_trace(
            go.Bar(
                name=region,
                x=["HS" + c for c, r in summaries],
                y=[r[0][region] * 100 for c, r in summaries],
                marker_color=COLORS[i],
                hovertemplate="%{x}: %{y:.2f}%<extra>" + region + "</extra>",
            )
        )
    reg.update_layout(
        barmode="stack",
        height=400,
        yaxis={"range": [0, 100], "title": "All-partner share (%)"},
        legend={"orientation": "h", "y": -0.2},
        margin=dict(l=45, r=10, t=15, b=100),
    )
    cov = shown.value.sum() / total if total > 0 else 0
    missing = d.loc[~d.partner.isin(positions().index), "value"].sum()
    scope = f"{country} · {year} · {product} · {direction} · Top {top} covers {cov:.1%}; all-partner total ${total/1e6:,.2f}bn. Partners lacking coordinates: ${missing/1e6:,.3f}bn, retained in denominators."
    finding = (
        "; ".join(
            (
                f"HS{c}: same-region share {r[1]:.1%}–{r[2]:.1%}"
                if r[1] is not None
                else f"HS{c}: unknown focal region"
            )
            for c, r in summaries
        )
        or "No data to compare product regions."
    )
    finding += (
        ". Imports describe suppliers and do not test export destination concentration."
        if direction == "import"
        else ". Compare these shares to locate differences; they do not establish a preference after controlling for region size."
    )
    detail = "Select a partner on the map or ranking."
    if selected:
        r = d[d.partner.eq(selected)]
        detail = f"{selected}: " + (
            f"{r.iloc[0].share:.2%}; ${r.iloc[0].value/1e6:.3f}bn; {r.iloc[0].region}."
            if len(r)
            else "No recorded flow in the current scope."
        )
    records = d.assign(
        year=year,
        focal_country=country,
        product=product,
        direction=direction,
        unit="thousand current USD",
    ).to_dict("records")
    if total <= 0:
        scope += " No observed positive total; no share conclusion."
    return fig, rank, reg, scope, finding, detail, records


def register_callbacks(app):
    @app.callback(Output(cid("table"), "data"), Input(cid("records"), "data"))
    def table(rows):
        return rows or []

    @app.callback(
        Output(cid("country"), "value"),
        Output(cid("selected"), "data"),
        Input(cid("graph"), "clickData"),
        Input(cid("ranking"), "clickData"),
        State(cid("view"), "value"),
        State(ACTIVE_MODULE, "data"),
        prevent_initial_call=True,
    )
    def select(a, b, view, active):
        guard_active(MODULE_ID, active)
        click = a if ctx.triggered_id == cid("graph") else b
        if not click:
            return no_update, no_update
        p = click["points"][0]
        code = p.get("location") or p.get("customdata")
        if (
            ctx.triggered_id == cid("graph")
            and view == "map"
            and p.get("location") in FOCUS
        ):
            return code, None
        return no_update, code if isinstance(code, str) else None

    @app.callback(
        *[
            Output(cid(k), p)
            for k, p in [
                ("graph", "figure"),
                ("ranking", "figure"),
                ("regions", "figure"),
                ("scope", "children"),
                ("finding", "children"),
                ("detail", "children"),
                ("records", "data"),
            ]
        ],
        *[
            Input(cid(k), "value")
            for k in ["country", "year", "product", "direction", "top", "view"]
        ],
        Input(cid("selected"), "data"),
        Input(ACTIVE_MODULE, "data"),
    )
    def update(country, year, product, direction, top, view, selected, active):
        guard_active(MODULE_ID, active)
        try:
            if (
                country not in FOCUS
                or direction not in {"export", "import"}
                or top not in {5, 10, 20}
            ):
                raise ValueError(
                    "Select a valid focal economy, direction and display range."
                )
            return figures(country, year, product, direction, top, view, selected)
        except (FileNotFoundError, ValueError) as error:
            message = str(error)
            empty = theme.empty_figure(message)
            return empty, empty, empty, message, "No result calculated.", "", []

    @app.callback(
        Output(cid("download"), "data"),
        Input(cid("export"), "n_clicks"),
        State(cid("records"), "data"),
        prevent_initial_call=True,
    )
    def export(n, rows):
        return dcc.send_data_frame(
            pd.DataFrame(rows).to_csv, "M3_partners.csv", index=False
        )
