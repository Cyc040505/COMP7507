"""M1: global economic scale, single-dimension matching and two-country evidence."""

from functools import lru_cache
from math import log10

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dcc, html, dash_table, ClientsideFunction
from dash.exceptions import PreventUpdate

from src import components, config, data_loader, theme
from src.analytics.economy import (
    FOCUS_COUNTRIES, MODES, country_names, prepare_year,
    match_candidates, evidence_frame, display_candidates,
)
from src.ids import ACTIVE_MODULE, mid
from src.module_base import guard_active

MODULE_ID = "M1"
NAV_LABEL = "M1  Economy"
ORDER = 1
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
    path = config.DATA_DIR / "reference/m1_country_codes_V202601.csv"
    if not path.exists():
        raise FileNotFoundError("Missing M1 BACI country dictionary. Restore data/reference/m1_country_codes_V202601.csv.")
    return pd.read_csv(path)


def data_for_year(year):
    return prepare_year(data_loader.load_country_year(), data_loader.load_gdp_year(), reference(), year)


def field(label, widget):
    return html.Div([html.Label(label, htmlFor=widget.id), widget], className="m1-field")


def anchor_options(valid_codes=FOCUS_COUNTRIES):
    return [
        {
            "label": f"{name} ({code})" + (" · Data unavailable" if code not in valid_codes else ""),
            "value": code,
        }
        for code, name in zip(FOCUS_COUNTRIES, FOCUS_NAMES)
    ]


def layout():
    return html.Div(className="module-inner m1", children=[
        dcc.Store(id=cid("context")), dcc.Download(id=cid("download")),
        dcc.Store(id=cid("reference-lines-ready")),
        components.module_intro(
            "Similar GDP. Similar exports?",
            "Similar economic size does not necessarily mean similar goods exports.",
        ),
        html.Div([
            html.Div([
                components.field(
                    "Analysis year",
                    dcc.Dropdown(
                        id=cid("year"), options=list(range(1995, 2024)),
                        value=2023, clearable=False, className="ctl-dropdown",
                    ),
                ),
                components.field("Starting economy", dcc.Dropdown(
                    id=cid("anchor"), options=anchor_options(), value="DEU",
                    clearable=False, className="ctl-dropdown",
                )),
                components.field("Similarity range", dcc.Dropdown(
                    id=cid("factor"),
                    options=[{"label": "1.25×", "value": 1.25}, {"label": "1.5×", "value": 1.5}],
                    value=1.25, clearable=False, className="ctl-dropdown",
                )),
                components.field("Match by", dcc.RadioItems(
                    id=cid("mode"),
                    options=[{"label": "Similar GDP", "value": "gdp"}, {"label": "Similar exports", "value": "export_value"}],
                    value="gdp", className="radio-row",
                )),
            ], className="toolbar-row"),
        ], className="module-toolbar"),
        html.Div([
            components.card("GDP and goods exports", html.Div([
                html.Div(id=cid("scope"), className="m1-note", role="status"),
                dcc.Graph(id=cid("graph"), figure=theme.empty_figure("Select M1 to begin."),
                          className="graph-interactive",
                          config={"displayModeBar": False, "displaylogo": False,
                                  "responsive": True, "scrollZoom": True, "doubleClick": "reset",
                                  "showAxisDragHandles": False, "showAxisRangeEntryBoxes": False},
                          style={"height": "510px", "minHeight": "510px"}),
                html.P("Drag to pan · Scroll to zoom · Double-click to reset", className="m1-note"),
                html.Details([
                    html.Summary("How to read this chart"),
                    html.P("Both axes use logarithmic scales: equal distances represent equal ratios. Darker blue lines indicate higher exports/GDP (10%, 50%, 100%). The shaded band shows the selected similarity range. Drag to move around; click a highlighted dot to compare.", className="m1-note"),
                ], className="m1-chart-help"),
            ])),
            components.card("Compare two economies", html.Div([
                field("Choose an economy to compare", dcc.Dropdown(id=cid("comparator"), options=[{"label": "Japan · JPN", "value": "JPN"}], value="JPN", clearable=False)),
                html.Div(id=cid("relative")),
                html.Section([
                    html.H4("Exact values"),
                    html.Div(id=cid("cards"), className="m1-comparison"),
                ], id=cid("amounts"), className="m1-amounts"),
            ])),
        ], className="m1-analysis"),
        components.findings_card(
            finding=html.P(id=cid("finding")),
            implication=html.P(id=cid("implication")),
            limits=html.P("The comparison uses one year of GDP and goods exports in current USD. Exports can reflect prices and exchange rates."),
        ),
        components.module_data_details([
            html.P("Closest matches for the selected measure and range appear first. The CSV covers the selected year and includes exclusions."),
            components.module_data_table_header(
                "Matching economies",
                download_id=cid("export"),
                download_label="Download economy comparison data (CSV)",
                disabled=True,
            ),
            dash_table.DataTable(id=cid("table"), columns=[
                {"name": "Economy", "id": "economy"},
                {"name": "GDP · $bn", "id": "gdp"},
                {"name": "Goods exports · $bn", "id": "exports"},
                {"name": "Exports / GDP", "id": "ratio"},
                {"name": "Selected measure / starting economy", "id": "matching_ratio"},
            ], data=[], page_size=10, style_table={"overflowX": "auto"}, style_cell={"textAlign": "left", "fontFamily": "inherit", "fontSize": 12, "padding": "9px"}, style_header={"fontWeight": 600, "backgroundColor": theme.ACCENT_SOFT}),
            components.module_data_methods([
                html.P(LIMITATION),
                html.P("Sources are BACI HS92 V202601 and CHELEM GDP-VAL V202502. Charts and cards show billion current USD. The CSV labels each amount’s original unit."),
                html.P("Matching requires positive GDP and exports with comparable geographic coverage. Territory changes exclude Belgium–Luxembourg through 1998 and Sudan through 2011. Regional or unspecified groups such as Other Asia nes, Europe EFTA nes and SACU are also excluded."),
                html.Div(id=cid("exclusions"), className="m1-note"),
            ]),
        ], id=cid("data-details")),
    ])


def scatter_figure(rows, anchor, comparator, mode, factor):
    valid = display_candidates(rows)
    if valid.empty:
        return theme.empty_figure("No finite positive GDP/export pairs for this year.")
    peers = match_candidates(rows, anchor, mode, factor)
    matched = set(peers.country)
    fig = go.Figure()
    # Reference endpoints must not set the axis range, but the rightmost
    # comparison's marker and country label still need room inside the clip box.
    # Reserve 0.9 decades when the comparison is the rightmost economy;
    # otherwise retain the usual spacing between the background points.
    rightmost = valid.loc[valid.gdp_billion_usd.idxmax(), "country"]
    right_padding = 8 if comparator == rightmost else 1.5
    xmin, xmax = valid.gdp_billion_usd.min() / 1.5, valid.gdp_billion_usd.max() * right_padding
    ymin, ymax = valid.exports_billion_usd.min() / 1.5, valid.exports_billion_usd.max() * 1.5
    span = max(log10(xmax / xmin), log10(ymax / ymin))
    for ratio, color in [(0.1, "#9dbad5"), (0.5, "#547fa8"), (1, "#254d73")]:
        # Native data traces share the scatter layer's live gesture transform.
        # Spare coverage avoids recomputing geometry on every pointer movement.
        lo = 10 ** (min(log10(xmin), log10(ymin / ratio)) - 2 * span)
        hi = 10 ** (max(log10(xmax), log10(ymax / ratio)) + 2 * span)
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[lo * ratio, hi * ratio], mode="lines",
            name=f"Exports/GDP = {ratio:.0%}", line={"color": color, "width": 1.8},
            hoverinfo="skip", legendgroup=f"ratio-{ratio}", meta={"m1_ratio": ratio},
        ))
    a = valid[valid.country.eq(anchor)]
    if not a.empty:
        value = a.iloc[0]["gdp_billion_usd" if mode == "gdp" else "exports_billion_usd"]
        band = {"fillcolor": theme.ACCENT, "opacity": .16, "line_width": 0, "layer": "below"}
        if mode == "gdp":
            fig.add_vrect(x0=value / factor, x1=value * factor, **band)
        else:
            fig.add_hrect(y0=value / factor, y1=value * factor, **band)
    roles = [
        ("Other economies", valid[~valid.country.isin(matched | {anchor, comparator})], 10, "circle", False),
        ("Matches", valid[valid.country.isin(matched - {comparator})], 14, "circle", False),
        ("Anchor", a, 18, "diamond", True),
        ("Comparison", valid[valid.country.eq(comparator)], 18, "square", True),
    ]
    for role, data, size, symbol, labels in roles:
        if data.empty:
            continue
        custom = [[r.country, r.name, r.export_gdp_ratio] for r in data.itertuples()]
        fig.add_trace(go.Scatter(
            x=data.gdp_billion_usd.tolist(), y=data.exports_billion_usd.tolist(),
            customdata=custom, text=[dict(zip(FOCUS_COUNTRIES, FOCUS_NAMES)).get(r.country, r.name) for r in data.itertuples()] if labels else data.country.tolist(), name=role,
            mode="markers+text" if labels else "markers",
            textposition="top left" if role == "Anchor" else "bottom right",
            textfont={"size": 12, "color": theme.INK},
            marker={"size": size, "symbol": symbol,
                    "color": "#b8c2ce" if role == "Other economies" else [theme.country_color(c) for c in data.country],
                    "opacity": .65 if role == "Other economies" else 1,
                    "line": {"color": theme.ACCENT if role == "Matches" else "white", "width": 2 if role == "Matches" else 1}},
            hovertemplate="<b>%{customdata[1]} (%{customdata[0]})</b><br>GDP: $%{x:,.3f}bn<br>Goods exports: $%{y:,.3f}bn<br>Exports / GDP: %{customdata[2]:.2%}<extra>" + role + "</extra>",
        ))
    fig.update_layout(
        template=theme.PLOT_TEMPLATE, height=510, margin={"l": 65, "r": 25, "t": 35, "b": 105},
        dragmode="pan",
        xaxis={"type": "log", "dtick": 1, "title": "GDP · billion current USD (log)", "autorange": True,
               "autorangeoptions": {"clipmin": xmin, "clipmax": xmax}},
        yaxis={"type": "log", "dtick": 1, "title": "Goods exports · billion current USD (log)", "autorange": True,
               "autorangeoptions": {"clipmin": ymin, "clipmax": ymax}},
        legend={"orientation": "h", "y": -0.22, "x": 0, "font": {"size": 11}},
        uirevision=f"M1-{int(rows.year.iloc[0])}-{anchor}-{mode}-{factor}",
    )
    return fig


def economy_card(row, role):
    return html.Div([
        html.Div(role, className="m1-eyebrow"), html.H3(f"{row['name']} · {row['country']}"),
        html.Dl([
            html.Div([html.Dt("GDP"), html.Dd(f"${row['gdp_billion_usd']:,.3f}bn")]),
            html.Div([html.Dt("Goods exports"), html.Dd(f"${row['exports_billion_usd']:,.3f}bn")]),
            html.Div([html.Dt("Exports / GDP"), html.Dd(f"{row['export_gdp_ratio']:.2%}")]),
        ]),
    ], className="m1-economy", style={"borderTopColor": theme.country_color(row["country"])})


def finding_text(a, b, mode, year):
    other = "export_value" if mode == "gdp" else "gdp"
    return (
        f"In {year}, {b['name']}'s {MODES[mode]} measured {b[mode] / a[mode]:.2f}× "
        f"{a['name']}'s, while its {MODES[other]} measured {b[other] / a[other]:.2f}×. "
    )


def relative_comparison(a, b, year):
    """Two comparable, dimensionless indices; percentage points stay separate."""
    indices = [100 * b[key] / a[key] for key in ("gdp", "export_value")]
    labels = ["GDP", "Goods exports"]
    color = theme.country_color(b["country"])
    fig = go.Figure(go.Bar(
        x=indices, y=labels, orientation="h", width=.42,
        marker={"color": color}, text=[f"{v:,.1f}" for v in indices],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:,.2f}<br>Starting economy = 100<extra>" + b["country"] + "</extra>",
    ))
    fig.add_vline(x=100, line_width=1.5, line_dash="dash", line_color=theme.INK)
    fig.update_layout(
        template=theme.PLOT_TEMPLATE, height=230, showlegend=False,
        margin={"l": 90, "r": 42, "t": 12, "b": 48},
        xaxis={"title": "Relative size · starting economy = 100", "range": [0, max(100, *indices) * 1.25],
               "fixedrange": True, "zeroline": False},
        yaxis={"autorange": "reversed", "fixedrange": True},
        font={"color": theme.INK}, bargap=.4,
    )
    differences = []
    for label, value in zip(labels, indices):
        delta = value - 100
        text = ("Same at displayed precision" if round(abs(delta), 1) == 0 else
                f"{abs(delta):,.1f}% {'higher' if delta > 0 else 'lower'}")
        differences.append(html.Div([html.Span(label), html.Strong(text)]))
    return html.Div([
        html.H4(f"Relative size · {year}"),
        html.P(f"{a['name']} = 100", className="m1-note"),
        dcc.Graph(id=cid("relative-graph"), figure=fig,
                  config={"displayModeBar": False, "responsive": True}, style={"height": "230px"}),
        html.Div(differences, className="m1-differences"),
    ], className="m1-relative")


def register_callbacks(app):
    app.clientside_callback(
        ClientsideFunction(namespace="m1", function_name="extendReferenceLines"),
        Output(cid("reference-lines-ready"), "data"),
        Input(cid("graph"), "figure"), Input(ACTIVE_MODULE, "data"),
    )
    @app.callback(
        Output(cid("graph"), "figure"), Output(cid("anchor"), "options"),
        Output(cid("comparator"), "options"), Output(cid("comparator"), "value"),
        Output(cid("comparator"), "disabled"), Output(cid("scope"), "children"),
        Output(cid("cards"), "children"),
        Output(cid("finding"), "children"), Output(cid("implication"), "children"),
        Output(cid("table"), "data"),
        Output(cid("exclusions"), "children"), Output(cid("context"), "data"),
        Output(cid("export"), "disabled"),
        Output(cid("relative"), "children"),
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
            return (theme.empty_figure(message), anchor_options(), [], None, True, message,
                    [], "No finding without valid source data.", "Check the selected year and data coverage.",
                    [], message, None, True, [])
        valid = rows[rows.valid]
        pool = peers.country.tolist()
        if ctx.triggered_id == cid("graph") and click:
            points = click.get("points") or []
            custom = points[0].get("customdata") if points else None
            if custom and custom[0] in pool:
                comparator = custom[0]
        if comparator not in pool:
            comparator = pool[0] if pool else None
        names = country_names(ref)
        valid_codes = set(valid.country)
        options = anchor_options(valid_codes)
        peer_options = [{"label": f"{names[c]} · {c}", "value": c} for c in pool]
        shown = display_candidates(rows)
        scope = f"{len(shown)} economies shown · billion current USD"
        a = valid[valid.country.eq(anchor)]
        cards = []
        relative = []
        implication = "Choose another starting economy or matching measure."
        if a.empty:
            reason = rows.loc[rows.country.eq(anchor), "exclusion"]
            finding = f"{names.get(anchor, anchor)} · {year}: {reason.iloc[0] if len(reason) else 'Data unavailable this year'}."
            implication = "Choose a selection with comparable GDP and goods exports."
        else:
            a = a.iloc[0]
            cards = [economy_card(a, f"Starting economy · {year}")]
            if comparator:
                b = valid.loc[valid.country.eq(comparator)].iloc[0]
                cards.append(economy_card(b, f"Comparison · {year}"))
                relative = relative_comparison(a, b, year)
                finding = finding_text(a, b, mode, year)
                other = "export_value" if mode == "gdp" else "gdp"
                other_matches = match_candidates(rows, anchor, other, factor)
                range_name = f"{factor:g}× similarity range for {MODES[other]}"
                if comparator in other_matches.country.values:
                    implication = f"The pair also falls within the {range_name}."
                else:
                    implication = f"The pair falls outside the same {range_name}."
            else:
                cards.append(html.Div("No matching economy in this range.", className="m1-empty"))
                finding = f"No two-country finding for {year}: the anchor is the only economy in this window."
        table = [{"economy": f"{r.name} · {r.country}", "gdp": f"{r.gdp_billion_usd:,.3f}", "exports": f"{r.exports_billion_usd:,.3f}", "ratio": f"{r.export_gdp_ratio:.2%}", "matching_ratio": f"{r.matching_ratio:.4f}×"} for r in peers.itertuples()]
        excluded = rows[~rows.valid]
        summary = "; ".join(f"{reason}: {count}" for reason, count in excluded.exclusion.value_counts().items()) or "None"
        exclusions = [html.P(f"Scatter coverage: {len(shown)} of {len(valid)} valid economies. "
                               "Shown economies are the six starting economies and their matches within 1.5× "
                               "on either GDP or exports for this year. Matching uses only your selected measure; "
                               "valid economies outside the display range remain in the CSV."),
                      html.P(f"Exclusions ({len(excluded)}): {summary}. Reasons and values are included in the CSV."),
                      html.Ul([html.Li(f"{r.name} ({r.country}): {r.exclusion}") for r in excluded.itertuples()])]
        context = {"year": year, "anchor": anchor, "comparator": comparator, "mode": mode, "factor": factor, "anchor_valid": not a.empty}
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
                peer_options, comparator, not bool(pool), scope, cards, finding,
                implication, table, exclusions, context, False, relative)

    @app.callback(Output(cid("download"), "data"), Input(cid("export"), "n_clicks"),
                  State(cid("context"), "data"), State(ACTIVE_MODULE, "data"),
                  prevent_initial_call=True)
    def _download(clicks, context, active):
        guard_active(MODULE_ID, active)
        if not clicks or not context or context.get("anchor") not in FOCUS_COUNTRIES:
            raise PreventUpdate
        rows = data_for_year(context["year"])
        frame = evidence_frame(rows, context["anchor"], context["comparator"], context["mode"], context["factor"])
        return dcc.send_data_frame(frame.to_csv, f"M1_{context['year']}_{context['anchor']}_{context['mode']}.csv", index=False)
