"""Module 3 — Cooperator network.

Are trade links concentrated within regions or across them? Core view is a
country × partner-share matrix grouped by region, plus a force-directed network
(dash-cytoscape).
"""

from __future__ import annotations

from dash import Input, Output, dcc, html

from src import components, theme
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active, placeholder_text

MODULE_ID = "M3"
NAV_LABEL = "M3  Network & Partners"
ORDER = 3

_HYPOTHESIS = (
    "Trade partner networks exhibit regional concentration, and the degree of concentration "
    "may vary across product categories."
)
_ACTION = (
    "country × partner-share matrix grouped by fixed geographic regions + force-directed "
    "partner network (cytoscape)"
)
_VIEWS = {"matrix": "Regional share matrix", "network": "Force-directed network"}


def layout():
    return html.Div(
        className="module-inner",
        children=[
            components.control_bar(
                [
                    dcc.RadioItems(
                        id=mid(MODULE_ID, "view"),
                        options=[
                            {"label": "Regional share matrix", "value": "matrix"},
                            {"label": "Force-directed network", "value": "network"},
                        ],
                        value="matrix",
                        className="radio-row",
                    ),
                    dcc.Dropdown(
                        id=mid(MODULE_ID, "share-metric"),
                        options=[
                            {"label": "Partner share", "value": "share"},
                            {"label": "Intra-regional share", "value": "intra_share"},
                        ],
                        value="share",
                        clearable=False,
                        className="ctl-dropdown",
                    ),
                ],
                "M3 controls",
            ),
            components.card(
                "Main view · Partner network / regional matrix",
                components.placeholder_graph(mid(MODULE_ID, "graph")),
                extra_class="graph-card",
            ),
            components.card(
                "Statistics / Detail table",
                html.Div("Awaiting data.", id=mid(MODULE_ID, "stats"), className="stats-body"),
            ),
            components.verification_panel(
                _HYPOTHESIS,
                "No evidence yet: once the country-pair table is grouped by region, the "
                "intra-regional export share and main partners will appear here.",
                "No conclusion yet: regional linkage will be measured as a descriptive quantity, "
                "not equated with algorithmically detected 'communities'.",
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
        Input(mid(MODULE_ID, "view"), "value"),
        Input(mid(MODULE_ID, "share-metric"), "value"),
    )
    def _update(filters, active_module, view, share_metric):
        guard_active(MODULE_ID, active_module)
        view_label = _VIEWS.get(view, view)
        msg = placeholder_text(
            NAV_LABEL, filters, _ACTION, extra=f"view: {view_label} | metric: {share_metric}"
        )
        stats = f"(placeholder) view={view_label} | share metric={share_metric}"
        return (
            theme.empty_figure(msg),
            stats,
            "Waiting for the country-pair table to compute each region's partner share; the "
            "force-directed network will render with dash-cytoscape.",
            "Intra-regional concentration will be presented as a descriptive measure, not mixed "
            "with community-detection conclusions.",
        )
