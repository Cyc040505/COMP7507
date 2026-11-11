"""M5's two-year composition view; percentages retain the original denominators."""

import math

import plotly.graph_objects as go

from src import theme
from src.m5_portraits import NAMES, PLOT_FONT, finite


def comparison_summary(summary, rows, baseline, selected):
    """Structural findings describe the inspected year, independently of recovery."""
    result = summary.copy()
    lookup = {(r["country"], r["year"]): r for r in rows}
    for idx, country in result.country.items():
        base = lookup.get((country, baseline), {})
        current = lookup.get((country, selected), {})
        a, b = base.get("product_share"), current.get("product_share")
        result.loc[idx, "end_product_change_pp"] = 100 * (b - a) if finite(a) and finite(b) else math.nan
        low0, high0 = base.get("intra_share"), base.get("intra_upper")
        low1, high1 = current.get("intra_share"), current.get("intra_upper")
        result.loc[idx, "observed_region_change_pp"] = 100 * (low1 - low0) if finite(low0) and finite(low1) else math.nan
        if all(finite(v) for v in (low0, high0, low1, high1)):
            low = 0 if selected == baseline else 100 * (low1 - high0)
            high = 0 if selected == baseline else 100 * (high1 - low0)
        else:
            low = high = math.nan
        result.loc[idx, "region_change_min_pp"] = low
        result.loc[idx, "region_change_max_pp"] = high
    return result


def country_labels(figure, countries, centers, colors):
    """Fixed-pixel country labels: a colored vertical rule and a readable name."""
    for country, center in zip(countries, centers):
        figure.add_shape(type="line", xref="paper", yref="y",
            xsizemode="pixel", xanchor=0, x0=-164, x1=-164,
            ysizemode="pixel", yanchor=center, y0=-14, y1=14,
            line=dict(color=colors[country], width=3))
        figure.add_annotation(xref="paper", x=0, xshift=-154, yref="y", y=center,
            text=f"<b>{NAMES[country]}</b>", showarrow=False, xanchor="left", yanchor="middle",
            font=dict(family=PLOT_FONT, size=16, color=theme.INK))


def composition_figure(rows, countries, product, metric, baseline, selected, country_colors=None):
    if metric == "product" and product == "TOTAL":
        return theme.empty_figure("Select an HS2 chapter to compare its share of all-product exports.", height=330)
    country_colors = country_colors or {c: theme.country_color(c) for c in countries}
    lookup = {(r["country"], r["year"]): r for r in rows}
    years = list(dict.fromkeys((baseline, selected)))
    parts = [(f"HS{product}", theme.ACCENT), ("Other products", "#e8edf2")] if metric == "product" else [
        ("Known same-region", theme.ACCENT), ("Known other-region", "#e8edf2"),
        ("Unknown region", "#b8c3ce"),
    ]
    positions, ticktext, custom, splits, annotations = [], [], [], [], []
    for country_idx, country in enumerate(countries):
        for year_idx, year in enumerate(years):
            y = country_idx * (len(years) + .7) + year_idx
            row = lookup.get((country, year), {})
            if metric == "product":
                share = row.get("product_share")
                valid = finite(share) and 0 <= share <= 1 + 1e-8
                components = [share * 100, (1 - share) * 100] if valid else [None] * 2
                low = high = share * 100 if valid else None
            else:
                low, high, coverage = row.get("intra_share"), row.get("intra_upper"), row.get("region_coverage")
                valid = all(finite(v) for v in (low, high, coverage)) and 0 <= low <= coverage + 1e-8 <= 1 + 2e-8
                components = [low * 100, max(0, coverage - low) * 100, max(0, 1 - coverage) * 100] if valid else [None] * 3
                low, high = (low * 100, high * 100) if valid else (None, None)
            positions.append(y)
            ticktext.append(str(year))
            splits.append(components)
            custom.append([country, year, components[0], low, high])
            annotations.append(dict(
                x=(components[0] + 1.5) if valid else 50, y=y,
                text=f"{components[0]:.2f}%" if valid else "No data", showarrow=False,
                xanchor="left" if valid else "center", font=dict(size=14, color=theme.INK),
            ) if not valid or components[0] < 82 else dict(
                x=components[0] - 1.5, y=y, text=f"{components[0]:.2f}%", showarrow=False,
                xanchor="right", font=dict(size=14, color="white"),
            ))
    figure = go.Figure()
    for idx, (name, color) in enumerate(parts):
        figure.add_trace(go.Bar(
            name=name, orientation="h", x=[part[idx] for part in splits], y=positions,
            width=.88, marker=dict(color=color, line=dict(width=0)),
            customdata=custom,
            hovertemplate=f"<b>%{{customdata[0]}} · %{{customdata[1]}}</b><br>{name}: %{{x:.2f}}%<extra></extra>",
        ))
    height = max(330, len(countries) * (92 if len(years) > 1 else 56) + 110)
    theme.style_figure(figure, height=height)
    figure.update_layout(
        font=dict(family=PLOT_FONT, size=14, color=theme.INK),
        barmode="stack", margin=dict(l=178, r=18, t=28, b=78),
        legend=dict(orientation="h", traceorder="normal", x=0, y=-.2, xanchor="left", yanchor="top",
                    font=dict(size=13), itemclick=False, itemdoubleclick=False),
        hovermode="closest", clickmode="event", dragmode=False,
        annotations=annotations,
        uirevision=f"M5-composition-{product}-{metric}-{baseline}-{selected}",
    )
    figure.update_xaxes(range=[0, 100], dtick=25, ticksuffix="%", title=None, tickfont=dict(size=14), fixedrange=True)
    figure.update_yaxes(tickmode="array", tickvals=positions, ticktext=ticktext,
        range=[positions[-1] + .7, -.7] if positions else [1, 0],
        title=None, showgrid=False, tickfont=dict(size=14), fixedrange=True)
    country_labels(figure, countries, [i * (len(years) + .7) + (len(years) - 1) / 2 for i in range(len(countries))], country_colors)
    return figure


def change_figure(summary, countries, metric, baseline, selected, colors, height):
    """Zero-based signed changes; regional uncertainty stays explicit in hover."""
    values = {r["country"]: r for r in summary}
    positions, amounts, bases, labels, custom, bounds = [], [], [], [], [], []
    for idx, country in enumerate(countries):
        row = values.get(country, {})
        low = row.get("end_product_change_pp") if metric == "product" else row.get("region_change_min_pp")
        high = low if metric == "product" else row.get("region_change_max_pp")
        change = row.get("end_product_change_pp") if metric == "product" else row.get("observed_region_change_pp")
        valid = finite(change)
        positions.append(idx)
        amounts.append(change if valid else None)
        bases.append(0)
        labels.append(f"{change:+.2f} pp" if valid else "No data")
        custom.append([country, baseline, selected, low, high, change])
        if valid:
            bounds.append(abs(change))
    ceiling = max(1, math.ceil(max(bounds, default=1) * 1.35 * 2) / 2)
    figure = go.Figure(go.Bar(
        x=amounts, y=positions, base=bases, orientation="h", width=.48,
        marker=dict(color=[colors[c] for c in countries]), customdata=custom,
        hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]} → %{customdata[2]}<br>Known same-region share change: %{customdata[5]:+.2f} pp<br>Possible overall change: %{customdata[3]:+.2f} to %{customdata[4]:+.2f} pp<extra></extra>"
            if metric == "intra" else "<b>%{customdata[0]}</b> · %{customdata[1]} → %{customdata[2]}<br>Change: %{customdata[5]:+.2f} pp<extra></extra>"),
    ))
    theme.style_figure(figure, height=height)
    annotations = []
    for idx, country in enumerate(countries):
        low, high, change = custom[idx][3:]
        valid = finite(change)
        negative = valid and change < 0
        value_label = (f"<b>{change:+.2f}</b><span style='font-size:12px;color:{theme.MUTED}'> pp</span>"
                       if valid else labels[idx])
        annotations.append(dict(x=change if valid else 0, y=idx, text=value_label, showarrow=False,
            xanchor="right" if negative else "left", xshift=-7 if negative else 7,
            font=dict(size=14, color=theme.INK)))
    annotations += [dict(x=x, xref="paper", y=1.08, yref="paper", text=label,
        showarrow=False, font=dict(size=13, color=theme.MUTED))
        for x, label in ((.23, "Lower share"), (.77, "Higher share"))]
    if metric == "intra":
        annotations.append(dict(x=.5, xref="paper", y=-.28, yref="paper",
            text="Bars: known same-region share change · Hover: possible overall range", showarrow=False,
            font=dict(size=13, color=theme.MUTED)))
    figure.update_layout(font=dict(family=PLOT_FONT, size=14, color=theme.INK),
        showlegend=False, margin=dict(l=178, r=50, t=28, b=78), annotations=annotations,
        hovermode="closest", dragmode=False, clickmode="none")
    figure.update_xaxes(range=[-ceiling, ceiling], title="Change in share (percentage points)",
        tickfont=dict(size=14), title_font=dict(size=14), fixedrange=True, zeroline=True, zerolinecolor="#8292a3", zerolinewidth=1.5)
    figure.update_yaxes(tickmode="array", tickvals=positions, ticktext=[""] * len(countries),
        range=[len(countries)-.3, -.7], title=None, showgrid=False, tickfont=dict(size=14), fixedrange=True)
    country_labels(figure, countries, positions, colors)
    return figure
