"""Module 2 — Economy.

Do countries with similar GDP export similarly? Same-year GDP vs export value.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html

from src import components, theme
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active, placeholder_text

MODULE_ID = "M2"
NAV_LABEL = "M2  Economy"
ORDER = 2

_HYPOTHESIS = (
    "Countries of similar economic scale may export similarly; export differences at equal "
    "scale become the entry point for the later structural analysis."
)
_ACTION = "same-year GDP vs export value scatter; select comparable-GDP countries to compare their exports"


def layout():
    return html.Div(
        className="module-inner",
        children=[
            components.control_bar(
                [
                    dcc.Dropdown(
                        id=mid(MODULE_ID, "gdp-metric"),
                        options=[
                            {"label": "GDP (current, GDP-VAL)", "value": "gdp"},
                            {"label": "GDP per capita (GDP-CAP)", "value": "gdp_per_capita"},
                            {"label": "GDP PPP (GDP-PPP)", "value": "gdp_ppp"},
                        ],
                        value="gdp",
                        clearable=False,
                        className="ctl-dropdown",
                    ),
                    dcc.Checklist(
                        id=mid(MODULE_ID, "opts"),
                        options=[{"label": "Log scale", "value": "log"}],
                        value=["log"],
                        className="check-row",
                    ),
                ],
                "M2 controls",
            ),
            components.card(
                "Main view · GDP vs exports",
                components.placeholder_graph(mid(MODULE_ID, "graph")),
                extra_class="graph-card",
            ),
            components.card(
                "Statistics / Detail table",
                html.Div("Awaiting data.", id=mid(MODULE_ID, "stats"), className="stats-body"),
            ),
            components.verification_panel(
                _HYPOTHESIS,
                "No evidence yet: once country_year + gdp_year are wired in, the largest export "
                "outliers will be listed here.",
                "No conclusion yet: export differences at equal GDP serve as the entry point for "
                "the structural analysis.",
                evidence_id=mid(MODULE_ID, "evidence"),
                conclusion_id=mid(MODULE_ID, "conclusion"),
            ),
        ],
    )


def register_callbacks(app):
    @app.callback(
        Output(mid(MODULE_ID, "graph"), "figure"),
        Output(mid(MODULE_ID, "stats"), "children"),
        Output(mid(MODULE_ID, "evidence"), "children"),
        Output(mid(MODULE_ID, "conclusion"), "children"),
        Input(GLOBAL_FILTERS, "data"),
        Input(ACTIVE_MODULE, "data"),
        Input(mid(MODULE_ID, "gdp-metric"), "value"),
        Input(mid(MODULE_ID, "opts"), "value"),
    )
    def _update(filters, active_module, gdp_metric, opts):
        guard_active(MODULE_ID, active_module)
        scale_txt = "log scale" if "log" in (opts or []) else "linear scale"
        msg = placeholder_text(
            NAV_LABEL, filters, _ACTION, extra=f"GDP metric: {gdp_metric} | {scale_txt}"
        )
        stats = f"(placeholder) GDP metric={gdp_metric} | {scale_txt}"
        return (
            theme.empty_figure(msg),
            stats,
            "Waiting for GDP and exports to plot the same-year scatter and flag export outliers "
            "at equal scale.",
            "The differences themselves are the entry point; no causal claim is made in this module.",
        )
