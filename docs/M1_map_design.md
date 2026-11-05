# M1 geography map

The M1 view fills partner countries using a sequential teal palette and highlights the exporter in amber. Top 10 by share and Top 40 partners encode export share (darker = larger share); Nearest 10 encodes the selected GeoDist distance in kilometres using the reversed palette (darker = nearer). Both scales start at zero and end at the largest displayed value. Grey countries are outside the displayed selection. The legend, colour bar and side ranking change with the mode. Hover over a country for share, export value and distance. No partner circles are drawn.

The side ranking shows six partners: descending share in share modes and ascending distance in Nearest 10. Bars represent the displayed measure. The headline always gives the displayed partners’ combined share of the selected export scope. Display filters never change the share denominator or full-scope correlation.

Plotly’s 50m country boundaries provide the territorial fills, including more detail for small economies. Very small territories can still be difficult to see at world scale; their values remain in the ranking and comparison table. `data/processed/country_locations.csv` (225 GeoDist main-city coordinates) is now used only to position the exporter’s text label, with an ISO country-centre fallback. Bilateral distances continue to come from the chosen GeoDist metric.

Styles are scoped to `.m1-module` in `assets/m1.css`. The map and ranking sit side by side on large screens and stack below 1150 px. Existing data sources, module-local filters and other modules are preserved.

The map supports wheel / trackpad zoom and drag navigation, with always-visible zoom-in, zoom-out and reset buttons. The current view persists when the year, product or display mode changes; selecting a different exporter resets the view. The map opts out of the shell’s static-chart interaction lock using `graph-interactive`, while still resizing when its module becomes visible.
