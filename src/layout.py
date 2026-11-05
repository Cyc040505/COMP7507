"""Application shell: compact header, persistent module navigation and analysis area.

The shell knows nothing about module internals — it only asks the registry for nav
items and panels. It owns the two global stores and is their *sole writer*.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html, callback_context

from src import config
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, RESIZE_TOKEN, nav_id
from src.modules import build_panels, nav_items

DEFAULT_MODULE = "M0"


# --- building blocks ----------------------------------------------------------
def _header() -> html.Header:
    return html.Header(
        className="app-header",
        children=[
            html.Div(
                [
                    html.H1("Global trade, in perspective"),
                    html.P(
                        "Scale, geography and product structure", className="subtitle"
                    ),
                ]
            ),
            html.Div(
                [
                    html.Span("1995–2024", className="header-period"),
                    html.Span("BACI / CHELEM / GeoDist", className="header-source"),
                ],
                className="header-meta",
            ),
        ],
    )


def _nav() -> html.Nav:
    titles = {
        "M0": ("Overview", "The global context"),
        "M1": ("Geography", "Distance & partners"),
        "M2": ("Economy", "GDP & export scale"),
        "M3": ("Trade partners", "Flows & regions"),
        "M4": ("Product structure", "Share & specialization"),
        "M5": ("Time change", "Recovery & structure"),
    }
    buttons = []
    for module_id, label in nav_items():
        title, desc = titles[module_id]
        buttons.append(
            html.Button(
                [
                    html.Span(
                        module_id, className="nav-code", **{"aria-hidden": "true"}
                    ),
                    html.Span(
                        [html.Strong(title), html.Small(desc)], className="nav-copy"
                    ),
                ],
                id=nav_id(module_id),
                n_clicks=0,
                className="nav-item",
                **{"aria-label": label.strip()},
            )
        )
    return html.Nav(buttons, className="nav", **{"aria-label": "Analysis modules"})


def _sidebar():
    return html.Aside(
        className="left-col",
        children=[
            html.Div(
                [
                    html.Div("Trade atlas", className="brand-name"),
                    html.P("COMP7507 · Group 7", className="brand-caption"),
                ],
                className="sidebar-brand",
            ),
            _nav(),
            html.Div(
                [
                    html.Strong("Six focal economies"),
                    html.P("USA · DEU · CHN\nMEX · NLD · ITA"),
                    html.Small("Worldwide partners.\nIndependent module controls."),
                ],
                className="sidebar-context",
            ),
        ],
    )


def _view_area() -> html.Div:
    return html.Div(
        className="view-area",
        children=[
            dcc.Loading(
                id="view-loading",
                type="dot",
                color="#147e8b",
                delay_show=350,
                children=html.Div(
                    id="module-host", className="module-host", children=build_panels()
                ),
            ),
            html.Footer(
                "CEPII merchandise trade · Nominal current USD · Descriptive analysis",
                className="app-footer",
            ),
        ],
    )


# --- layout -------------------------------------------------------------------
def build_layout() -> html.Div:
    return html.Div(
        className="page-shell",
        children=[
            # Read-only compatibility snapshot for unfinished legacy placeholders.
            # Implemented modules own their controls; this is not a live global filter.
            dcc.Store(
                id=GLOBAL_FILTERS,
                storage_type="memory",
                data={
                    "year": config.DEFAULT_YEAR,
                    "country": "CHN",
                    "product": "TOTAL",
                    "indicator": "export_value",
                },
            ),
            dcc.Store(id=ACTIVE_MODULE, storage_type="memory", data=DEFAULT_MODULE),
            dcc.Store(id=RESIZE_TOKEN, storage_type="memory"),
            html.A("Skip to analysis", href="#analysis-main", className="skip-link"),
            _sidebar(),
            html.Div(
                [
                    _header(),
                    html.Main(
                        _view_area(),
                        id="analysis-main",
                        tabIndex=-1,
                        className="right-col",
                    ),
                ],
                className="workspace",
            ),
        ],
    )


# --- shell callbacks ----------------------------------------------------------
def register_shell_callbacks(app) -> None:
    module_ids = [m for m, _ in nav_items()]
    nav_ids = [nav_id(m) for m in module_ids]
    panel_ids = [f"{m}-panel" for m in module_ids]

    @app.callback(
        Output(ACTIVE_MODULE, "data"),
        [Input(i, "n_clicks") for i in nav_ids],
        prevent_initial_call=True,
    )
    def _set_active_module(*_n_clicks):
        triggered = callback_context.triggered_id
        if not triggered:
            return DEFAULT_MODULE
        return triggered.split("nav-", 1)[1]

    @app.callback(
        [Output(i, "className") for i in nav_ids]
        + [Output(i, "className") for i in panel_ids],
        Input(ACTIVE_MODULE, "data"),
    )
    def _toggle_visibility(active_module):
        nav_classes = [
            "nav-item on" if m == active_module else "nav-item" for m in module_ids
        ]
        panel_classes = [
            "module-panel" if m == active_module else "module-panel panel-hidden"
            for m in module_ids
        ]
        return nav_classes + panel_classes

    app.clientside_callback(
        """
        function(active) {
            // Navigation changes the reading position, never a module's filter state.
            window.scrollTo({top:0, behavior:'instant'});
            window.requestAnimationFrame(function() {
                window.setTimeout(function() {
                    var panel = document.getElementById(active + '-panel');
                    if (!panel || !window.Plotly) return;
                    panel.querySelectorAll('.js-plotly-plot').forEach(function(gd) {
                        window.Plotly.Plots.resize(gd);
                    });
                    document.querySelectorAll('.nav-item').forEach(function(button) {
                        button.setAttribute('aria-current',button.id === 'nav-' + active ? 'page' : 'false');
                    });
                }, 100);
            });
            return active;
        }
        """,
        Output(RESIZE_TOKEN, "data"),
        Input(ACTIVE_MODULE, "data"),
    )
