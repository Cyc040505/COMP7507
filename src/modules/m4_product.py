"""M4 guided visual analysis: composition, specialization and fixed-sample change."""

from functools import lru_cache
from textwrap import wrap
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, dcc, html, dash_table, no_update
from src import components, data_loader, theme
from src.analytics.product import (
    chapters,
    label,
    validate_trade,
    year_metrics,
    product_set,
    income_peers,
    income_allowed,
    income_policy,
    candidate_pool,
    two_year_metrics,
    spread_finding,
)
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active

MODULE_ID = "M4"
NAV_LABEL = "M4  Product Structure"
ORDER = 4
DEFAULTS = ["CHN", "RUS", "MEX"]
PRODUCT_GROUPS = {
    "HS84": ["84", "85"],
    "HS87": ["87"],
    "HS28": [f"{p:02}" for p in range(28, 39)],
    "HS61": ["61", "62"],
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
STEPS = {
    "structure": {
        "question": "Similar incomes. Similar export baskets?",
        "action": "Compare the leading chapters, then inspect an economy against the world.",
        "metric": "share",
        "mode": "income",
        "focus": "CHN",
        "product": "85",
        "view": "world",
        "countries": DEFAULTS,
    },
    "specialization": {
        "question": "Does a large export share mean stronger specialization?",
        "action": "Inspect Russia’s fuels and fertilizers. Compare their shares and RCA.",
        "metric": "rca",
        "mode": "income",
        "focus": "RUS",
        "product": "31",
        "view": "world",
        "countries": DEFAULTS,
    },
    "change": {
        "question": "Has a larger product share crossed the RCA = 1 threshold?",
        "action": "Keep China and Mexico fixed. Compare HS87 in 2010 and 2023; switch the detail economy to check the contrast.",
        "metric": "share",
        "mode": "selected",
        "focus": "CHN",
        "product": "87",
        "view": "change",
        "countries": ["CHN", "MEX"],
    },
}


def cid(s):
    return mid(MODULE_ID, s)


def graph(s):
    return dcc.Graph(
        id=cid(s),
        figure=theme.empty_figure("Select M4 to begin."),
        config=GRAPH_CONFIG,
        style={"height": "420px"},
    )


def field(title, widget):
    return html.Div(
        [html.Label(title, htmlFor=widget.id), widget], className="m4-field"
    )


def table(s, columns):
    return dash_table.DataTable(
        id=cid(s),
        columns=[{"name": title, "id": key} for key, title in columns],
        data=[],
        page_size=12,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "left",
            "fontSize": 12,
            "fontFamily": "inherit",
            "padding": "8px",
            "maxWidth": "220px",
            "whiteSpace": "normal",
        },
        style_header={"fontWeight": 600, "backgroundColor": "#eef3ff"},
    )


def layout():
    products = [
        {"label": label(p), "value": p}
        for p in sorted(chapters())
        if p not in ["77", "99"]
    ]
    return html.Div(
        className="module-inner m4",
        children=[
            dcc.Store(id=cid("intent")),
            dcc.Store(id=cid("case")),
            dcc.Store(id=cid("global-context")),
            dcc.Store(id=cid("detail-context")),
            dcc.Store(id=cid("comparison")),
            html.Div(
                className="m4-intro",
                children=[
                    html.Div("STRUCTURE / M4", className="m4-eyebrow"),
                    html.H2("Income, export baskets & specialization"),
                    html.P(
                        "Follow a focused comparison, test it with a second measure, then check two years."
                    ),
                ],
            ),
            html.Div(
                className="m4-steps",
                children=[
                    html.Button(
                        [
                            html.Span(f"0{i}", className="m4-step-number"),
                            html.Strong(title),
                        ],
                        id=cid("step-" + key),
                        n_clicks=0,
                        className="m4-step",
                    )
                    for i, (key, title) in enumerate(
                        [
                            ("structure", "Compare structure"),
                            ("specialization", "Test specialization"),
                            ("change", "Check change"),
                        ],
                        1,
                    )
                ],
            ),
            html.Div(id=cid("question"), className="m4-question"),
            html.Details(
                className="module-controls m4-advanced",
                children=[
                    html.Summary("Customize this comparison"),
                    html.Div(
                        className="m4-controls",
                        children=[
                            field(
                                "Comparison rule",
                                dcc.RadioItems(
                                    id=cid("mode"),
                                    options=[
                                        {
                                            "label": "Selected economies",
                                            "value": "selected",
                                        },
                                        {"label": "Similar income", "value": "income"},
                                    ],
                                    value="income",
                                    className="radio-row",
                                ),
                            ),
                            field(
                                "Economies · up to 6 in manual mode",
                                dcc.Dropdown(
                                    id=cid("countries"),
                                    multi=True,
                                    value=DEFAULTS,
                                    options=[],
                                    placeholder="Search economies",
                                    className="ctl-dropdown",
                                ),
                            ),
                            field(
                                "Income candidates",
                                dcc.Dropdown(
                                    id=cid("pool"),
                                    options=[
                                        {
                                            "label": "Overview · ever Top10 exporters",
                                            "value": "overview",
                                        },
                                        {
                                            "label": "All named economies",
                                            "value": "all",
                                        },
                                    ],
                                    value="overview",
                                    clearable=False,
                                    className="ctl-dropdown",
                                ),
                            ),
                            field(
                                "Income range · anchor ÷ factor to anchor × factor",
                                dcc.Dropdown(
                                    id=cid("factor"),
                                    options=[
                                        {"label": "1.25 × (narrow)", "value": 1.25},
                                        {"label": "1.5 ×", "value": 1.5},
                                        {"label": "2 × (broad)", "value": 2.0},
                                    ],
                                    value=1.25,
                                    clearable=False,
                                    className="ctl-dropdown",
                                ),
                            ),
                            field(
                                "Products · blank = union of each economy’s top 5",
                                dcc.Dropdown(
                                    id=cid("products"),
                                    multi=True,
                                    options=products,
                                    placeholder="Search HS2 chapter",
                                    className="ctl-dropdown",
                                ),
                            ),
                            html.Button(
                                "Reset guided case",
                                id=cid("reset"),
                                n_clicks=0,
                                className="m4-button",
                            ),
                        ],
                    ),
                    html.P(
                        "Year and income anchor follow the global console. Product groups locate chapters; all-product denominators stay fixed. Changing the preset conditions switches the narrative to custom exploration.",
                        className="m4-note",
                    ),
                ],
            ),
            html.Div(id=cid("scope"), className="m4-scope", role="status"),
            html.Div(id=cid("kpis"), className="m4-kpis"),
            components.card(
                "01 / Compare the same products",
                html.Div(
                    [
                        field(
                            "Heatmap measure",
                            dcc.RadioItems(
                                id=cid("metric"),
                                options=[
                                    {"label": "Export share", "value": "share"},
                                    {"label": "RCA", "value": "rca"},
                                ],
                                value="share",
                                className="radio-row",
                            ),
                        ),
                        html.Div(id=cid("heat-note"), className="m4-note"),
                        graph("graph"),
                        html.P(
                            "Click a cell to inspect it below. Grey cells indicate no recorded value, not an assumed zero.",
                            className="m4-note",
                        ),
                    ]
                ),
                extra_class="m4-chart",
            ),
            components.card(
                "02 / Check the evidence",
                html.Div(
                    [
                        field(
                            "Detail view",
                            dcc.RadioItems(
                                id=cid("detail-view"),
                                options=[
                                    {"label": "Economy vs world", "value": "world"},
                                    {"label": "Two-year comparison", "value": "change"},
                                ],
                                value="world",
                                className="radio-row",
                            ),
                        ),
                        html.Div(
                            className="m4-detail-controls",
                            children=[
                                field(
                                    "Focus economy",
                                    dcc.Dropdown(
                                        id=cid("focus"),
                                        options=[],
                                        value="CHN",
                                        clearable=False,
                                        className="ctl-dropdown",
                                    ),
                                ),
                                field(
                                    "Inspect a product",
                                    dcc.Dropdown(
                                        id=cid("inspect"),
                                        options=products,
                                        value="85",
                                        clearable=False,
                                        className="ctl-dropdown",
                                    ),
                                ),
                                field(
                                    "Baseline · used in two-year view",
                                    dcc.Dropdown(
                                        id=cid("baseline"),
                                        options=[
                                            {"label": str(y), "value": y}
                                            for y in range(1995, 2025)
                                        ],
                                        value=2010,
                                        clearable=False,
                                        className="ctl-dropdown",
                                    ),
                                ),
                            ],
                        ),
                        html.Div(id=cid("detail-note"), className="m4-note"),
                        graph("detail"),
                        html.Div(id=cid("cell-stats"), className="m4-kpis"),
                    ]
                ),
                extra_class="m4-chart",
            ),
            components.card(
                "Finding / Implication / Limits",
                html.Div(
                    className="m4-findings",
                    children=[
                        html.Article([html.H4(title), html.P(id=cid(key))])
                        for title, key in [
                            ("Finding", "evidence"),
                            ("Implication", "conclusion"),
                            ("Limits", "limits"),
                        ]
                    ],
                ),
            ),
            html.Details(
                className="card m4-method",
                children=[
                    html.Summary("Methods, coverage & evidence downloads"),
                    html.P(
                        "Share = product exports / the economy’s all-product exports. RCA = economy product share / same-year world product share. RCA > 1 indicates relative specialization, not technology, productivity or causation."
                    ),
                    html.P(
                        "World totals include all recorded BACI exporters, including special/historical entities. Display selection never changes the world reference. Amounts are thousand current USD; goods only, not services or domestic value added. HS85 is broader than chips; HS87 is broader than cars."
                    ),
                    html.P(
                        "Income: CHELEM GDP-CAP in current USD/person. The default Overview candidate pool is the union of annual Top10 exporters after metadata matching, not an S-prefix filter. Matching retains positive same-year GDP-CAP within the displayed multiplicative range; at most six nearest log ratios are shown. The complete qualified list and a 1.25/1.5 sensitivity comparison are reported below. This is an exploratory rule, not an official income grouping or control for other country differences."
                    ),
                    html.P(
                        "Income comparisons use 1995–2023 only: this release’s CHELEM trade data end in 2023 and later GDP values may be projections/IMF estimates. Historical estimates can remain; the source has no per-cell status flags, so historical values are not certified final observations. Income mode at 2024 produces a notice and no matched group; it never substitutes a previous year. BACI-only analysis still extends to 2024."
                    ),
                    html.P(
                        "Two-year view fixes the focus economy and chapter set, uses each year’s complete world denominator, and subtracts baseline share from current share in percentage points. Missing endpoints remain unknown. Two observations do not establish a continuous trend or event effect. Income peers are recalculated when the year changes; never mistake changing peers for fixed-sample change."
                    ),
                    html.Div(id=cid("audit-note"), className="m4-note"),
                    html.Div(
                        [
                            html.A(
                                "BACI",
                                href="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
                                target="_blank",
                            ),
                            " · ",
                            html.A(
                                "CHELEM / income policy",
                                href="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=17",
                                target="_blank",
                            ),
                            " · ",
                            html.A(
                                "HS1992 titles",
                                href="https://comtradeapi.un.org/files/v1/app/reference/H0.json",
                                target="_blank",
                            ),
                        ]
                    ),
                    html.Button(
                        "Download heatmap evidence (CSV)",
                        id=cid("download-button"),
                        n_clicks=0,
                        className="m4-button",
                    ),
                    dcc.Download(id=cid("download")),
                    table(
                        "table",
                        [
                            ("year", "Year"),
                            ("country", "Economy"),
                            ("hs2", "HS2"),
                            ("product", "Product"),
                            ("value", "Thousand USD"),
                            ("share_pct", "Export share %"),
                            ("world_pct", "World share %"),
                            ("rca", "RCA"),
                        ],
                    ),
                    html.Button(
                        "Download detail / two-year evidence (CSV)",
                        id=cid("detail-download-button"),
                        n_clicks=0,
                        className="m4-button",
                    ),
                    dcc.Download(id=cid("detail-download")),
                    table(
                        "detail-table",
                        [
                            ("country", "Economy"),
                            ("hs2", "HS2"),
                            ("baseline", "Baseline"),
                            ("year", "Current year"),
                            ("base_share_pct", "Baseline share %"),
                            ("current_share_pct", "Current share %"),
                            ("change_pp", "Change (pp)"),
                            ("base_rca", "Baseline RCA"),
                            ("current_rca", "Current RCA"),
                            ("missing_endpoint", "Missing endpoint"),
                        ],
                    ),
                ],
            ),
        ],
    )


@lru_cache(maxsize=1)
def trade():
    d = data_loader.load_exporter_hs2_year()
    validate_trade(d)
    return d


@lru_cache(maxsize=30)
def metrics(year):
    return year_metrics(trade(), year)


def names():
    return dict(
        zip(data_loader.load_country_meta().iso3, data_loader.load_country_meta().name)
    )


def eligible(d):
    # Restrict selectable cases to audited metadata, not an S-prefix test.
    return sorted(set(d.exporter) & set(names()))


def base_style(fig, height):
    theme.style_figure(fig, height=height)
    fig.update_layout(
        font=dict(family="Segoe UI, system-ui, sans-serif", size=12, color=theme.INK),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=16, r=20, t=36, b=45),
    )
    return fig


def heat_figure(d, countries, products, metric):
    if not countries or not products:
        return theme.empty_figure("No recorded products for this comparison.")
    ix = pd.MultiIndex.from_product([products, countries], names=["hs2", "exporter"])
    a = d.set_index(["hs2", "exporter"]).reindex(ix)
    n = len(countries)
    vals = a[metric].to_numpy().reshape(-1, n)
    share = a.share.to_numpy().reshape(-1, n) * 100
    rca = a.rca.to_numpy().reshape(-1, n)
    z = vals * 100 if metric == "share" else np.log2(np.maximum(vals, 1e-12))
    text = np.array(
        [
            (
                "—"
                if not np.isfinite(v)
                else (
                    ("<0.1%" if 0 < v < 0.001 else f"{v*100:.1f}%")
                    if metric == "share"
                    else ("<0.01" if 0 < v < 0.01 else f"{v:.2f}")
                )
            )
            for v in vals.flat
        ]
    ).reshape(-1, n)
    custom = []
    for p in products:
        row = []
        for c in countries:
            r = a.loc[(p, c)]
            row.append(
                [
                    c,
                    p,
                    chapters().get(p, p),
                    r.value,
                    r.share * 100,
                    r.world_share * 100,
                    r.rca,
                ]
            )
        custom.append(row)
    fig = go.Figure(
        go.Heatmap(
            x=countries,
            y=products,
            z=z,
            customdata=custom,
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=12),
            zmin=0 if metric == "share" else -3,
            zmax=50 if metric == "share" else 3,
            colorscale=(
                [[0, "#f0f6fc"], [0.2, "#cfdeef"], [0.5, "#699bc8"], [1, "#124576"]]
                if metric == "share"
                else [[0, "#a85828"], [0.5, "#faf8f3"], [1, "#176b83"]]
            ),
            colorbar=dict(
                title="Share %" if metric == "share" else "RCA",
                thickness=12,
                len=0.8,
                tickvals=(
                    [0, 10, 20, 30, 40, 50]
                    if metric == "share"
                    else [-3, -2, -1, 0, 1, 2, 3]
                ),
                ticktext=(
                    ["0", "10", "20", "30", "40", "≥50"]
                    if metric == "share"
                    else ["≤0.125", "0.25", "0.5", "1", "2", "4", "≥8"]
                ),
            ),
            xgap=3,
            ygap=3,
            hoverongaps=False,
            hovertemplate="<b>%{customdata[0]} · HS%{customdata[1]}</b><br>%{customdata[2]}<br>Exports: %{customdata[3]:,.0f} thousand USD<br>Economy share: %{customdata[4]:.2f}%<br>World share: %{customdata[5]:.2f}%<br>RCA: %{customdata[6]:.3f}<extra></extra>",
        )
    )
    base_style(fig, max(370, 110 + 34 * len(products)))
    ticks = [label(p) for p in products]
    # Wrap long UN descriptions without concealing their codes.
    ticks = ["<br>".join(wrap(s, 34)) for s in ticks]
    fig.update_layout(
        plot_bgcolor="#e8edf2",
        margin=dict(l=20, r=22, t=60, b=20),
        xaxis=dict(
            side="top",
            tickmode="array",
            tickvals=countries,
            ticktext=[f"<b>{c}</b>" for c in countries],
            fixedrange=True,
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=products,
            ticktext=ticks,
            autorange="reversed",
            automargin=True,
            fixedrange=True,
        ),
    )
    return fig


def detail_figure(d, focus, product):
    a = d[d.exporter.eq(focus)].sort_values(["value", "hs2"], ascending=[False, True])
    if a.empty:
        return theme.empty_figure(
            "This economy has no recorded exports in the selected year."
        )
    codes = list(a.head(8).hs2)
    if product not in codes and product in set(d.hs2):
        codes.append(product)
    w = d.drop_duplicates("hs2").set_index("hs2").world_share
    local = a.set_index("hs2").share.reindex(codes)
    fig = go.Figure()
    for name, values, color in [
        (focus, local, theme.ACCENT),
        ("World", w.reindex(codes), "#90a5b8"),
    ]:
        fig.add_trace(
            go.Bar(
                name=name,
                x=values * 100,
                y=codes,
                orientation="h",
                marker_color=color,
                text=[
                    (
                        ("<0.1%" if 0 < v < 0.001 else f"{v*100:.1f}%")
                        if pd.notna(v)
                        else "—"
                    )
                    for v in values
                ],
                textposition="outside",
                cliponaxis=False,
                hovertemplate=name
                + " · HS%{y}<br>%{x:.2f}% of all-product exports<extra></extra>",
            )
        )
    base_style(fig, max(390, 105 + 42 * len(codes)))
    fig.update_layout(
        barmode="group",
        bargap=0.25,
        legend=dict(orientation="h", y=1.12, x=0),
        xaxis=dict(
            title="Share of all-product exports (%)", rangemode="tozero", ticksuffix="%"
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=codes,
            ticktext=["<br>".join(wrap(label(p), 32)) for p in codes],
            autorange="reversed",
            automargin=True,
        ),
        margin=dict(l=20, r=55, t=50, b=45),
    )
    return fig


@lru_cache(maxsize=1)
def overview_pool():
    return candidate_pool(data_loader.load_country_year(), eligible(trade()))


def recipe(step):
    settings = STEPS[step]
    products = sorted(set(product_set(metrics(2023), DEFAULTS)) | {"31"})
    return dict(
        settings,
        step=step,
        year=2023,
        anchor="CHN",
        products=products,
        baseline=2010,
        pool="overview",
        factor=1.25,
    )


def number(value, digits=6):
    return (
        round(float(value), digits) if pd.notna(value) and np.isfinite(value) else None
    )


def context_metadata(comparison):
    return {
        k: comparison.get(k)
        for k in [
            "year",
            "baseline",
            "comparison_mode",
            "selection_state",
            "case_step",
            "income_factor",
            "income_anchor",
            "income_status",
            "candidate_pool",
            "source_version",
            "reference_scope",
            "value_unit",
        ]
    }


def comparison_figure(rows, baseline, year):
    if rows.empty:
        return theme.empty_figure(
            "Select products recorded in at least one comparison year."
        )
    rows = rows.sort_values(
        ["change_pp", "hs2"], ascending=[False, True], na_position="last"
    )
    fig = go.Figure()
    for suffix, title, color in [
        ("base", str(baseline), "#90a5b8"),
        ("current", str(year), theme.ACCENT),
    ]:
        vals = rows["share_" + suffix] * 100
        custom = [
            [r.hs2, number(getattr(r, "rca_" + suffix)), number(r.change_pp)]
            for r in rows.itertuples()
        ]
        fig.add_trace(
            go.Bar(
                name=title,
                x=vals,
                y=rows.hs2,
                orientation="h",
                marker_color=color,
                customdata=custom,
                text=[
                    ("—" if pd.isna(v) else "<0.1%" if 0 < v < 0.1 else f"{v:.1f}%")
                    for v in vals
                ],
                textposition="outside",
                cliponaxis=False,
                hovertemplate=title
                + " · HS%{y}<br>Share: %{x:.3f}%<br>RCA: %{customdata[1]}<br>Current − baseline: %{customdata[2]} pp<extra></extra>",
            )
        )
    base_style(fig, max(390, 110 + 43 * len(rows)))
    fig.update_layout(
        barmode="group",
        legend=dict(orientation="h", y=1.12),
        bargap=0.25,
        margin=dict(l=20, r=55, t=50, b=45),
        xaxis=dict(
            title="Share of all-product exports (%)", rangemode="tozero", ticksuffix="%"
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=list(rows.hs2),
            ticktext=["<br>".join(wrap(label(p), 32)) for p in rows.hs2],
            autorange="reversed",
            automargin=True,
        ),
    )
    return fig


def register_callbacks(app):
    @app.callback(
        Output(cid("case"), "data"),
        Output(cid("intent"), "data"),
        Input(ACTIVE_MODULE, "data"),
        Input(cid("step-structure"), "n_clicks"),
        Input(cid("step-specialization"), "n_clicks"),
        Input(cid("step-change"), "n_clicks"),
        Input(cid("reset"), "n_clicks"),
        State(cid("case"), "data"),
        State(GLOBAL_FILTERS, "data"),
    )
    def apply_case(active, first, second, third, reset, current, filters):
        guard_active(MODULE_ID, active)
        trigger = ctx.triggered_id
        if trigger == ACTIVE_MODULE and current:
            return no_update, no_update
        filters = filters or {}
        if (
            trigger == ACTIVE_MODULE
            and not current
            and (
                filters.get("year", 2024) != 2024
                or filters.get("country", "CHN") != "CHN"
                or filters.get("product", "TOTAL") != "TOTAL"
            )
        ):
            # Preserve an explicit Overview/global selection on first entry.
            country = filters.get("country", "CHN")
            entry = dict(
                recipe("structure"),
                step="entry",
                mode="selected",
                countries=[country] if country in eligible(trade()) else [],
                products=PRODUCT_GROUPS.get(filters.get("product"), []),
                year=filters.get("year", 2024),
                anchor=country,
                focus=country,
            )
            return entry, no_update
        key = (
            "change"
            if trigger == cid("step-change")
            else (
                "specialization"
                if trigger == cid("step-specialization")
                else "structure"
            )
        )
        r = recipe(key)
        r["request_id"] = sum(n or 0 for n in [first, second, third, reset])
        return r, {
            "source": "M4",
            "year": r["year"],
            "country": r["anchor"],
            "product": "TOTAL",
            "step": key,
            "request_id": r["request_id"],
        }

    @app.callback(
        Output(cid("countries"), "options"),
        Output(cid("countries"), "value"),
        Output(cid("products"), "value"),
        Output(cid("global-context"), "data"),
        Output(cid("mode"), "value"),
        Output(cid("metric"), "value"),
        Output(cid("pool"), "value"),
        Output(cid("factor"), "value"),
        Output(cid("detail-view"), "value"),
        Output(cid("baseline"), "value"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        Input(cid("case"), "data"),
        State(cid("countries"), "value"),
        State(cid("products"), "value"),
        State(cid("global-context"), "data"),
    )
    def sync(filters, active, case, current, products, previous):
        guard_active(MODULE_ID, active)
        filters = filters or {}
        previous = previous or {}
        opts = eligible(trade())
        ns = names()
        glob = filters.get("country", "CHN")
        apply = case and (ctx.triggered_id == cid("case") or not previous)
        extras = [no_update] * 6
        if apply:
            current = case["countries"]
            products = case["products"]
            extras = [
                case["mode"],
                case["metric"],
                case["pool"],
                case["factor"],
                case["view"],
                case["baseline"],
            ]
        else:
            if previous.get("country") != glob and glob in opts:
                current = [glob] + [c for c in (current or []) if c != glob][:5]
            if previous.get("product") != filters.get("product"):
                products = PRODUCT_GROUPS.get(filters.get("product"), [])
        return (
            [{"label": f"{ns.get(c,c)} ({c})", "value": c} for c in opts],
            [c for c in (current or []) if c in opts],
            products,
            {"country": glob, "product": filters.get("product")},
            *extras,
        )

    @app.callback(
        Output(cid("focus"), "options"),
        Output(cid("countries"), "disabled"),
        Output(cid("scope"), "children"),
        Output(cid("kpis"), "children"),
        Output(cid("graph"), "figure"),
        Output(cid("graph"), "style"),
        Output(cid("heat-note"), "children"),
        Output(cid("table"), "data"),
        Output(cid("evidence"), "children"),
        Output(cid("conclusion"), "children"),
        Output(cid("limits"), "children"),
        Output(cid("question"), "children"),
        Output(cid("audit-note"), "children"),
        Output(cid("comparison"), "data"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        Input(cid("countries"), "value"),
        Input(cid("products"), "value"),
        Input(cid("metric"), "value"),
        Input(cid("mode"), "value"),
        Input(cid("pool"), "value"),
        Input(cid("factor"), "value"),
        Input(cid("case"), "data"),
        Input(cid("baseline"), "value"),
        Input(cid("detail-view"), "value"),
    )
    def overview(
        filters,
        active,
        selected,
        requested,
        metric,
        mode,
        pool,
        factor,
        case,
        baseline,
        detail_view,
    ):
        guard_active(MODULE_ID, active)
        filters = filters or {}
        year = int(filters.get("year", 2024))
        baseline = int(baseline or 2010)
        factor = float(factor or 1.25)
        pool = pool or "overview"
        mode = mode or "selected"
        metric = metric or "share"
        d = metrics(year)
        ns = names()
        messages = []
        gdp_values = {}
        qualified = []
        sensitivity = {}
        anchor = filters.get("country", "CHN")
        income_status = "Not used"
        cases = case or {}
        chosen = list(dict.fromkeys(selected or []))[:6]
        if len(selected or []) > 6:
            messages.append(
                "First six manual selections shown; reduce the list to include different cases."
            )
        candidates = overview_pool() if pool == "overview" else eligible(d)
        candidates = sorted(
            set(candidates) | ({anchor} if anchor in eligible(d) else set())
        )
        if mode == "income":
            chosen = []
            g = data_loader.load_gdp_year()
            if not income_allowed(year):
                income_status = "Excluded: outside historical comparison window"
                messages.append(
                    f"Income matching unavailable for {year}. This CHELEM release is restricted to 1995–2023; no previous-year GDP is substituted. Select a historical year or manual economies for BACI-only analysis."
                )
            elif g.attrs.get("demo", True) or trade().attrs.get("demo", True):
                income_status = "Unavailable: synthetic input"
                messages.append(
                    "Income analysis requires both real trade and real GDP inputs."
                )
            elif anchor == "WLD":
                income_status = "Unavailable: select an economy"
                messages.append(
                    "Select an individual global country as the income anchor; World is not an economy."
                )
            else:
                all_peers, peer_rows, base = income_peers(
                    g, year, anchor, candidates, factor=factor, limit=10000
                )
                qualified = all_peers
                chosen = all_peers[:6]
                gdp_values = {
                    r.country: float(r.income) for r in peer_rows.itertuples()
                }
                income_status = "Historical window; historical estimates may remain"
                if base is None:
                    messages.append(
                        f"No positive same-year GDP-CAP for {anchor}; no year substitution."
                    )
                else:
                    messages.append(
                        f"Income anchor {anchor}: ${base:,.0f}/person; range ${base/factor:,.0f}–${base*factor:,.0f}. "
                        + ", ".join(f"{c} ${gdp_values[c]:,.0f}" for c in chosen)
                        + f". {len(all_peers)} qualify; at most 6 nearest log ratios shown."
                    )
                    for f in [1.25, 1.5]:
                        sensitivity[str(f)] = income_peers(
                            g, year, anchor, candidates, factor=f, limit=10000
                        )[0]
        missing = [c for c in chosen if c not in set(d.exporter)]
        chosen = [c for c in chosen if c in set(d.exporter)]
        if missing:
            messages.append("No recorded trade this year: " + ", ".join(missing) + ".")
        products = product_set(d, chosen, requested)
        absent = sorted(set(requested or []) - set(products))
        if absent:
            messages.append(
                "No same-year world observations for chapters "
                + ", ".join(absent)
                + "."
            )
        guided = (
            bool(case)
            and cases.get("step") in STEPS
            and year == cases.get("year")
            and anchor == cases.get("anchor")
            and filters.get("product", "TOTAL") == "TOTAL"
            and mode == cases.get("mode")
            and metric == cases.get("metric")
            and pool == cases.get("pool")
            and factor == cases.get("factor")
            and set(products) == set(cases.get("products", []))
            and set(chosen) == set(cases.get("countries", []))
            and (
                cases.get("view") != "change"
                or (baseline == cases.get("baseline") and detail_view == "change")
            )
        )
        state = "Guided case" if guided else "Custom exploration"
        context = {
            "year": year,
            "baseline": baseline,
            "detail_view": detail_view,
            "countries": chosen,
            "products": products,
            "metric": metric,
            "comparison_mode": mode,
            "selection_state": state,
            "case_step": cases.get("step") if guided else "custom",
            "income_factor": factor if mode == "income" else None,
            "income_anchor": anchor if mode == "income" else None,
            "income_status": income_status,
            "gdp": gdp_values,
            "candidate_pool": pool if mode == "income" else "Manual selection",
            "qualified_candidates": qualified,
            "sensitivity": sensitivity,
            "source_version": "BACI HS92 V202601 / CHELEM GDP V202502",
            "reference_scope": "All BACI exporters and products, same-year world denominator",
            "value_unit": "thousand current USD",
        }
        demo = bool(trade().attrs.get("demo", True))
        mode_label = (
            "SYNTHETIC DEMO — not research evidence"
            if demo
            else "BACI HS92 · real data"
        )
        scope = (
            f"{state} · {year} · {mode_label} · {len(chosen)} economies · {len(products)} displayed chapters. "
            + " ".join(messages)
        )
        if mode == "income":
            scope += " Historical estimates may remain. Manual economy list inactive."
        if filters.get("indicator") not in [None, "export_value"]:
            scope += " Heatmap measure follows the local Share/RCA selector."
        if not chosen:
            scope += " Choose a valid comparison."
        world = d.value.sum()
        coverage = d[d.exporter.isin(chosen)].value.sum() / world if world else 0
        all_selected = d[d.exporter.isin(chosen)].value.sum()
        shown = d[d.exporter.isin(chosen) & d.hs2.isin(products)]
        product_coverage = shown.value.sum() / all_selected if all_selected else 0
        cards = components.kpi_row(
            [
                ("Displayed economies", str(len(chosen))),
                ("Economies / world exports", f"{coverage:.1%}"),
                ("Shown chapters / selected exports", f"{product_coverage:.1%}"),
            ]
        )
        figure = heat_figure(d, chosen, products, metric)
        note = (
            "Fixed chapters from the income-case economies’ Top5, including HS31; retained across guided steps. "
            if guided
            else "Displayed chapter scope; all-product reference totals stay fixed. "
        ) + (
            "Share colours saturate at 50%; values above 50% are retained."
            if metric == "share"
            else "RCA colours use log₂ centred at 1, saturating below 0.125 / above 8. Cell numbers and hover retain actual values."
        )
        records = []
        lookup = shown.set_index(["exporter", "hs2"])
        meta = context_metadata(context)
        for c in chosen:
            for p in products:
                r = lookup.loc[(c, p)] if (c, p) in lookup.index else None
                world_share = d.loc[d.hs2.eq(p), "world_share"].iloc[0]
                records.append(
                    dict(
                        meta,
                        country=c,
                        hs2=p,
                        product=chapters().get(p, p),
                        value=number(r.value) if r is not None else None,
                        share_pct=number(r.share * 100) if r is not None else None,
                        world_pct=number(world_share * 100),
                        rca=number(r.rca) if r is not None else None,
                        gdp_cap=gdp_values.get(c),
                        missing_record=r is None,
                        income_candidates="|".join(qualified),
                    )
                )
        finding = "No valid comparison selected."
        implication = "Select a comparison to inspect its composition and relative specialization."
        spread = spread_finding(d, chosen, products)
        if spread:
            f = spread
            finding = f'Within the displayed chapters recorded for every shown economy, HS{f["hs2"]} has the largest share difference: {f["high"]} {f["high_share"]:.1%} vs {f["low"]} {f["low_share"]:.1%} ({f["spread_pp"]:.1f} pp).'
            implication = "The displayed export baskets differ. Compare Share with RCA to separate domestic importance from specialization against the world."
            if mode == "income":
                implication = "Within this income-matched sample, similar nominal GDP per person does not imply the same export basket. Product structure adds information beyond this income comparison."
        elif len(chosen) == 1:
            finding = f"{chosen[0]} is selected; add another economy for a cross-country finding."
        if guided and cases.get("step") == "specialization":
            a = d[d.exporter.eq("RUS")].set_index("hs2")
            if {"27", "31"} <= set(a.index) & set(products):
                x = a.loc["27"]
                y = a.loc["31"]
                finding = f"RUS HS27: share {x.share:.2%}, RCA {x.rca:.2f}; HS31: share {y.share:.2%}, RCA {y.rca:.2f}."
                implication = (
                    "Fertilizers have a smaller export share but a higher RCA than fuels in this case. A large domestic share and strong relative specialization answer different questions."
                    if y.share < x.share and y.rca > x.rca
                    else "The current values do not support the preset share/RCA reversal; inspect the displayed evidence."
                )
        if guided and cases.get("step") == "change":
            evidence = []
            for c in chosen:
                r = two_year_metrics(trade(), c, year, baseline, ["87"]).iloc[0]
                if not r.missing_endpoint:
                    evidence.append(
                        f"{c} HS87 share {r.share_base:.2%} → {r.share_current:.2%}; RCA {r.rca_base:.3f} → {r.rca_current:.3f}"
                    )
            finding = f"{baseline} → {year}: " + "; ".join(evidence) + "."
            implication = "Compare both the share change and RCA = 1. A rising share need not mean specialization above the world benchmark; check each economy in the two-year detail view."
        limits = "Descriptive evidence for this sample and displayed chapters, not a causal or population-wide test. HS2 is broad; nominal goods values include price, exchange-rate and re-export effects."
        if mode == "income":
            limits += " Income matching is a heuristic using current USD/person; historical estimates may remain. Peers can change by year."
        if guided and cases.get("step") == "change":
            limits += " The 2010 sample is fixed, not asserted to have similar incomes then. Two endpoints do not establish a continuous trend or event effect."
        if demo:
            finding = "Synthetic demonstration only. " + finding
        question = html.Div(
            [
                html.Span(state, className="m4-badge"),
                html.H3(
                    cases["question"]
                    if guided
                    else "What does your selected comparison show?"
                ),
                html.P(
                    cases["action"]
                    if guided
                    else "Your conditions differ from the preset. Findings below are recomputed for this selection."
                ),
            ]
        )
        audit = (
            f"Income candidates ({len(candidates)}): "
            + ", ".join(candidates)
            + ". Qualified: "
            + (", ".join(qualified) or "not applicable")
            + ". "
        )
        if sensitivity:
            audit += (
                "Sensitivity, complete qualified sets: "
                + "; ".join(f"{k}×: " + ", ".join(v) for k, v in sensitivity.items())
                + "."
            )
        return (
            [{"label": f"{ns.get(c,c)} ({c})", "value": c} for c in chosen],
            mode == "income",
            scope,
            cards,
            figure,
            {"height": f"{figure.layout.height}px"},
            note,
            records,
            finding,
            implication,
            limits,
            question,
            audit,
            context,
        )

    @app.callback(
        Output(cid("focus"), "value"),
        Output(cid("inspect"), "value"),
        Output(cid("detail-context"), "data"),
        Input(cid("graph"), "clickData"),
        Input(cid("comparison"), "data"),
        Input(cid("case"), "data"),
        Input(ACTIVE_MODULE, "data"),
        State(cid("focus"), "value"),
        State(cid("inspect"), "value"),
        State(cid("detail-context"), "data"),
    )
    def select(click, comparison, case, active, focus, product, previous):
        guard_active(MODULE_ID, active)
        comparison = comparison or {}
        case = case or {}
        valid = comparison.get("countries", [])
        previous = previous or {}
        step = case.get("step")
        context = {"step": step}
        if ctx.triggered_id == cid("graph") and click:
            pt = click["points"][0]
            c, p = pt.get("x"), pt.get("y")
            v = pt.get("customdata")
            if c is None and v:
                c, p = v[0], v[1]
            if c in valid and p in chapters():
                return c, p, context
        if previous.get("step") != step or ctx.triggered_id == cid("case"):
            focus = case.get("focus")
            product = case.get("product", "85")
        focus = focus if focus in valid else valid[0] if valid else None
        return focus, product or "85", context

    @app.callback(
        Output(cid("detail"), "figure"),
        Output(cid("detail"), "style"),
        Output(cid("detail-note"), "children"),
        Output(cid("cell-stats"), "children"),
        Output(cid("detail-table"), "data"),
        Input(cid("focus"), "value"),
        Input(cid("inspect"), "value"),
        Input(cid("comparison"), "data"),
        Input(cid("detail-view"), "value"),
        Input(cid("baseline"), "value"),
        Input(ACTIVE_MODULE, "data"),
    )
    def detail(c, p, comparison, view, baseline, active):
        guard_active(MODULE_ID, active)
        comparison = comparison or {}
        year = int(comparison.get("year", 2023))
        baseline = int(baseline or 2010)
        p = p or "85"
        d = metrics(year)
        a = d[d.exporter.eq(c)]
        if not c or c not in comparison.get("countries", []):
            return (
                theme.empty_figure("Choose a focus economy with data."),
                {"height": "420px"},
                "No valid focus economy.",
                [],
                [],
            )
        if view == "change":
            if baseline >= year:
                return (
                    theme.empty_figure(
                        "Choose a baseline earlier than the current year."
                    ),
                    {"height": "420px"},
                    f"Baseline {baseline} must precede {year}. No change is computed.",
                    [],
                    [],
                )
            codes = list(dict.fromkeys(comparison.get("products", []) + [p]))
            rows = two_year_metrics(trade(), c, year, baseline, codes)
            figure = comparison_figure(rows, baseline, year)
            note = f"{names().get(c,c)} ({c}) · {baseline} vs {year}. Fixed displayed chapters plus HS{p}; sorted by share change (pp). Each year uses its own full world reference. Missing endpoints are not filled."
        else:
            if a.empty:
                return (
                    theme.empty_figure("No recorded exports for this economy-year."),
                    {"height": "420px"},
                    "No recorded exports.",
                    [],
                    [],
                )
            figure = detail_figure(d, c, p)
            codes = list(figure.data[0].y)
            rows = two_year_metrics(trade(), c, year, baseline, codes)
            note = f"{names().get(c,c)} ({c}) · {year} · HS{p}. Top8 chapters by exports plus inspected chapter; same-year economy and world shares. Other chapters remain in the denominators."
        r = rows[rows.hs2.eq(p)]
        stats = []
        if not r.empty:
            r = r.iloc[0]
            if view == "change":
                stats = components.kpi_row(
                    [
                        ("Inspected chapter", f"HS{p}"),
                        (
                            "Share change",
                            (
                                f"{r.change_pp:+.2f} pp"
                                if pd.notna(r.change_pp)
                                else "Unknown"
                            ),
                        ),
                        (
                            f"RCA · {baseline}",
                            (
                                f"{r.rca_base:.3f}"
                                if pd.notna(r.rca_base)
                                else "No record"
                            ),
                        ),
                        (
                            f"RCA · {year}",
                            (
                                f"{r.rca_current:.3f}"
                                if pd.notna(r.rca_current)
                                else "No record"
                            ),
                        ),
                    ]
                )
            else:
                stats = components.kpi_row(
                    [
                        (
                            "Exports · current USD",
                            (
                                theme.fmt_usd(r.value_current)
                                if pd.notna(r.value_current)
                                else "No record"
                            ),
                        ),
                        (
                            "Export share",
                            (
                                f"{r.share_current:.2%}"
                                if pd.notna(r.share_current)
                                else "No record"
                            ),
                        ),
                        (
                            "World share",
                            (
                                f"{r.world_share_current:.2%}"
                                if pd.notna(r.world_share_current)
                                else "No record"
                            ),
                        ),
                        (
                            "RCA",
                            (
                                f"{r.rca_current:.3f}"
                                if pd.notna(r.rca_current)
                                else "No record"
                            ),
                        ),
                    ]
                )
        records = []
        meta = context_metadata(comparison)
        for r in rows.itertuples():
            records.append(
                dict(
                    meta,
                    baseline=baseline if view == "change" else None,
                    country=c,
                    hs2=r.hs2,
                    product=chapters().get(r.hs2, r.hs2),
                    detail_view=view,
                    base_value=number(r.value_base) if view == "change" else None,
                    current_value=number(r.value_current),
                    base_share_pct=(
                        number(r.share_base * 100) if view == "change" else None
                    ),
                    current_share_pct=number(r.share_current * 100),
                    base_world_pct=(
                        number(r.world_share_base * 100) if view == "change" else None
                    ),
                    current_world_pct=number(r.world_share_current * 100),
                    change_pp=number(r.change_pp) if view == "change" else None,
                    base_rca=number(r.rca_base) if view == "change" else None,
                    current_rca=number(r.rca_current),
                    missing_endpoint=(
                        bool(r.missing_endpoint)
                        if view == "change"
                        else pd.isna(r.share_current)
                    ),
                    gdp_cap=comparison.get("gdp", {}).get(c),
                )
            )
        return figure, {"height": f"{figure.layout.height}px"}, note, stats, records

    @app.callback(
        Output(cid("download"), "data"),
        Input(cid("download-button"), "n_clicks"),
        State(cid("table"), "data"),
        prevent_initial_call=True,
    )
    def download(n, rows):
        return dcc.send_data_frame(
            pd.DataFrame(rows or []).to_csv, "M4_heatmap_evidence.csv", index=False
        )

    @app.callback(
        Output(cid("detail-download"), "data"),
        Input(cid("detail-download-button"), "n_clicks"),
        State(cid("detail-table"), "data"),
        prevent_initial_call=True,
    )
    def download_detail(n, rows):
        return dcc.send_data_frame(
            pd.DataFrame(rows or []).to_csv, "M4_detail_evidence.csv", index=False
        )

    @app.callback(
        [Output(cid("step-" + key), "className") for key in STEPS]
        + [Output(cid("baseline"), "disabled")],
        Input(cid("comparison"), "data"),
    )
    def step_styles(comparison):
        step = (comparison or {}).get("case_step")
        return ["m4-step on" if step == key else "m4-step" for key in STEPS] + [
            (comparison or {}).get("detail_view", "world") != "change"
        ]
