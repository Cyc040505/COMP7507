"""Module 1 — Geography.

Map-first view of an exporter's partners. Country fills encode export share
or proximity, with a matching partner ranking beside the atlas.
The comparison table lists top-share and nearest partners and marks the overlap.

The module owns its local controls and never writes the global filter store.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib

import pandas as pd
import plotly.graph_objects as go
from dash import ALL, ClientsideFunction, Input, Output, State, dcc, html, dash_table
from flask import Response, request
import plotly.colors as pc

from src import components, config, data_loader, theme
from src.analytics.partners import FOCUS, flows
from src.analytics.geography import METRIC_LABELS, analyze, distance_profile
from src.analytics.product import chapters, label
from src.ids import ACTIVE_MODULE, mid
from src.module_base import guard_active
from src.geo_topology import optimized_world

MODULE_ID = "M1"
NAV_LABEL = "M1  Geography"
ORDER = 1

_HYPOTHESIS = (
    "Bilateral trade intensity is associated with geographic proximity "
    "(a description of association, not an estimate of a causal effect)."
)


def cid(name: str) -> str:
    return mid(MODULE_ID, name)


def _product_options() -> list[dict]:
    options = [{"label": "All products", "value": "TOTAL"}]
    options += [
        {"label": label(p), "value": p}
        for p in sorted(chapters())
        if p not in ("77", "99")
    ]
    return options


def _focus_subset(frame, show) -> "pd.DataFrame":
    if frame.empty:
        return frame.copy()
    valid = frame.loc[
        frame["has_distance"] & frame["share_pct"].notna() & (frame["share_pct"] > 0)
    ].copy()
    if valid.empty:
        return valid
    if show == "top10":
        valid["share_rank"] = valid["share_pct"].rank(ascending=False, method="min")
        return valid[valid["share_rank"] <= 10].sort_values(
            "share_pct", ascending=False
        )
    if show == "nearest10":
        valid["distance_rank"] = valid["distance"].rank(ascending=True, method="min")
        return valid[valid["distance_rank"] <= 10].sort_values("distance")
    # Default "all": keep the meaningful top-40 pool so the map stays readable.
    return valid.sort_values("value", ascending=False).head(40)


# Sequential, high-contrast palette shared by the map and partner ranking.
_MAP_SCALE = [[0, "#c8e8eb"], [.35, "#8acdd4"], [.7, "#49acb8"], [1, "#168493"]]
_EXPORTER_COLOR = "#b27a2a"


@lru_cache(maxsize=1)
def _map_asset_url():
    version = hashlib.sha256(optimized_world()).hexdigest()[:12]
    return f"/m1-map-assets/{version}/"


@lru_cache(maxsize=24)
def _analysis(year, exporter, product, metric="dist"):
    pair = data_loader.load_country_pair_year() if product == "TOTAL" else flows(year, product)
    return analyze(pair, data_loader.load_geodist(), data_loader.load_country_meta(),
                   exporter, year, hs2=None if product == "TOTAL" else product, metric=metric)


def _country_options() -> list[dict]:
    meta = data_loader.load_country_meta().drop_duplicates("iso3")
    return [
        {"label": f"{r.name} ({r.iso3})", "value": r.iso3}
        for r in meta[meta.iso3.isin(FOCUS)].sort_values("name").itertuples(index=False)
    ]


@lru_cache(maxsize=1)
def _country_locations() -> pd.DataFrame:
    """Compact GeoDist main-city coordinates, including small economies."""
    path = config.processed_path("country_locations.csv")
    if not path.exists():
        return pd.DataFrame(columns=["lat", "lon"])
    return pd.read_csv(path).set_index("iso3")


def _geo_positions(codes) -> dict:
    codes = list(codes)
    coordinates = _country_locations()
    if all(code in coordinates.index for code in codes):
        selected = coordinates.loc[codes]
        return {"lat": selected["lat"].tolist(), "lon": selected["lon"].tolist()}
    return {"locations": codes, "locationmode": "ISO-3"}


def _map_figure(res, exporter, show, selected=None) -> go.Figure:
    subset = _focus_subset(res["frame"], show)
    fig = go.Figure()

    names = data_loader.load_country_meta().drop_duplicates("iso3").set_index("iso3")["name"].to_dict()
    exporter_name = names.get(exporter, exporter)

    # Exporter identity is separate from the partner colour scale.
    fig.add_trace(
        go.Choropleth(
            locations=[exporter],
            locationmode="ISO-3",
            z=[1],
            colorscale=[[0, "#e6c28d"], [1, "#e6c28d"]],
            showscale=False,
            marker_line_color=_EXPORTER_COLOR,
            marker_line_width=1.2,
            hovertemplate=f"<b>{exporter_name} ({exporter})</b><br>Selected exporter<extra></extra>",
            showlegend=False,
        )
    )

    if not subset.empty:
        by_distance = show == "nearest10"
        metric = "distance" if by_distance else "share_pct"
        plotted = subset.sort_values(metric, ascending=by_distance)
        customdata = [
            [
                r.name,
                r.partner,
                float(r.share_pct),
                float(r.distance),
                theme.fmt_usd(r.value),
            ]
            for r in plotted.itertuples(index=False)
        ]
        fig.add_trace(
            go.Choropleth(
                locations=plotted["partner"].tolist(),
                locationmode="ISO-3",
                z=plotted[metric].tolist(),
                zmin=0,
                zmax=float(plotted[metric].max()),
                colorscale=_MAP_SCALE,
                reversescale=by_distance,
                name="Trade partners",
                showlegend=False,
                customdata=customdata,
                hovertemplate=(
                    "<b>%{customdata[0]}</b> · %{customdata[1]}"
                    "<br>Export share  <b>%{customdata[2]:.2f}%</b>"
                    "<br>Exports  %{customdata[4]}"
                    "<br>Distance  %{customdata[3]:,.0f} km<extra></extra>"
                ),
                marker=dict(line=dict(color="white", width=0.7)),
                showscale=False,
                colorbar=dict(
                    title=dict(
                        text="Distance (km)" if by_distance else "Export share (%)",
                        side="top",
                        font=dict(size=11),
                    ),
                    orientation="h",
                    x=0.03,
                    xanchor="left",
                    y=-0.04,
                    yanchor="top",
                    len=0.52,
                    thickness=8,
                    outlinewidth=0,
                    tickfont=dict(size=10, color=theme.MUTED),
                    ticksuffix=" km" if by_distance else "%",
                    nticks=4,
                    tickformat=",.0f" if by_distance else ".1f",
                ),
            )
        )
    else:
        fig.add_annotation(
            text="No partners with distance data in this selection.",
            x=0.5,
            y=0.08,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=12, color=theme.MUTED),
        )

    # A text label identifies the exporter without covering country fills.
    fig.add_trace(
        go.Scattergeo(
            **_geo_positions([exporter]),
            mode="text",
            name="Exporter",
            text=[exporter_name],
            textposition="bottom center",
            textfont=dict(size=11, color="#9b5b1b"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    theme.style_figure(fig, height=520, uirevision=f"M1-map-{exporter}")
    fig.update_layout(
        dragmode="pan",
        margin=dict(l=5, r=5, t=5, b=5),
        paper_bgcolor="#f2f7f9",
        font=dict(family="Segoe UI, sans-serif", color=theme.INK),
        hoverlabel=dict(bgcolor="white", bordercolor="#b4c3d2",
                        font=dict(size=13, color=theme.INK, family=theme.FONT), align="left"),
        geo=dict(
            projection=dict(type="natural earth", scale=1, rotation=dict(lon=0, lat=0)),
            center=dict(lon=0, lat=13.5),
            uirevision=f"M1-map-{exporter}",
            resolution=50,
            showframe=False,
            bgcolor="#f2f7f9",
            showland=True,
            landcolor="#e0e9ed",
            showcountries=True,
            countrycolor="#ffffff",
            countrywidth=0.65,
            showcoastlines=False,
            coastlinecolor="#ccd9e0",
            coastlinewidth=0.5,
            showocean=True,
            oceancolor="#f2f7f9",
            showlakes=False,
            lataxis=dict(range=[-58, 85]),
            lonaxis=dict(range=[-180, 180]),
        ),
    )
    if selected in set(res["frame"].get("partner", [])):
        row = res["frame"].set_index("partner").loc[selected]
        distance_text = f"{row.distance:,.0f} km" if pd.notna(row.distance) else "Unavailable"
        selected_hover = (f"<b>{row['name']} ({selected})</b><br>Export share  {row.share_pct:.2f}%"
                          f"<br>Exports  {theme.fmt_usd(row.value)}<br>Distance  {distance_text}<extra></extra>")
        fig.add_trace(
            go.Choropleth(
                locations=[selected],
                z=[1],
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                showscale=False,
                marker_line_color=_EXPORTER_COLOR, marker_line_width=2.4,
                hovertemplate=selected_hover,
                name="Selected partner", showlegend=False,
            )
        )
        fig.add_trace(go.Scattergeo(
            **_geo_positions([selected]), mode="text", text=[row["name"]],
            textposition="top center", textfont=dict(size=12, color="#633e16"),
            customdata=[selected], hovertemplate=selected_hover,
            name="Selected country label", showlegend=False,
        ))
    else:
        # Local highlighting can locate a scatter-selected partner outside the
        # displayed map scope without rebuilding the base country geometries.
        fig.add_trace(go.Choropleth(
            locations=[], z=[], name="Selected outside scope", showscale=False,
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            marker_line_color=_EXPORTER_COLOR, marker_line_width=2.4, showlegend=False))
    return fig


def _map_summary(res, exporter, show) -> list:
    subset = _focus_subset(res["frame"], show)
    if subset.empty:
        return [html.P("No partners to display.", className="m1-empty")]
    by_distance = show == "nearest10"
    metric = "distance" if by_distance else "share_pct"
    ordered = subset.sort_values(metric, ascending=by_distance)
    share = float(ordered["share_pct"].sum())
    peak = float(ordered[metric].max())
    entries = []
    for r in ordered.head(6).itertuples(index=False):
        entries.append(
            html.Li(
                [
                    html.Div(
                        [
                            html.Span(
                                r.partner, className="m1-partner-code", title=r.name
                            ),
                            html.Strong(
                                f"{r.distance:,.0f} km"
                                if by_distance
                                else f"{r.share_pct:.1f}%"
                            ),
                        ],
                        className="m1-rank-line",
                    ),
                    html.Div(
                        html.Span(
                            style={"width": f"{getattr(r, metric) / peak * 100:.1f}%"}
                        ),
                        className="m1-rank-track",
                    ),
                ],
                title=f"{r.name} · {r.distance:,.0f} km · {theme.fmt_usd(r.value)}",
            )
        )
    return [
        html.Div("PARTNERS IN VIEW", className="m1-eyebrow"),
        html.Div(
            [html.Strong(f"{share:.1f}%"), html.Span("of selected exports")],
            className="m1-map-total",
        ),
        html.P(f"{len(subset)} partners · {exporter}", className="m1-map-scope"),
        html.Div(
            "NEAREST PARTNERS IN VIEW" if by_distance else "LARGEST SHARES IN VIEW",
            className="m1-eyebrow",
        ),
        html.Ol(entries, className="m1-rank-list"),
        html.P(
            (
                "Bars show distance. Darker country fills indicate nearer partners."
                if by_distance
                else "Shares use all exports in the selected year and product scope."
            ),
            className="m1-rail-note",
        ),
    ]


def _partner_list(res, show):
    subset = _focus_subset(res["frame"], show)
    if subset.empty:
        return html.P("No partners to display.", className="m1-empty")
    metric = "distance" if show == "nearest10" else "share_pct"
    maximum, peak_share = float(subset[metric].max()), float(subset.share_pct.max())
    rows = []
    for rank, row in enumerate(subset.itertuples(index=False), 1):
        intensity = float(getattr(row, metric)) / maximum if maximum else 0
        color = pc.sample_colorscale(_MAP_SCALE, 1 - intensity if show == "nearest10" else intensity)[0]
        rows.append(html.Button([
            html.Span(f"{rank:02}", className="m1-rank-number"),
            html.Div([
                html.Div([html.Strong(row.name), html.Small(row.partner)], className="m1-rank-name"),
                html.Div(html.I(style={"width": f"{max(2, row.share_pct / max(peak_share, .01) * 100)}%",
                                      "background": color}), className="m1-rank-track"),
            ], className="m1-rank-country"),
            html.Div([html.Strong(f"{row.share_pct:.2f}%"), html.Small(f"{row.distance:,.0f}")],
                     className="m1-rank-values"),
        ], id={"type": "M1-partner", "code": row.partner}, n_clicks=0,
            title=f"{row.name} ({row.partner})", className="m1-partner-row"))
    return rows


def _map_context(res, exporter, show, figure):
    return dict(exporter=exporter, key=f"{exporter}:{show}:{res['frame'].value.sum()}",
                mapCodes=list(figure.data[1].locations) if not _focus_subset(res["frame"], show).empty else [],
                rows={r.partner: dict(name=r.name, share=f"{r.share_pct:.2f}%",
                      distance=f"{r.distance:,.0f} km" if pd.notna(r.distance) else "Unavailable",
                      usd=theme.fmt_usd(r.value)) for r in res["frame"].itertuples(index=False)})


def _scale_view(res, show):
    subset = _focus_subset(res["frame"], show)
    near = show == "nearest10"
    maximum = float(subset["distance" if near else "share_pct"].max()) if not subset.empty else 0
    return [
        html.Div([html.Strong("Distance / km" if near else "Export share / %"),
                  html.Span("Darker = nearer" if near else "Darker = larger share")], className="m1-scale-title"),
        html.Div(className="m1-scale-gradient" + (" reverse" if near else "")),
        html.Div([html.Span("0"), html.Span(f"{maximum:,.0f}" if near else f"{maximum:.2f}%")], className="m1-scale-ticks"),
    ]


def _preserve_map_view(figure, relayout, previous):
    """Carry the last map gesture across server renders for the same exporter."""
    if (
        not previous
        or previous.get("layout", {}).get("uirevision") != figure.layout.uirevision
    ):
        return figure
    geo = figure.layout.geo.to_plotly_json()
    old_geo = previous.get("layout", {}).get("geo", {})
    old_projection = old_geo.get("projection", {})
    for key in ("scale", "rotation"):
        if key in old_projection:
            geo["projection"][key] = old_projection[key]
    if "center" in old_geo:
        geo["center"] = old_geo["center"]
    allowed = {
        "geo.projection.scale",
        "geo.projection.rotation.lon",
        "geo.projection.rotation.lat",
        "geo.center.lon",
        "geo.center.lat",
        "geo.center",
        "geo.projection.rotation",
    }
    for key, value in (relayout or {}).items():
        if key not in allowed:
            continue
        parts = key.split(".")[1:]
        target = geo
        for part in parts[:-1]:
            if not isinstance(target.get(part), dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
    figure.layout.geo = geo
    return figure


def _comparison_rows(frame) -> list[dict]:
    if frame.empty:
        return []
    valid = frame.loc[
        frame["has_distance"] & frame["share_pct"].notna() & (frame["share_pct"] > 0)
    ].copy()
    if valid.empty:
        return []
    # Ranks are computed across all valid partners, then the table shows the
    # union of the top-10 by share, the nearest 10 and the top-40 by value.
    valid["share_rank"] = (
        valid["share_pct"].rank(ascending=False, method="min").astype(int)
    )
    valid["distance_rank"] = (
        valid["distance"].rank(ascending=True, method="min").astype(int)
    )
    union = pd.concat(
        [
            valid[valid["share_rank"] <= 10],
            valid[valid["distance_rank"] <= 10],
            valid.sort_values("value", ascending=False).head(40),
        ]
    ).drop_duplicates("partner")
    rows = []
    for r in union.sort_values("share_pct", ascending=False).itertuples(index=False):
        flags = []
        if r.share_rank <= 10:
            flags.append("Top 10 share")
        if r.distance_rank <= 10:
            flags.append("Nearest 10")
        rows.append(
            {
                "name": r.name,
                "partner": r.partner,
                "distance": round(float(r.distance), 0),
                "value": round(float(r.value), 2),
                "share_pct": round(float(r.share_pct), 3),
                "share_rank": int(r.share_rank),
                "distance_rank": int(r.distance_rank),
                "flags": " · ".join(flags),
            }
        )
    return rows


def _overlap_text(rows) -> str:
    both = [
        r["partner"]
        for r in rows
        if "Top 10 share" in r["flags"] and "Nearest 10" in r["flags"]
    ]
    if both:
        return "Overlap of top-10 share and nearest-10: " + ", ".join(both)
    return "No partner is both a top-10 share partner and among the nearest 10."


def _stats_view(res, demo: bool, requested_metric: str) -> list:
    s = res["stats"]
    rho = s["spearman"]
    rho_text = f"{rho:.2f}" if rho is not None else "n/a"
    wavg = s["weighted_distance"]
    wavg_text = f"{wavg:,.0f} km" if wavg is not None else "n/a"

    kpis = components.kpi_row(
        [
            ("Partners", str(s["n"])),
            ("Partners with distance", f"{s['coverage']:.0%}"),
            ("Weighted distance", wavg_text),
            ("Spearman ρ", rho_text),
        ]
    )

    notes = []
    if demo:
        notes.append(
            "Running on demo fallback data; build the analysis tables for real values."
        )
    if requested_metric != s["metric_used"]:
        notes.append(
            f"Requested metric '{requested_metric}' is unavailable; using '{s['metric_used']}' instead."
        )
    if s["n_missing"]:
        notes.append(
            f"{s['n_missing']} partner(s) have no distance record: excluded from distance analysis, retained in share denominators."
        )

    children = [kpis]
    if notes:
        children.append(
            html.Ul([html.Li(note) for note in notes], className="m1-notes")
        )
    if s["top_partner"]:
        children.append(
            html.P(
                f"Top partner: {s['top_name']} ({s['top_partner']}) · "
                f"{s['top_share']:.2f}% of this scope."
            )
        )
    return children


def _finding(res, rows, show) -> str:
    s = res["stats"]
    rho = s["spearman"]
    scope = {
        "top10": "top-10 share partners",
        "nearest10": "nearest 10 partners",
        "all": "top-40 partners",
    }.get(show, "partners")
    if s["n"] < 3 or rho is None:
        return f"Not enough partners to summarise the {scope} yet."
    if rho <= -0.3:
        direction = "nearby partners tend to hold larger shares"
    elif rho < 0:
        direction = (
            "there is only a weak tendency for nearby partners to hold larger shares"
        )
    else:
        direction = "nearby partners do not hold larger shares in this selection"
    return f"Across all partners with distance data, {direction} (ρ = {rho:.2f}). {_overlap_text(rows)}"


def _evidence(res, product) -> list:
    s = res["stats"]
    scope = "all products" if product == "TOTAL" else f"HS{product}"
    rho = s["spearman"]
    parts = [
        f"{s['n']} partners in scope ({scope}), {s['coverage']:.0%} partner-count distance coverage. "
    ]
    if rho is not None:
        parts.append(f"Spearman ρ = {rho:.2f} between distance and share.")
    else:
        parts.append("Not enough partners to compute a rank correlation.")
    return parts


def _conclusion(res) -> str:
    s = res["stats"]
    rho = s["spearman"]
    if s["n"] < 3 or s["coverage"] < 0.5:
        return "Not enough evidence yet: too few partners or too little distance coverage. "
    if rho is None:
        return "Not enough paired observations to draw a conclusion."
    if rho <= -0.3:
        return (
            "Nearby partners tend to hold larger shares in this selection, "
            "although the map and overlap list describe, not cause, the pattern."
        )
    if rho < 0:
        return "Only a weak negative association is visible in this selection."
    return (
        "No expected negative association appears in this selection; the "
        "nearest partners and top-share partners should be inspected separately."
    )


def layout():
    year_options = [
        {"label": str(y), "value": y}
        for y in range(config.YEAR_MIN, config.YEAR_MAX + 1)
    ]
    return html.Div(
        className="module-inner m1-module",
        children=[
            components.module_intro(
                "Does distance shape trade?",
                "Locate the main export partners, then compare typical export shares across distance groups.",
            ),
            dcc.Store(id=cid("selected")),
            dcc.Store(id=cid("map-context")),
            dcc.Store(id=cid("highlight-token")),
            dcc.Store(id=cid("map-view")),
            dcc.Download(id=cid("download")),
            html.Div(
                html.Div(
                    [
                        components.field(
                            "Year",
                            dcc.Dropdown(
                                id=cid("year"),
                                options=year_options,
                                value=2023,
                                clearable=False,
                                className="ctl-dropdown",
                            ),
                        ),
                        components.field(
                            "Exporter",
                            dcc.Dropdown(
                                id=cid("exporter"),
                                options=_country_options(),
                                value="CHN",
                                clearable=False,
                                className="ctl-dropdown",
                            ),
                        ),
                        components.field(
                            "Product",
                            dcc.Dropdown(
                                id=cid("product"),
                                options=_product_options(),
                                value="TOTAL",
                                clearable=False,
                                className="ctl-dropdown",
                            ),
                        ),
                        components.field(
                            "Distance measure",
                            dcc.Dropdown(
                                id=cid("dist-metric"),
                                options=[
                                    {"label": METRIC_LABELS[m], "value": m}
                                    for m in ("dist",)
                                ],
                                value="dist",
                                clearable=False,
                                className="ctl-dropdown",
                            ),
                        ),
                        components.field(
                            "Map / ranking scope",
                            dcc.Dropdown(
                                id=cid("show"),
                                options=[
                                    {"label": "Top 10 by share", "value": "top10"},
                                    {"label": "Nearest 10", "value": "nearest10"},
                                    {"label": "Top 40 partners", "value": "all"},
                                ],
                                value="top10",
                                clearable=False,
                                className="ctl-dropdown",
                            ),
                        ),
                    ],
                    className="chips",
                ),
                className="module-controls",
            ),
            html.Div(id=cid("stats"), className="stats-body"),
            html.Div([
                html.Div([
                    html.Div([html.Span("PARTNER GEOGRAPHY", className="m1-map-eyebrow"),
                              html.H3(id=cid("map-title"), className="card-title-text")]),
                    html.Span(id=cid("map-badge"), className="m1-scope-badge"),
                ], className="m1-map-heading"),
                html.Div([
                    html.Span([html.I(className="m1-key-exporter"), "Exporter"]),
                    html.Span([html.I(className="m1-key-partner"), "Trade partner"]),
                    html.Span([html.I(className="m1-key-selected"), "Selected partner"]),
                    html.Span(id=cid("map-encoding"), className="m1-encoding-key"),
                ], className="m1-map-legend"),
                html.Div([
                    html.Div([
                        dcc.Graph(id=cid("map"), style={"height": "520px"},
                                  figure=theme.empty_figure("Loading partner geography…", height=520),
                                  className="graph-interactive", responsive=True,
                                  config={"displayModeBar": True, "displaylogo": False,
                                          "topojsonURL": _map_asset_url(), "responsive": True,
                                          "scrollZoom": True, "doubleClick": "reset",
                                          "modeBarButtons": [["zoomInGeo", "zoomOutGeo", "resetGeo"]]}),
                        html.Div(id=cid("map-scale"), className="m1-map-scale"),
                        html.Div([html.Span("Scroll to zoom · Drag to pan · Reset for world view"),
                                  html.Span("Click a country or partner")], className="m1-map-tools"),
                    ], className="m1-map-stage"),
                    html.Aside([
                        html.Div([html.Span("PARTNERS IN VIEW", className="m1-map-eyebrow"),
                                  html.Strong(id=cid("partner-count"))], className="m1-rail-heading"),
                        html.Div([html.Span("Partner / share"), html.Span("Share / distance km")], className="m1-rank-head"),
                        html.Div(id=cid("partner-list"), className="m1-partner-list"),
                        html.Div(id=cid("map-summary"), className="m1-rail-total"),
                    ], className="m1-map-rail"),
                ], className="m1-map-grid"),
                html.Div([
                    html.Div(id=cid("map-detail"), role="status"),
                    html.Button("Clear selection", id=cid("clear-selection"), className="m1-clear-button"),
                ], className="m1-detail-strip"),
                html.Div([html.Span("PATTERN", className="m1-eyebrow"),
                          html.P(id=cid("finding"))], className="m1-map-finding"),
            ], className="card m1-map-card"),
            html.Div(
                [
                    components.card(
                        "Do nearer partners receive larger shares?",
                        [html.P("Each dot is a partner. The gold line shows the typical share across distance groups.", className="m1-scatter-intro"),
                        dcc.Graph(
                            id=cid("scatter"),
                            style={"height": "430px"},
                            config={"displayModeBar": False},
                        ),
                        html.P("Gold line: median share in up to five similarly sized distance groups. Shaded band: the middle 50% of partner shares, not a confidence interval. All valid partners are included regardless of the map filter. This is a descriptive comparison, not a causal effect.", className="m1-scatter-note")],
                    ),
                    components.verification_panel(
                        _HYPOTHESIS,
                        "Select a country, year and product to see the map and partner lists.",
                        "A dynamic conclusion will follow once the selection has enough coverage.",
                        evidence_id=cid("evidence"),
                        conclusion_id=cid("conclusion"),
                    ),
                ],
                className="m1-analysis",
            ),
            html.Div(
                id=cid("selection-detail"), className="selection-detail", role="status"
            ),
            html.Details(
                [
                    html.Summary("Top-share & nearest-partner evidence"),
                    dash_table.DataTable(
                        id=cid("comparison-table"),
                        columns=[
                            {"name": "Partner", "id": "name"},
                            {"name": "Distance (km)", "id": "distance"},
                            {"name": "Exports (k USD)", "id": "value"},
                            {"name": "Share %", "id": "share_pct"},
                            {"name": "Share rank", "id": "share_rank"},
                            {"name": "Distance rank", "id": "distance_rank"},
                            {"name": "Flags", "id": "flags"},
                        ],
                        data=[],
                        page_size=10,
                        style_table={"overflowX": "auto"},
                        style_cell={
                            "textAlign": "left",
                            "fontSize": 12,
                            "fontFamily": "inherit",
                            "padding": "8px",
                            "minWidth": "90px",
                        },
                        style_header={"fontWeight": 600, "backgroundColor": "#eef3ff"},
                    ),
                ]
            ),
            html.Details(
                className="card",
                children=[
                    html.Summary("How this view works"),
                    html.Button("Download complete partner evidence", id=cid("export")),
                    html.P(
                        "The amber country marks the exporter. Partner countries are filled in teal: darker means a larger export share in Top 10 by share and Top 40 partners, or a shorter distance in Nearest 10. Grey countries are outside the displayed selection. Hover over a country to see its export value, share and distance. The ranking summarises the current map selection. The table lists the top-10 partners by share and the nearest 10 partners in one place and marks any overlap."
                    ),
                    html.P(
                        "Spearman ρ is reported as a supporting description of the distance–share association, not a causal estimate."
                    ),
                ],
            ),
        ],
    )


def register_callbacks(app):
    @app.server.route("/m1-map-assets/<version>/world_50m.json", endpoint="m1_topology")
    def m1_topology(version):
        response = Response(optimized_world(), mimetype="application/json")
        response.cache_control.public = True
        response.cache_control.max_age = 86400
        response.add_etag()
        return response.make_conditional(request)

    app.clientside_callback(ClientsideFunction(namespace="m1", function_name="choose"),
        Output(cid("selected"), "data"),
        Input(cid("map"), "clickData"), Input(cid("scatter"), "clickData"),
        Input({"type": "M1-partner", "code": ALL}, "n_clicks"),
        Input(cid("clear-selection"), "n_clicks"),
        Input(cid("exporter"), "value"), Input(cid("year"), "value"),
        Input(cid("product"), "value"), Input(cid("show"), "value"),
        State(cid("map-context"), "data"), State({"type": "M1-partner", "code": ALL}, "id"),
        State(ACTIVE_MODULE, "data"), prevent_initial_call=True)
    app.clientside_callback(ClientsideFunction(namespace="m1", function_name="highlight"),
        Output(cid("map-detail"), "children"),
        Output({"type": "M1-partner", "code": ALL}, "className"),
        Output(cid("highlight-token"), "data"),
        Input(cid("selected"), "data"), Input(cid("map-context"), "data"),
        State({"type": "M1-partner", "code": ALL}, "id"))
    app.clientside_callback(ClientsideFunction(namespace="m1", function_name="rememberView"),
        Output(cid("map-view"), "data"), Input(cid("map"), "relayoutData"),
        Input(cid("exporter"), "value"), State(cid("map-view"), "data"))

    @app.callback(
        Output(cid("selection-detail"), "children"),
        Input(cid("selected"), "data"),
        Input(cid("exporter"), "value"),
        Input(cid("year"), "value"),
        Input(cid("product"), "value"),
        Input(ACTIVE_MODULE, "data"),
    )
    def selection_detail(selected, country, year, product, active):
        guard_active(MODULE_ID, active)
        if not selected:
            return "Click a scatter point, map country or partner row to highlight the same partner across all three views."
        res = _analysis(year, country, product)
        d = res["frame"]
        r = d[d.partner.eq(selected)]
        if r.empty:
            return f"{selected} · No recorded partner flow in the current scope."
        r = r.iloc[0]
        distance = (
            f"{r.distance:,.0f} km" if pd.notna(r.distance) else "Distance unavailable"
        )
        return f"Selected: {r['name']} ({selected}) · {r.share_pct:.2f}% of exports · {distance}. Highlighting preserves the full association sample."

    @app.callback(
        Output(cid("download"), "data"),
        Input(cid("export"), "n_clicks"),
        State(cid("year"), "value"),
        State(cid("exporter"), "value"),
        State(cid("product"), "value"),
        prevent_initial_call=True,
    )
    def download(n, year, country, product):
        res = _analysis(year, country, product)
        return dcc.send_data_frame(
            res["frame"]
            .assign(
                year=year,
                exporter=country,
                product=product,
                unit="thousand current USD",
            )
            .to_csv,
            "M1_evidence.csv",
            index=False,
        )

    @app.callback(
        Output(cid("scatter"), "figure"),
        Input(cid("year"), "value"),
        Input(cid("exporter"), "value"),
        Input(cid("product"), "value"),
        Input(ACTIVE_MODULE, "data"),
        Input(cid("selected"), "data"),
    )
    def scatter(year, country, product, active, selected):
        guard_active(MODULE_ID, active)
        if country not in FOCUS:
            return theme.empty_figure("Select one of the six focal economies.")
        res = _analysis(year, country, product)
        return scatter_figure(res, selected)

    @app.callback(
        Output(cid("partner-list"), "children"),
        Output(cid("finding"), "children"),
        Output(cid("map"), "figure"),
        Output(cid("stats"), "children"),
        Output(cid("comparison-table"), "data"),
        Output(cid("evidence"), "children"),
        Output(cid("conclusion"), "children"),
        Output(cid("exporter"), "options"),
        Output(cid("map-summary"), "children"),
        Output(cid("map-encoding"), "children"),
        Output(cid("map-context"), "data"),
        Output(cid("map-title"), "children"),
        Output(cid("map-badge"), "children"),
        Output(cid("map-scale"), "children"),
        Output(cid("partner-count"), "children"),
        Input(cid("year"), "value"),
        Input(cid("exporter"), "value"),
        Input(cid("product"), "value"),
        Input(cid("dist-metric"), "value"),
        Input(cid("show"), "value"),
        Input(ACTIVE_MODULE, "data"),
        State(cid("map-view"), "data"),
    )
    def _update(
        year,
        exporter,
        product,
        dist_metric,
        show,
        active_module,
        map_view,
    ):
        guard_active(MODULE_ID, active_module)

        meta = data_loader.load_country_meta().drop_duplicates("iso3")
        options = _country_options()

        if exporter not in FOCUS:
            return (
                [],
                "Select an exporter.",
                theme.empty_figure("Select an exporter."),
                html.Div(),
                [],
                "No exporter selected.",
                "Select an exporter to begin.",
                options,
                [],
                "Select an exporter to colour partner countries",
                {"rows": {}, "mapCodes": []}, "Select an exporter", "", [], "00",
            )

        res = _analysis(year, exporter, product, dist_metric)
        demo = bool(data_loader.is_demo())
        rows = _comparison_rows(res["frame"])
        figure = _map_figure(res, exporter, show)
        if map_view and map_view.get("exporter") == exporter:
            _preserve_map_view(figure, map_view.get("gesture"),
                               {"layout": {"uirevision": figure.layout.uirevision}})
        finding = _finding(res, rows, show)
        stats = _stats_view(res, demo, dist_metric)
        evidence = _evidence(res, product)
        conclusion = _conclusion(res)
        encoding = (
            "Darker = nearer partner"
            if show == "nearest10"
            else "Darker = larger export share"
        )
        return (
            _partner_list(res, show),
            finding,
            figure,
            stats,
            rows,
            evidence,
            conclusion,
            options,
            [html.Span("Displayed export share"),
             html.Strong(f"{_focus_subset(res['frame'], show).share_pct.sum():.2f}%" if not res['frame'].empty else "0.00%")],
            encoding,
            {**_map_context(res, exporter, show, figure), "key": f"{year}:{exporter}:{product}:{show}:{dist_metric}"},
            f"{meta.set_index('iso3').loc[exporter, 'name']} · Export partners",
            f"{year} · {len(_focus_subset(res['frame'], show))} partners",
            _scale_view(res, show),
            f"{len(_focus_subset(res['frame'], show)):02}",
        )


def scatter_figure(res, selected=None):
    d = res["frame"]
    d = d[d.has_distance & d.share_pct.gt(0)] if not d.empty else d
    if d.empty:
        return theme.empty_figure("No positive trade with valid distance.")
    fig = go.Figure(
        go.Scatter(
            x=d.distance,
            y=d.share_pct,
            customdata=d.partner,
            mode="markers",
            text=d.name,
            marker={
                "size": [11 if p == selected else 7 for p in d.partner],
                "color": ["#c79750" if p == selected else "#315c88" for p in d.partner],
                "opacity": [.95 if p == selected else .45 for p in d.partner],
                "line": {"color": "white", "width": .5},
            },
            name="Partner observations", showlegend=True,
            hovertemplate="%{text} (%{customdata})<br>%{x:,.0f} km · %{y:.3f}%<extra></extra>",
        )
    )
    total = res["frame"].value.sum()
    coverage = d.value.sum() / total if total else 0
    profile = distance_profile(res["frame"])
    if not profile.empty:
        fig.add_trace(go.Scatter(
            x=profile.distance, y=profile.q25, mode="lines",
            line=dict(width=0), hoverinfo="skip", showlegend=False,
            name="Lower quartile", legendgroup="profile"))
        fig.add_trace(go.Scatter(
            x=profile.distance, y=profile.q75, mode="lines",
            line=dict(width=0), fill="tonexty", fillcolor="rgba(178,122,42,.12)",
            hoverinfo="skip", name="Middle 50%", legendgroup="profile"))
        fig.add_trace(go.Scatter(
            x=profile.distance, y=profile.share, mode="lines+markers",
            line=dict(color="#b27a2a", width=2.8),
            marker=dict(size=8, color="#b27a2a", line=dict(color="white", width=1.3)),
            name="Group median", legendgroup="profile",
            customdata=profile[["n", "near", "far", "q25", "q75"]].values.tolist(),
            hovertemplate=("<b>Typical partner share</b><br>Median %{y:.3f}%"
                           "<br>%{customdata[0]:.0f} partners · %{customdata[1]:,.0f}–%{customdata[2]:,.0f} km"
                           "<br>Middle 50%: %{customdata[3]:.3f}%–%{customdata[4]:.3f}%<extra></extra>")))
    labels = d.nlargest(3, "share_pct").copy()
    if selected in set(d.partner) and selected not in set(labels.partner):
        labels = pd.concat([labels, d[d.partner.eq(selected)]])
    fig.add_trace(go.Scatter(
        x=labels.distance, y=labels.share_pct, mode="text", text=labels.partner,
        customdata=labels.partner, textposition=["top right", "top left", "bottom right", "bottom center"][:len(labels)],
        textfont=dict(color="#3f566c", size=11), showlegend=False,
        hovertemplate="%{customdata}<br>%{x:,.0f} km · %{y:.3f}%<extra></extra>"))
    fig.update_xaxes(
        tickmode="array",
        tickvals=[100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        ticktext=["100", "200", "500", "1,000", "2,000", "5,000", "10,000", "20,000"],
    )
    fig.update_yaxes(
        tickmode="array",
        tickvals=[10.0**n for n in range(-10, 3)],
        ticktext=[f"{10.0**n:g}" for n in range(-10, 3)],
    )
    fig.update_layout(
        height=430,
        xaxis={"type": "log", "title": "Partner distance (km · log scale)"},
        yaxis={"type": "log", "title": "Export share (% · log scale)"},
        title=dict(text=(
            f"Near-group median {profile.iloc[0]['share']:.3f}% → far-group median {profile.iloc[-1]['share']:.3f}%"
            if not profile.empty else "Too few distinct distances for a grouped trend"
        ) + f"<br><sup>{len(d)} partners · {coverage:.1%} of export value has valid distance</sup>",
                   font=dict(size=12, color=theme.MUTED), x=0, xanchor="left"),
        legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", font=dict(size=10), traceorder="normal"),
        margin={"l": 75, "r": 20, "t": 95, "b": 60},
        uirevision="M1-distance-share",
    )
    return fig


def ranking_figure(res, show, selected):
    d = _focus_subset(res["frame"], show)
    if selected and selected not in set(d.partner):
        d = pd.concat([d, res["frame"][res["frame"].partner.eq(selected)]])
    if d.empty:
        return theme.empty_figure("No partners in the selected scope.")
    fig = go.Figure(
        go.Bar(
            x=d.share_pct,
            y=d.partner,
            customdata=d.partner,
            orientation="h",
            marker_color=["#c79750" if p == selected else "#315c88" for p in d.partner],
            hovertemplate="%{y}: %{x:.3f}%<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(260, len(d) * 22),
        margin=dict(l=98, r=10, t=10, b=40),
        xaxis_title="All-partner share (%)",
        yaxis=dict(autorange="reversed", tickmode="array", tickvals=d.partner,
                   ticktext=[name if len(name) < 19 else code for name, code in zip(d.name, d.partner)]),
    )
    return fig
