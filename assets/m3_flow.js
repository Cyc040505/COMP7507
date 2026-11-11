/* M3 · 01 Trade flows — travel each trade arc from exporter to importer.
 *
 * Pure SVG overlay: we read the already-drawn Plotly scattergeo paths and move a
 * small arrowhead along each one. No figure data is added or changed, so hover,
 * click, export and every analytical encoding keep working untouched.
 */
(function () {
    if (window.__m3FlowBooted) return;
    window.__m3FlowBooted = true;

    var NS = 'http://www.w3.org/2000/svg';
    var PERIOD = 2600;      // ms for one full traversal
    var SAMPLES = 64;       // pre-sampled positions per arc
    var MIN_PATH = 40;      // px; skips arrow heads (~8px) and legend stubs (0px)
    var motionQuery = window.matchMedia
        ? window.matchMedia('(prefers-reduced-motion: reduce)')
        : null;

    function pauses() {
        return motionQuery && motionQuery.matches;
    }

    function geometry(path) {
        var length;
        try {
            length = path.getTotalLength();
        } catch (error) {
            return null;
        }
        if (!length || length < MIN_PATH) return null;
        var points = [];
        for (var i = 0; i <= SAMPLES; i += 1) {
            points.push(path.getPointAtLength((length * i) / SAMPLES));
        }
        return {length: length, points: points};
    }

    function token(stroke, strokeOpacity, width, path) {
        var group = document.createElementNS(NS, 'g');
        group.setAttribute('class', 'm3-flow-token');
        group.style.pointerEvents = 'none';
        var head = document.createElementNS(NS, 'path');
        head.setAttribute('d', 'M 5.5,0 L -3.5,3.1 L -3.5,-3.1 Z');
        head.setAttribute('fill', stroke || '#75b5c7');
        // Plotly splits rgba() into stroke + stroke-opacity; keep the fade.
        head.setAttribute('fill-opacity', String(strokeOpacity));
        head.setAttribute('stroke', 'none');
        group.appendChild(head);
        // Wider arcs carry a slightly larger arrowhead, like their strokes.
        var scale = Math.min(1.7, 0.75 + 0.16 * width);
        group.setAttribute('data-scale', String(scale));
        path.parentNode.appendChild(group);
        return group;
    }

    function collect(plot) {
        var layer = plot.querySelector('.scatterlayer');
        if (!layer) return [];
        var nodes = layer.children;
        var arcs = [];
        for (var i = 0; i < nodes.length; i += 1) {
            var trace = nodes[i];
            if (!trace.classList || !trace.classList.contains('trace')) continue;
            // Leader lines of the capital callouts carry a text label; trade arcs
            // only carry hover text, so a rendered <text> excludes them.
            if (trace.querySelector('text')) continue;
            var path = trace.querySelector('path.js-line');
            if (!path) continue;
            var shape = geometry(path);
            if (!shape) continue;
            var style = window.getComputedStyle(path);
            var alpha = parseFloat(style.strokeOpacity);
            if (isNaN(alpha)) alpha = 1;
            arcs.push({
                node: token(
                    style.stroke, alpha,
                    parseFloat(style.strokeWidth) || 1, path
                ),
                length: shape.length,
                points: shape.points,
                // Stagger the arcs so the map pulses instead of blinking in sync.
                phase: (arcs.length % 7) / 7
            });
        }
        return arcs;
    }

    function clear(state) {
        if (state.frame) window.cancelAnimationFrame(state.frame);
        for (var i = 0; i < state.arcs.length; i += 1) {
            var node = state.arcs[i].node;
            if (node && node.parentNode) node.parentNode.removeChild(node);
        }
        state.arcs = [];
    }

    function place(arc, t) {
        var count = arc.points.length - 1;
        var scaled = Math.min(Math.max(t, 0), 1) * count;
        var low = Math.min(Math.floor(scaled), count - 1);
        var mix = scaled - low;
        var a = arc.points[low];
        var b = arc.points[low + 1];
        var x = a.x + (b.x - a.x) * mix;
        var y = a.y + (b.y - a.y) * mix;
        var angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
        arc.node.setAttribute(
            'transform',
            'translate(' + x + ',' + y + ') rotate(' + angle + ') scale(' +
                arc.node.getAttribute('data-scale') + ')'
        );
    }

    function run(plot) {
        var state = plot.__m3FlowState;
        if (!state || !state.arcs.length) return;
        var start = window.performance.now();
        function step(now) {
            var elapsed = (now - start) % PERIOD;
            for (var i = 0; i < state.arcs.length; i += 1) {
                var arc = state.arcs[i];
                var t = (elapsed / PERIOD + arc.phase) % 1;
                place(arc, t);
                // Fade out at the destination, then start again at the origin.
                arc.node.setAttribute(
                    'opacity', t > 0.93 ? String((1 - t) / 0.07) : '1'
                );
            }
            state.frame = window.requestAnimationFrame(step);
        }
        state.frame = window.requestAnimationFrame(step);
    }

    function restart(plot) {
        var state = plot.__m3FlowState;
        if (!state) return;
        clear(state);
        if (pauses()) return;
        state.arcs = collect(plot);
        if (state.arcs.length) run(plot);
    }

    // The graph can mount before its geo layer is drawn (hidden panel, first
    // paint), so keep checking until at least one arc exists.
    function retry(plot, left) {
        if (!plot.isConnected || left <= 0) return;
        var state = plot.__m3FlowState;
        if (!state || state.arcs.length || pauses()) return;
        window.setTimeout(function () {
            restart(plot);
            if (!state.arcs.length) retry(plot, left - 1);
        }, 150);
    }

    function attach(plot) {
        if (plot.__m3FlowState) return;
        plot.__m3FlowState = {arcs: [], frame: null};
        plot.on('plotly_afterplot', function () {
            restart(plot);
        });
        if (motionQuery) {
            var onChange = function () {
                restart(plot);
            };
            if (motionQuery.addEventListener) motionQuery.addEventListener('change', onChange);
            else if (motionQuery.addListener) motionQuery.addListener(onChange);
        }
        restart(plot);
        retry(plot, 60);
    }

    function boot() {
        // Dash renders the graph after this script loads, so wait for it once.
        var tries = 0;
        var timer = window.setInterval(function () {
            var plot = document.querySelector('#M3-graph .js-plotly-plot');
            tries += 1;
            if (plot) {
                window.clearInterval(timer);
                attach(plot);
            } else if (tries > 200) {
                window.clearInterval(timer);
            }
        }, 100);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
