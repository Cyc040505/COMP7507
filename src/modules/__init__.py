"""Module registry.

Every feature module lives in its own file under ``src/modules/`` and exposes the
contract described in the README:

    MODULE_ID   : str   unique id, also the component-id prefix (never change)
    NAV_LABEL   : str   text shown in the left navigation
    ORDER       : int   navigation sort order (0 = overview)
    layout()    -> Component          the module's right-column panel
    register_callbacks(app) -> None   defines this module's callbacks

Adding a module later = drop in a new file + add one import + one entry below.
The shell never learns any module's internals.
"""

from __future__ import annotations

from src.modules import (
    m1_geography,
    m2_economy,
    m3_network,
    m4_product,
    m5_time,
    overview,
)

MODULES = [
    overview,
    m1_geography,
    m2_economy,
    m3_network,
    m4_product,
    m5_time,
]

MODULE_MAP = {m.MODULE_ID: m for m in MODULES}


def ordered_modules():
    """Modules sorted by their navigation order."""
    return sorted(MODULES, key=lambda m: m.ORDER)


def nav_items() -> list[tuple[str, str]]:
    """``(module_id, nav_label)`` pairs for the left navigation."""
    return [(m.MODULE_ID, m.NAV_LABEL) for m in ordered_modules()]


def build_panels() -> list:
    """One panel component per module, wrapped for show/hide toggling."""
    from dash import html

    from src.ids import mid

    panels = []
    for m in ordered_modules():
        panels.append(
            html.Div(
                m.layout(),
                id=mid(m.MODULE_ID, "panel"),
                className="module-panel",
            )
        )
    return panels


def register_all(app) -> None:
    """Register every module's callbacks on ``app``."""
    for m in MODULES:
        m.register_callbacks(app)
