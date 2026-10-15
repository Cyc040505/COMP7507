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


# --- options ------------------------------------------------------------------
def _country_options() -> list[dict]:
    meta = data_loader.load_country_meta()
    opts = [{"label": "World (global)", "value": "WLD"}]
    for _, row in meta.sort_values("name").iterrows():
        opts.append({"label": f"{row['name']} ({row['iso3']})", "value": row["iso3"]})
    return opts


_PRODUCT_OPTIONS = [
    {"label": "All products", "value": "TOTAL"},
    {"label": "HS2 · Machinery & electrical (84–85)", "value": "HS84"},
    {"label": "HS2 · Vehicles & transport (87)", "value": "HS87"},
    {"label": "HS2 · Chemicals (28–38)", "value": "HS28"},
    {"label": "HS2 · Textiles & apparel (61–62)", "value": "HS61"},
]

_INDICATOR_OPTIONS = [
    {"label": "Export value", "value": "export_value"},
    {"label": "GDP (current, GDP-VAL)", "value": "gdp"},
    {"label": "GDP per capita (GDP-CAP)", "value": "gdp_per_capita"},
    {"label": "Openness", "value": "openness"},
    {"label": "RCA", "value": "rca"},
]

_YEAR_OPTIONS = [{"label": str(y), "value": y} for y in range(config.YEAR_MIN, config.YEAR_MAX + 1)]


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


def _console() -> html.Div:
    return html.Div(
        className="console",
        children=[
            html.Div("Console · global parameters", className="lbl"),
            html.Label("Year", className="ctl-label"),
            dcc.Dropdown(
                id="global-year",
                options=_YEAR_OPTIONS,
                value=config.DEFAULT_YEAR,
                clearable=False,
                className="ctl-dropdown",
            ),
            html.Label("Country / exporter", className="ctl-label"),
            dcc.Dropdown(
                id="global-country",
                options=_country_options(),
                value="CHN",
                clearable=False,
                className="ctl-dropdown",
            ),
            html.Label("Product", className="ctl-label"),
            dcc.Dropdown(
                id="global-product",
                options=_PRODUCT_OPTIONS,
                value="TOTAL",
                clearable=False,
                className="ctl-dropdown",
            ),
            html.Label("Indicator", className="ctl-label"),
            dcc.Dropdown(
                id="global-indicator",
                options=_INDICATOR_OPTIONS,
                value="export_value",
                clearable=False,
                className="ctl-dropdown",
            ),
        ],
    )


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
            # Global state (single source of truth; written only by the shell).
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
                    html.Aside(className="left-col", children=[_nav(), _console()]),
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

    @app.callback(
        Output(GLOBAL_FILTERS, "data"),
        Input("global-year", "value"),
        Input("global-country", "value"),
        Input("global-product", "value"),
        Input("global-indicator", "value"),
    )
    def _write_filters(year, country, product, indicator):
        return {
            "year": year,
            "country": country,
            "product": product,
            "indicator": indicator,
        }

    # Resize Plotly graphs in the newly-shown panel (hidden graphs lay out at 0×0).
    app.clientside_callback(
        """
        function(active) {
            window.setTimeout(function() {
                var panel = document.getElementById(active + '-panel');
                if (!panel) { return; }
                panel.querySelectorAll('.js-plotly-plot').forEach(function(gd) {
                    if (window.Plotly && window.Plotly.Plots) {
                        window.Plotly.Plots.resize(gd);
                    }
                });
            }, 80);
            return active;
        }
        """,
        Output(RESIZE_TOKEN, "data"),
        Input(ACTIVE_MODULE, "data"),
    )
