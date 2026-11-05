"""Design tokens and small Plotly helpers.

Colours are ported from the report's section-4 UI
(``COMP7507_报告_Group7.html``) so the running app matches the written proposal.
"""

from __future__ import annotations

from textwrap import wrap

import plotly.graph_objects as go
import plotly.io as pio

# --- Palette (report section 4) ------------------------------------------------
INK = "#1a2233"
MUTED = "#5f6f86"
LINE = "#e3e8ef"
BG = "#f7f9fc"
ACCENT = "#147e8b"
ACCENT_SOFT = "#eaf4f5"
ACCENT_LINE = "#b9d8dc"

# Narrative-stage accents.
S1 = "#0d9488"
S2 = "#7c3aed"
S3 = "#c2410c"
S4 = "#0369a1"

STAGE_COLORS = {"stage0": MUTED, "stage1": S1, "stage2": S2, "stage3": S3}

FONT = "Helvetica Neue, Segoe UI, Arial, sans-serif"
MAP_BG = "#102a3b"
MAP_LAND = "#29485d"
MAP_TEXT = "#eaf3f8"
PLOT_TEMPLATE = "trade_review"
pio.templates[PLOT_TEMPLATE] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, size=13, color=INK),
        title=dict(font=dict(size=16, color=INK), x=0, xanchor="left"),
        paper_bgcolor="white",
        plot_bgcolor="white",
        colorway=["#147e8b", "#c48c36", "#738ba5", "#776592", "#4a8271"],
        xaxis=dict(
            gridcolor="#e5ecf0",
            gridwidth=1,
            zeroline=False,
            automargin=True,
            tickfont=dict(size=12, color=MUTED),
            title=dict(font=dict(size=12, color=MUTED), standoff=14),
        ),
        yaxis=dict(
            gridcolor="#e5ecf0",
            gridwidth=1,
            zeroline=False,
            automargin=True,
            tickfont=dict(size=12, color=MUTED),
            title=dict(font=dict(size=12, color=MUTED), standoff=12),
        ),
        legend=dict(font=dict(size=12), bgcolor="rgba(0,0,0,0)", borderwidth=0),
        hoverlabel=dict(
            bgcolor="#152f41",
            bordercolor="#152f41",
            font=dict(family=FONT, size=13, color="white"),
        ),
        barcornerradius=3,
        bargap=0.3,
        margin=dict(l=55, r=25, t=30, b=55),
    ),
    data=dict(scatter=[go.Scatter(line=dict(width=2.4))]),
)
pio.templates.default = PLOT_TEMPLATE
_EMPTY_MSG = "Awaiting data · real results appear here once the data pipeline is built"


# --- Units --------------------------------------------------------------------
# BACI's ``v`` (export_value) is stored in THOUSANDS of US dollars. To convert a
# stored value to *trillions* of USD, divide by ``T_UNITS`` (= 1e9 thousand-USD per
# trillion). To convert to *dollars*, multiply by ``EXPORT_VALUE_UNIT`` (= 1000).
EXPORT_VALUE_UNIT = 1000  # thousand-USD → USD
T_UNITS = 1e9  # thousand-USD → trillion USD (1e9 × 1000 = 1e12 USD)


def stored_to_trillions(value_stored: float) -> float:
    """Convert a BACI stored value (thousand USD) to trillions of USD."""
    return value_stored / T_UNITS


def fmt_usd(value_stored: float, sig: int = 3) -> str:
    """Render a stored BACI value (thousand USD) as a compact USD string."""
    dollars = value_stored * EXPORT_VALUE_UNIT
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(dollars) >= div:
            return f"${dollars / div:,.{sig}f}".rstrip("0").rstrip(".") + unit
    return f"${dollars:,.0f}"


# --- Categorical country palette (M0 ranking) ----------------------------------
# 8 distinct identities, assigned in the reference palette's validated categorical
# order (CVD-safe, see the dataviz skill). Color follows the *country*, never its
# rank, so a country keeps its hue as it climbs the ranking. The tail of the
# ever-Top-10 set folds into a desaturated "Other" gray (the sanctioned exception
# for a low-chroma bucket); every bar also carries a direct country label so
# identity is never colour-alone (relief for the sub-3:1 slots).
COUNTRY_COLORS: dict[str, str] = {
    "CHN": "#2a78d6",  # blue
    "USA": "#eb6834",  # orange
    "DEU": "#1baf7a",  # aqua
    "KOR": "#eda100",  # yellow
    "JPN": "#e87ba4",  # magenta
    "MEX": "#008300",  # green
    "ITA": "#6250d6",  # violet
    "FRA": "#e34948",  # red
    "GBR": "#0d9488",  # teal
    "CAN": "#8d5524",  # brown
    "NLD": "#0e7490",  # cyan
    "BEL": "#7c3aed",  # purple
    "RUS": "#b45309",  # amber-brown
    "S19": "#6b7280",  # slate
}
OTHER_COLOR = "#6b7280"  # fallback for any top-10 member not in the table above


def country_color(iso3: str) -> str:
    """Stable per-country hue; unknown top-10 members fold into the 'Other' gray."""
    return COUNTRY_COLORS.get(iso3, OTHER_COLOR)


def empty_figure(message: str = _EMPTY_MSG, height: int = 420) -> go.Figure:
    """A real, renderable figure carrying a centred explanatory annotation.

    Every graph starts as one of these and every "not ready" branch returns one,
    so the skeleton never shows a blank/broken panel before the data layer exists.
    """
    # Presentation only: wrap plain annotations without dropping any content.
    # Preserve callers' existing Plotly HTML markup unchanged.
    annotation = message
    if isinstance(message, str) and "<" not in message:
        annotation = "<br>".join(
            line
            for paragraph in message.splitlines()
            for line in (
                wrap(
                    paragraph, width=40, break_long_words=False, break_on_hyphens=False
                )
                or [""]
            )
        )
    fig = go.Figure()
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=height,
        margin=dict(l=24, r=24, t=56, b=24),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text=annotation,
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
