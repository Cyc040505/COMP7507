"""Component-id helpers.

Namespacing is the backbone of this multi-module app: every module owns the
``{MODULE_ID}-*`` prefix *exclusively*, while the shell reserves ``global-*`` and
``nav-*``. This keeps Dash's startup id-validation useful as a fail-fast guard for
the team (see README "Module development conventions").
"""

from __future__ import annotations

# Shell-owned ids (never used by a module).
GLOBAL_FILTERS = "global-filters"
ACTIVE_MODULE = "active-module"
RESIZE_TOKEN = "ui-resize-token"


def mid(module_id: str, name: str) -> str:
    """Namespaced id for a component owned by ``module_id``.

    >>> mid("M1", "graph")
    'M1-graph'
    """
    return f"{module_id}-{name}"


def nav_id(module_id: str) -> str:
    """Id of the left-nav button for a module."""
    return f"nav-{module_id}"
