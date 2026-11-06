/* Native data traces move with the points during every Plotly gesture.
 * Only extend endpoints when a completed view approaches their spare coverage.
 * Axis autorange clips are derived from real countries, never these endpoints.
 */
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    m2: {
        extendReferenceLines: function (figure, active) {
            if (active !== 'M2') return window.dash_clientside.no_update;
            const install = function () {
                const gd = document.querySelector('#M2-graph .js-plotly-plot');
                if (!gd || !gd._fullLayout || !gd.on) return;
                if (!gd._m2ReferenceUpdate) {
                    let busy = false, frame = null;
                    const schedule = function () {
                        if (frame !== null) return;
                        frame = window.requestAnimationFrame(function () {
                            frame = null;
                            update();
                        });
                    };
                    const update = function () {
                        if (busy || !gd._fullLayout || !window.Plotly) return;
                        const xr = gd._fullLayout.xaxis.range;
                        const yr = gd._fullLayout.yaxis.range;
                        const span = Math.max(xr[1] - xr[0], yr[1] - yr[0]);
                        if (!(span > 0 && Number.isFinite(span))) return;
                        const indices = [], xs = [], ys = [];
                        gd.data.forEach(function (trace, i) {
                            const ratio = trace.meta && trace.meta.m2_ratio;
                            if (!(ratio > 0)) return;
                            const offset = Math.log10(ratio);
                            const lo = Math.min(xr[0], yr[0] - offset);
                            const hi = Math.max(xr[1], yr[1] - offset);
                            if (Math.log10(trace.x[0]) <= lo - span * .25 &&
                                Math.log10(trace.x[1]) >= hi + span * .25) return;
                            // Keep powers finite and positive, including y = ratio*x.
                            const low = Math.max(-300 - Math.min(offset, 0), lo - 2 * span);
                            const high = Math.min(300 - Math.max(offset, 0), hi + 2 * span);
                            const x = [10 ** low, 10 ** high];
                            if (x[0] === trace.x[0] && x[1] === trace.x[1]) return;
                            indices.push(i);
                            xs.push(x);
                            ys.push(x.map(v => v * ratio));
                        });
                        if (!indices.length) return;
                        busy = true;
                        // Restyle endpoints only; preserve the user's relayoutData.
                        Promise.resolve(Plotly.restyle(gd, {x: xs, y: ys}, indices))
                            .finally(function () { busy = false; schedule(); });
                    };
                    gd._m2ReferenceUpdate = schedule;
                    gd.on('plotly_afterplot', schedule);
                    gd.on('plotly_relayout', schedule);
                }
                gd._m2ReferenceUpdate();
            };
            window.setTimeout(install, 0);
            window.setTimeout(install, 200);
            return window.dash_clientside.no_update;
        }
    }
});
