"""Module 5 — Time change.

How do trade values and partner/product structures move around major events? A
baseline-year index and share timeline reusing the M1–M4 filters.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html

from src import components, theme
from src.config import YEAR_MAX, YEAR_MIN
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, mid
from src.module_base import guard_active, placeholder_text

MODULE_ID = "M5"
NAV_LABEL = "M5  Time Change"
ORDER = 5

_HYPOTHESIS = (
    "Around major events, export values and partner / product structures change; it is "
    "necessary to distinguish 'value recovery' from 'structural change'."
)
_ACTION = "baseline-year index and share timeline (reuses the M1–M4 filters)"
_EVENTS = {"covid": "2020 pandemic", "gfc": "2008 financial crisis"}


def layout():
    return html.Div(
        className="module-inner",
        children=[
            components.control_bar(
                [
                    dcc.Dropdown(
                        id=mid(MODULE_ID, "baseline"),
                        options=[{"label": str(y), "value": y} for y in range(YEAR_MIN, YEAR_MAX + 1)],
                        value=2019,
                        clearable=False,
                        className="ctl-dropdown narrow",
                    ),
                    dcc.Dropdown(
                        id=mid(MODULE_ID, "event"),
                        options=[
                            {"label": "2020 pandemic", "value": "covid"},
                            {"label": "2008 financial crisis", "value": "gfc"},
                        ],
                        value="covid",
                        clearable=False,
                        className="ctl-dropdown",
                    ),
                ],
                "M5 controls",
            ),
            components.card(
                "Main view · Index and share timeline",
                components.placeholder_graph(mid(MODULE_ID, "graph")),
                extra_class="graph-card",
            ),
            components.card(
                "Statistics / Detail table",
                html.Div("Awaiting data.", id=mid(MODULE_ID, "stats"), className="stats-body"),
            ),
            components.verification_panel(
                _HYPOTHESIS,
                "No evidence yet: once the time series is wired in, 'recovered' and "
                "'not recovered' countries will be marked here.",
                "No conclusion yet: a before/after comparison emphasises association and does not "
                "prove that the event caused the change.",
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
        Input(mid(MODULE_ID, "baseline"), "value"),
        Input(mid(MODULE_ID, "event"), "value"),
    )
    def _update(filters, active_module, baseline, event):
        guard_active(MODULE_ID, active_module)
        event_label = _EVENTS.get(event, event)
        msg = placeholder_text(
            NAV_LABEL, filters, _ACTION, extra=f"baseline year: {baseline} | event: {event_label}"
        )
        stats = f"(placeholder) baseline={baseline} | event={event_label}"
        return (
            theme.empty_figure(msg),
            stats,
            "Waiting for the time series to compute the index with baseline year = 100 and list "
            "unrecovered countries.",
            "Distinguish value recovery from structural change; make no causal inference about "
            "the event.",
        )
