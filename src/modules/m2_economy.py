"""M2: global economic scale, single-dimension matching and two-country evidence."""

from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dcc, html, dash_table, ClientsideFunction
from dash.exceptions import PreventUpdate

from src import components, config, data_loader, theme
from src.analytics.economy import (
    FOCUS_COUNTRIES, MODES, country_names, prepare_year,
    match_candidates, evidence_frame,
)
from src.ids import ACTIVE_MODULE, mid
from src.module_base import guard_active

MODULE_ID = "M2"
NAV_LABEL = "M2  Economy"
ORDER = 2
FOCUS_NAMES = ["United States", "Germany", "China", "Mexico", "Netherlands", "Italy"]
LIMITATION = (
    "Nominal goods exports / nominal GDP compares gross trade with value added; "
    "it is not GDP contribution or efficiency. Values above 100% can occur. "
    "Services are excluded; similar scale does not establish causation."
)


def cid(name):
    return mid(MODULE_ID, name)


@lru_cache(maxsize=1)
def reference():
    path = config.DATA_DIR / "reference/m2_country_codes_V202601.csv"
    if not path.exists():
        raise FileNotFoundError("Missing M2 BACI country dictionary. Restore data/reference/m2_country_codes_V202601.csv.")
    return pd.read_csv(path)


def data_for_year(year):
    return prepare_year(data_loader.load_country_year(), data_loader.load_gdp_year(), reference(), year)


def field(label, widget):
    return html.Div([html.Label(label, htmlFor=widget.id), widget], className="m2-field")


def layout():
    return html.Div(className="module-inner m2", children=[
        dcc.Store(id=cid("context")), dcc.Download(id=cid("download")),
        dcc.Store(id=cid("reference-lines-ready")),
        html.Div([
            html.Div("ECONOMIC SCALE / M2", className="m2-eyebrow"),
            html.H2("Similar GDP. Similar exports?"),
            html.P("Start with Germany and Japan in 2023, then reverse the question: at similar exports, how different is GDP?"),
        ], className="m2-intro"),
        components.card(None, html.Div([
            html.Div([
                field("Analysis year", dcc.Dropdown(id=cid("year"), options=list(range(1995, 2024)), value=2023, clearable=False)),
                field("Match on one dimension", dcc.RadioItems(id=cid("mode"), options=[{"label": "Similar GDP", "value": "gdp"}, {"label": "Similar exports", "value": "export_value"}], value="gdp", className="m2-radio")),
                field("Similarity window", dcc.RadioItems(id=cid("factor"), options=[{"label": "1.25×", "value": 1.25}, {"label": "1.5×", "value": 1.5}], value=1.25, className="m2-radio")),
            ], className="m2-controls"),
            field("Anchor economy · select one of the six focus countries", dcc.RadioItems(
                id=cid("anchor"),
                options=[{"label": name, "value": code} for code, name in zip(FOCUS_COUNTRIES, FOCUS_NAMES)],
                value="DEU", className="m2-anchors")),
            html.P("Choose an anchor from the six focus countries. Matching candidates and the scatter background cover all eligible global economies; Japan remains available as a comparison.", className="m2-note"),
        ])),
        components.card("Global context · GDP and goods exports", html.Div([
            html.Div(id=cid("scope"), className="m2-note", role="status"),
            dcc.Graph(id=cid("graph"), figure=theme.empty_figure("Select M2 to begin."),
                      className="graph-interactive",
                      config={"displayModeBar": True, "displaylogo": False,
                              "responsive": True, "scrollZoom": True, "doubleClick": "reset",
                              "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
                      style={"height": "510px", "minHeight": "510px"}),
            html.P("Both axes are logarithmic and use billion current USD. Reference lines use darker blue for higher export/GDP ratios (10%, 50%, 100%). The band marks the selected matching dimension only. Click a matching point to compare it with the anchor.", className="m2-note"),
            html.P("Scroll to zoom, or drag a rectangle to enlarge it. Use Pan in the chart toolbar to move the view; double-click or use Reset axes to restore it. Zooming does not change the matching pool.", className="m2-note"),
        ])),
        components.card("Compare two economies", html.Div([
            field("Comparison economy · current matches", dcc.Dropdown(id=cid("comparator"), options=[{"label": "Japan · JPN", "value": "JPN"}], value="JPN", clearable=False)),
            html.P(id=cid("match-status"), role="status", className="m2-note"),
            html.Div(id=cid("cards"), className="m2-comparison"),
            html.Div(id=cid("finding"), className="m2-finding"),
            html.P(LIMITATION, className="m2-note"),
        ])),
        html.Details([
            html.Summary("Matching list, exclusions and source evidence"),
            html.P("All matches are listed, sorted by multiplicative distance from the anchor. No Top-N restriction or second-dimension filter is used.", className="m2-note"),
            dash_table.DataTable(id=cid("table"), columns=[
                {"name": "Economy", "id": "economy"},
                {"name": "GDP · $bn", "id": "gdp"},
                {"name": "Goods exports · $bn", "id": "exports"},
                {"name": "Exports / GDP", "id": "ratio"},
                {"name": "Matching value / anchor", "id": "matching_ratio"},
            ], data=[], page_size=10, style_table={"overflowX": "auto"}, style_cell={"textAlign": "left", "fontFamily": "inherit", "fontSize": 12, "padding": "9px"}, style_header={"fontWeight": 600, "backgroundColor": theme.ACCENT_SOFT}),
            html.Div(id=cid("exclusions"), className="m2-note"),
            html.Button("Download current evidence CSV", id=cid("export"), n_clicks=0, className="m2-download", disabled=True),
            html.P("CSV includes all source entities for the selected year, exclusion reasons, matching flags and unrounded amounts. Sources: BACI HS92 V202601 (thousand current USD); CHELEM GDP-VAL V202502 (million current USD). Exports/GDP = exports ÷ (GDP × 1,000).", className="m2-note"),
            html.P("Country scope follows the BACI dictionary. Other Asia nes, Europe EFTA nes and SACU are excluded. Belgium–Luxembourg through 1998 and pre-split Sudan through 2011 are excluded from matching to avoid pairing historical trade territories with different GDP territories. No missing amount is treated as zero.", className="m2-note"),
        ], className="card m2-details"),
    ])


def scatter_figure(rows, anchor, comparator, mode, factor):
    valid = rows[rows.valid]
    if valid.empty:
        return theme.empty_figure("No finite positive GDP/export pairs for this year.")
    peers = match_candidates(rows, anchor, mode, factor)
    matched = set(peers.country)
    fig = go.Figure()
    for ratio, color in [(0.1, "#9dbad5"), (0.5, "#547fa8"), (1, "#254d73")]:
        # Legend-only traces do not expand autorange. The client positions each
        # reference shape at the exact viewport edges in logarithmic space.
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=f"Exports/GDP = {ratio:.0%}", line={"color": color, "width": 1.8}, hoverinfo="skip", legendgroup=f"ratio-{ratio}"))
        fig.add_shape(type="line", name=f"m2-ratio-{ratio}", xref="x domain", yref="y domain",
                      x0=0, x1=0, y0=0, y1=0, visible=False, layer="above",
                      line={"color": color, "width": 1.8})
    a = valid[valid.country.eq(anchor)]
    if not a.empty:
        value = a.iloc[0]["gdp_billion_usd" if mode == "gdp" else "exports_billion_usd"]
        band = {"fillcolor": theme.ACCENT, "opacity": .07, "line_width": 0, "layer": "below"}
        if mode == "gdp":
            fig.add_vrect(x0=value / factor, x1=value * factor, **band)
        else:
            fig.add_hrect(y0=value / factor, y1=value * factor, **band)
    roles = [
        ("Global economies", valid[~valid.country.isin(matched | {anchor, comparator})], 7, "circle", False),
        ("Matches", valid[valid.country.isin(matched - {comparator})], 11, "circle", False),
        ("Anchor", a, 16, "diamond", True),
        ("Comparison", valid[valid.country.eq(comparator)], 15, "square", True),
    ]
    for role, data, size, symbol, labels in roles:
        if data.empty:
            continue
        custom = [[r.country, r.name, r.export_gdp_ratio] for r in data.itertuples()]
        fig.add_trace(go.Scatter(
            x=data.gdp_billion_usd.tolist(), y=data.exports_billion_usd.tolist(),
            customdata=custom, text=data.country.tolist(), name=role,
            mode="markers+text" if labels else "markers",
            textposition="top left" if role == "Anchor" else "bottom right",
            textfont={"size": 12, "color": theme.INK},
            marker={"size": size, "symbol": symbol,
                    "color": "#b8c2ce" if role == "Global economies" else [theme.country_color(c) for c in data.country],
                    "opacity": .65 if role == "Global economies" else 1,
                    "line": {"color": theme.ACCENT if role == "Matches" else "white", "width": 2 if role == "Matches" else 1}},
            hovertemplate="<b>%{customdata[1]} (%{customdata[0]})</b><br>GDP: $%{x:,.3f}bn<br>Goods exports: $%{y:,.3f}bn<br>Exports / GDP: %{customdata[2]:.2%}<extra>" + role + "</extra>",
        ))
    fig.update_layout(
        template=theme.PLOT_TEMPLATE, height=510, margin={"l": 65, "r": 25, "t": 35, "b": 105},
        dragmode="zoom",
        xaxis={"type": "log", "title": "GDP · billion current USD (log)", "autorange": True},
        yaxis={"type": "log", "title": "Goods exports · billion current USD (log)", "autorange": True},
        legend={"orientation": "h", "y": -0.22, "x": 0, "font": {"size": 11}},
        uirevision=f"M2-{int(rows.year.iloc[0])}-{anchor}-{mode}-{factor}",
    )
    return fig


def economy_card(row, role):
    return html.Div([
        html.Div(role, className="m2-eyebrow"), html.H3(f"{row['name']} · {row['country']}"),
        html.Dl([
            html.Div([html.Dt("GDP"), html.Dd(f"${row['gdp_billion_usd']:,.3f}bn")]),
            html.Div([html.Dt("Goods exports"), html.Dd(f"${row['exports_billion_usd']:,.3f}bn")]),
            html.Div([html.Dt("Exports / GDP"), html.Dd(f"{row['export_gdp_ratio']:.2%}")]),
        ]),
    ], className="m2-economy", style={"borderTopColor": theme.country_color(row["country"])})


def finding_text(a, b, mode, year):
    other = "export_value" if mode == "gdp" else "gdp"
    return (
        f"In {year}, {b['name']}'s {MODES[mode]} measured {b[mode] / a[mode]:.2f}× "
        f"{a['name']}'s, while its {MODES[other]} measured {b[other] / a[other]:.2f}×. "
        f"Exports/GDP was {b['export_gdp_ratio']:.2%} versus {a['export_gdp_ratio']:.2%}. "
        "Matching on one measure leaves differences in the other visible; scale alone does not explain those differences."
    )


def register_callbacks(app):
    app.clientside_callback(
        ClientsideFunction(namespace="m2", function_name="extendReferenceLines"),
        Output(cid("reference-lines-ready"), "data"),
        Input(cid("graph"), "figure"), Input(ACTIVE_MODULE, "data"),
    )
    @app.callback(
        Output(cid("graph"), "figure"), Output(cid("anchor"), "options"),
        Output(cid("comparator"), "options"), Output(cid("comparator"), "value"),
        Output(cid("comparator"), "disabled"), Output(cid("scope"), "children"),
        Output(cid("match-status"), "children"), Output(cid("cards"), "children"),
        Output(cid("finding"), "children"), Output(cid("table"), "data"),
        Output(cid("exclusions"), "children"), Output(cid("context"), "data"),
        Output(cid("export"), "disabled"),
        Input(ACTIVE_MODULE, "data"), Input(cid("year"), "value"),
        Input(cid("anchor"), "value"), Input(cid("mode"), "value"),
        Input(cid("factor"), "value"), Input(cid("comparator"), "value"),
        Input(cid("graph"), "clickData"),
        State(cid("graph"), "relayoutData"), State(cid("context"), "data"),
    )
    def _render(active, year, anchor, mode, factor, comparator, click, viewport, previous):
        guard_active(MODULE_ID, active)
        try:
            if anchor not in FOCUS_COUNTRIES:
                raise ValueError("Select an anchor from the six focus countries: USA, DEU, CHN, MEX, NLD, ITA.")
            rows = data_for_year(year)
            peers = match_candidates(rows, anchor, mode, factor)
            ref = reference()
        except (ValueError, FileNotFoundError, OSError) as exc:
            message = f"Data unavailable: {exc}"
            return (theme.empty_figure(message), [{"label": name, "value": code} for code, name in zip(FOCUS_COUNTRIES, FOCUS_NAMES)], [], None, True, message,
                    "No matching comparison available.", [], "No finding without valid source data.", [], message, None, True)
        valid = rows[rows.valid]
        pool = peers.country.tolist()
        if ctx.triggered_id == cid("graph") and click:
            points = click.get("points") or []
            custom = points[0].get("customdata") if points else None
            if custom and custom[0] in pool:
                comparator = custom[0]
        switched = comparator not in pool
        if switched:
            comparator = pool[0] if pool else None
        names = country_names(ref)
        valid_codes = set(valid.country)
        options = [{"label": name + (" (no valid pair this year)" if code not in valid_codes else ""), "value": code}
                   for code, name in zip(FOCUS_COUNTRIES, FOCUS_NAMES)]
        peer_options = [{"label": f"{names[c]} · {c}", "value": c} for c in pool]
        scope = (f"{year} · {len(valid)} countries/economies plotted from {len(rows)} source entities; "
                 f"{len(rows) - len(valid)} excluded. Goods exports to all partners, all products. "
                 "GDP and trade must both be finite and positive.")
        a = valid[valid.country.eq(anchor)]
        cards = []
        if a.empty:
            reason = rows.loc[rows.country.eq(anchor), "exclusion"]
            status = f"{names.get(anchor, anchor)}: {reason.iloc[0] if len(reason) else 'No source records this year'}. No comparison calculated."
            finding = f"No finding for {year}: the anchor has no comparable GDP/export pair."
        else:
            a = a.iloc[0]
            cards = [economy_card(a, f"Anchor · {year}")]
            status = (f"{len(pool)} other economies match {MODES[mode]} within "
                      f"[{1 / factor:.3f}, {factor:g}] × {names.get(anchor, anchor)}. "
                      "The other dimension is not filtered.")
            if comparator:
                b = valid.loc[valid.country.eq(comparator)].iloc[0]
                cards.append(economy_card(b, f"Comparison · {year}"))
                finding = finding_text(a, b, mode, year)
                if switched:
                    status += " The previous comparison is outside this pool; the closest current match is shown."
            else:
                status += " No matching economy; the window has not been widened."
                cards.append(html.Div("No matching economy. Select a different anchor or explicitly choose the 1.5× window.", className="m2-empty"))
                finding = f"No two-country finding for {year}: the anchor is the only economy in this window."
        table = [{"economy": f"{r.name} · {r.country}", "gdp": f"{r.gdp_billion_usd:,.3f}", "exports": f"{r.exports_billion_usd:,.3f}", "ratio": f"{r.export_gdp_ratio:.2%}", "matching_ratio": f"{r.matching_ratio:.4f}×"} for r in peers.itertuples()]
        excluded = rows[~rows.valid]
        summary = "; ".join(f"{reason}: {count}" for reason, count in excluded.exclusion.value_counts().items()) or "None"
        exclusions = [html.P(f"Exclusions ({len(excluded)}): {summary}. Reasons and values are included in the CSV."),
                      html.Ul([html.Li(f"{r.name} ({r.country}): {r.exclusion}") for r in excluded.itertuples()])]
        context = {"year": year, "anchor": anchor, "comparator": comparator, "mode": mode, "factor": factor}
        figure = scatter_figure(rows, anchor, comparator, mode, factor)
        # Dash may recreate the graph on callback updates. Carry the current
        # viewport explicitly when only comparison/highlight/navigation changes.
        if previous and all(previous.get(k) == context[k] for k in ("year", "anchor", "mode", "factor")):
            retained = dict(previous.get("viewport", {}))
            for axis in ("xaxis", "yaxis"):
                view = viewport or {}
                bounds = view.get(f"{axis}.range")
                if bounds is None and all(f"{axis}.range[{i}]" in view for i in (0, 1)):
                    bounds = [view[f"{axis}.range[{i}]"] for i in (0, 1)]
                if view.get(f"{axis}.autorange") is True:
                    retained.pop(axis, None)
                    continue
                if bounds is None:
                    bounds = retained.get(axis)
                if bounds is not None:
                    figure.update_layout(**{axis: {"range": bounds, "autorange": False}})
                    retained[axis] = bounds
            context["viewport"] = retained
        return (figure, options,
                peer_options, comparator, not bool(pool), scope, status, cards, finding,
                table, exclusions, context, False)

    @app.callback(Output(cid("download"), "data"), Input(cid("export"), "n_clicks"),
                  State(cid("context"), "data"), State(ACTIVE_MODULE, "data"),
                  prevent_initial_call=True)
    def _download(clicks, context, active):
        guard_active(MODULE_ID, active)
        if not clicks or not context or context.get("anchor") not in FOCUS_COUNTRIES:
            raise PreventUpdate
        rows = data_for_year(context["year"])
        frame = evidence_frame(rows, context["anchor"], context["comparator"], context["mode"], context["factor"])
        return dcc.send_data_frame(frame.to_csv, f"M2_{context['year']}_{context['anchor']}_{context['mode']}.csv", index=False)
