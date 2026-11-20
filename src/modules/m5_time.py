"""M5: continuous nominal export recovery and structural indicators."""

import hashlib
import json
import math
from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dash_table, dcc, html, no_update

from src import components, config, data_loader, handoffs, theme
from src.analytics.product import chapters, label
from src.analytics.time_change import build_timeline, summarize_recovery
from src.ids import ACTIVE_MODULE, mid
from src.m5_portraits import FOCUS_COUNTRIES, PLOT_FONT, finite, portrait_cards
from src.module_base import guard_active
from src.m5_structure import composition_figure, comparison_summary, change_figure

MODULE_ID = "M5"
NAV_LABEL = "M5  Time Change"
ORDER = 5
YEARS = list(range(1995, 2025))
VEHICLE_COUNTRIES = ["CHN", "MEX"]
VEHICLE_WINDOW = (2019, 2023)
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
        VEHICLE_WINDOW,
        "product",
        "How did vehicle exports change from 2019 to 2023?",
        "Compare the two export value indices, then check the share of HS87 in each export basket.",
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


def story_heading(section):
    return html.Div(
        [
            html.P(id=cid(section + "-question"), className="m5-story-question"),
            html.H3(id=cid(section + "-title"), className="m5-story-title"),
        ],
        className="m5-story-heading",
    )


def layout():
    ns = country_names()
    return html.Div(
        className="module-inner m5 m5-fieldnotes",
        children=[
            dcc.Store(id=cid("selected"), data=VEHICLE_WINDOW[1]),
            dcc.Store(id=cid("rows")),
            dcc.Store(id=cid("import-reset")),
            dcc.Download(id=cid("download")),
            components.module_intro(
                "Recovery & structural change",
                "Export recovery can coincide with shifts in product and regional partner shares.",
            ),
            html.Div(
                [
                    field(
                        "Analysis year",
                        dcc.Dropdown(
                            id=cid("inspect-year"),
                            options=[
                                {"label": str(y), "value": y} for y in range(VEHICLE_WINDOW[0], VEHICLE_WINDOW[1] + 1)
                            ],
                            value=VEHICLE_WINDOW[1],
                            clearable=False,
                            searchable=False,
                            className="ctl-dropdown",
                        ),
                    ),
                    dcc.RadioItems(
                        id=cid("section"),
                        options=[
                            {
                                "label": html.Span(
                                    [
                                        html.Span("01", className="m5-step-number"),
                                        html.Strong("Compare recovery"),
                                    ],
                                    className="m5-step-label",
                                ),
                                "value": "recovery",
                            },
                            {
                                "label": html.Span(
                                    [
                                        html.Span("02", className="m5-step-number"),
                                        html.Strong("Check structure"),
                                    ],
                                    className="m5-step-label",
                                ),
                                "value": "structure",
                            },
                        ],
                        value="recovery",
                        inline=True,
                        className="m5-major-tabs",
                    ),
                    components.comparison_actions(
                        cid, handoffs.actions(cid, "Use current M4 selection", apply_id="import", undo_id="undo-import"),
                    ),
                    html.Div(components.comparison_fields(
                        [
                            components.field(
                                "Economies (up to 6)",
                                dcc.Dropdown(
                                    id=cid("countries"),
                                    options=[
                                        {"label": f"{ns[c]} ({c})", "value": c}
                                        for c in FOCUS_COUNTRIES
                                    ],
                                    value=VEHICLE_COUNTRIES,
                                    multi=True,
                                ),
                                extra_class="comparison-wide",
                            ),
                            components.field(
                                "Product",
                                dcc.Dropdown(
                                    id=cid("product"),
                                    options=[{"label": "All products", "value": "TOTAL"}]
                                    + [{"label": label(p), "value": p} for p in chapters()],
                                    value="87",
                                    clearable=False,
                                ),
                                extra_class="comparison-wide",
                            ),
                            components.field(
                                "Baseline year",
                                dcc.Dropdown(id=cid("baseline"), options=YEARS, value=2019, clearable=False),
                                extra_class="comparison-year",
                            ),
                            components.field(
                                "Event year",
                                dcc.Dropdown(id=cid("event"), options=YEARS, value=2020, clearable=False),
                                extra_class="comparison-year",
                            ),
                        ],
                        [
                            components.field(
                                "Observation window",
                                dcc.RangeSlider(
                                    id=cid("window"),
                                    min=1995,
                                    max=2024,
                                    value=list(VEHICLE_WINDOW),
                                    step=1,
                                    marks={year: str(year) for year in (1995, 2000, 2005, 2010, 2015, 2020, 2024)},
                                    allowCross=False,
                                    tooltip={"placement": "bottom"},
                                ),
                                extra_class="comparison-range",
                            ),
                        ],
                    ), id=cid("customize"), hidden=True),
                ],
                className="m5-toolbar module-toolbar toolbar-row",
            ),
            dcc.Store(id=cid("import-history")),
            html.Div(
                [
                    html.Div(
                        [
                            html.Button("Pandemic recovery", id=cid("pandemic"), n_clicks=0),
                            html.Button("Vehicles & parts", id=cid("vehicles"), n_clicks=0),
                            html.Button("Financial crisis", id=cid("crisis"), n_clicks=0),
                        ],
                        id=cid("presets"), className="m5-presets",
                    ),
                    html.Div(id=cid("import-note"), className="m5-hint", role="status"),
                ],
                className="module-toolbar toolbar-row",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    story_heading("recovery"),
                                ],
                                className="m5-section-heading",
                            ),
                            html.P(id=cid("recovery-caption"), className="m5-hint"),
                            dcc.Graph(
                                id=cid("index"),
                                style={"height": "380px"},
                                config={"displayModeBar": False, "responsive": True},
                            ),
                            html.H3("Recovery results", className="m5-path-title"),
                            html.Div(
                                id=cid("portraits"),
                                className="m5-country-grid",
                                children=portrait_cards(
                                    [],
                                    [],
                                    [],
                                    2019,
                                    2020,
                                    list(VEHICLE_WINDOW),
                                    "product",
                                    "87",
                                    VEHICLE_WINDOW[1],
                                    message="Loading the selected comparison…",
                                    show_graph=True,
                                ),
                            ),

                        ],
                        className="card m5-story m5-recovery-chart",
                    ),
                ],
                id=cid("recovery-panel"),
                className="m5-section-panel",
                style={"display": "flex"},
            ),
            html.Section([
                html.Div([
                    html.Div([
                        story_heading("structure"),
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
                            value="product",
                            inline=True,
                            className="m5-radio",
                        ),

                        html.P(id=cid("structure-note"), className="m5-hint"),
                    ], className="m5-structure-intro"),
                    html.Div([
                        components.card(None, [
                            html.P("01 / COMPOSITION", className="m5-chart-eyebrow"),
                            html.H3(id=cid("composition-heading"), className="m5-pair-title"),
                            dcc.Graph(id=cid("structure"), style={"height": "330px"},
                                config={"displayModeBar": False, "responsive": True}),
                        ], extra_class="m5-composition-card"),
                        components.card(None, [
                            html.P("02 / CHANGE", className="m5-chart-eyebrow"),
                            html.H3(id=cid("change-heading"), className="m5-pair-title"),
                            dcc.Graph(id=cid("structure-change"), style={"height": "330px"},
                                config={"displayModeBar": False, "responsive": True}),
                        ], extra_class="m5-change-card"),
                    ], className="m5-structure-pair"),
                ], className="card m5-story m5-structure-chart"),
                html.Div([
                    html.H3(["Annual detail", html.Span(id=cid("detail-year"))],
                        className="m5-detail-heading"),
                    html.Div(id=cid("detail"), className="m5-detail"),
                ], className="m5-analysis-rail m5-structure-detail"),
            ], id=cid("structure-panel"), className="m5-section-panel", style={"display": "none"}),
            html.Div(id=cid("message"), className="m5-source"),
            components.findings_card(
                finding=html.P(id=cid("summary-finding")),
                implication=html.P(id=cid("summary-implication")),
                limits=html.P(
                    "Current-dollar values reflect prices and exchange rates. Missing years can obscure recovery timing, and unknown partner regions can affect conclusions about regional change."
                ),
            ),
            components.module_data_details(
                [
                    html.P(
                        "Recovery is the first observed return to 100 or above after a loss. The table flags cases with no observed loss. The CSV includes annual values for the selected comparison."
                    ),
                    components.module_data_table_header(
                        "Recovery status",
                        download_id=cid("download-button"),
                        download_label="Download selected annual evidence (CSV)",
                    ),
                    dash_table.DataTable(
                        id=cid("summary"),
                        columns=[
                            {"name": "Economy", "id": "country"},
                            {"name": "Observed status", "id": "status_label"},
                            {"name": "First observed return ≥100", "id": "first_at_baseline"},
                            {
                                "name": "End index",
                                "id": "end_index",
                                "type": "numeric",
                                "format": {"specifier": ".1f"},
                            },
                            {"name": "Observed / expected years", "id": "coverage"},
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
                        style_header={"fontWeight": 600, "backgroundColor": "#f3f6fa"},
                        style_table={"overflowX": "auto"},
                    ),
                    components.module_data_methods(
                        [
                            html.P(
                                "BACI HS92 V202601 covers 1995–2024 in thousand current USD. The value index follows the selected product scope. Product share uses all goods exports as its denominator. Annual gaps stay missing."
                            ),
                            html.P(
                                "Regional shares use Africa, the Americas, Asia, Europe and Oceania. The denominator includes destinations with unknown regions, so the observed same-region share is a lower bound. Change intervals account for unknown destinations. Regional shares require a known origin region."
                            ),
                            html.P(
                                "The baseline precedes the event within the comparison window. Recovery is tracked through the end of that window. Missing annual observations can affect the observed timing. Nominal values can reflect prices and exchange rates. Event markers support before-and-after comparisons."
                            ),
                            html.P(
                                "The regional inputs were rebuilt from official BACI annual files and reconciled at the exporter–importer–HS2 and exporter–HS2 levels. Source and output SHA256 hashes are in the audit manifest."
                            ),
                            html.P(id=cid("limits")),
                            html.A(
                                "CEPII BACI source attribution",
                                href="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
                                target="_blank",
                            ),
                        ],
                    ),
                ],
                id=cid("data-details"),
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
        font=dict(family=PLOT_FONT, size=12, color=theme.INK),
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


def story_headlines(summary, product, baseline, metric):
    headings = dict(
        recovery_question="01 / When did exports regain their baseline value?",
        recovery_title="Select a valid comparison",
        structure_question="02 / Did product or regional export shares change?",
        structure_title="Select a valid comparison",
    )
    if summary is None or summary.empty:
        return headings
    scope = (
        "exports"
        if product == "TOTAL"
        else "vehicle and parts exports"
        if product == "87"
        else f"HS{product} exports"
    )
    headings["recovery_question"] = (
        f"01 / When did {scope} regain their {baseline} value?"
    )
    observed = summary.end_index.dropna()
    above = int(observed.ge(100 - 1e-9).sum())
    returns = summary.first_at_baseline.dropna()
    if observed.empty:
        title = "Recovery cannot be compared"
    elif above == len(observed):
        if summary.status.eq("never_below").all():
            title = "No below-baseline loss was observed"
        elif returns.nunique() > 1:
            title = "Observed returns occurred in different years"
        else:
            title = "Exports regained their baseline value"
        if len(observed) < len(summary):
            title = "Comparable exports regained their baseline value"
    elif above:
        title = "Recovery remains uneven"
    else:
        title = "Exports remain below their baseline value"
    headings["recovery_title"] = title
    if metric == "product":
        headings["structure_question"] = (
            f"02 / Did HS{product} gain or lose weight in the export basket?"
            if product != "TOTAL"
            else "02 / How did product shares change?"
        )
        changes = summary.end_product_change_pp.dropna()
        up, down = int(changes.ge(0.005).sum()), int(changes.le(-0.005).sum())
        if changes.empty:
            title = "Choose a chapter to compare export shares"
        elif up and down:
            title = "Product shares moved in different directions"
        elif up == len(changes):
            title = "The selected chapter gained export share"
        elif down == len(changes):
            title = "The selected chapter lost export share"
        elif up:
            title = "Some export baskets shifted toward this chapter"
        elif down:
            title = "Some export baskets shifted away from this chapter"
        else:
            title = "Product shares changed little"
    else:
        headings["structure_question"] = (
            "02 / Did exports become more concentrated within each economy’s region?"
        )
        bounds = summary[["region_change_min_pp", "region_change_max_pp"]].dropna()
        up = int(bounds.region_change_min_pp.ge(0.005).sum())
        down = int(bounds.region_change_max_pp.le(-0.005).sum())
        if bounds.empty:
            title = "Regional change cannot be compared"
        elif up == len(bounds):
            title = "Exports became more regionally concentrated"
        elif down == len(bounds):
            title = "Exports became less regionally concentrated"
        elif up and down:
            title = "Regional concentration moved in different directions"
        elif up or down:
            title = "Regional shifts vary in strength and certainty"
        else:
            title = "The direction of regional change remains uncertain"
    headings["structure_title"] = title
    return headings


def compute_view(
    countries, product, baseline, event, window, metric, selected, chart_type="line",
    show_country_charts=True
):
    def empty(message):
        return dict(
            index=theme.empty_figure(message),
            structure=theme.empty_figure(message),
            structure_style={"height": "330px"},
            structure_change=theme.empty_figure(message),
            composition_heading="How did the composition change?",
            change_heading="Who gained or lost share?",
            rows=[],
            summary=[],
            message=message,
            summary_finding="The current selection has no comparable evidence.",
            implication="Use a valid selection to compare export recovery and structure.",
            **story_headlines(None, product, baseline, metric),
            preset_class="m5-presets",
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
                show_graph=show_country_charts,
            ),
            year_options=[{"label": str(y), "value": y} for y in YEARS],
            detail_year="",
            recovery_caption=message,
        )

    if not countries:
        return empty("Select one to six economies to begin.")
    if len(countries) > len(FOCUS_COUNTRIES):
        return empty("Select at most 6 focus economies for comparison.")
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
        c: ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"][i]
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
    fig.add_hline(
        y=100,
        line_dash="dot",
        line_color="#64748b",
    )
    style(fig, start, end, event, selected, "Nominal export index")
    fig.update_layout(height=380)
    snapshot_rows = json_records(f)
    structure = composition_figure(snapshot_rows, countries, product, metric, baseline, selected, colors)
    structure_summary = comparison_summary(summary, snapshot_rows, baseline, selected)
    structure_change = change_figure(json_records(structure_summary), countries, metric, baseline, selected, colors, structure.layout.height)
    note = (
        "Selected chapter / all exports · Change in percentage points"
        if metric == "product"
        else "Bars use known same-region shares · Unknown destinations stay separate"
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
    summary_finding = (
        f"In {end}, {above} of {int(valid.sum())} comparable economies were at or above their {baseline} export level."
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
    implication = describe_structure(structure_summary, metric, product, baseline, selected)
    signature = (product, baseline, event, (start, end), metric)
    key = next(
        (
            name
            for name, case in CASES.items()
            if signature == case[:5] and set(countries) == set(VEHICLE_COUNTRIES if name == "vehicles" else CASE_COUNTRIES)
        ),
        None,
    )
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
        structure_style={"height": f"{structure.layout.height}px"},
        structure_change=structure_change,
        composition_heading="How did the export basket change?" if metric == "product" else "How did destinations change?",
        change_heading="Who gained or lost product share?" if metric == "product" else "How did known same-region shares change?",
        rows=records,
        summary=summaries,
        message="",
        summary_finding=summary_finding,
        implication=implication,
        **story_headlines(structure_summary, product, baseline, metric),
        preset_class="m5-presets " + (key or "custom"),
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
            chart_type=chart_type,
            show_graph=show_country_charts,
        ),
        year_options=[{"label": str(y), "value": y} for y in range(start, end + 1)],
        detail_year=str(selected),
        recovery_caption=f"Nominal exports · {baseline} = 100 · Click a point to inspect",
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
            f"from {baseline} to {end}, the largest shift among comparable economies."
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
    if not parts:
        return "Regional coverage is insufficient to compare the selected endpoints."
    return f"{baseline} → {end}. " + " ".join(parts)


def validate_import(comparison, product):
    """Reject incompatible handoffs atomically; never silently trim or change years."""
    if not isinstance(comparison, dict):
        raise ValueError("Open M4 and select a comparison first.")
    countries = comparison.get("countries")
    if not isinstance(countries, list) or not 1 <= len(countries) <= len(
        FOCUS_COUNTRIES
    ):
        raise ValueError("M4 must display 1–6 economies before importing.")
    if any(
        not isinstance(c, str) or c not in FOCUS_COUNTRIES for c in countries
    ) or len(set(countries)) != len(countries):
        raise ValueError(
            "M4 economies must be distinct members of USA, DEU, CHN, MEX, NLD, ITA."
        )
    year = comparison.get("year")
    if type(year) is not int or year not in YEARS:
        raise ValueError("Select an M4 analysis year from 1995 to 2024.")
    scope = "TOTAL" if product in (None, "", "TOTAL") else product
    if not isinstance(scope, str) or (scope != "TOTAL" and scope not in chapters()):
        raise ValueError("M4 product must be a valid HS2 chapter; M5 was unchanged.")
    return list(countries), scope, year


def register_callbacks(app):
    components.register_comparison_toggle(app, cid)
    import_fields = ("countries", "product", "baseline", "event", "window", "metric")

    @app.callback(
        Output(cid("undo-import"), "hidden"),
        Input(cid("import-history"), "data"),
        *[Input(cid(key), "value") for key in (*import_fields, "inspect-year")],
    )
    def hide_import_undo(history, *current):
        return not history or list(current) != history["applied"]

    @app.callback(
        Output(cid("recovery-panel"), "style"),
        Output(cid("structure-panel"), "style"),
        Input(cid("section"), "value"),
        State(ACTIVE_MODULE, "data"),
    )
    def show_section(section, active):
        guard_active(MODULE_ID, active)
        structural = section == "structure"
        return (
            {"display": "none" if structural else "flex"},
            {"display": "flex" if structural else "none"},
        )

    @app.callback(
        Output(cid("metric"), "value", allow_duplicate=True),
        Input(cid("product"), "value"),
        Input(cid("import-reset"), "data"),
        State(ACTIVE_MODULE, "data"),
        prevent_initial_call=True,
    )
    def default_metric(product, _reset, active):
        guard_active(MODULE_ID, active)
        if f"{cid('import-reset')}.data" in ctx.triggered_prop_ids:
            return no_update
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
        Output(cid("import-history"), "data"),
        Input(cid("pandemic"), "n_clicks"),
        Input(cid("vehicles"), "n_clicks"),
        Input(cid("crisis"), "n_clicks"),
        Input(cid("import"), "n_clicks"),
        Input(cid("undo-import"), "n_clicks"),
        State("M4-comparison", "data"),
        State("M4-inspect", "value"),
        State("M4-products", "value"),
        State(ACTIVE_MODULE, "data"),
        State("M4-year", "value"),
        State("M4-case", "data"),
        State("M4-detail-context", "data"),
        State("M4-mode", "value"),
        State("M4-countries", "value"),
        State("M4-anchor", "value"),
        State("M4-factor", "value"),
        *[State(cid(key), "value") for key in (*import_fields, "inspect-year")],
        State(cid("import-history"), "data"),
        prevent_initial_call=True,
    )
    def presets(pandemic, vehicles, crisis, imported, undo, comparison, product, products,
                active, source_year, source_case, source_detail, source_mode,
                source_countries, source_anchor, source_factor, *values):
        guard_active(MODULE_ID, active)
        trigger = ctx.triggered_id
        *local, history = values
        if trigger == cid("undo-import"):
            if not history or local != history["applied"]:
                return [no_update] * 6 + ["Selection has changed. Nothing to undo."] + [no_update] * 4
            return (
                *history["before"][:6], "",
                {"source": "undo", "click": undo, "year": history["before"][6]},
                None, None, None,
            )
        if trigger == cid("import"):
            try:
                # A single chapter filter is an explicit scope even if the
                # hidden detail chart is still inspecting another chapter.
                scope = products[0] if isinstance(products, list) and len(products) == 1 else product
                countries, scope, year = validate_import(comparison, scope)
                if source_year is not None and source_year != year:
                    raise ValueError("Wait for M4 to finish loading the current year.")
                if products and not set(products).issubset(comparison.get("products", [])):
                    raise ValueError("Wait for M4 to finish applying the current products.")
                current_controls = handoffs.product_comparison_inputs(
                    source_mode, source_countries, products, source_anchor, source_factor
                )
                if comparison.get("source_controls") != current_controls:
                    raise ValueError("Return to Product structure, wait for the comparison to update, then import again.")
                request_id = (source_case or {}).get("transfer_request")
                if request_id and (source_detail or {}).get("transfer_request") != request_id:
                    raise ValueError("Wait for M4 to finish applying the current selection.")
            except ValueError as exc:
                return [no_update] * 6 + [str(exc)] + [no_update] * 4
            if year == VEHICLE_WINDOW[1] and scope == "87" and set(countries) == set(VEHICLE_COUNTRIES):
                baseline, event, window = 2019, 2020, list(VEHICLE_WINDOW)
            elif year >= 2020:
                baseline, event, window = 2019, 2020, [2016, year]
            else:
                # Historical imports use adjacent years. The earliest year
                # can only serve as a baseline, but is still the inspected year.
                baseline = max(YEARS[0], year - 1)
                event = baseline + 1
                window = [max(YEARS[0], year - 4), event]
            applied = [countries, scope, baseline, event, window,
                       "intra" if scope == "TOTAL" else "product"]
            if applied + [year] == local:
                return [no_update] * 6 + [""] + [no_update] * 4
            return (
                *applied,
                "",
                {"source": "import", "click": imported, "year": year},
                None,
                None,
                {"before": local, "applied": applied + [year]},
            )
        key = {cid(name): name for name in CASES}.get(trigger, "pandemic")
        scope, baseline, event, window, measure = CASES[key][:5]
        return (
            list(VEHICLE_COUNTRIES if key == "vehicles" else CASE_COUNTRIES),
            scope,
            baseline,
            event,
            list(window),
            measure,
            "",
            {"source": key, "click": dict(zip(CASES, (pandemic, vehicles, crisis)))[key]},
            None,
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
        *[Input(cid("portrait-" + country), "clickData") for country in FOCUS_COUNTRIES],
        State(cid("selected"), "data"),
        State(ACTIVE_MODULE, "data"),
    )
    def select_year(a, b, window, reset, analysis_year, *values):
        *portrait_clicks, selected, active = values
        guard_active(MODULE_ID, active)
        if not window or len(window) != 2:
            return no_update, no_update
        trigger = ctx.triggered_id
        if f"{cid('import-reset')}.data" in ctx.triggered_prop_ids:
            if isinstance(reset, dict):
                year = reset.get("year")
                if type(year) is int and window[0] <= year <= window[1]:
                    return year, year
            return window[1], window[1]
        sources = {cid("index"): a, cid("structure"): b}
        sources.update(zip((cid("portrait-" + c) for c in FOCUS_COUNTRIES), portrait_clicks))
        click = sources.get(trigger)
        candidate = analysis_year if trigger == cid("inspect-year") else None
        if isinstance(click, dict) and click.get("points"):
            point = click["points"][0]
            custom = point.get("customdata")
            candidate = (custom[1] if trigger == cid("structure") and isinstance(custom, (list, tuple)) and len(custom) == 5
                         else custom[0] if trigger in {cid("portrait-" + c) for c in FOCUS_COUNTRIES}
                         and isinstance(custom, (list, tuple)) and len(custom) == 2
                         else point.get("x"))
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
            year if year != analysis_year else no_update,
        )

    @app.callback(
        Output(cid("index"), "figure"),
        Output(cid("structure"), "figure"),
        Output(cid("structure"), "style"),
        Output(cid("structure-change"), "figure"),
        Output(cid("structure-change"), "style"),
        Output(cid("composition-heading"), "children"),
        Output(cid("change-heading"), "children"),
        Output(cid("rows"), "data"),
        Output(cid("summary"), "data"),
        Output(cid("message"), "children"),
        Output(cid("recovery-question"), "children"),
        Output(cid("recovery-title"), "children"),
        Output(cid("structure-question"), "children"),
        Output(cid("structure-title"), "children"),
        Output(cid("presets"), "className"),
        Output(cid("detail"), "children"),
        Output(cid("limits"), "children"),
        Output(cid("structure-note"), "children"),
        Output(cid("portraits"), "children"),
        Output(cid("inspect-year"), "options"),
        Output(cid("detail-year"), "children"),
        Output(cid("recovery-caption"), "children"),
        Output(cid("summary-finding"), "children"),
        Output(cid("summary-implication"), "children"),
        Input(cid("countries"), "value"),
        Input(cid("product"), "value"),
        Input(cid("baseline"), "value"),
        Input(cid("event"), "value"),
        Input(cid("window"), "value"),
        Input(cid("metric"), "value"),
        Input(cid("selected"), "data"),
        Input(ACTIVE_MODULE, "data"),
    )
    def render(
        countries,
        product,
        baseline,
        event,
        window,
        metric,
        selected,
        active,
    ):
        guard_active(MODULE_ID, active)
        v = compute_view(
            countries, product, baseline, event, window, metric, selected,
            chart_type="bar", show_country_charts=True
        )
        return tuple(
            v[k]
            for k in [
                "index",
                "structure",
                "structure_style",
                "structure_change",
                "structure_style",
                "composition_heading",
                "change_heading",
                "rows",
                "summary",
                "message",
                "recovery_question",
                "recovery_title",
                "structure_question",
                "structure_title",
                "preset_class",
                "detail",
                "limits",
                "structure_note",
                "portraits",
                "year_options",
                "detail_year",
                "recovery_caption",
                "summary_finding",
                "implication",
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
