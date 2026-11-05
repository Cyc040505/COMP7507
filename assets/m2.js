/* Reference lines are clipped in log space to the current plot rectangle.
 * Domain coordinates keep these decorations out of Plotly's autorange.
 */
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    m2: {
        extendReferenceLines: function (figure, active) {
            if (active !== 'M2') return window.dash_clientside.no_update;
            const install = function () {
                const gd = document.querySelector('#M2-graph .js-plotly-plot');
                if (!gd || !gd._fullLayout || !gd.on) return;
                if (!gd._m2ReferenceUpdate) {
                    let busy = false;
                    const update = function () {
                        if (busy || !gd._fullLayout || !window.Plotly) return;
                        const xr = gd._fullLayout.xaxis.range;
                        const yr = gd._fullLayout.yaxis.range;
                        const dx = xr[1] - xr[0], dy = yr[1] - yr[0];
                        if (!(dx > 0 && dy > 0)) return;
                        const patch = {};
                        (gd.layout.shapes || []).forEach(function (shape, i) {
                            if (!(shape.name || '').startsWith('m2-ratio-')) return;
                            const ratio = Number(shape.name.slice('m2-ratio-'.length));
                            const offset = Math.log10(ratio);
                            const lo = Math.max(xr[0], yr[0] - offset);
                            const hi = Math.min(xr[1], yr[1] - offset);
                            const trace = gd.data.find(t => t.legendgroup === 'ratio-' + ratio);
                            const visible = hi >= lo && trace && trace.visible !== 'legendonly' && trace.visible !== false;
                            const values = {visible: Boolean(visible)};
                            if (visible) {
                                values.x0 = (lo - xr[0]) / dx;
                                values.x1 = (hi - xr[0]) / dx;
                                values.y0 = (lo + offset - yr[0]) / dy;
                                values.y1 = (hi + offset - yr[0]) / dy;
                            }
                            Object.entries(values).forEach(function ([key, value]) {
                                if (typeof value === 'boolean' ? shape[key] !== value :
                                    !Number.isFinite(shape[key]) || Math.abs(shape[key] - value) > 1e-9) {
                                    patch['shapes[' + i + '].' + key] = value;
                                }
                            });
                        });
                        if (!Object.keys(patch).length) return;
                        busy = true;
                        // A decoration update must not overwrite Graph.relayoutData,
                        // which stores the user's zoom/pan ranges for callbacks.
                        Promise.resolve(Plotly.update(gd, {}, patch)).finally(function () { busy = false; });
                    };
                    gd._m2ReferenceUpdate = update;
                    gd.on('plotly_afterplot', update);
                    gd.on('plotly_relayout', update);
                }
                gd._m2ReferenceUpdate();
            };
            // Dash may deliver the figure before Graph has finished Plotly.react.
            window.setTimeout(install, 0);
            window.setTimeout(install, 200);
            return window.dash_clientside.no_update;
        }
    }
});
