"""M2: global economic scale, single-dimension matching and two-country evidence."""

from functools import lru_cache
from math import log10

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
                field("Find similar economies by", dcc.RadioItems(id=cid("mode"), options=[{"label": "Similar GDP", "value": "gdp"}, {"label": "Similar exports", "value": "export_value"}], value="gdp", className="m2-radio")),
                field("Similarity range", dcc.RadioItems(id=cid("factor"), options=[{"label": "1.25×", "value": 1.25}, {"label": "1.5×", "value": 1.5}], value=1.25, className="m2-radio")),
            ], className="m2-controls"),
            field("Choose your starting economy", dcc.RadioItems(
                id=cid("anchor"),
                options=[{"label": name, "value": code} for code, name in zip(FOCUS_COUNTRIES, FOCUS_NAMES)],
                value="DEU", className="m2-anchors")),
            html.P("Compare your chosen economy with similar economies around the world. Select 1.5× to explore a wider range.", className="m2-note"),
        ])),
        html.Div(id=cid("takeaway"), className="m2-takeaway", role="status"),
        html.Div([
            components.card("GDP and goods exports around the world", html.Div([
                html.Div(id=cid("scope"), className="m2-note", role="status"),
                dcc.Graph(id=cid("graph"), figure=theme.empty_figure("Select M2 to begin."),
                          className="graph-interactive",
                          config={"displayModeBar": True, "displaylogo": False,
                                  "responsive": True, "scrollZoom": True, "doubleClick": "reset",
                                  "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
                          style={"height": "510px", "minHeight": "510px"}),
                html.P("Each dot is an economy. Both axes use logarithmic scales: equal distances represent equal ratios. Darker blue lines indicate higher exports/GDP (10%, 50%, 100%). The shaded band shows your similarity range; click a highlighted dot to compare.", className="m2-note"),
                html.Details([html.Summary("How to explore this chart"), html.P("Scroll to zoom or drag a box to enlarge an area. Choose Pan to move around; double-click or choose Reset axes to return to the full view.", className="m2-note")]),
            ])),
            components.card("Compare two economies", html.Div([
                field("Choose an economy to compare", dcc.Dropdown(id=cid("comparator"), options=[{"label": "Japan · JPN", "value": "JPN"}], value="JPN", clearable=False)),
                html.P(id=cid("match-status"), role="status", className="m2-note"),
                html.Div(id=cid("relative")),
                html.Details([html.Summary("Exact amounts for both economies"),
                              html.Div(id=cid("cards"), className="m2-comparison")]),
                html.Div(id=cid("finding"), className="m2-finding"),
                html.P(LIMITATION, className="m2-note"),
            ])),
        ], className="m2-analysis"),
        html.Details([
            html.Summary("All matches, data coverage and sources"),
            html.P("Browse all economies in your similarity range, with the closest matches first. Similarity is based on the measure you selected above.", className="m2-note"),
            dash_table.DataTable(id=cid("table"), columns=[
                {"name": "Economy", "id": "economy"},
                {"name": "GDP · $bn", "id": "gdp"},
                {"name": "Goods exports · $bn", "id": "exports"},
                {"name": "Exports / GDP", "id": "ratio"},
                {"name": "Selected measure / starting economy", "id": "matching_ratio"},
            ], data=[], page_size=10, style_table={"overflowX": "auto"}, style_cell={"textAlign": "left", "fontFamily": "inherit", "fontSize": 12, "padding": "9px"}, style_header={"fontWeight": 600, "backgroundColor": theme.ACCENT_SOFT}),
            html.Div(id=cid("exclusions"), className="m2-note"),
            html.Button("Download comparison data (CSV)", id=cid("export"), n_clicks=0, className="m2-download", disabled=True),
            html.P("Download the selected year’s amounts, matching economies and reasons for missing comparisons. Sources: BACI HS92 V202601 and CHELEM GDP-VAL V202502. Charts and cards show billion current USD; the CSV labels the original units for each amount.", className="m2-note"),
            html.P("Some economies cannot be compared because GDP or exports are missing or non-positive, or their geographic coverage differs between sources. Missing values are not treated as zero.", className="m2-note"),
            html.P("Historical coverage: Belgium–Luxembourg through 1998 and Sudan through 2011 are excluded because the trade and GDP territories are not directly comparable. Regional or unspecified groups (Other Asia nes, Europe EFTA nes and SACU) are also excluded.", className="m2-note"),
        ], className="card m2-details"),
    ])


def scatter_figure(rows, anchor, comparator, mode, factor):
    valid = rows[rows.valid]
    if valid.empty:
        return theme.empty_figure("No finite positive GDP/export pairs for this year.")
    peers = match_candidates(rows, anchor, mode, factor)
    matched = set(peers.country)
    fig = go.Figure()
    # Reference endpoints must not set the axis range, but the rightmost
    # comparison's marker and ISO3 label still need room inside the clip box.
    # Reserve 0.6 decades when the comparison is the rightmost economy;
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
            hoverinfo="skip", legendgroup=f"ratio-{ratio}", meta={"m2_ratio": ratio},
        ))
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
            customdata=custom, text=[dict(zip(FOCUS_COUNTRIES, FOCUS_NAMES)).get(r.country,r.name) for r in data.itertuples()] if labels else data.country.tolist(), name=role,
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
        xaxis={"type": "log", "dtick": 1, "title": "GDP · billion current USD (log)", "autorange": True,
               "autorangeoptions": {"clipmin": xmin, "clipmax": xmax}},
        yaxis={"type": "log", "dtick": 1, "title": "Goods exports · billion current USD (log)", "autorange": True,
               "autorangeoptions": {"clipmin": ymin, "clipmax": ymax}},
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
        "The relative-size bars show the gap in each measure. These figures describe the comparison, not what caused it."
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
    pp = 100 * (b["export_gdp_ratio"] - a["export_gdp_ratio"])
    gap = ("equal at displayed precision" if round(abs(pp), 2) == 0 else
           f"{abs(pp):,.2f} percentage points {'higher' if pp > 0 else 'lower'}")
    return html.Div([
        html.H4(f"Relative size · {year}"),
        html.P(f"{b['name']} compared with {a['name']}. The dashed line marks {a['name']} = 100 for each measure.", className="m2-note"),
        dcc.Graph(id=cid("relative-graph"), figure=fig,
                  config={"displayModeBar": False, "responsive": True}, style={"height": "230px"}),
        html.Div(differences, className="m2-differences"),
        html.P(f"Exports / GDP: {b['name']} {b['export_gdp_ratio']:.2%} versus "
               f"{a['name']} {a['export_gdp_ratio']:.2%} — {gap}.", className="m2-ratio-gap"),
    ], className="m2-relative")


def register_callbacks(app):
    @app.callback(Output(cid("takeaway"), "children"), Input(cid("context"), "data"), Input(ACTIVE_MODULE, "data"))
    def takeaway(context, active):
        guard_active(MODULE_ID, active)
        if not context or not context.get("comparator"):
            return html.H3("Choose two economies with comparable data")
        try:
            d = data_for_year(context["year"]).set_index("country")
            a, b = d.loc[context["anchor"]], d.loc[context["comparator"]]
            full_names = dict(zip(FOCUS_COUNTRIES, FOCUS_NAMES))
            aname = full_names.get(context["anchor"], a['name'])
            bname = full_names.get(context["comparator"], b['name'])
            return html.Div([
                html.H3(f"{bname} has {100*b.gdp/a.gdp:.1f}% of {aname}’s GDP, but {100*b.export_value/a.export_value:.1f}% of its goods exports"),
                html.P(f"{context['year']} · Matched by {MODES[context['mode']]}. Each percentage compares the same measure between the two economies; it is not exports divided by GDP.")])
        except (KeyError, ValueError, FileNotFoundError):
            return html.H3("No comparable pair in this selection")


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
            return (theme.empty_figure(message), [{"label": name, "value": code} for code, name in zip(FOCUS_COUNTRIES, FOCUS_NAMES)], [], None, True, message,
                    "No matching comparison available.", [], "No finding without valid source data.", [], message, None, True, [])
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
        options = [{"label": name + (" (data unavailable this year)" if code not in valid_codes else ""), "value": code}
                   for code, name in zip(FOCUS_COUNTRIES, FOCUS_NAMES)]
        peer_options = [{"label": f"{names[c]} · {c}", "value": c} for c in pool]
        scope = (f"{year} · {len(valid)} economies shown · {len(rows) - len(valid)} records excluded. "
                 "All goods, all trading partners · billion current USD. "
                 "See data coverage below for excluded records.")
        a = valid[valid.country.eq(anchor)]
        cards = []
        relative = []
        if a.empty:
            reason = rows.loc[rows.country.eq(anchor), "exclusion"]
            status = f"{names.get(anchor, anchor)}: {reason.iloc[0] if len(reason) else 'Data unavailable this year'}. Choose another economy or year to compare."
            finding = f"No finding for {year}: the anchor has no comparable GDP/export pair."
        else:
            a = a.iloc[0]
            cards = [economy_card(a, f"Starting economy · {year}")]
            status = (f"{len(pool)} other economies match {MODES[mode]} within "
                      f"[{1 / factor:.3f}, {factor:g}] × {names.get(anchor, anchor)}. "
                      "Choose a comparison below, or click a highlighted dot.")
            if comparator:
                b = valid.loc[valid.country.eq(comparator)].iloc[0]
                cards.append(economy_card(b, f"Comparison · {year}"))
                relative = relative_comparison(a, b, year)
                finding = finding_text(a, b, mode, year)
                if switched:
                    status += " Your previous comparison is outside this range; the closest current match is shown."
            else:
                status += " No matching economy; the window has not been widened."
                cards.append(html.Div("No matching economy. Try a different starting economy or widen the range to 1.5×.", className="m2-empty"))
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
                table, exclusions, context, False, relative)

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
