"""Design tokens and small Plotly helpers.

Colours are ported from the report's section-4 UI
(``COMP7507_报告_Group7.html``) so the running app matches the written proposal.
"""

from __future__ import annotations

import plotly.graph_objects as go

# --- Palette (report section 4) ------------------------------------------------
INK = "#1a2233"
MUTED = "#5f6f86"
LINE = "#e3e8ef"
BG = "#f7f9fc"
ACCENT = "#1d4ed8"
ACCENT_SOFT = "#eef3ff"
ACCENT_LINE = "#c7d7fb"

# Narrative-stage accents.
S1 = "#0d9488"
S2 = "#7c3aed"
S3 = "#c2410c"
S4 = "#0369a1"

STAGE_COLORS = {"stage0": MUTED, "stage1": S1, "stage2": S2, "stage3": S3}

PLOT_TEMPLATE = "plotly_white"
_EMPTY_MSG = "Awaiting data · real results appear here once the data pipeline is built"


def empty_figure(message: str = _EMPTY_MSG, height: int = 420) -> go.Figure:
    """A real, renderable figure carrying a centred explanatory annotation.

    Every graph starts as one of these and every "not ready" branch returns one,
    so the skeleton never shows a blank/broken panel before the data layer exists.
    """
    fig = go.Figure()
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=height,
        margin=dict(l=24, r=24, t=56, b=24),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14, color=MUTED),
            )
        ],
    )
    return fig


def style_figure(fig, *, title=None, height: int = 420, uirevision=None):
    """Apply the shared template to a module-produced figure.

    ``uirevision`` keeps the user's zoom/selection when unrelated inputs change —
    pass a stable key (e.g. the module id).
    """
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=height,
        margin=dict(l=24, r=24, t=56, b=24),
        uirevision=uirevision,
    )
    if title:
        fig.update_layout(title=title)
    return fig
