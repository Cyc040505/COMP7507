"""Explicit selection transfers. The receiving module owns every write."""

from dash import Input, Output, State, ctx, dcc, html, no_update

from src.analytics.partners import FOCUS, partners
from src.analytics.product import chapters
from src.ids import ACTIVE_MODULE
from src.module_base import guard_active


def scope(country, year, product="TOTAL", *, last_year=2024):
    if country not in FOCUS:
        raise ValueError("Choose one of the six project economies in the source module.")
    if type(year) is not int or not 1995 <= year <= last_year:
        raise ValueError(f"This comparison supports 1995–{last_year}.")
    if product != "TOTAL" and product not in chapters():
        raise ValueError("Choose an available HS2 chapter or all products.")
    return country, year, product


def require_trade(country, year, product):
    frame = partners(country, year, product, "export")
    if frame.empty or frame.value.sum() <= 0:
        raise ValueError("No recorded exports for the selected economy, year and product.")


def actions(cid, label, *, apply_id="handoff", undo_id="handoff-undo"):
    return html.Div(
        [
            html.Button("Undo", id=cid(undo_id), n_clicks=0, hidden=True),
            html.Button(label, id=cid(apply_id), n_clicks=0, className="handoff-apply"),
        ],
        className="toolbar-actions",
    )


def controls(cid, *options, preview=False):
    return html.Div(
        [
            *options,
            *([html.Span(id=cid("handoff-preview"), className="handoff-note")] if preview else []),
            html.Div(id=cid("handoff-status"), className="handoff-note", role="status"),
            dcc.Store(id=cid("handoff-history")),
        ],
        className="handoff-controls",
    )


def register_transfer(
    app, module, cid, fields, source, prepare, *, preview=None, restore_on_undo=()
):
    """Register a filter transfer with one-step undo and optional dependent state."""
    if preview is not None:
        @app.callback(
            Output(cid("handoff-preview"), "children"),
            Input(ACTIVE_MODULE, "data"),
            *[Input(*field) for field in source],
        )
        def show_preview(active, *values):
            guard_active(module, active)
            return preview(*values)

    @app.callback(
        *[Output(cid(key), prop, allow_duplicate=duplicate) for key, prop, duplicate in fields],
        Output(cid("handoff-history"), "data"),
        Output(cid("handoff-status"), "children"),
        Input(cid("handoff"), "n_clicks"),
        Input(cid("handoff-undo"), "n_clicks"),
        State(ACTIVE_MODULE, "data"),
        *[State(*field) for field in source],
        *[State(cid(key), prop) for key, prop, _ in fields],
        *[State(cid(key), prop) for key, prop in restore_on_undo],
        State(cid("handoff-history"), "data"),
        prevent_initial_call=True,
    )
    def transfer(_apply, _undo, active, *args):
        guard_active(module, active)
        snapshot = list(args[len(source):-1])
        current = snapshot[:len(fields)]
        history = args[-1]
        keep = [no_update] * (len(fields) + 1)
        if ctx.triggered_id == cid("handoff-undo"):
            if not history or current != history.get("applied"):
                return *keep, "Selection has changed. Nothing to undo."
            restored = {"restored": history["dependent"]} if restore_on_undo else None
            return *history["before"], restored, ""
        try:
            result = prepare(*args[:len(source)], current)
        except (ValueError, FileNotFoundError) as exc:
            return *keep, str(exc)
        if result == current:
            return *keep, ""
        history = {"before": current, "applied": result}
        if restore_on_undo:
            history["dependent"] = {
                key: value for (key, _), value in zip(restore_on_undo, snapshot[len(fields):])
            }
        return *result, history, ""

    @app.callback(
        Output(cid("handoff-undo"), "hidden"),
        Input(cid("handoff-history"), "data"),
        *[Input(cid(key), prop) for key, prop, _ in fields],
    )
    def hide_undo(history, *current):
        return not history or list(current) != history.get("applied")
