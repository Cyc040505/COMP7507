"""COMP7507 Group 7 — Global Trade Over Three Decades.

Single-page Plotly Dash application (framework skeleton). Run from the project
root:

    python app.py

See README.md for the data-pipeline and module-development conventions.
"""

from __future__ import annotations

from dash import Dash

from src import config
from src.layout import build_layout, register_shell_callbacks
from src.modules import register_all

app = Dash(
    __name__,
    title="Global Trade Over Three Decades · Group 7",
    # All module panels are built once at startup, so Dash's id validation stays
    # on as a fail-fast guard for the team.
    suppress_callback_exceptions=False,
)
server = app.server

# Dev convenience: don't let the browser hard-cache assets/styles.css.
server.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

app.layout = build_layout()

register_shell_callbacks(app)
register_all(app)


def _assert_unique_ids(component, seen: dict) -> None:
    """Dev-only guard: every component id in the layout must be globally unique."""
    from dash.development.base_component import Component

    if isinstance(component, (list, tuple)):
        for item in component:
            _assert_unique_ids(item, seen)
        return
    if isinstance(component, Component):
        comp_id = getattr(component, "id", None)
        if comp_id is not None:
            if comp_id in seen:
                raise RuntimeError(
                    f"Duplicate component id {comp_id!r} "
                    f"(used by {type(component).__name__} and {seen[comp_id]})."
                )
            seen[comp_id] = type(component).__name__
        children = getattr(component, "children", None)
        if children is not None:
            _assert_unique_ids(children, seen)


if __debug__:
    _assert_unique_ids(app.layout, {})


if __name__ == "__main__":
    print(f"[startup] data mode: {'DEMO (fallback)' if not config.DATA_READY else 'ANALYTIC TABLES'}")
    print("[startup] open http://127.0.0.1:8050")
    app.run(host="127.0.0.1", port=8050, debug=False, use_reloader=False)
