"""Explicit selection transfers. The receiving module owns every write."""

from dash import dcc, html

from src.analytics.partners import FOCUS, partners
from src.analytics.product import chapters


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


def controls(cid, *options):
    return html.Div(
        [
            *options,
            html.Div(id=cid("handoff-status"), className="handoff-note", role="status"),
            dcc.Store(id=cid("handoff-history")),
        ],
        className="handoff-controls",
    )
