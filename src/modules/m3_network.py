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
# Unselected flows recede once a partner is chosen, so the amber path stays readable.
DIM_ARC = "rgba(117,181,199,0.22)"
DIM_ARC_LIGHT = "rgba(39,140,150,0.22)"
# Amber marks everything that belongs to the selected partner: arc, moving
# arrowhead, capital dot and country fill. light_map() restyles it in light mode.
HIGHLIGHT = "#e5b878"
HIGHLIGHT_LIGHT = "#b27a2a"


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
                                "Arrows point to importers · Width encodes value · Moving arrowheads trace each flow from exporter to importer · The selected partner's country is filled in the same amber as its arc. Capitals locate economies; curves are not transport routes.",
                                id=cid("map-caption"),
                                className="m3-map-caption",
                            ),
                        ],
                        id=cid("map-card"),
                        className="card m3-map-card m3-light-card",
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
                        "03  Does trade follow regional gravity?",
                        [
                            html.P(
                                "Same product pair for every case · HS85 electrical equipment vs HS87 vehicles & parts",
                                className="chart-subtitle",
                            ),
                            html.H4(id=cid("regional-takeaway"), className="m3-takeaway"),
                            dcc.Graph(
                                id=cid("gravity"),
                                responsive=True,
                                style={"height": "190px"},
                                config=graph_config,
                            ),
                            html.P(
                                "Each bar is the home region's share minus the share of the largest other region, in percentage points; both shares are printed in the row label. Left of zero means the home region is out-traded — an exception to the gravity pattern. Grey means unknown-region trade is large enough to reverse the verdict.",
                                className="m3-map-caption",
                            ),
                            html.H5(
                                "Regional mix by product",
                                className="m3-subhead",
                            ),
                            dcc.Graph(
                                id=cid("regions"),
                                responsive=True,
                                style={"height": "380px"},
                                config=graph_config,
                            ),
                            html.P("All partners, including unknown regions, remain in the denominator. Differences use unrounded shares; pp = percentage points.", className="m3-map-caption m3-region-caption"),
                        ],
                    ),
                    components.verification_panel(
                        "When does regional trade concentration break down?",
                        "",
                        "A gap compares the home-region share with the single largest other region; it is not a test against every region at once. Regional shares describe composition, not preference adjusted for region size. No causal inference.",
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
                        "BACI HS92 V202601; nominal merchandise trade, thousand current USD. Shares use all partners before Top-N. Unknown regions remain in the denominator. Regions follow GeoDist: Russia is in Asia; the Americas are not split. The matrix shows the 12 partners with the highest share in any one of the six economies for the selected year, product and direction, ordered by that peak share; Other includes remaining partners and is not Unknown. Blank rows mean no observed total. Zero cells mean no recorded flow in the selected source, not proof of structural absence."
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
    territories = set(codes)
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
    # The chosen partner gets its own country fill in the same amber as its arc,
    # so country and path highlight agree. This applies even when the partner is
    # one of the six focal economies: the selection, not the panel, decides.
    if selected and selected in territories:
        fig.add_trace(
            go.Choropleth(
                locations=[selected],
                z=[1],
                colorscale=[[0, HIGHLIGHT], [1, HIGHLIGHT]],
                showscale=False,
                marker_line_color=theme.MAP_BG,
                hovertemplate="%{location}<extra>Selected partner</extra>",
            )
        )
    shown = d.head(top)
    maxv = float(shown.value.max()) if len(shown) else 1
    # A selection isolates one partner: fade the other arcs and draw the chosen
    # one last, so no wider or later link can cover the highlighted path.
    focus = selected if selected in set(shown.partner) else None
    if country in pos.index:
        for r in sorted(shown.itertuples(), key=lambda row: row.partner == focus):
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
            if r.partner == focus:
                color = HIGHLIGHT
            elif focus is not None:
                color = DIM_ARC
            else:
                color = "#75b5c7"
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
                    # Same highlight as the arcs: the chosen partner and the focal
                    # economy stay amber, every other partner recedes with its flow.
                    "color": [HIGHLIGHT]
                    + [
                        HIGHLIGHT if p == selected else (DIM_ARC if focus else "#75b5c7")
                        for p in codes[1:]
                    ],
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
        dragmode=False,
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
            dragmode=False,
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
        dragmode=False,
    )
    summaries = []
    for code in ["85", "87"]:
        r = regional(country, year, code, direction)
        if r is not None:
            summaries.append((code, r))
    reg = regional_comparison(country, year, direction)
    cov = shown.value.sum() / total if total > 0 else 0
    missing = d.loc[~d.partner.isin(positions().index), "value"].sum()
    scope = f"{country} · {year} · {product} · {direction} · Top {top} covers {cov:.1%}; all-partner total ${total/1e6:,.2f}bn. Partners lacking coordinates: ${missing/1e6:,.3f}bn, retained in denominators."
    finding = gravity_takeaway(country, year, direction)
    finding += " Bounds are the identified home-region share and the same share if all unknown-region trade were home-region trade: " + (
        "; ".join(
            (
                f"HS{c} {r[1]:.1%}–{r[2]:.1%}"
                if r[1] is not None
                else f"HS{c} unknown focal region"
            )
            for c, r in summaries
        )
        or "no data to compare product regions."
    )
    finding += (
        ". Imports describe suppliers and do not test export destinations."
        if direction == "import"
        else ". Shares describe composition, not preference after controlling for region size."
    )
    bounds = {c: r for c, r in summaries}
    if all(c in bounds and bounds[c][1] is not None for c in ["85", "87"]):
        a, b = bounds["85"], bounds["87"]
        if b[2] < a[1]:
            finding += " HS87 has a lower same-region share than HS85, even when all unknown HS87 trade is assigned to the focal region."
        elif a[2] < b[1]:
            finding += " HS87 has a higher same-region share than HS85, even when all unknown HS85 trade is assigned to the focal region."
        else:
            finding += " The same-region bounds overlap; unknown-region trade prevents an unambiguous ordering."
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


def light_map(fig):
    """Restyle an existing geographic figure without changing its data or geometry."""
    fig = go.Figure(fig)
    palette = {theme.MAP_LAND: "#e0e9ed", theme.MAP_BG: "#f2f7f9",
               theme.MAP_TEXT: theme.INK, "#3a5a6e": "#c1d8dc",
               "#bd955c": "#147d87", HIGHLIGHT: HIGHLIGHT_LIGHT, "#75b5c7": "#278c96",
               DIM_ARC: DIM_ARC_LIGHT}
    for trace in fig.data:
        if trace.type == "choropleth":
            trace.colorscale = [(v, palette.get(c, c)) for v, c in trace.colorscale]
            trace.marker.line.color = "#ffffff"
        else:
            if trace.line.color:
                trace.line.color = palette.get(trace.line.color, trace.line.color)
            if trace.textfont.color:
                trace.textfont.color = theme.INK
            if trace.marker.color:
                colors = trace.marker.color
                trace.marker.color = ([palette.get(c, c) for c in colors]
                                      if not isinstance(colors, str) else palette.get(colors, colors))
                trace.marker.line.color = "#ffffff"
    fig.update_geos(landcolor="#e0e9ed", oceancolor="#f2f7f9", bgcolor="#f2f7f9", countrycolor="#ffffff")
    fig.update_layout(paper_bgcolor="#ffffff", plot_bgcolor="#f2f7f9", font_color=theme.INK,
                      legend_font_color=theme.INK)
    return fig


def regional_comparison(country, year, direction):
    """A second encoding of the same full-partner regional shares and unknowns."""
    order = ["Asia", "Europe", "America", "Africa", "Oceania", "Unknown"]
    summaries = {code: regional(country, year, code, direction) for code in ["85", "87"]}
    if all(r is None for r in summaries.values()):
        return theme.empty_figure("No data to compare product regions.", height=430)
    fig = go.Figure()
    values = {}
    for code, name, color in [("85", "Electrical equipment", "#7892ac"),
                               ("87", "Vehicles & parts", "#147d87")]:
        r = summaries[code]
        vals = [float(r[0][region]) * 100 if r is not None else float("nan") for region in order]
        values[code] = vals
        fig.add_trace(go.Bar(
            x=vals, y=order, name=name, orientation="h", marker_color=color,
            text=["—" if pd.isna(v) else "<0.1%" if 0 < v < .1 else f"{v:.1f}%" for v in vals],
            textposition="outside", cliponaxis=False,
            hovertemplate=name + "<br>%{y}: %{x:.3f}% of all partners<extra></extra>",
        ))
    for i, region in enumerate(order):
        a, b = values["85"][i], values["87"][i]
        delta = "—" if pd.isna(a) or pd.isna(b) else f"{b-a:+.1f} pp" if abs(b-a) >= .05 else "0.0 pp"
        fig.add_annotation(x=1, y=region, xref="paper", yref="y", text=delta,
                           showarrow=False, xanchor="right", font=dict(size=12, color=theme.INK))
    fig.add_annotation(x=1, y=1.09, xref="paper", yref="paper", text="<b>HS87 − HS85</b>",
                       showarrow=False, xanchor="right", font=dict(size=12))
    valid = [v for vals in values.values() for v in vals if pd.notna(v)]
    fig.update_layout(
        template=theme.PLOT_TEMPLATE, height=430, barmode="group", bargap=.3, bargroupgap=.15,
        margin=dict(l=85, r=12, t=65, b=50), font=dict(color=theme.INK),
        legend=dict(orientation="h", x=0, y=1.24, font=dict(size=12)),
        xaxis=dict(domain=[0,.78], range=[0, max(5, max(valid, default=0)*1.16)],
                   title="All-partner share (%)", ticksuffix="%", nticks=5, fixedrange=True),
        yaxis=dict(categoryorder="array", categoryarray=order, autorange="reversed", fixedrange=True,
                   showgrid=False, tickmode="array", tickvals=order,
                   ticktext=["Americas" if r == "America" else r for r in order]),
        dragmode=False,
    )
    meta = data_loader.load_country_meta().drop_duplicates("iso3").set_index("iso3")
    home = meta.loc[country,"region"]
    home = "Oceania" if home == "Pacific" else home
    if home in order and home != "Unknown":
        i = order.index(home)
        fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=i-.46, y1=i+.46,
                      fillcolor="rgba(212,161,91,.12)", line_width=0, layer="below")
    if any(r is None for r in summaries.values()):
        missing = ", ".join("HS" + c for c, r in summaries.items() if r is None)
        fig.add_annotation(x=0, y=-.2, xref="paper", yref="paper", xanchor="left",
                           text=missing + ": no positive total; shares and differences unavailable.", showarrow=False)
    return fig


REGION_LABEL = {"America": "Americas"}


def gravity_rows(country, year, direction):
    """Home-region share against the largest other region, one row per product.

    Returns ``(home, rows, notes)``. ``rows`` holds the numbers the figure and
    the sentence both read, so the two can never disagree.
    """
    meta = data_loader.load_country_meta().drop_duplicates("iso3").set_index("iso3")
    home = meta.loc[country, "region"]
    home = "Oceania" if home == "Pacific" else home
    if home not in REGIONS or home == "Unknown":
        return home, [], ["unknown focal region"]
    rows, notes = [], []
    for code, name in [
        ("85", "Electrical equipment"),
        ("87", "Vehicles & parts"),
    ]:
        r = regional(country, year, code, direction)
        if r is None:
            rows.append(None)
            notes.append("no positive total")
            continue
        shares, _, _ = r
        own = float(shares[home])
        unknown = float(shares["Unknown"])
        others = {
            k: float(v) for k, v in shares.items() if k not in (home, "Unknown")
        }
        if not others:
            rows.append(None)
            notes.append("no other region")
            continue
        rival = max(others, key=others.get)
        rival_share = others[rival]
        # Assigning every unknown flow to the home region is the most favourable
        # case; if that still loses, the break is unambiguous.
        if own > rival_share:
            verdict, tone = "holds", "#147d87"
        elif own + unknown < rival_share:
            verdict, tone = "breaks", "#b4552d"
        else:
            verdict, tone = "unclear", theme.MUTED
        rows.append(
            {
                "code": code, "name": name, "own": own,
                "short": "electronics" if code == "85" else "vehicles",
                "rival": rival, "rival_share": rival_share,
                "gap": (own - rival_share) * 100, "verdict": verdict, "tone": tone,
                "unknown": unknown,
            }
        )
        notes.append("")
    return home, rows, notes


def gravity_test(country, year, direction):
    """Does trade stay with the focal economy's own region, or break that rule?

    Compares the home-region share with the largest other region for each
    product. Negative gaps are the interesting exceptions: trade that ignores
    distance. Unknown-region trade bounds the verdict instead of being dropped.
    """
    home, rows, notes = gravity_rows(country, year, direction)
    if home not in REGIONS or home == "Unknown":
        return theme.empty_figure(
            "The focal economy’s region is unknown; no gravity test.", height=200
        )
    if all(r is None for r in rows):
        return theme.empty_figure("No regional data to test.", height=200)
    fig = go.Figure()
    gaps = [abs(r["gap"]) for r in rows if r]
    span = max(6.0, max(gaps, default=0) * 1.55)
    for row in rows:
        if row is None:
            continue
        # Bars long enough to hold the numbers print them inside; a bar too short
        # to hold them (an almost-empty gap) prints them just past its tip.
        inside = abs(row["gap"]) / (2 * span) >= 0.16
        fig.add_trace(
            go.Bar(
                x=[row["gap"]],
                y=[f"HS{row['code']}  {row['name']}"],
                orientation="h",
                marker_color=row["tone"],
                width=0.58,
                text=[f"<b>{row['gap']:+.1f} pp</b><br>{row['verdict']}"],
                textposition="inside" if inside else "outside",
                insidetextanchor="middle",
                cliponaxis=False,
                textfont=dict(size=11, color="#ffffff" if inside else theme.INK),
                hovertemplate=(
                    f"{REGION_LABEL.get(home, home)}: {row['own']:.1%}<br>"
                    f"Largest other, {REGION_LABEL.get(row['rival'], row['rival'])}: "
                    f"{row['rival_share']:.1%}<br>"
                    f"Unknown: {row['unknown']:.1%}<extra></extra>"
                ),
            )
        )
    fig.add_vline(x=0, line_width=1, line_color=theme.MUTED)
    fig.update_layout(
        template=theme.PLOT_TEMPLATE, height=178, bargap=0.42,
        margin=dict(l=176, r=26, t=8, b=30), font=dict(color=theme.INK),
        showlegend=False, dragmode=False,
        xaxis=dict(
            range=[-span, span],
            title="Home region share − largest other region (pp)",
            ticksuffix=" pp", nticks=5, fixedrange=True, zeroline=False,
        ),
        yaxis=dict(
            categoryorder="array",
            categoryarray=[f"HS{r['code']}  {r['name']}" for r in rows if r],
            autorange="reversed", showgrid=False, fixedrange=True,
            ticks="",
            tickmode="array",
            tickvals=[f"HS{r['code']}  {r['name']}" for r in rows if r],
            # Each row names the two regions being compared, so the bar never
            # carries an anonymous difference.
            ticktext=[
                f"HS{r['code']}  {r['name']}"
                f"<br><span style='font-size:10px;color:{theme.MUTED}'>"
                f"{REGION_LABEL.get(home, home)} {r['own']:.1%} vs "
                f"{REGION_LABEL.get(r['rival'], r['rival'])} {r['rival_share']:.1%}"
                "</span>"
                for r in rows if r
            ],
            tickfont=dict(size=12),
        ),
    )
    if any(notes):
        fig.add_annotation(
            x=0, y=-0.16, xref="paper", yref="paper", xanchor="left", yanchor="top",
            showarrow=False, font=dict(size=11, color=theme.MUTED),
            text="; ".join(
                f"{r['code'] if r else c}: {n}" for r, c, n in zip(rows, ["HS85", "HS87"], notes) if n
            ),
        )
    return fig


def gravity_takeaway(country, year, direction):
    """One sentence naming the exception instead of restating the chart."""
    home, all_rows, _ = gravity_rows(country, year, direction)
    rows = [r for r in all_rows if r]
    if not rows:
        return "Regional comparison unavailable for this selection."
    meta = data_loader.load_country_meta().drop_duplicates("iso3").set_index("iso3")
    name = meta.loc[country, "name"]
    noun = "exports" if direction == "export" else "imports"
    lead = f"{name}, {year} {noun} · home region {home}: "
    holds = [r for r in rows if r["verdict"] == "holds"]
    breaks = [r for r in rows if r["verdict"] == "breaks"]
    unclear = [r for r in rows if r["verdict"] == "unclear"]

    def fmt(rows):
        return ", ".join(f"{r['short']} ({r['gap']:+.0f} pp)" for r in rows)

    if breaks and holds:
        lead += (
            f"gravity holds for {fmt(holds)} but breaks for {fmt(breaks)}."
        )
    elif breaks:
        lead += f"gravity breaks for {fmt(breaks)}."
    elif holds:
        lead += (
            f"gravity holds for {fmt(holds)}; no exception to the pattern."
        )
    else:
        return (
            lead + "unknown-region trade is too large to decide whether the "
            "gravity pattern holds."
        )
    if unclear:
        lead += (
            f" Inconclusive for {fmt(unclear)}: unknown-region trade could "
            "reverse the gap."
        )
    return lead


def register_callbacks(app):
    @app.callback(Output(cid("regional-takeaway"), "children"),
                  Input(cid("country"), "value"), Input(cid("year"), "value"),
                  Input(cid("direction"), "value"), Input(ACTIVE_MODULE, "data"))
    def takeaway(country, year, direction, active):
        guard_active(MODULE_ID, active)
        try:
            return gravity_takeaway(country, year, direction)
        except (KeyError, ValueError, FileNotFoundError):
            return "No regional comparison available for this selection."


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
                ("gravity", "figure"),
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
            result = list(figures(country, year, product, direction, top, view, selected))
            if view == "map":
                result[0] = light_map(result[0])
            result.insert(2, gravity_test(country, year, direction))
            return result
        except (FileNotFoundError, ValueError) as error:
            message = str(error)
            empty = theme.empty_figure(message)
            return empty, empty, empty, empty, message, "No result calculated.", "", []

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
            "card m3-map-card" + (" m3-matrix-card" if view == "matrix" else " m3-light-card"),
            "01  Six-economy partner matrix" if view == "matrix" else "01  Trade flows",
            (
                "Rows = six focal economies; columns = the 12 partners with the highest share in any one row, ordered left to right by that peak share for the current year, product and direction. Each cell is the partner’s share of that row’s trade, not a flow between continents. Common 0–100% scale; Other retains partners outside these columns."
                if view == "matrix"
                else "Arrows point to importers · Width encodes value · Moving arrowheads trace each flow from exporter to importer · The selected partner's country is filled in the same amber as its arc. Capitals locate economies; curves are not transport routes."
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
