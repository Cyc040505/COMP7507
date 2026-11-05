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
COLORS = ["#637f91", "#bb9360", "#4c7096", "#6f9389", "#a58d9d", "#c6ccd3"]


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
    meta = data_loader.load_country_meta().drop_duplicates("iso3").set_index("iso3")
    graph_config = {"displaylogo": False, "displayModeBar": False, "responsive": True}
    return html.Div(
        className="module-inner m3",
        children=[
            components.module_intro(
                "Trade partners & regional reach",
                "Follow the flows, compare partner shares, then test how destinations change across products.",
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
                            options=[
                                {"label": f"{meta.loc[c, 'name']} ({c})", "value": c}
                                for c in FOCUS
                            ],
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
            html.Div(
                [
                    html.Div(id=cid("kpis")),
                    html.Div(
                        [
                            html.Button("Reset case", id=cid("reset")),
                            html.Button("Export data ↓", id=cid("export")),
                        ],
                        className="m3-actions",
                    ),
                ],
                className="m3-summary",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H3(
                                        "01  Trade flows",
                                        id=cid("map-title"),
                                        className="card-title-text",
                                    ),
                                    dcc.RadioItems(
                                        id=cid("view"),
                                        options=[
                                            {"label": "Map", "value": "map"},
                                            {
                                                "label": "Partner matrix",
                                                "value": "matrix",
                                            },
                                        ],
                                        value="map",
                                        className="radio-row",
                                    ),
                                ],
                                className="m3-map-heading",
                            ),
                            dcc.Graph(
                                id=cid("graph"),
                                responsive=True,
                                style={"height": "435px"},
                                className="graph-interactive",
                                config={**graph_config, "topojsonURL": "/assets/"},
                            ),
                            html.Div(
                                id=cid("detail"),
                                className="m3-selection",
                                role="status",
                            ),
                            html.P(
                                "Arrows point to importers · Width encodes value. Capitals locate economies; curves are not transport routes.",
                                id=cid("map-caption"),
                                className="m3-map-caption",
                            ),
                        ],
                        id=cid("map-card"),
                        className="card m3-map-card",
                    ),
                    components.card(
                        "02  Partner shares",
                        [
                            html.P(
                                "Share of trade with all partners",
                                className="chart-subtitle",
                            ),
                            dcc.Graph(
                                id=cid("ranking"),
                                responsive=True,
                                style={"height": "435px"},
                                config=graph_config,
                            ),
                            html.Div(id=cid("remaining"), className="m3-remaining"),
                        ],
                        extra_class="m3-rank-card",
                    ),
                ],
                className="m3-primary",
            ),
            html.Div(
                [
                    components.card(
                        "03  How does the regional mix change?",
                        [
                            html.P(
                                "HS85 · Electrical equipment  /  HS87 · Vehicles & parts",
                                className="chart-subtitle",
                            ),
                            dcc.Graph(
                                id=cid("regions"),
                                responsive=True,
                                style={"height": "350px"},
                                config=graph_config,
                            ),
                        ],
                    ),
                    components.verification_panel(
                        "Does the regional concentration of trade differ between electronics and vehicles?",
                        "",
                        "Regional shares describe composition, not preference adjusted for region size. No causal inference.",
                        evidence_id=cid("finding"),
                        conclusion_id=cid("limits"),
                    ),
                ],
                className="m3-secondary",
            ),
            html.Div(id=cid("scope"), className="scope-note"),
            html.Details(
                [
                    html.Summary("Scope, methods & complete partner data"),
                    html.P(
                        "BACI HS92 V202601; nominal merchandise trade, thousand current USD. Shares use all partners before Top-N. Unknown regions remain in the denominator. Regions follow GeoDist: Russia is in Asia; the Americas are not split. The matrix uses the fixed union of six economies’ 2023 all-product Top5 partners; Other includes remaining partners and is not Unknown. Blank rows mean no observed total. Zero cells mean no recorded flow in the selected source, not proof of structural absence."
                    ),
                    html.P(
                        "Click a focal economy on the map to switch; other partners select a detail. Select a table cell for the same partner highlight."
                    ),
                    dash_table.DataTable(
                        id=cid("table"),
                        columns=[
                            {
                                "name": {
                                    "partner": "Partner",
                                    "name": "Economy",
                                    "value": "Trade (thousand USD)",
                                    "share": "All-partner share",
                                    "region": "Region",
                                }[c],
                                "id": c,
                                **(
                                    {
                                        "type": "numeric",
                                        "format": {
                                            "specifier": (
                                                ",.3f" if c == "value" else ".2%"
                                            )
                                        },
                                    }
                                    if c in {"value", "share"}
                                    else {}
                                ),
                            }
                            for c in ["partner", "name", "value", "share", "region"]
                        ],
                        page_size=10,
                        sort_action="native",
                        cell_selectable=True,
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "textAlign": "left",
                            "padding": "8px",
                            "fontSize": 12,
                        },
                    ),
                    html.P(
                        "Trade value is in thousand current USD; table shares are percentages. CSV retains fractional shares and the complete current partner scope."
                    ),
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
            colorscale=[[0, theme.MAP_LAND], [1, theme.MAP_LAND]],
            showscale=False,
            hovertemplate="%{location}<extra>Partner</extra>",
            marker_line_color=theme.MAP_BG,
        )
    )
    fig.add_trace(
        go.Choropleth(
            locations=FOCUS,
            z=[1] * 6,
            colorscale=[[0, "#3a5a6e"], [1, "#3a5a6e"]],
            showscale=False,
            customdata=FOCUS,
            hovertemplate="%{location}<extra>Focal economy</extra>",
            marker_line_color=theme.MAP_BG,
        )
    )
    fig.add_trace(
        go.Choropleth(
            locations=[country],
            z=[1],
            colorscale=[[0, "#bd955c"], [1, "#bd955c"]],
            showscale=False,
            marker_line_color=theme.MAP_BG,
            hovertemplate="%{location}<extra>Selected focal economy</extra>",
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

            # Schematic quadratic arcs keep links continuous across the world
            # view. Endpoints remain the true capitals; these are not routes.
            t = np.linspace(0, 1, 40)
            start_lon, end_lon = float(pos.loc[a, "lon"]), float(pos.loc[b, "lon"])
            start_lat, end_lat = float(pos.loc[a, "lat"]), float(pos.loc[b, "lat"])
            control_lon = (start_lon + end_lon) / 2 + abs(end_lat - start_lat) * 0.12
            control_lat = min(
                84, (start_lat + end_lat) / 2 + min(50, abs(end_lon - start_lon) * 0.45)
            )
            lon = (
                (1 - t) ** 2 * start_lon
                + 2 * (1 - t) * t * control_lon
                + t**2 * end_lon
            )
            lat = (
                (1 - t) ** 2 * start_lat
                + 2 * (1 - t) * t * control_lat
                + t**2 * end_lat
            )
            color = "#e5b878" if r.partner == selected else "#75b5c7"
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
                text=[
                    (
                        {
                            "CHN": "China",
                            "USA": "United States",
                            "MEX": "Mexico",
                            "RUS": "Russia",
                            "JPN": "Japan",
                            "AUS": "Australia",
                            "THA": "Thailand",
                            "SAU": "Saudi Arabia",
                        }.get(c, c)
                        if c not in {"GBR", "DEU", "FRA", "NLD", "BEL"}
                        else ""
                    )
                    for c in codes
                ],
                hovertext=codes,
                customdata=codes,
                mode="markers+text",
                textposition=[
                    (
                        "middle right"
                        if c == "JPN"
                        else "bottom left" if c == "THA" else "top center"
                    )
                    for c in codes
                ],
                textfont={"size": 13, "color": theme.MAP_TEXT},
                marker={
                    "size": [11] + [6] * (len(codes) - 1),
                    "line": {"width": 1.2, "color": theme.MAP_BG},
                    "color": ["#e5b878"]
                    + ["#e5b878" if p == selected else "#75b5c7" for p in codes[1:]],
                },
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            )
        )
    callouts = {
        "GBR": (-30, 65, "United Kingdom", "top left"),
        "DEU": (33, 69, "Germany", "top right"),
        "FRA": (-17, 31, "France", "bottom left"),
        "NLD": (-19, 56, "Netherlands", "middle left"),
        "BEL": (29, 34, "Belgium", "bottom right"),
    }
    for partner, (lon, lat, name, placement) in callouts.items():
        if partner not in codes or partner not in pos.index:
            continue
        fig.add_trace(
            go.Scattergeo(
                lon=[float(pos.loc[partner, "lon"]), lon],
                lat=[float(pos.loc[partner, "lat"]), lat],
                mode="lines+text",
                text=["", name],
                textposition=placement,
                textfont=dict(size=12, color=theme.MAP_TEXT),
                line=dict(width=1, color="#9cb0c0"),
                customdata=[partner, partner],
                hoverinfo="skip",
                showlegend=False,
            )
        )
    for fraction in [0.25, 1]:
        fig.add_trace(
            go.Scattergeo(
                lon=[None],
                lat=[None],
                mode="lines",
                line={"width": 1 + 5 * math.sqrt(fraction), "color": "#75b5c7"},
                name=f"${maxv*fraction/1e6:.1f}bn",
            )
        )
    fig.update_geos(
        projection_type="natural earth",
        projection_rotation=dict(lon=0, lat=0, roll=0),
        center=dict(lon=0, lat=10),
        fitbounds=False,
        lonaxis=dict(range=[-180, 180]),
        lataxis=dict(range=[-60, 85]),
        showland=True,
        landcolor=theme.MAP_LAND,
        showocean=True,
        oceancolor=theme.MAP_BG,
        showcountries=True,
        countrycolor=theme.MAP_BG,
        bgcolor=theme.MAP_BG,
        showcoastlines=False,
        showframe=False,
    )
    fig.update_layout(
        height=max(480, top * 26),
        paper_bgcolor=theme.MAP_BG,
        plot_bgcolor=theme.MAP_BG,
        font=dict(color=theme.MAP_TEXT),
        margin=dict(l=0, r=0, t=15, b=10),
        legend={
            "orientation": "h",
            "title": "Flow amount",
            "font": {"size": 11, "color": theme.MAP_TEXT},
            "x": 0.02,
            "y": 0,
        },
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
                colorscale=[
                    [0, "#f2f5f9"],
                    [0.2, "#b6c9dd"],
                    [0.5, "#6289b0"],
                    [1, "#254b73"],
                ],
                colorbar={"title": "Share %"},
                hovertemplate="%{y} / %{x}: %{z:.2f}%<extra></extra>",
            )
        )
        fig.update_layout(
            height=max(480, top * 26),
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
                "#d4a15b" if p == selected else theme.ACCENT for p in shown.partner
            ],
            text=[f"{v:.1%}" for v in shown.share],
            textposition="outside",
            cliponaxis=False,
            width=0.55,
            hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
        )
    )
    rank.update_layout(
        height=max(480, top * 26),
        margin=dict(l=75, r=37, t=30, b=35),
        xaxis=dict(
            side="top",
            ticksuffix="%",
            range=[0, max(float(shown.share.max() * 125) if len(shown) else 1, 1)],
            nticks=4,
            tickangle=0,
            tickfont=dict(size=12),
        ),
        yaxis=dict(
            tickvals=shown.partner.tolist(),
            ticktext=[
                {
                    "Russian Federation": "Russia",
                    "United States of America": "United States",
                    "United Kingdom": "UK",
                }.get(n, n)
                for n in shown.name
            ],
            tickfont=dict(size=12),
            showgrid=False,
        ),
        xaxis_title=None,
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
                text=[
                    f"{r[0][region]*100:.1f}%" if r[0][region] >= 0.055 else ""
                    for c, r in summaries
                ],
                textposition="inside",
                insidetextfont=dict(color="white", size=12),
                hovertemplate="%{x}: %{y:.2f}%<extra>" + region + "</extra>",
            )
        )
    reg.update_layout(
        barmode="stack",
        uniformtext=dict(minsize=12, mode="hide"),
        height=350,
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
    bounds = {c: r for c, r in summaries}
    if all(c in bounds and bounds[c][1] is not None for c in ["85", "87"]):
        a, b = bounds["85"], bounds["87"]
        if b[2] < a[1]:
            comparison = "HS87 has a lower same-region share than HS85, even when all unknown HS87 trade is assigned to the focal region. "
        elif a[2] < b[1]:
            comparison = "HS87 has a higher same-region share than HS85, even when all unknown HS85 trade is assigned to the focal region. "
        else:
            comparison = "The same-region bounds overlap; unknown-region trade prevents an unambiguous ordering. "
        finding = comparison + finding
    detail = html.Span("Select a partner on the map or ranking.")
    if selected:
        selected_rows = d[d.partner.eq(selected)]
        if len(selected_rows):
            row = selected_rows.iloc[0]
            route = (
                f"{country} → {selected}"
                if direction == "export"
                else f"{selected} → {country}"
            )
            detail = html.Div(
                [
                    html.Span(f"{route} / {row['name']}", className="m3-flow-name"),
                    html.Strong(f"${row.value/1e6:.3f}bn", className="m3-flow-value"),
                    html.Span(
                        f"{row.share:.2%} of all partners · {row.region}",
                        className="m3-flow-share",
                    ),
                ],
                className="m3-flow-detail",
            )
        else:
            detail = html.Span(f"{selected}: No recorded flow in the current scope.")
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
        Output(cid("kpis"), "children"),
        Output(cid("remaining"), "children"),
        Input(cid("records"), "data"),
        Input(cid("top"), "value"),
    )
    def summary(rows, top):
        d = pd.DataFrame(rows or [])
        total = float(d.value.sum()) if len(d) else 0
        coverage = float(d.head(top).value.sum() / total) if total > 0 else 0
        return components.kpi_row(
            [
                ("Selected trade value", theme.fmt_usd(total, 1)),
                (f"Top {top} coverage", f"{coverage:.1%}" if total > 0 else "—"),
                ("Complete scope", f"{len(d)} partners"),
            ]
        ), [
            html.Span("Remaining partners"),
            html.Strong(f"{1-coverage:.1%}" if total > 0 else "—"),
        ]

    @app.callback(
        Output(cid("map-card"), "className"),
        Output(cid("map-title"), "children"),
        Output(cid("map-caption"), "children"),
        Input(cid("view"), "value"),
    )
    def map_style(view):
        return (
            "card m3-map-card" + (" m3-matrix-card" if view == "matrix" else ""),
            "01  Six-economy partner matrix" if view == "matrix" else "01  Trade flows",
            (
                "Fixed partner columns · All-partner shares · Common 0–100% scale. Other includes partners outside the fixed columns."
                if view == "matrix"
                else "Arrows point to importers · Width encodes value. Capitals locate economies; curves are not transport routes."
            ),
        )

    @app.callback(
        Output(cid("country"), "value", allow_duplicate=True),
        Output(cid("selected"), "data", allow_duplicate=True),
        *[
            Output(cid(k), "value")
            for k in ["year", "product", "direction", "top", "view"]
        ],
        Input(cid("reset"), "n_clicks"),
        prevent_initial_call=True,
    )
    def reset(n):
        return "CHN", None, 2023, "87", "export", 10, "map"

    @app.callback(
        Output(cid("selected"), "data", allow_duplicate=True),
        Input(cid("table"), "active_cell"),
        State(cid("table"), "derived_viewport_data"),
        prevent_initial_call=True,
    )
    def select_table(cell, rows):
        if not cell or not rows or cell["row"] >= len(rows):
            return no_update
        return rows[cell["row"]]["partner"]

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
