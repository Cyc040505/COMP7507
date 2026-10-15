"""Module 4 — Product structure.

What does each country mainly export, and which categories stand out? Core view
is a country × product heatmap toggling between export share and RCA.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html

from src import components, theme
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active, placeholder_text

MODULE_ID = "M4"
NAV_LABEL = "M4  Product Structure"
ORDER = 4

_HYPOTHESIS = (
    "Export product structures differ across countries, with some categories standing out "
    "(RCA > 1 indicates relative specialization)."
)
_ACTION = "country × product heatmap, switchable between export share and RCA"
_METRICS = {"share": "Export share", "rca": "RCA"}
_LEVELS = {"hs2": "HS2 chapter", "chel": "CHELEM broad category"}


def layout():
    return html.Div(
        className="module-inner",
        children=[
            components.control_bar(
                [
                    dcc.RadioItems(
                        id=mid(MODULE_ID, "metric"),
                        options=[
                            {"label": "Export share", "value": "share"},
                            {"label": "RCA", "value": "rca"},
                        ],
                        value="share",
                        className="radio-row",
                    ),
                    dcc.Dropdown(
                        id=mid(MODULE_ID, "level"),
                        options=[
                            {"label": "HS2 chapter", "value": "hs2"},
                            {"label": "CHELEM broad category", "value": "chel"},
                        ],
                        value="hs2",
                        clearable=False,
                        className="ctl-dropdown",
                    ),
                ],
                "M4 controls",
            ),
            components.card(
                "Main view · Country × product heatmap",
                components.placeholder_graph(mid(MODULE_ID, "graph")),
                extra_class="graph-card",
            ),
            components.card(
                "Statistics / Detail table",
                html.Div("Awaiting data.", id=mid(MODULE_ID, "stats"), className="stats-body"),
            ),
            components.verification_panel(
                _HYPOTHESIS,
                "No evidence yet: once exporter_hs2_year is wired in, the standout categories "
                "with RCA > 1 will appear here.",
                "No conclusion yet: RCA indicates relative specialization, not proven "
                "technological or productive advantage.",
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
        Input(mid(MODULE_ID, "metric"), "value"),
        Input(mid(MODULE_ID, "level"), "value"),
    )
    def _update(filters, active_module, metric, level):
        guard_active(MODULE_ID, active_module)
        metric_label = _METRICS.get(metric, metric)
        level_label = _LEVELS.get(level, level)
        msg = placeholder_text(
            NAV_LABEL, filters, _ACTION, extra=f"metric: {metric_label} | level: {level_label}"
        )
        stats = f"(placeholder) metric={metric_label} | level={level_label}"
        return (
            theme.empty_figure(msg),
            stats,
            "Waiting for the exporter × HS2 × year table to compute the share and RCA heatmap.",
            "RCA only indicates relative specialization and must be read with care as an advantage.",
        )
