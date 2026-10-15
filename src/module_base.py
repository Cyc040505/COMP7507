"""Shared helpers for feature modules.

Small utilities that keep each ``src/modules/*.py`` file short and consistent:
the standard "recompute only while active" guard, and a human-readable summary of
the current global filters for placeholder panels.
"""

from __future__ import annotations

from dash import callback_context
from dash.exceptions import PreventUpdate

# Global-console parameter labels for building summaries.
_FILTER_LABELS = {
    "year": "Year",
    "country": "Country",
    "product": "Product",
    "indicator": "Indicator",
}


def guard_active(module_id: str, active_module) -> None:
    """Block hidden modules from recomputing.

    Call this first inside a module callback: when the module is not the active
    one, raise ``PreventUpdate`` so a global-filter change does not trigger work in
    six hidden panels. Because ``active-module`` is also a callback ``Input``,
    becoming the active module re-runs the callback and renders it on switch.
    """
    if active_module != module_id:
        raise PreventUpdate


def triggered_id(default: str | None = None):
    """The id of the component that triggered the current callback."""
    return callback_context.triggered_id if callback_context.triggered else default


def describe_filters(filters: dict | None, extra: str | None = None) -> str:
    """Render the active global filters as a one-line summary string."""
    filters = filters or {}
    parts = []
    for key, label in _FILTER_LABELS.items():
        value = filters.get(key)
        if value not in (None, ""):
            parts.append(f"{label} {value}")
    if extra:
        parts.append(extra)
    return " · ".join(parts) if parts else "no parameters set"


def placeholder_text(module_label: str, filters: dict | None, action: str, extra: str | None = None) -> str:
    """A placeholder annotation describing what this panel will show."""
    return f"{module_label} | {describe_filters(filters, extra)}\nTo implement: {action}"
