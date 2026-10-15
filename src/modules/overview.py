"""Module 0 — Overview.

Global trade totals and the ranking of country shares, 1995–2024. No explicit
hypothesis; this module poses the core question that the later modules answer.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html

from src import components, theme
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active, placeholder_text

MODULE_ID = "M0"
NAV_LABEL = "0  Overview"
ORDER = 0

_QUESTION = (
    "Over 1995–2024, what drives bilateral trade between countries, "
    "and how has the global trade landscape evolved?"
)
_ACTION = (
    "global trade-total time series + country-share ranking + trade-map animation "
    "(reuses the global year / country / indicator)"
)
_VIEWS = {"total": "Total", "share": "Country share", "map": "Trade map"}


def layout():
    return html.Div(
        className="module-inner",
        children=[
            components.control_bar(
                [
                    dcc.RadioItems(
                        id=mid(MODULE_ID, "display"),
                        options=[
                            {"label": "Total", "value": "total"},
                            {"label": "Country share", "value": "share"},
                            {"label": "Trade map", "value": "map"},
                        ],
                        value="total",
                        className="radio-row",
                    )
                ],
                "Overview controls",
            ),
            components.card(
                "Main view · Global trade pattern",
                components.placeholder_graph(mid(MODULE_ID, "graph")),
                extra_class="graph-card",
            ),
            components.card(
                "Statistics / Detail table",
                html.Div("Awaiting data.", id=mid(MODULE_ID, "stats"), className="stats-body"),
            ),
            components.verification_panel(
                _QUESTION,
                "No evidence yet: once analysis tables are wired in, key totals and country shares "
                "will be placed here.",
                "No conclusion yet: the overview poses the core question that M1–M5 answer in turn.",
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
        Input(mid(MODULE_ID, "display"), "value"),
    )
    def _update(filters, active_module, display):
        guard_active(MODULE_ID, active_module)
        label = _VIEWS.get(display, display)
        msg = placeholder_text(NAV_LABEL, filters, _ACTION, extra=f"view: {label}")
        stats = f"(placeholder) filters: {filters} | view: {label}"
        return (
            theme.empty_figure(msg),
            stats,
            f"View '{label}' selected; numeric evidence appears once flow_year / country_year "
            "tables are wired in.",
            "The overview only provides background; conclusions are formed in the later modules.",
        )
