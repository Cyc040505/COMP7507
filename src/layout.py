"""Application shell: header + left column (nav + global console) + right view area.

The shell knows nothing about module internals — it only asks the registry for nav
items and panels. It owns the two global stores and is their *sole writer*.
"""

from __future__ import annotations

from dash import Input, Output, dcc, html, callback_context

from src import components, config, data_loader
from src.ids import ACTIVE_MODULE, GLOBAL_FILTERS, RESIZE_TOKEN, nav_id
from src.modules import build_panels, nav_items

DEFAULT_MODULE = "M0"


# --- building blocks ----------------------------------------------------------
def _header() -> html.Header:
    mode = config.DEMO_TAG if data_loader.is_demo() else config.ANALYTIC_TAG
    return html.Header(
        className="app-header",
        children=[
            html.P("COMP7507 Visualization & Visual Analytics · Group 7", className="eyebrow"),
            html.H1("Global Trade Over Three Decades: Scale, Geography and Product Structure"),
            html.P(
                f"1995–2024 · CEPII BACI / CHELEM / GeoDist · {mode}",
                className="subtitle",
            ),
        ],
    )


def _nav() -> html.Div:
    buttons = []
    for module_id, label in nav_items():
        buttons.append(
            html.Button(
                label,
                id=nav_id(module_id),
                n_clicks=0,
                className="nav-item",
            )
        )
    return html.Nav(className="nav", children=[html.Div("Modules", className="lbl"), *buttons])


def _view_area() -> html.Div:
    return html.Div(
        className="view-area",
        children=[
            html.Div("View · active module", className="lbl"),
            dcc.Loading(
                id="view-loading",
                type="default",
                children=html.Div(id="module-host", className="module-host", children=build_panels()),
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
            dcc.Store(id=GLOBAL_FILTERS, storage_type="memory", data={
                "year": config.DEFAULT_YEAR,
                "country": "CHN",
                "product": "TOTAL",
                "indicator": "export_value",
            }),
            dcc.Store(id=ACTIVE_MODULE, storage_type="memory", data=DEFAULT_MODULE),
            dcc.Store(id=RESIZE_TOKEN, storage_type="memory"),
            _header(),
            html.Div(
                className="layout-grid",
                children=[
                    html.Aside(className="left-col", children=[_nav()]),
                    html.Main(_view_area(), className="right-col"),
                ],
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
        [Output(i, "className") for i in nav_ids] + [Output(i, "className") for i in panel_ids],
        Input(ACTIVE_MODULE, "data"),
    )
    def _toggle_visibility(active_module):
        nav_classes = ["nav-item on" if m == active_module else "nav-item" for m in module_ids]
        panel_classes = [
            "module-panel" if m == active_module else "module-panel panel-hidden"
            for m in module_ids
        ]
        return nav_classes + panel_classes

    # Resize Plotly graphs in the newly-shown panel (hidden graphs lay out at 0×0),
    # and re-lock their interactions. Dash applies a graph's ``config`` client-side
    # only on re-render, so on initial mount Plotly falls back to its default
    # box-zoom / drag-zoom / pan. Re-issuing the locked config through the Plotly JS
    # API (after the graph is visible) disables those gestures while leaving the
    # per-point hover layer untouched.
    app.clientside_callback(
        """
        function(active) {
            window.setTimeout(function() {
                var panel = document.getElementById(active + '-panel');
                if (!panel) { return; }
                var locked = {
                    zoom: false, pan: false, scrollZoom: false,
                    dragmode: false, selectable: false,
                    displayModeBar: false, responsive: true
                };
                panel.querySelectorAll('.js-plotly-plot').forEach(function(gd) {
                    if (!window.Plotly) { return; }
                    // The ranking graph (M0 share) uses dcc.Graph(animate=True) and
                    // drives its own frame tweens via Plotly.animate(). A
                    // Plotly.update(uirevision) onto it resets the categorical tick
                    // labels (country names vanish). It carries a .graph-animate
                    // class — skip it; lock only the static graphs.
                    var wrap = gd.closest ? gd.closest('.dash-graph') : null;
                    if (wrap && wrap.classList && wrap.classList.contains('graph-animate')) {
                        return;
                    }
                    if (window.Plotly.Plots) { window.Plotly.Plots.resize(gd); }
                    // Maps and other opt-in interactive views own their gestures.
                    // Resize them on navigation without applying the shell lock.
                    if (wrap && wrap.classList && wrap.classList.contains('graph-interactive')) {
                        return;
                    }
                    if (gd.locked !== true) {
                        Plotly.update(gd, {}, locked, {
                            layout: { uirevision: 'locked', dragmode:false }
                        });
                        gd.locked = true;
                    }
                });
            }, 80);
            return active;
        }
        """,
        Output(RESIZE_TOKEN, "data"),
        Input(ACTIVE_MODULE, "data"),
    )
