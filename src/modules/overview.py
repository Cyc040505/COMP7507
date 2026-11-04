"""Module 0 — Overview.

Global trade totals and the ranking of country shares, 1995–2024. No explicit
hypothesis; this module poses the core question that the later modules answer.

Two data-backed views:
  * **Total** — the global export time series (``flow_year``) with a peak callout.
  * **Share** — a Top-N country ranking (``country_year``) with stable per-country
    colours and an optional auto-play that steps through the years so the shift in
    rankings is visible.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from src import components, config, data_loader, theme
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active

MODULE_ID = "M0"
NAV_LABEL = "M0  Overview"
ORDER = 0

_TOP_N = 10

# BACI aggregate/bucket codes (e.g. S19 = "Other Asia, nes", S9 = World) are not
# sovereign countries; drop them so the ranking stays a genuine country list.
def _is_country(code: str) -> bool:
    """True for a real country code; False for BACI S* aggregate buckets."""
    return not (isinstance(code, str) and code.startswith("S"))


def _years_frame() -> list[int]:
    return list(range(config.YEAR_MIN, config.YEAR_MAX + 1))


def _total_figure(flow: pd.DataFrame) -> go.Figure:
    """Global export total per year (thousand USD → trillions) with a peak marker."""
    df = flow.sort_values("year")
    trillions = [theme.stored_to_trillions(v) for v in df["export_value"].to_numpy()]
    peak_i = int(df["export_value"].to_numpy().argmax())
    peak_year, peak_val = df["year"].iloc[peak_i], trillions[peak_i]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=trillions,
            mode="lines+markers",
            name="Global exports",
            line=dict(color=theme.ACCENT, width=2),
            marker=dict(size=6, color=theme.ACCENT,
                        line=dict(color="#fff", width=1)),
            fill="tozeroy",
            fillcolor="rgba(29,78,216,0.10)",
            hovertemplate=(
                "Year %{x}<br>Global exports: "
                + "<b>$%{y:.2f} T</b>"
                + "<extra></extra>"
            ),
        )
    )
    fig.add_annotation(
        x=peak_year,
        y=peak_val,
        text=f"<b>${peak_val:,.2f} T</b><br>peak {peak_year}",
        showarrow=True,
        arrowhead=2,
        ax=0,
        ay=-34,
        font=dict(size=12, color=theme.INK),
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor=theme.LINE,
        borderwidth=1,
        borderpad=6,
    )
    theme.style_figure(
        fig,
        title=None,
        height=460,
    )
    fig.update_layout(
        yaxis=dict(
            title="Global exports (trillion USD)",
            range=[0, 25],
            fixedrange=True,
            # Show 5,10,15,20,25 — drop the 0 tick so "0.0" is hidden.
            tickvals=[5, 10, 15, 20, 25],
            tickformat=",0",
            gridcolor=theme.LINE,
            zerolinecolor=theme.LINE,
            color=theme.MUTED,
        ),
        xaxis=dict(
            title="Year",
            range=[1995, 2025],
            fixedrange=True,
            color=theme.MUTED,
        ),
        legend=dict(orientation="h", x=0, y=1.08),
        margin=dict(l=24, r=24, t=52, b=44),
    )
    return fig


def _share_figure(country_year: pd.DataFrame, year: int, demo: bool) -> go.Figure:
    top = (
        country_year[country_year["year"] == year]
        .loc[country_year[country_year["year"] == year]["country"].map(_is_country)]
        .sort_values("export_value", ascending=False)
        .head(_TOP_N)
    ).copy()

    top = top.iloc[::-1].reset_index(drop=True)
    trillions = [theme.stored_to_trillions(v) for v in top["export_value"].to_numpy()]
    names = _country_names(top)
    codes = list(top["country"])
    ranks = [_TOP_N - i for i in range(len(top))]

    yr_rows = country_year[country_year["year"] == year]
    global_total = float(yr_rows["export_value"].sum())
    shares = (
        top["export_value"].to_numpy() / global_total * 100.0
        if global_total else [0.0] * len(top)
    )

    # Country code + its share of global exports, inside the bar.
    text = [
        f"{code} ({pct:.1f}%)"
        for code, pct in zip(codes, shares)
    ]
    # Fixed rank labels for the y-axis; index i from the bottom is rank ranks[i].
    rank_labels = [f"Top {r}" for r in ranks]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=trillions,
            y=rank_labels,
            orientation="h",
            marker=dict(
                color=[theme.country_color(c) for c in codes],
                line=dict(color=theme.BG, width=2),  # 2px surface gap between bars
            ),
            # Country name + figure live inside the bar, left-aligned.
            text=text,
            textposition="inside",
            textfont=dict(size=11, color="#fff"),
            hovertemplate=(
                "%{y}<br>"
                + "%{customdata.name} (%{customdata.code})<br>"
                + "Exports: <b>$%{x:.2f} T</b>"
                + "<extra></extra>"
            ),
            customdata=[
                {"name": name, "code": code}
                for name, code in zip(names, codes)
            ],
        )
    )
    theme.style_figure(
        fig,
        title=None,
        height=480,
    )
    fig.update_layout(
        xaxis=dict(
            title="Exports (trillion USD)",
            range=[0, 4.5],
            fixedrange=True,
            tickvals=[0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5],
            tickformat="0.1f",
            gridcolor=theme.LINE,
            zerolinecolor=theme.LINE,
            color=theme.MUTED,
        ),
        yaxis=dict(
            title=None,
            automargin=True,
            categoryorder="array",
            categoryarray=[f"Top {r}" for r in range(_TOP_N, 0, -1)],
            fixedrange=True,
            color=theme.INK,
            tickfont=dict(size=12),
        ),
        # Left-align the in-bar country text.
        margin=dict(l=70, r=24, t=40, b=44),
    )
    return fig


def _country_names(top: pd.DataFrame) -> list[str]:
    """Resolve ISO3 codes to display names, falling back to the code itself."""
    if top.empty:
        return []
    names = {r.iso3: r.name for r in _meta_iter()}
    return [names.get(c, c) for c in top["country"]]


def _meta_iter():
    # Lazily built each call; cheap because country_meta is small (238 rows).
    yield from data_loader.load_country_meta().itertuples(index=False)


def _summary_category(title: str, items: list[tuple[str, str]]) -> html.Div:
    """One archetype block: a heading plus a 'country: reason' list."""
    return html.Div(
        className="summary-category",
        children=[
            html.H5(title, className="summary-cat-title"),
            html.Ul(
                className="summary-list",
                children=[
                    html.Li([html.Strong(f"{country}: "), reason])
                    for country, reason in items
                ],
            ),
        ],
    )


def _global_trend_card() -> html.Div:
    """The global export-total description, shown between the two graphs."""
    return components.card(
        "Global trade over time",
        html.Div(
            className="summary-body",
            children=[
                html.P(
                    "Global trade has grown steadily, on an overall upward trend. "
                    "Global exports rose from $5.07 trillion in 1995 to $22.83 "
                    "trillion in 2024 — about a 4.5× increase. The series dipped "
                    "twice, around the 2009 financial crisis (down ~23% year on "
                    "year) and the 2020 COVID-19 pandemic (down ~7.5%), but "
                    "recovered quickly both times and reached a historical peak "
                    "of $24.15 trillion in 2022."
                ),
            ],
        ),
        extra_class="summary-card",
    )


def _ranking_summary_card() -> html.Div:
    """Three-archetype reading of the ever-Top-10 country ranking."""
    return components.card(
        "Top-10 country ranking",
        html.Div(
            className="summary-body",
            children=[
                _summary_category("Consistently dominant (always in the top three)", [
                    ("United States (USA)",
                     "Ranked Top1 for 1995–2003, then held Top2–3; never left the top "
                     "three, with a share of 8–13%."),
                    ("Germany (DEU)",
                     "Ranked Top2 for 1995–2003, briefly Top1 in 2004, then held Top2–3; "
                     "also never left the top three, with a share of 6.4–9.7%."),
                ]),
                _summary_category("Rising fast (rank and share climbed sharply)", [
                    ("China (CHN)",
                     "Only Top6 in 1995 (4.5% share), took the top spot from 2005 "
                     "and has held it since (15.7% in 2024) — a ~3.5× share gain, "
                     "the classic chaser-turned-leader."),
                    ("Mexico (MEX)",
                     "First entered the Top10 in 2015, rising to Top6 by 2024 "
                     "(2.8% share) — the fastest late newcomer."),
                ]),
                _summary_category("Steadily stable (narrow rank band, small share swings)", [
                    ("Netherlands (NLD)",
                     "In the top 10 for all 30 years, ranked Top7–10, share 2.4–3.4% "
                     "— the smallest swings, the most stable economy."),
                    ("Italy (ITA)",
                     "In the top 10 for all 30 years, ranked Top6–9, share 2.6–4.5% "
                     "— steady in the upper-mid tier."),
                ]),
            ],
        ),
        extra_class="summary-card",
    )


def layout():
    return html.Div(
        className="module-inner",
        children=[
            html.Div(
                id=mid(MODULE_ID, "view-host"),
                className="view-host",
                children=[
                    components.card(
                        "Global exports over time, 1995–2024",
                        components.placeholder_graph(mid(MODULE_ID, "total-graph")),
                        extra_class="graph-card",
                    ),
                    _global_trend_card(),
                    components.card(
                        "Top-10 exporting countries by year",
                        html.Div(
                            className="share-view",
                            children=[
                                html.Div(
                                    id=mid(MODULE_ID, "share-title"),
                                    className="graph-title",
                                ),
                                components.placeholder_graph(
                                    mid(MODULE_ID, "share-graph"),
                                    animate=True,
                                    animation_options={
                                        "frame": {"redraw": False},
                                        "transition": {"duration": 400, "ease": "cubic-in-out"},
                                    },
                                    initial_figure=_share_figure(
                                        data_loader.load_country_year(), config.YEAR_MIN,
                                        data_loader.is_demo(),
                                    ),
                                ),
                            ],
                        ),
                        extra_class="graph-card graph-card-share",
                    ),
                ],
            ),
            html.Div(
                id=mid(MODULE_ID, "share-controls"),
                className="module-controls",
                children=[
                    html.Label("Year · drag to scrub the ranking", className="ctl-label"),
                    dcc.Slider(
                        id=mid(MODULE_ID, "year-slider"),
                        min=config.YEAR_MIN,
                        max=config.YEAR_MAX,
                        step=1,
                        value=config.YEAR_MIN,
                        marks={y: str(y) for y in _years_frame()},
                        tooltip={"placement": "bottom"},
                        updatemode="drag",
                        className="year-slider",
                    ),
                    html.Span(id=mid(MODULE_ID, "year-display"), className="year-display"),
                ],
            ),
            _ranking_summary_card(),
        ],
    )


def register_callbacks(app):
    # Static Total graph. Always renders, independent of the ranking view.
    @app.callback(
        Output(mid(MODULE_ID, "total-graph"), "figure"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        prevent_initial_call=False,
    )
    def _update_total(filters, active_module):
        guard_active(MODULE_ID, active_module)
        return _total_figure(data_loader.load_flow_year())

    @app.callback(
        Output(mid(MODULE_ID, "share-graph"), "figure"),
        Output(mid(MODULE_ID, "share-title"), "children"),
        Output(mid(MODULE_ID, "year-display"), "children"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        Input(mid(MODULE_ID, "year-slider"), "value"),
        prevent_initial_call=False,
    )
    def _share_view(filters, active_module, year):
        guard_active(MODULE_ID, active_module)
        years = _years_frame()
        current = year if year in years else config.YEAR_MIN
        fig = _share_figure(data_loader.load_country_year(), current, data_loader.is_demo())
        # The year title lives outside the Plotly figure (see layout), because
        # Plotly.animate() tweens trace data but not layout.title.
        title = f"Top-{_TOP_N} exporters in {current}"
        return fig, title, str(current)
