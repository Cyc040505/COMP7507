"""M4: product composition, relative specialization and comparable-income peers."""

from functools import lru_cache
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from textwrap import wrap
from dash import Input, Output, State, ctx, dcc, html, dash_table, no_update
from src import components, data_loader, theme
from src.analytics.product import (
    chapters,
    label,
    validate_trade,
    year_metrics,
    product_set,
    income_peers,
)
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active

MODULE_ID = "M4"
NAV_LABEL = "M4  Product Structure"
ORDER = 4
DEFAULTS = ["CHN", "DEU", "USA"]
# Explicit sets match the existing shell labels. They locate rows, never redefine totals.
PRODUCT_GROUPS = {
    "HS84": ["84", "85"],
    "HS87": ["87"],
    "HS28": [f"{p:02}" for p in range(28, 39)],
    "HS61": ["61", "62"],
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


def cid(s):
    return mid(MODULE_ID, s)


def graph(s):
    return dcc.Graph(
        id=cid(s),
        figure=theme.empty_figure("Select M4 to explore product structure."),
        config=GRAPH_CONFIG,
    )


def field(title, widget):
    return html.Div(
        [html.Label(title, htmlFor=widget.id), widget], className="m4-field"
    )


def layout():
    return html.Div(
        className="module-inner m4",
        children=[
            dcc.Store(id=cid("global-context")),
            dcc.Store(id=cid("detail-context")),
            html.Div(
                className="m4-intro",
                children=[
                    html.Div("STRUCTURE / M4", className="m4-eyebrow"),
                    html.H2("What countries sell — and where they specialize"),
                    html.P(
                        "Compare export composition, then test whether large categories also stand out against the world."
                    ),
                ],
            ),
            html.Div(
                className="module-controls m4-controls",
                children=[
                    field(
                        "Comparison",
                        dcc.RadioItems(
                            id=cid("mode"),
                            options=[
                                {"label": "Selected economies", "value": "selected"},
                                {"label": "Similar income", "value": "income"},
                            ],
                            value="selected",
                            className="radio-row",
                        ),
                    ),
                    field(
                        "Economies · choose up to 6",
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
                        "Measure",
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
                    field(
                        "Products · blank = union of each economy’s top 5",
                        dcc.Dropdown(
                            id=cid("products"),
                            multi=True,
                            options=[
                                {"label": label(p), "value": p}
                                for p in sorted(chapters())
                                if p not in ["77", "99"]
                            ],
                            placeholder="Search HS2 chapter, or leave blank for key products",
                            className="ctl-dropdown",
                        ),
                    ),
                    html.Button(
                        "Reset comparison",
                        id=cid("reset"),
                        n_clicks=0,
                        className="m4-button",
                    ),
                ],
            ),
            html.Div(id=cid("scope"), className="m4-scope", role="status"),
            html.Div(id=cid("kpis"), className="m4-kpis"),
            components.card(
                "01 / Compare the same products across economies",
                html.Div(
                    [
                        html.Div(id=cid("heat-note"), className="m4-note"),
                        graph("graph"),
                        html.P(
                            "Click a cell to inspect it below, or use the detail selectors. Grey cells mean no recorded value; they are not assumed zero.",
                            className="m4-note",
                        ),
                    ]
                ),
                extra_class="m4-chart",
            ),
            components.card(
                "02 / Inspect composition against the world",
                html.Div(
                    [
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
                                        options=[
                                            {"label": label(p), "value": p}
                                            for p in sorted(chapters())
                                            if p not in ["77", "99"]
                                        ],
                                        value="85",
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
            components.verification_panel(
                "Export product structures differ across economies; compare both composition and relative specialization. Similar-income mode addresses the income comparison in H3.",
                "Select a comparison to inspect evidence.",
                "No causal interpretation is implied.",
                evidence_id=cid("evidence"),
                conclusion_id=cid("conclusion"),
            ),
            html.Details(
                className="card m4-method",
                children=[
                    html.Summary("Definitions, data coverage & downloadable evidence"),
                    html.P(
                        "Share = product exports / the economy’s all-product exports. RCA = that share / the same-year world product share. RCA > 1 means relative specialization, not technological superiority."
                    ),
                    html.P(
                        "World reference includes every exporter and recorded product in the BACI input, including special/historical entities; selecting economies or products never changes it. Amounts are nominal, thousand current USD. Goods only; HS2 categories are broad, and HS85 is not synonymous with chips."
                    ),
                    html.P(
                        "Similar income: same-year CHELEM GDP-CAP in current USD, within 1/1.5 to 1.5 times the focus economy. At most six closest log ratios are shown. This is a comparison rule, not an official income classification or a control for other factors. GDP estimates may apply, particularly at the end of the series; missing years are not carried forward."
                    ),
                    html.P(
                        "Missing product records are retained as unknown/no recorded flow, rather than silently set to zero. Missing economy-years are excluded with a notice. Top-three share measures concentration at the HS2 chapter level, not across firms or HS6 products."
                    ),
                    html.P(
                        "Sources: BACI HS92 V202601; CHELEM GDP V202502; UN Comtrade HS1992 chapter titles. The data table includes only displayed heatmap cells; all reference totals were calculated before this display selection."
                    ),
                    html.Div(
                        [
                            html.A(
                                "BACI",
                                href="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37",
                                target="_blank",
                            ),
                            " · ",
                            html.A(
                                "CHELEM",
                                href="https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=17",
                                target="_blank",
                            ),
                            " · ",
                            html.A(
                                "HS1992 dictionary",
                                href="https://comtradeapi.un.org/files/v1/app/reference/H0.json",
                                target="_blank",
                            ),
                        ]
                    ),
                    html.Button(
                        "Download displayed evidence (CSV)",
                        id=cid("download-button"),
                        n_clicks=0,
                        className="m4-button",
                    ),
                    dcc.Download(id=cid("download")),
                    dash_table.DataTable(
                        id=cid("table"),
                        columns=[
                            {"name": n, "id": k}
                            for k, n in [
                                ("country", "Economy"),
                                ("hs2", "HS2"),
                                ("product", "Product"),
                                ("value", "Thousand USD"),
                                ("share_pct", "Export share %"),
                                ("world_pct", "World share %"),
                                ("rca", "RCA"),
                            ]
                        ],
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


def register_callbacks(app):
    @app.callback(
        Output(cid("countries"), "options"),
        Output(cid("countries"), "value"),
        Output(cid("products"), "value"),
        Output(cid("global-context"), "data"),
        Output(cid("mode"), "value"),
        Output(cid("metric"), "value"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        Input(cid("reset"), "n_clicks"),
        State(cid("countries"), "value"),
        State(cid("products"), "value"),
        State(cid("global-context"), "data"),
    )
    def sync(filters, active, reset, current, products, previous):
        guard_active(MODULE_ID, active)
        opts = eligible(trade())
        ns = names()
        filters = filters or {}
        glob = filters.get("country", "CHN")
        if ctx.triggered_id == cid("reset"):
            current = DEFAULTS
            products = []
        elif not previous or previous.get("country") != glob:
            if glob in opts:
                current = [glob] + [c for c in (current or DEFAULTS) if c != glob][:5]
        # Clear deliberately stays empty; never silently reset it on a year change.
        current = [c for c in (current or []) if c in opts]
        if not previous or previous.get("product") != filters.get("product"):
            products = PRODUCT_GROUPS.get(filters.get("product"), [])
        return (
            [{"label": f"{ns.get(c,c)} ({c})", "value": c} for c in opts],
            current,
            products,
            {"country": glob, "product": filters.get("product")},
            ("selected" if ctx.triggered_id == cid("reset") else no_update),
            ("share" if ctx.triggered_id == cid("reset") else no_update),
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
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        Input(cid("countries"), "value"),
        Input(cid("products"), "value"),
        Input(cid("metric"), "value"),
        Input(cid("mode"), "value"),
        State(cid("focus"), "value"),
    )
    def overview(filters, active, selected, requested, metric, mode, focus):
        guard_active(MODULE_ID, active)
        year = int((filters or {}).get("year", 2024))
        d = metrics(year)
        ns = names()
        messages = []
        demo = bool(trade().attrs.get("demo", True))
        mode_label = (
            "DEMONSTRATION DATA — not research evidence"
            if demo
            else "BACI HS92 · real analysis data"
        )
        if len(selected or []) > 6:
            messages.append(
                "Select at most six economies; the first six are displayed."
            )
        chosen = list(dict.fromkeys(selected or []))[:6]
        if mode == "income":
            anchor = (filters or {}).get("country", "CHN")
            if anchor == "WLD":
                anchor = focus if focus in eligible(d) else "CHN"
            g = data_loader.load_gdp_year()
            if bool(g.attrs.get("demo", True)):
                chosen = []
                messages.append(
                    "Real GDP data are unavailable; no synthetic income peers are presented."
                )
            else:
                chosen, peers, base = income_peers(g, year, anchor, eligible(d))
                if base is None:
                    messages.append(
                        f"No positive same-year GDP-CAP for {anchor}; no year substitution is made."
                    )
                else:
                    messages.append(
                        f"Income anchor {anchor}: ${base:,.0f}/person. Range ${base/1.5:,.0f}–${base*1.5:,.0f}; {len(chosen)} closest economies (maximum 6). "
                        + ", ".join(
                            f"{r.country} ${r.income:,.0f}" for r in peers.itertuples()
                        )
                        + ". CHELEM GDP-CAP, current USD; estimates may apply."
                    )
        present = set(d.exporter)
        missing = [c for c in chosen if c not in present]
        chosen = [c for c in chosen if c in present]
        if missing:
            messages.append(
                "No trade observations this year: " + ", ".join(missing) + "."
            )
        products = product_set(d, chosen, requested)
        if requested:
            absent = set(requested) - set(products)
            if absent:
                messages.append(
                    "No world observations for selected chapters: "
                    + ", ".join(sorted(absent))
                    + "."
                )
        focus = focus if focus in chosen else chosen[0] if chosen else None
        total = d.value.sum()
        coverage = d[d.exporter.isin(chosen)].value.sum() / total if total else 0
        scope = (
            f"{year} · {mode_label} · {len(chosen)} economies · {len(products)} displayed chapters. "
            + " ".join(messages)
        )
        if mode == "income":
            scope += " Income anchor follows the global country selector; the manual economy list is inactive."
        if (filters or {}).get("indicator") not in ["export_value", None]:
            scope += " M4 uses its own Share / RCA selector; the global indicator does not change this view."
        if not chosen:
            scope += " Choose at least one economy with recorded data."
        cards = components.kpi_row(
            [
                ("Comparison year", str(year)),
                ("Displayed economies", str(len(chosen))),
                ("Share of world exports", f"{coverage:.1%}"),
            ]
        )
        figure = heat_figure(d, chosen, products, metric)
        note = (
            (
                "Each economy’s top 5 chapters, combined into a common comparison set."
                if not requested
                else "Selected HS2 chapters; all-product denominators remain fixed."
            )
            + " "
            + (
                "Share colours saturate at 50%; numbers remain exact."
                if metric == "share"
                else "RCA colours use log₂, centred at 1 and saturated below 0.125 / above 8; numbers remain exact."
            )
        )
        shown = d[d.exporter.isin(chosen) & d.hs2.isin(products)]
        lookup = shown.set_index(["exporter", "hs2"])
        records = []
        for c in chosen:
            for p in products:
                r = lookup.loc[(c, p)] if (c, p) in lookup.index else None
                records.append(
                    {
                        "year": year,
                        "country": c,
                        "hs2": p,
                        "product": chapters().get(p, p),
                        "value": round(float(r.value), 3) if r is not None else None,
                        "share_pct": (
                            round(float(r.share * 100), 4)
                            if r is not None and pd.notna(r.share)
                            else None
                        ),
                        "world_pct": round(
                            float(d[d.hs2.eq(p)].world_share.iloc[0] * 100), 4
                        ),
                        "rca": (
                            round(float(r.rca), 4)
                            if r is not None and pd.notna(r.rca)
                            else None
                        ),
                    }
                )
        summaries = []
        for c in chosen:
            a = d[d.exporter.eq(c)].sort_values(
                ["value", "hs2"], ascending=[False, True]
            )
            r = a.iloc[0]
            summaries.append(
                f"{c}: HS{r.hs2} leads at {r.share:.1%} (RCA {r.rca:.2f}); top 3 account for {a.head(3).share.sum():.1%}"
            )
        evidence = (
            f"{year}: " + "; ".join(summaries) + "."
            if summaries
            else "No valid comparison is selected."
        )
        conclusion = (
            "Use the common rows to compare composition, then switch to RCA to check specialization. Differences are descriptive; the view does not show that specialization causes export growth. "
            + (
                "The income range is a comparison heuristic and does not control for other country differences."
                if mode == "income"
                else "Selected economies have not been asserted to have similar incomes."
            )
        )
        # Quantify an actual cross-economy difference rather than auto-accepting H3.
        common = (
            d[d.exporter.isin(chosen)]
            .pivot(index="hs2", columns="exporter", values="share")
            .dropna()
        )
        if len(chosen) > 1 and not common.empty:
            spread = common.max(axis=1) - common.min(axis=1)
            chapter = spread.idxmax()
            low = common.loc[chapter].idxmin()
            high = common.loc[chapter].idxmax()
            finding = f"Among chapters recorded for every displayed economy, HS{chapter} has the largest share spread: {high} {common.loc[chapter,high]:.1%} vs {low} {common.loc[chapter,low]:.1%} ({spread[chapter]*100:.1f} percentage points). "
            conclusion = finding + conclusion
        if demo:
            evidence = "Synthetic demonstration only. " + evidence

        return (
            [{"label": f"{ns.get(c,c)} ({c})", "value": c} for c in chosen],
            mode == "income",
            scope,
            cards,
            figure,
            {"height": f"{figure.layout.height}px"},
            note,
            records,
            evidence,
            conclusion,
        )

    @app.callback(
        Output(cid("focus"), "value"),
        Output(cid("inspect"), "value"),
        Output(cid("detail-context"), "data"),
        Input(cid("graph"), "clickData"),
        Input(cid("focus"), "options"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        State(cid("focus"), "value"),
        State(cid("inspect"), "value"),
        State(cid("detail-context"), "data"),
    )
    def select(click, options, filters, active, focus, product, previous):
        guard_active(MODULE_ID, active)
        valid = [o["value"] for o in (options or [])]
        previous = previous or {}
        context = {
            "country": (filters or {}).get("country"),
            "product": (filters or {}).get("product"),
        }
        if ctx.triggered_id == cid("graph") and click:
            point = click["points"][0]
            # Some Plotly/Dash versions omit customdata from heatmap click events.
            # The categorical x/y keys are the authoritative cell identity.
            country, chapter = point.get("x"), point.get("y")
            v = point.get("customdata")
            if country is None and v:
                country, chapter = v[0], v[1]
            if country in valid and chapter in chapters():
                return country, chapter, context
        glob = (filters or {}).get("country")
        if previous.get("country") != glob and glob in valid:
            focus = glob
        focus = focus if focus in valid else valid[0] if valid else None
        if previous.get("product") != (filters or {}).get("product"):
            group = PRODUCT_GROUPS.get((filters or {}).get("product"))
            if group:
                product = group[0]
        return focus, product or "85", context

    @app.callback(
        Output(cid("detail"), "figure"),
        Output(cid("detail"), "style"),
        Output(cid("detail-note"), "children"),
        Output(cid("cell-stats"), "children"),
        Input(cid("focus"), "value"),
        Input(cid("inspect"), "value"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
    )
    def detail(c, p, filters, active):
        guard_active(MODULE_ID, active)
        year = int((filters or {}).get("year", 2024))
        p = p or "85"
        d = metrics(year)
        a = d[d.exporter.eq(c)]
        r = a[a.hs2.eq(p)]
        if a.empty:
            return (
                theme.empty_figure("Choose a focus economy with data for this year."),
                {"height": "420px"},
                "No valid focus economy.",
                [],
            )
        figure = detail_figure(d, c, p)
        note = f"{names().get(c,c)} ({c}) · {year} · inspecting HS{p}. Top 8 chapters by exports; inspected chapter added if needed. Bars compare the same-year economy and world shares."
        if r.empty:
            return (
                figure,
                {"height": f"{figure.layout.height}px"},
                note + " No recorded economy–product value; it is not treated as zero.",
                components.kpi_row([("Selected product", "No recorded value")]),
            )
        r = r.iloc[0]
        return (
            figure,
            {"height": f"{figure.layout.height}px"},
            note,
            components.kpi_row(
                [
                    ("Exports · current USD", theme.fmt_usd(r.value)),
                    ("Export share", f"{r.share:.2%}"),
                    ("World share", f"{r.world_share:.2%}"),
                    ("RCA", f"{r.rca:.3f}"),
                ]
            ),
        )

    @app.callback(
        Output(cid("download"), "data"),
        Input(cid("download-button"), "n_clicks"),
        State(cid("table"), "data"),
        prevent_initial_call=True,
    )
    def download(n, rows):
        return dcc.send_data_frame(
            pd.DataFrame(rows or []).to_csv, "M4_displayed_evidence.csv", index=False
        )
