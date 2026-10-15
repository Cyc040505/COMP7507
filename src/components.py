"""Reusable Dash building blocks shared by the shell and every module.

Keeping these in one place means new modules stay small and visually consistent.
"""

from __future__ import annotations

from dash import dcc, html

from src import theme


def card(title: str | None, body, *, extra_class: str = "") -> html.Div:
    """A white rounded panel with an optional title (report section-4 ``.card``)."""
    children = []
    if title:
        children.append(html.H3(title, className="card-title-text"))
    children.append(body)
    return html.Div(children, className=f"card {extra_class}".strip())


def kpi_row(items: list[tuple[str, str]]) -> html.Div:
    """A row of small label/value stat tiles.

    ``items`` is a list of ``(label, value)`` pairs; values may be component ids
    (strings) that callbacks fill in later.
    """
    return html.Div(
        className="kpi-row",
        children=[
            html.Div([html.Span(label), html.Strong(str(value))], className="kpi-card")
            for label, value in items
        ],
    )


def control_bar(children, label: str = "Module controls") -> html.Div:
    """Per-module control strip (the second layer of the two-layer console)."""
    return html.Div(
        className="module-controls",
        children=[html.Div(label, className="lbl"), html.Div(children, className="chips")],
    )


def verification_panel(
    hypothesis: str,
    evidence,
    conclusion,
    *,
    evidence_id: str | None = None,
    conclusion_id: str | None = None,
) -> html.Div:
    """The 'hypothesis → evidence → conclusion' panel required for every module.

    The hypothesis is a fixed claim from the proposal; ``evidence`` and
    ``conclusion`` may be live text components (pass their ids) that callbacks
    update as the user explores.
    """
    return card(
        "Verification · Hypothesis → Evidence → Conclusion",
        html.Ol(
            className="verify-list",
            children=[
                html.Li([html.Span("Hypothesis", className="vtag vtag-h"), html.P(hypothesis)]),
                html.Li(
                    [
                        html.Span("Evidence", className="vtag vtag-e"),
                        html.P(evidence, id=evidence_id),
                    ]
                ),
                html.Li(
                    [
                        html.Span("Conclusion", className="vtag vtag-c"),
                        html.P(conclusion, id=conclusion_id),
                    ]
                ),
            ],
        ),
        extra_class="verify",
    )


def placeholder_graph(graph_id: str, message: str | None = None) -> dcc.Graph:
    """A graph that starts life as an ``empty_figure`` placeholder."""
    return dcc.Graph(
        id=graph_id,
        figure=theme.empty_figure(message) if message else theme.empty_figure(),
        config={"displayModeBar": False, "responsive": True},
    )
