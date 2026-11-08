"""M5: continuous nominal export recovery and structural indicators."""

import hashlib
import json
import math
from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dash_table, dcc, html, no_update

from src import components, config, data_loader, theme
from src.analytics.product import chapters, label
from src.analytics.time_change import build_timeline, summarize_recovery
from src.ids import ACTIVE_MODULE, mid
from src.m5_portraits import FOCUS_COUNTRIES, finite, portrait_cards
from src.module_base import guard_active

MODULE_ID = "M5"
NAV_LABEL = "M5  Time Change"
ORDER = 5
YEARS = list(range(1995, 2025))
CASE_COUNTRIES = ["CHN", "DEU", "MEX"]
CASES = {
    "pandemic": (
        "TOTAL",
        2019,
        2020,
        (2016, 2024),
        "intra",
        "When did exports regain their 2019 value?",
        "Compare each line with 100, then check where its exports went.",
    ),
    "vehicles": (
        "87",
        2019,
        2020,
        (2016, 2024),
        "product",
        "Did vehicles and parts recover at the same pace as all goods?",
        "Read the first return year, then compare HS87’s weight in each export basket.",
    ),
    "crisis": (
        "TOTAL",
        2007,
        2008,
        (2004, 2013),
        "intra",
        "Where did trade go after the financial crisis?",
        "Compare 2007 with 2013. Use the regional bounds to judge which shifts have a clear direction.",
    ),
}
STATUS = {
    "invalid_baseline": "Baseline missing or zero",
    "no_observations": "No post-event observations",
    "not_recovered": "Loss observed; no subsequent return to baseline",
    "unobserved_incomplete": "No recovery observed; incomplete coverage",
    "endpoint_missing": "Endpoint missing; inspect observed history",
    "relapsed": "Reached baseline, then fell below again",
    "never_below": "No observed below-baseline loss",
    "recovered": "At/above baseline at window end",
}


def cid(name):
    return mid(MODULE_ID, name)


@lru_cache(maxsize=1)
def inputs():
    p = data_loader.load_exporter_hs2_year()
    if p.attrs.get("demo", True):
        raise ValueError(
            "Real product data is required; synthetic data is disabled in M5."
        )
    path = config.processed_path("m5_region_hs2_year.parquet")
    manifest_path = config.processed_path("m5_source_manifest.json")
    if not path.exists() or not manifest_path.exists():
        raise ValueError(
            "M5 regional data is missing. Run scripts/build_m5_data.py before analysis."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    for name in ("exporter_hs2_year.parquet", "country_meta.parquet"):
        digest = hashlib.sha256(config.processed_path(name).read_bytes()).hexdigest()
        if digest != manifest["project_inputs_sha256"][name]:
            raise ValueError(
                f"{name} changed since the regional audit. Reconcile M5 inputs again."
            )
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["output_sha256"]:
        raise ValueError(
            "M5 regional file changed; rebuild and reconcile it before analysis."
        )
    return p, pd.read_parquet(path), manifest


def country_names():
    m = data_loader.load_country_meta()
    return dict(zip(m.iso3, m.name))


def field(title, control):
    return html.Label([html.Span(title), control], className="m5-field")


def layout():
    ns = country_names()
    return html.Div(
        className="module-inner m5 m5-fieldnotes",
        children=[
            dcc.Store(id=cid("selected"), data=2024),
            dcc.Store(id=cid("rows")),
            dcc.Store(id=cid("import-reset")),
            dcc.Download(id=cid("download")),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("TIME / M5", className="m5-eyebrow"),
                            html.H2("Recovery & structural change"),
                            html.P(
                                "Compare the full recovery path, then check product and regional partner shares."
                            ),
                        ],
                        className="m5-heading",
                    ),
                    html.Div(id=cid("guide"), className="m5-guide"),
                ],
                className="m5-intro-row",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Button(text, id=cid(key), n_clicks=0)
                            for key, text in [
                                ("pandemic", "01 · Pandemic recovery"),
                                ("vehicles", "02 · Vehicles & parts"),
                                ("crisis", "03 · Financial crisis"),
                                ("import", "Use current M4 selection"),
                            ]
                        ],
                        className="m5-presets",
                        id=cid("presets"),
                    ),
                    html.Details(
                        [
                            html.Summary("Customize this comparison"),
                            html.Div(
                                [
                                    field(
                                        "Six focus economies · choose 1–4",
                                        dcc.Dropdown(
                                            id=cid("countries"),
                                            options=[
                                                {"label": f"{ns[c]} ({c})", "value": c}
                                                for c in FOCUS_COUNTRIES
                                            ],
                                            value=["CHN", "DEU", "MEX"],
                                            multi=True,
                                        ),
                                    ),
                                    field(
                                        "Export scope · HS2 chapter",
                                        dcc.Dropdown(
                                            id=cid("product"),
                                            options=[
                                                {
                                                    "label": "All products",
                                                    "value": "TOTAL",
                                                }
                                            ]
                                            + [
                                                {"label": label(p), "value": p}
                                                for p in chapters()
                                            ],
                                            value="TOTAL",
                                            clearable=False,
                                        ),
                                    ),
                                    field(
                                        "Baseline · index = 100",
                                        dcc.Dropdown(
                                            id=cid("baseline"),
                                            options=YEARS,
                                            value=2019,
                                            clearable=False,
                                        ),
                                    ),
                                    field(
                                        "Event marker · annual data",
                                        dcc.Dropdown(
                                            id=cid("event"),
                                            options=YEARS,
                                            value=2020,
                                            clearable=False,
                                        ),
                                    ),
                                ],
                                className="m5-controls",
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Observation window · summaries stop at the right endpoint"
                                    ),
                                    dcc.RangeSlider(
                                        id=cid("window"),
                                        min=1995,
                                        max=2024,
                                        value=[2016, 2024],
                                        step=1,
                                        marks={
                                            1995: "1995",
                                            2000: "2000",
                                            2005: "2005",
                                            2010: "2010",
                                            2015: "2015",
                                            2020: "2020",
                                            2024: "2024",
                                        },
                                        allowCross=False,
                                        tooltip={"placement": "bottom"},
                                    ),
                                ],
                                className="m5-window",
                            ),
                        ],
                        className="m5-methods m5-custom",
                    ),
                ],
                className="m5-toolbar",
            ),
            html.Div(id=cid("import-note"), className="m5-hint"),
            html.Div(id=cid("context"), className="m5-context"),
            html.Div(
                [
                    html.H3("01 / Compare the recovery"),
                    html.Span("Common scales · click any annual point to inspect"),
                ],
                className="m5-section-heading",
            ),
            html.Div(
                id=cid("portraits"),
                className="m5-country-grid",
                children=portrait_cards(
                    [],
                    [],
                    [],
                    2019,
                    2020,
                    [2016, 2024],
                    "intra",
                    "TOTAL",
                    2024,
                    message="Loading the selected comparison…",
                ),
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.H3("Read the comparison"),
                            html.P("Findings describe the full displayed window."),
                        ],
                        className="m5-reading-heading",
                    ),
                    html.Div(
                        [
                            html.Strong("Finding"),
                            html.Div(id=cid("finding")),
                            html.Strong("Implication"),
                            html.Div(id=cid("implication")),
                        ],
                        className="m5-finding",
                        role="status",
                    ),
                    html.Div(id=cid("kpis"), className="m5-reading-summary"),
                ],
                className="m5-reading",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Details(
                                [
                                    html.Summary("Overlay country recovery lines"),
                                    components.card(
                                        "01 / Follow nominal value recovery",
                                        html.Div(
                                            [
                                                html.P(
                                                    "Dotted horizontal line: baseline = 100. Dashed vertical line: event year. Click a point to inspect that year in both charts.",
                                                    className="m5-hint",
                                                ),
                                                dcc.Graph(
                                                    id=cid("index"),
                                                    style={"height": "330px"},
                                                    config={
                                                        "displayModeBar": False,
                                                        "responsive": True,
                                                    },
                                                ),
                                            ]
                                        ),
                                    ),
                                ],
                                className="m5-overlay",
                            ),
                            components.card(
                                "02 / Check structural indicators",
                                html.Div(
                                    [
                                        dcc.RadioItems(
                                            id=cid("metric"),
                                            options=[
                                                {
                                                    "label": "Product share",
                                                    "value": "product",
                                                },
                                                {
                                                    "label": "Intra-regional partner share",
                                                    "value": "intra",
                                                },
                                            ],
                                            value="intra",
                                            inline=True,
                                            className="m5-radio",
                                        ),
                                        html.P(
                                            id=cid("structure-note"),
                                            className="m5-hint",
                                        ),
                                        dcc.Graph(
                                            id=cid("structure"),
                                            style={"height": "330px"},
                                            config={
                                                "displayModeBar": False,
                                                "responsive": True,
                                            },
                                        ),
                                    ]
                                ),
                            ),
                        ],
                        className="m5-timelines",
                    ),
                    html.Aside(
                        [
                            html.H3(
                                ["Annual detail", html.Span(id=cid("detail-year"))],
                                className="m5-detail-heading",
                            ),
                            html.Div(id=cid("detail"), className="m5-detail"),
                        ],
                        className="m5-analysis-rail",
                    ),
                ],
                className="m5-analysis",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Label("Inspect year", htmlFor=cid("inspect-year")),
                            html.Strong(id=cid("year-label")),
                        ],
                        className="m5-inspect-caption",
                    ),
                    html.Div(
                        dcc.Slider(
                            id=cid("inspect-year"),
                            min=2016,
                            max=2024,
                            value=2024,
                            step=1,
                            marks={2016: "2016", 2024: "2024"},
                            tooltip={"placement": "bottom"},
                            updatemode="mouseup",
                        ),
                        role="group",
                        **{"aria-label": "Inspect year across M5 charts"},
                    ),
                    html.P(
                        "Choose a year here or click a point in a country card or either chart. "
                        "All inspected values use the same year."
                    ),
                ],
                className="m5-inspect-control",
            ),
            html.Div(id=cid("message"), className="m5-source"),
            html.Details(
                [
                    html.Summary("Recovery status · expand for the complete table"),
                    html.Div(
                        [
                            html.P(
                                "First observed return ≥100 follows an observed below-baseline loss. It is not necessarily an exact recovery date. No observed loss is identified separately.",
                                className="m5-hint",
                            ),
                            dash_table.DataTable(
                                id=cid("summary"),
                                columns=[
                                    {"name": "Economy", "id": "country"},
                                    {"name": "Observed status", "id": "status_label"},
                                    {
                                        "name": "First observed return ≥100",
                                        "id": "first_at_baseline",
                                    },
                                    {
                                        "name": "End index",
                                        "id": "end_index",
                                        "type": "numeric",
                                        "format": {"specifier": ".1f"},
                                    },
                                    {
                                        "name": "Observed / expected years",
                                        "id": "coverage",
                                    },
                                    {"name": "Timing", "id": "timing_label"},
                                ],
                                data=[],
                                style_cell={
                                    "textAlign": "left",
                                    "whiteSpace": "normal",
                                    "height": "auto",
                                    "padding": "12px",
                                    "fontFamily": "inherit",
                                    "fontSize": 12,
                                },
                                style_header={
                                    "fontWeight": 600,
                                    "backgroundColor": "#f3f6fa",
                                },
                                style_table={"overflowX": "auto"},
                            ),
                        ]
                    ),
                ],
                className="m5-methods",
            ),
            html.Details(
                [
                    html.Summary("Methods, provenance & evidence download"),
                    html.Div(
                        [
                            html.Section(
                                [
                                    html.H4("01 / Measurement"),
                                    html.P(
                                        "BACI HS92 V202601 · 1995–2024 · nominal merchandise exports, thousand current USD. Value index uses the selected product scope; product share always divides by ALL products. Annual records are not interpolated or filled with zeros."
                                    ),
                                ]
                            ),
                            html.Section(
                                [
                                    html.H4("02 / Region uncertainty"),
                                    html.P(
                                        "Regions use the project’s fixed Africa / America / Asia / Europe / Pacific (Oceania) classification. America includes the whole Americas, not only North America or a trade agreement area. Unknown destinations remain in the full denominator: observed intra-regional share is a lower bound; shading shows its possible range. Unknown origins have no regional share."
                                    ),
                                ]
                            ),
                            html.Section(
                                [
                                    html.H4("03 / Provenance"),
                                    html.P(
                                        "Regional inputs were rebuilt from official BACI HS92 V202601 annual CSVs for 1995–2024. Every exporter×importer×HS2 allocation and exporter×HS2 total was independently reconciled; source and output SHA256 hashes are recorded in the audit manifest."
                                    ),
                                ]
                            ),
                        ],
                        className="m5-methods-grid",
                    ),
                    html.P(
                        "Event markers support before/after exploration, not causal attribution. Nominal recovery can reflect prices and exchange rates. These two shares do not describe the entire export basket or partner distribution. The default CHN/DEU/MEX group is a time comparison, not a similar-income group. Similar-income matching belongs to M4."
                    ),
                    html.P(
                        "Recovery horizon ends at the displayed window endpoint. Baseline must precede the event and both must be in the window. Missing annual observations qualify timing."
                    ),
                    html.P(id=cid("limits")),
                    html.A(
                        "CEPII BACI source attribution",
                        href="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
                        target="_blank",
                    ),
                    html.Button(
                        "Download displayed annual evidence (CSV)",
                        id=cid("download-button"),
                        n_clicks=0,
                    ),
                ],
                className="m5-methods",
            ),
        ],
    )


def comparison_colors(countries):
    """Keep identities consistent across views, with no collisions in a comparison."""
    palette = ["#2463a6", "#b45309", "#087e8b", "#7651a8", "#bf3971", "#41752e"]
    result = {}
    for c in sorted(countries):
        preferred = theme.COUNTRY_COLORS.get(c)
        result[c] = (
            preferred
            if preferred and preferred not in result.values()
            else next(v for v in palette if v not in result.values())
        )
    return result


def style(fig, start, end, event, selected, ytitle):
    theme.style_figure(fig, height=330)
    fig.update_layout(
        margin=dict(l=55, r=30, t=42, b=48),
        legend=dict(orientation="h", y=1.15, x=0, traceorder="normal"),
        hovermode="x unified",
        clickmode="event",
        dragmode=False,
    )
    fig.update_xaxes(
        title="Year",
        range=[start - 0.2, end + 0.2],
        dtick=max(1, (end - start) // 7),
        fixedrange=True,
    )
    fig.update_yaxes(title=ytitle, fixedrange=True, rangemode="tozero")
    fig.add_vline(
        x=event,
        line_dash="dash",
        line_color="#7c8594",
        annotation_text=f"Event {event}",
        annotation_position="top left",
    )
    if start <= selected <= end:
        fig.add_vline(
            x=selected,
            line_color="#b88742",
            line_width=1,
            annotation_text=f"Inspect {selected}",
            annotation_position="bottom left",
            annotation_yshift=6,
        )
    return fig


def json_records(frame):
    return json.loads(frame.to_json(orient="records", double_precision=12))


def compute_view(countries, product, baseline, event, window, metric, selected):
    def empty(message):
        return dict(
            index=theme.empty_figure(message),
            structure=theme.empty_figure(message),
            rows=[],
            summary=[],
            message=message,
            finding=message,
            implication="",
            guide="",
            preset_class="m5-presets",
            kpis=[],
            detail=[],
            limits="",
            structure_note="",
            portraits=portrait_cards(
                [],
                [],
                [],
                baseline,
                event,
                [1995, 2024],
                metric,
                product,
                selected,
                message=message,
            ),
            context="Choose valid comparison settings to inspect annual evidence.",
            year_min=1995,
            year_max=2024,
            year_marks={1995: "1995", 2024: "2024"},
            year_label="—",
            detail_year="",
        )

    if not countries:
        return empty("Select one to four economies to begin.")
    if len(countries) > 4:
        return empty("Select at most 4 economies for a readable comparison.")
    if len(set(countries)) != len(countries) or any(
        c not in FOCUS_COUNTRIES for c in countries
    ):
        return empty(
            "Choose distinct economies from USA, DEU, CHN, MEX, NLD, ITA only."
        )
    if not window or len(window) != 2:
        return empty("Select a valid observation window.")
    start, end = map(int, window)
    if not (1995 <= start <= baseline < event <= end <= 2024):
        return empty(
            "Use window start ≤ baseline < event year ≤ window end (1995–2024)."
        )
    try:
        p, r, manifest = inputs()
        if product != "TOTAL" and product not in chapters():
            return empty("Select a valid HS2 chapter.")
        if any(c not in country_names() for c in countries):
            return empty("Select valid economy codes.")
        f = build_timeline(p, r, countries, product, baseline, start, end)
    except (ValueError, OSError, KeyError) as exc:
        return empty(str(exc))
    summary = summarize_recovery(f, baseline, event, end)
    selected = (
        int(selected) if selected is not None and start <= int(selected) <= end else end
    )
    fig = go.Figure()
    structure = go.Figure()
    colors = comparison_colors(countries)
    dashes = {
        c: ["solid", "dash", "dot", "dashdot"][i]
        for i, c in enumerate(sorted(countries))
    }
    for c in countries:
        d = f[f.country.eq(c)]
        fig.add_trace(
            go.Scatter(
                x=d.year,
                y=d["index"],
                name=c,
                mode="lines+markers",
                connectgaps=False,
                line=dict(color=colors[c], width=2.5, dash=dashes[c]),
                marker=dict(size=5),
                customdata=d[["value", "total"]].to_numpy(),
                hovertemplate=f"<b>{c}</b> · %{{x}}<br>Index: %{{y:.1f}}<br>Exports: %{{customdata[0]:,.0f}} thousand USD<extra></extra>",
            )
        )
        field_name = "product_share" if metric == "product" else "intra_share"
        if metric == "product" and product == "TOTAL":
            continue
        if (
            metric == "intra"
            and d.intra_share.notna().any()
            and d.region_coverage.lt(1 - 1e-8).any()
        ):
            structure.add_trace(
                go.Scatter(
                    x=d.year,
                    y=d.intra_upper * 100,
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                    connectgaps=False,
                )
            )
            structure.add_trace(
                go.Scatter(
                    x=d.year,
                    y=d.intra_share * 100,
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor="rgba(148,163,184,0.12)",
                    showlegend=False,
                    hoverinfo="skip",
                    connectgaps=False,
                )
            )
        structure.add_trace(
            go.Scatter(
                x=d.year,
                y=d[field_name] * 100,
                name=c,
                mode="lines+markers",
                connectgaps=False,
                line=dict(color=colors[c], width=2.5, dash=dashes[c]),
                marker=dict(size=5),
                customdata=d[["region_coverage"]].to_numpy() * 100,
                hovertemplate=(
                    f"<b>{c}</b> · %{{x}}<br>Product share: %{{y:.2f}}%<extra></extra>"
                    if metric == "product"
                    else f"<b>{c}</b> · %{{x}}<br>Same-region lower bound: %{{y:.2f}}%<br>Known-region coverage: %{{customdata[0]:.2f}}%<extra></extra>"
                ),
            )
        )
    fig.add_hline(
        y=100,
        line_dash="dot",
        line_color="#64748b",
    )
    style(fig, start, end, event, selected, "Nominal export index")
    if metric == "product" and product == "TOTAL":
        structure = theme.empty_figure(
            "Select an HS2 chapter to compare its share of all-product exports.",
            height=330,
        )
    else:
        style(structure, start, end, event, selected, "Share of exports (%)")
    note = (
        "Selected chapter / ALL product exports. A rising product share does not imply rising export value."
        if metric == "product"
        else "Same-region exports / ALL destinations in the selected product scope. Shading = uncertainty from unknown destination regions; hover for coverage."
    )
    summary["status_label"] = summary.status.map(STATUS)
    summary["coverage"] = (
        summary.observed_years.astype(str) + " / " + summary.expected_years.astype(str)
    )
    summary["timing_label"] = summary.timing_complete.map(
        {
            True: "No gaps through first return or endpoint",
            False: "Timing uncertain due to gaps",
        }
    )
    valid = summary.end_index.notna()
    above = int(summary.loc[valid, "end_index"].ge(100 - 1e-9).sum())
    finding = (
        f"In {end}, {above} of {int(valid.sum())} comparable economies were at or above their {baseline} export value."
        if valid.any()
        else "The selected series have no comparable baseline and endpoint amounts."
    )
    details = []
    for row in f[f.year.eq(selected)].itertuples():
        value = theme.fmt_usd(row.value) if pd.notna(row.value) else "No recorded value"
        product_txt = (
            f"Product share {row.product_share:.1%}"
            if pd.notna(row.product_share)
            else "Product share unavailable"
        )
        intra_txt = (
            f"Same-region share {row.intra_share:.1%}–{row.intra_upper:.1%}"
            if pd.notna(row.intra_share)
            else "Same-region share unavailable"
        )
        coverage_txt = (
            f"Known-region coverage {row.region_coverage:.1%}"
            if pd.notna(row.region_coverage)
            else None
        )
        details.append(
            html.Div(
                [
                    html.Strong(f"{row.country} · {selected} · {value}"),
                    html.Span(product_txt) if product != "TOTAL" else None,
                    html.Span(intra_txt),
                    html.Span(coverage_txt) if coverage_txt else None,
                ],
                style={"--country-color": colors[row.country]},
            )
        )
    below = summary.loc[valid & summary.end_index.lt(100 - 1e-9), "country"]
    if len(below):
        finding += " Below baseline at the endpoint: " + ", ".join(below) + "."
    if (~valid).any():
        finding += (
            " Missing comparison: " + ", ".join(summary.loc[~valid, "country"]) + "."
        )
    returns = summary.dropna(subset=["first_at_baseline"])
    if len(returns):
        finding += (
            " First observed returns after a loss: "
            + ", ".join(
                f"{row.country} {int(row.first_at_baseline)}"
                for row in returns.itertuples()
            )
            + "."
        )
    implication = describe_structure(summary, metric, product, baseline, end)
    signature = (product, baseline, event, (start, end), metric)
    key = next(
        (
            name
            for name, case in CASES.items()
            if signature == case[:5] and set(countries) == set(CASE_COUNTRIES)
        ),
        None,
    )
    question, action = (
        CASES[key][5:]
        if key
        else (
            "What changed across your selected window?",
            "Inspect one year in both charts and change the product to test the comparison.",
        )
    )
    guide = [
        html.Small("Guided case" if key else "Custom exploration"),
        html.H3(question),
        html.P(action),
    ]
    f["baseline"] = baseline
    f["event_year"] = event
    f["window_start"] = start
    f["window_end"] = end
    f["product"] = product
    f["source_version"] = manifest["source_version"]
    f["source_type"] = manifest["source_type"]
    f["value_unit"] = "thousand current USD"
    f["source_sha256"] = manifest["output_sha256"]
    f["missing_record"] = f.value.isna()
    f["selected_year"] = selected
    f["structural_measure"] = metric
    f = f.merge(
        summary[
            [
                "country",
                "status",
                "first_at_baseline",
                "timing_complete",
                "region_change_min_pp",
                "region_change_max_pp",
                "end_product_change_pp",
            ]
        ],
        on="country",
        how="left",
    )
    records, summaries = json_records(f), json_records(summary)
    return dict(
        index=fig,
        structure=structure,
        rows=records,
        summary=summaries,
        message=f"Official bilateral source audited · {manifest['source_version']} · {start}–{end} · "
        + ("All products" if product == "TOTAL" else label(product)),
        finding=finding,
        implication=implication,
        guide=guide,
        preset_class="m5-presets " + (key or "custom"),
        kpis=components.kpi_row(
            [
                ("Baseline", str(baseline) + " = 100"),
                ("At/above baseline at end", f"{above} / {int(valid.sum())}"),
                ("Inspect year", str(selected)),
            ]
        ),
        detail=details,
        limits="HS2 is broad; nominal USD includes price, exchange-rate and re-export effects. Neither event attribution nor full structural recovery is established by these indicators.",
        structure_note=note,
        portraits=portrait_cards(
            countries,
            records,
            summaries,
            baseline,
            event,
            [start, end],
            metric,
            product,
            selected,
        ),
        context=[
            html.Span(" · ".join(countries)),
            html.Span(
                "All merchandise exports" if product == "TOTAL" else label(product)
            ),
            html.Span(f"{baseline} baseline · {event} event · {start}–{end}"),
        ],
        year_min=start,
        year_max=end,
        year_marks={y: str(y) for y in sorted({start, baseline, event, end})},
        year_label=str(selected),
        detail_year=str(selected),
    )


def describe_structure(summary, metric, product, baseline, end):
    if metric == "product":
        changes = summary.set_index("country").end_product_change_pp.dropna()
        if changes.empty:
            return "Select an HS2 chapter with observations in both years to compare its share of total exports."
        name = changes.abs().idxmax()
        change = changes.loc[name]
        if abs(change) < 0.005:
            return "Across comparable endpoints, the selected chapter’s share changed by less than 0.005 percentage points."
        movement = "gained" if change > 0 else "lost"
        return (
            f"HS{product} {movement} {abs(change):.2f} percentage points of {name}’s export basket "
            f"from {baseline} to {end}. This is the largest absolute share shift among the selected economies with comparable endpoints."
        )
    evidence = []
    ambiguous = []
    for row in summary.itertuples():
        low, high = row.region_change_min_pp, row.region_change_max_pp
        if pd.isna(low) or pd.isna(high):
            continue
        if low >= 0.005 or high <= -0.005:
            movement, bound = ("rose", low) if low > 0 else ("fell", -high)
            # Round down so the reported lower bound remains mathematically valid.
            evidence.append(
                f"{row.country}’s intra-regional share {movement} by at least {math.floor(bound * 100) / 100:.2f} pp"
            )
        else:
            ambiguous.append(row.country)
    parts = []
    if evidence:
        parts.append(
            "Even allowing for unknown partner regions, " + ", ".join(evidence) + "."
        )
    if ambiguous:
        parts.append(
            "At the displayed precision, the bounds leave the direction of change unresolved for "
            + ", ".join(ambiguous)
            + "."
        )
    return (
        " ".join(parts)
        or "Regional coverage is insufficient to compare the selected endpoints."
    )


def validate_import(comparison, product):
    """Reject incompatible handoffs atomically; never silently trim or change years."""
    if not isinstance(comparison, dict):
        raise ValueError("Open M4 and select a comparison first.")
    countries = comparison.get("countries")
    if not isinstance(countries, list) or not 1 <= len(countries) <= 4:
        raise ValueError("M4 must display 1–4 economies before importing.")
    if any(
        not isinstance(c, str) or c not in FOCUS_COUNTRIES for c in countries
    ) or len(set(countries)) != len(countries):
        raise ValueError(
            "M4 economies must be distinct members of USA, DEU, CHN, MEX, NLD, ITA."
        )
    year = comparison.get("year")
    if isinstance(year, bool) or not isinstance(year, int) or not 2020 <= year <= 2024:
        raise ValueError(
            "M4 analysis year must be an integer from 2020 to 2024; M5 was unchanged."
        )
    scope = "TOTAL" if product in (None, "", "TOTAL") else product
    if not isinstance(scope, str) or (scope != "TOTAL" and scope not in chapters()):
        raise ValueError("M4 product must be a valid HS2 chapter; M5 was unchanged.")
    return list(countries), scope, year


def register_callbacks(app):
    @app.callback(
        Output(cid("metric"), "value", allow_duplicate=True),
        Input(cid("product"), "value"),
        State(ACTIVE_MODULE, "data"),
        prevent_initial_call=True,
    )
    def default_metric(product, active):
        guard_active(MODULE_ID, active)
        return "intra" if product == "TOTAL" else "product"

    @app.callback(
        Output(cid("countries"), "value"),
        Output(cid("product"), "value"),
        Output(cid("baseline"), "value"),
        Output(cid("event"), "value"),
        Output(cid("window"), "value"),
        Output(cid("metric"), "value"),
        Output(cid("import-note"), "children"),
        Output(cid("import-reset"), "data"),
        Output(cid("index"), "clickData"),
        Output(cid("structure"), "clickData"),
        Input(cid("pandemic"), "n_clicks"),
        Input(cid("vehicles"), "n_clicks"),
        Input(cid("crisis"), "n_clicks"),
        Input(cid("import"), "n_clicks"),
        State("M4-comparison", "data"),
        State("M4-inspect", "value"),
        State(ACTIVE_MODULE, "data"),
        prevent_initial_call=True,
    )
    def presets(pandemic, vehicles, crisis, imported, comparison, product, active):
        guard_active(MODULE_ID, active)
        trigger = ctx.triggered_id
        if trigger == cid("import"):
            try:
                countries, scope, end = validate_import(comparison, product)
            except ValueError as exc:
                return [no_update] * 6 + [str(exc)] + [no_update] * 3
            return (
                countries,
                scope,
                2019,
                2020,
                [2016, end],
                "intra" if scope == "TOTAL" else "product",
                f"Explicitly imported {', '.join(countries)} · {scope} · 2016–{end}; baseline 2019, event 2020. M5 only; old year highlight cleared.",
                imported,
                None,
                None,
            )
        key = {cid(name): name for name in CASES}.get(trigger, "pandemic")
        scope, baseline, event, window, measure = CASES[key][:5]
        return (
            list(CASE_COUNTRIES),
            scope,
            baseline,
            event,
            list(window),
            measure,
            "",
            no_update,
            None,
            None,
        )

    @app.callback(
        Output(cid("selected"), "data"),
        Output(cid("inspect-year"), "value"),
        Input(cid("index"), "clickData"),
        Input(cid("structure"), "clickData"),
        Input(cid("window"), "value"),
        Input(cid("import-reset"), "data"),
        Input(cid("inspect-year"), "value"),
        *[
            Input(cid("portrait-" + country), "clickData")
            for country in FOCUS_COUNTRIES
        ],
        State(cid("selected"), "data"),
        State(ACTIVE_MODULE, "data"),
    )
    def select_year(a, b, window, reset, slider, *values):
        *portrait_clicks, selected, active = values
        guard_active(MODULE_ID, active)
        if not window or len(window) != 2:
            return no_update, no_update
        trigger = ctx.triggered_id
        if f"{cid('import-reset')}.data" in ctx.triggered_prop_ids:
            return window[1], window[1]
        sources = {cid("index"): a, cid("structure"): b}
        sources.update(
            zip((cid("portrait-" + c) for c in FOCUS_COUNTRIES), portrait_clicks)
        )
        click = sources.get(trigger)
        candidate = slider if trigger == cid("inspect-year") else None
        if isinstance(click, dict) and click.get("points"):
            candidate = click["points"][0].get("x")
        valid = (
            finite(candidate)
            and candidate == int(candidate)
            and window[0] <= candidate <= window[1]
        )
        if valid:
            year = int(candidate)
        elif finite(selected) and window[0] <= selected <= window[1]:
            year = selected
        else:
            year = window[1]
        # Re-created graphs emit empty clickData. Returning no_update here is
        # essential: selected -> render cards -> empty clickData must terminate.
        return (
            year if year != selected else no_update,
            year if year != slider else no_update,
        )

    @app.callback(
        Output(cid("index"), "figure"),
        Output(cid("structure"), "figure"),
        Output(cid("rows"), "data"),
        Output(cid("summary"), "data"),
        Output(cid("message"), "children"),
        Output(cid("finding"), "children"),
        Output(cid("implication"), "children"),
        Output(cid("guide"), "children"),
        Output(cid("presets"), "className"),
        Output(cid("kpis"), "children"),
        Output(cid("detail"), "children"),
        Output(cid("limits"), "children"),
        Output(cid("structure-note"), "children"),
        Output(cid("portraits"), "children"),
        Output(cid("context"), "children"),
        Output(cid("inspect-year"), "min"),
        Output(cid("inspect-year"), "max"),
        Output(cid("inspect-year"), "marks"),
        Output(cid("year-label"), "children"),
        Output(cid("detail-year"), "children"),
        Input(cid("countries"), "value"),
        Input(cid("product"), "value"),
        Input(cid("baseline"), "value"),
        Input(cid("event"), "value"),
        Input(cid("window"), "value"),
        Input(cid("metric"), "value"),
        Input(cid("selected"), "data"),
        Input(ACTIVE_MODULE, "data"),
    )
    def render(countries, product, baseline, event, window, metric, selected, active):
        guard_active(MODULE_ID, active)
        v = compute_view(countries, product, baseline, event, window, metric, selected)
        return tuple(
            v[k]
            for k in [
                "index",
                "structure",
                "rows",
                "summary",
                "message",
                "finding",
                "implication",
                "guide",
                "preset_class",
                "kpis",
                "detail",
                "limits",
                "structure_note",
                "portraits",
                "context",
                "year_min",
                "year_max",
                "year_marks",
                "year_label",
                "detail_year",
            ]
        )

    @app.callback(
        Output(cid("download"), "data"),
        Input(cid("download-button"), "n_clicks"),
        State(cid("rows"), "data"),
        prevent_initial_call=True,
    )
    def download(n, rows):
        if not n or not rows:
            return no_update
        return dcc.send_data_frame(
            pd.DataFrame(rows).to_csv, "M5_annual_evidence.csv", index=False
        )
