"""Module 1 — Geography.

Are closer partners more strongly linked? Distance vs export share (log-log),
with contiguity / common language as auxiliary groupings.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html

from src import components, theme
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active, placeholder_text

MODULE_ID = "M1"
NAV_LABEL = "M1  Geography"
ORDER = 1

_HYPOTHESIS = (
    "Bilateral trade intensity is associated with geographic proximity "
    "(a description of association, not an estimate of a causal effect)."
)
_ACTION = (
    "distance from each exporter to its partners vs those partners' export share "
    "(log-log scatter); switch products to see whether the relationship changes"
)


def layout():
    return html.Div(
        className="module-inner",
        children=[
            components.control_bar(
                [
                    dcc.Dropdown(
                        id=mid(MODULE_ID, "dist-metric"),
                        options=[
                            {"label": "Weighted distance (distw)", "value": "distw"},
                            {"label": "Capital distance (distcap)", "value": "distcap"},
                            {"label": "Simple distance (dist)", "value": "dist"},
                        ],
                        value="distw",
                        clearable=False,
                        className="ctl-dropdown",
                    ),
                    dcc.Checklist(
                        id=mid(MODULE_ID, "aux"),
                        options=[
                            {"label": "Group by contiguity", "value": "contig"},
                            {"label": "Group by common language", "value": "comlang_off"},
                        ],
                        value=[],
                        className="check-row",
                    ),
                ],
                "M1 controls",
            ),
            components.card(
                "Main view · Distance vs partner share",
                components.placeholder_graph(mid(MODULE_ID, "graph")),
                extra_class="graph-card",
            ),
            components.card(
                "Statistics / Detail table",
                html.Div("Awaiting data.", id=mid(MODULE_ID, "stats"), className="stats-body"),
            ),
            components.verification_panel(
                _HYPOTHESIS,
                "No evidence yet: once country_pair_year + geodist are wired in, near/far "
                "exceptions will be listed here.",
                "No conclusion yet: expect an overall 'farther means smaller share' trend with "
                "several counter-examples.",
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
        Input(mid(MODULE_ID, "dist-metric"), "value"),
        Input(mid(MODULE_ID, "aux"), "value"),
    )
    def _update(filters, active_module, dist_metric, aux):
        guard_active(MODULE_ID, active_module)
        aux_txt = ", ".join(aux) if aux else "none"
        msg = placeholder_text(
            NAV_LABEL, filters, _ACTION, extra=f"distance metric: {dist_metric} | grouping: {aux_txt}"
        )
        stats = f"(placeholder) distance={dist_metric} | grouping={aux_txt}"
        return (
            theme.empty_figure(msg),
            stats,
            "Waiting for the country-pair × year table and GeoDist to compute the "
            "distance–share relationship.",
            "An association-based conclusion will follow once data is wired in, with "
            "counter-examples listed separately.",
        )
