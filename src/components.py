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
    children.extend(body if isinstance(body, (list, tuple)) else [body])
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
        children=[
            html.Div(label, className="lbl"),
            html.Div(children, className="chips"),
        ],
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
        "What the evidence shows",
        html.Ol(
            className="verify-list",
            children=[
                html.Li(
                    [html.Span("Question", className="vtag vtag-h"), html.P(hypothesis)]
                ),
                html.Li(
                    [
                        html.Span("Evidence", className="vtag vtag-e"),
                        html.P(evidence, id=evidence_id),
                    ]
                ),
                html.Li(
                    [
                        html.Span("Interpretation", className="vtag vtag-c"),
                        html.P(conclusion, id=conclusion_id),
                    ]
                ),
            ],
        ),
        extra_class="verify",
    )


def placeholder_graph(
    graph_id: str,
    message: str | None = None,
    *,
    animate: bool = False,
    animation_options: dict | None = None,
    initial_figure: "go.Figure | None" = None,
) -> dcc.Graph:
    """A graph that starts life as an ``empty_figure`` placeholder.

    Pass ``animate=True`` to have Plotly.js tween the figure between updates
    (e.g. a ranking chart morphs 0.6T → 0.9T instead of jumping). With
    ``animate=True`` you should also pass a non-empty ``initial_figure`` —
    Plotly.js's tween needs a real first frame to interpolate from, and an
    empty ``empty_figure`` starts the animation off a blank frame. Animate
    graphs get a ``graph-animate`` class so the shell's resize/lock callback
    can skip them (a ``Plotly.update(uirevision)`` onto an animate plot would
    reset its categorical tick labels).
    """
    kwargs = {}
    if animate:
        kwargs["animate"] = True
        kwargs["animation_options"] = animation_options or {
            "frame": {"redraw": False},
            "transition": {"duration": 750, "ease": "cubic-in-out"},
        }
        kwargs["className"] = "graph-animate"
    figure = (
        initial_figure
        if initial_figure is not None
        else theme.empty_figure(message) if message else theme.empty_figure()
    )
    return dcc.Graph(
        id=graph_id,
        style={"height": f"{figure.layout.height or 420}px"},
        figure=figure,
        config={"displayModeBar": False, "responsive": True},
        **kwargs,
    )


def module_intro(title, description):
    return html.Div([html.H2(title), html.P(description)], className="module-intro")


def field(label, widget):
    return html.Div(
        [html.Label(label, htmlFor=widget.id), widget], className="control-field"
    )
