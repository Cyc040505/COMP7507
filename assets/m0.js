/* M0 ranking transition.
 *
 * Dash repaints a dcc.Graph with Plotly.react, which swaps everything instantly.
 * Plotly's own animate/transition path is unusable here: tweening a categorical
 * y axis whose categories change every year leaves stale tick labels, and the
 * rounded-bar path generator emits invalid arcs while a bar is still tiny.
 *
 * Instead the figure is rendered normally (so axes, labels and colors are
 * always the final, correct ones) and only the geometry is animated:
 *   • bars grow/shrink from the country's previous-year share;
 *   • bars and their axis labels slide between row positions when the ranking
 *     order changes, so swaps read as movement rather than a jump.
 * If a new figure arrives mid-flight, the running tween is reset and its
 * current lengths/rows are carried into the next one.
 */
var M0_TWEEN_DURATION = 450;

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    m0: {
        tween_ranking: function (figure, view) {
            var noUpdate = window.dash_clientside.no_update;
            var state = (window.__m0RankTween = window.__m0RankTween || {
                previous: null,
                previousOrder: null,
                lastView: null,
                animation: null,
                poll: null
            });
            var trace = figure && figure.data && figure.data[0];
            var host = document.getElementById("M0-share");
            var gd = host && host.querySelector(".js-plotly-plot");
            var isBar = !!(trace && trace.type === "bar" && trace.y);

            // Plotly hands arrays over as typed-array wrappers, and it mutates
            // the traces it renders, so record the shares as plain numbers now.
            var shares = null;
            var order = null;
            if (isBar) {
                var xs = asArray(trace.x);
                var ys = asArray(trace.y);
                shares = {};
                ys.forEach(function (country, i) {
                    shares[country] = xs[i];
                });
                order = ys;
            }
            var previous = state.previous;
            var previousOrder = state.previousOrder;
            var viewChanged = view !== state.lastView;
            state.previous = shares;
            state.previousOrder = order;
            state.lastView = view;

            stopAnimation(state);
            if (state.poll) {
                cancelAnimationFrame(state.poll);
                state.poll = null;
            }

            if (!gd || !isBar || view !== "ranking" || !previous) {
                state.interrupted = null;
                state.interruptedRows = null;
                return noUpdate;
            }
            var reduced =
                window.matchMedia &&
                window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            if (viewChanged || reduced) {
                state.interrupted = null;
                state.interruptedRows = null;
                return noUpdate;
            }

            // Dash may commit the new figure after this callback runs, so wait
            // (a frame at a time, briefly) until the DOM shows the new values.
            var deadline = performance.now() + 2000;
            var start = function () {
                state.poll = null;
                if (!isRendered(gd, trace)) {
                    if (performance.now() < deadline && isBarRendered(gd)) {
                        state.poll = requestAnimationFrame(start);
                    } else {
                        state.interrupted = null;
                        state.interruptedRows = null;
                    }
                    return;
                }
                animate(gd, previous, previousOrder, trace, state);
            };
            start();
            return noUpdate;
        }
    }
});

function asArray(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value;
    if (typeof value !== "object") return [];
    if (value._inputArray) {
        return Object.keys(value._inputArray)
            .sort(function (a, b) {
                return Number(a) - Number(b);
            })
            .map(function (key) {
                return value._inputArray[key];
            });
    }
    if (typeof value.bdata === "string") {
        return decodeBase64(value.bdata, value.dtype);
    }
    return [];
}

function decodeBase64(b64, dtype) {
    var binary = atob(b64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    var view = new DataView(bytes.buffer);
    var size = { f8: 8, f4: 4, i4: 4, u4: 4, i2: 2, u2: 2, i1: 1, u1: 1 }[
        dtype
    ];
    if (!size) return [];
    var out = [];
    for (var offset = 0; offset + size <= bytes.length; offset += size) {
        if (dtype === "f8") out.push(view.getFloat64(offset, true));
        else if (dtype === "f4") out.push(view.getFloat32(offset, true));
        else if (dtype === "i4") out.push(view.getInt32(offset, true));
        else if (dtype === "u4") out.push(view.getUint32(offset, true));
        else if (dtype === "i2") out.push(view.getInt16(offset, true));
        else if (dtype === "u2") out.push(view.getUint16(offset, true));
        else if (dtype === "i1") out.push(view.getInt8(offset));
        else out.push(view.getUint8(offset));
    }
    return out;
}

function isBarRendered(gd) {
    return gd.querySelectorAll(".barlayer .point path").length > 0;
}

// The DOM keeps the last painted values, unlike gd.data which Plotly mutates
// in place, so the labels are the honest signal that the new year is on screen.
function isRendered(gd, trace) {
    var labels = gd.querySelectorAll(".barlayer text.bartext");
    var texts = asArray(trace.text);
    if (!labels.length || labels.length !== asArray(trace.y).length) {
        return false;
    }
    for (var i = 0; i < labels.length; i++) {
        if (labels[i].textContent !== String(texts[i])) return false;
    }
    return true;
}

function stopAnimation(state) {
    if (state.animation) {
        if (state.animation.raf) cancelAnimationFrame(state.animation.raf);
        // Remember where each bar actually was, so a tween interrupted by a
        // new year continues from that length/row instead of snapping back.
        state.interrupted = {};
        state.interruptedRows = {};
        state.animation.items.forEach(function (item) {
            if (typeof item.lastScale === "number") {
                state.interrupted[item.country] = item.target * item.lastScale;
            }
            if (typeof item.lastRow === "number") {
                state.interruptedRows[item.country] = item.lastRow;
            }
        });
        restore(state.animation.items);
        state.animation = null;
    }
}

function restore(items) {
    items.forEach(function (item) {
        item.path.removeAttribute("transform");
        item.point.removeAttribute("transform");
        item.point.style.opacity = item.pointOpacity;
        if (item.tick) {
            item.tick.removeAttribute("transform");
            item.tick.style.opacity = item.tickOpacity;
        }
        if (item.text) {
            if (item.textTransform === null) item.text.removeAttribute("transform");
            else item.text.setAttribute("transform", item.textTransform);
        }
    });
}

function animate(gd, previous, previousOrder, trace, state) {
    var points = Array.prototype.slice.call(
        gd.querySelectorAll(".barlayer .point")
    );
    var paths = Array.prototype.slice.call(
        gd.querySelectorAll(".barlayer .point path")
    );
    var labels = Array.prototype.slice.call(
        gd.querySelectorAll(".barlayer text.bartext")
    );
    var ticks = Array.prototype.slice.call(
        gd.querySelectorAll(".yaxislayer-above .ytick")
    );
    var ys = asArray(trace.y);
    var xs = asArray(trace.x);
    if (paths.length !== ys.length || points.length !== ys.length) return;

    var rowHeight = 0;
    if (points.length > 1) {
        rowHeight =
            points[1].getBoundingClientRect().top -
            points[0].getBoundingClientRect().top;
    }
    var tickByCountry = {};
    ticks.forEach(function (tick) {
        var label = tick.textContent.trim();
        if (label) tickByCountry[label] = tick;
    });
    var previousRow = {};
    (previousOrder || []).forEach(function (country, index) {
        previousRow[country] = index;
    });

    var carriedShares = state.interrupted || {};
    var carriedRows = state.interruptedRows || {};
    state.interrupted = null;
    state.interruptedRows = null;

    var items = [];
    for (var i = 0; i < paths.length; i++) {
        var country = ys[i];
        var current = xs[i];
        if (typeof current !== "number" || !(current > 0)) continue;
        var startRow =
            carriedRows[country] !== undefined
                ? carriedRows[country]
                : previousRow[country];
        var before =
            carriedShares[country] !== undefined
                ? carriedShares[country]
                : previous[country];
        // An unseen country enters from zero; anything else starts at the
        // share it had (or that its interrupted tween had reached).
        var ratio = before === undefined ? 0 : before / current;
        if (!isFinite(ratio) || ratio < 0) ratio = 0;
        var entering = startRow === undefined;
        var rowDelta = entering ? 0 : (startRow - i) * rowHeight;
        if (ratio === 1 && rowDelta === 0 && !entering) continue;
        var box = paths[i].getBBox();
        var tick = tickByCountry[country] || null;
        items.push({
            country: country,
            endRow: i,
            startRow: entering ? null : startRow,
            rowDelta: rowDelta,
            point: points[i],
            pointOpacity: points[i].style.opacity,
            path: paths[i],
            text: labels[i] || null,
            textTransform: labels[i] ? labels[i].getAttribute("transform") : null,
            tick: tick,
            tickOpacity: tick ? tick.style.opacity : null,
            left: box.x,
            width: box.width,
            target: current,
            ratio: ratio
        });
    }
    if (!items.length) return;

    var draw = function (eased) {
        items.forEach(function (item) {
            var scale = item.ratio + (1 - item.ratio) * eased;
            var shift = item.rowDelta * (1 - eased);
            item.lastScale = scale;
            item.lastRow =
                item.startRow === null ? item.endRow : item.startRow + (item.endRow - item.startRow) * eased;
            // Vertical motion lives on the group so bar and label stay in step.
            item.point.setAttribute("transform", "translate(0 " + shift + ")");
            if (item.startRow === null) item.point.style.opacity = eased;
            if (item.tick) {
                item.tick.setAttribute("transform", "translate(0 " + shift + ")");
                // Two labels swapping rows pass through the same spot; a dip
                // in opacity keeps the crossing legible instead of garbled.
                if (item.rowDelta !== 0) {
                    item.tick.style.opacity = 1 - 0.55 * Math.sin(Math.PI * eased);
                }
            }
            item.path.setAttribute(
                "transform",
                "translate(" + item.left + " 0) scale(" + scale +
                    " 1) translate(" + -item.left + " 0)"
            );
            if (item.text) {
                // Keep the label at the moving bar end instead of its final
                // position; only the offset changes, so the glyphs stay crisp.
                var dx = item.width * (scale - 1);
                item.text.setAttribute(
                    "transform",
                    "translate(" + dx + " 0)" +
                        (item.textTransform ? " " + item.textTransform : "")
                );
            }
        });
    };

    // Paint the start state in this task so the previous year's lengths are
    // never preceded by a frame of the final ones.
    draw(0);
    var began = performance.now();
    var frame = function (now) {
        var progress = Math.min(1, (now - began) / M0_TWEEN_DURATION);
        var eased =
            progress < 0.5
                ? 4 * progress * progress * progress
                : 1 - Math.pow(-2 * progress + 2, 3) / 2;
        draw(eased);
        if (progress < 1 && items[0].path.isConnected) {
            state.animation = { raf: requestAnimationFrame(frame), items: items };
        } else {
            restore(items);
            state.animation = null;
        }
    };
    state.animation = { raf: requestAnimationFrame(frame), items: items };
}

/* Playback guard.
 *
 * Year playback is driven by a server-side interval. When the reader takes the
 * slider over, that has to stop before the new value commits, otherwise a step
 * still in flight can land afterwards and replace the chosen year. Pausing on
 * pointerdown / arrow key (by pressing the same Pause button) closes that gap.
 */
(function () {
    if (window.__m0PlayGuard) return;
    window.__m0PlayGuard = true;

    var pauseIfPlaying = function () {
        var button = document.getElementById("M0-play");
        if (button && button.classList.contains("on")) button.click();
    };
    var onSlider = function (target) {
        return !!(
            target &&
            target.closest &&
            target.closest("#M0-year .dash-slider-root")
        );
    };
    document.addEventListener(
        "pointerdown",
        function (event) {
            if (event.target.closest && event.target.closest("#M0-play")) return;
            if (onSlider(event.target)) pauseIfPlaying();
        },
        true
    );
    document.addEventListener(
        "keydown",
        function (event) {
            var keys = [
                "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
                "Home", "End", "PageUp", "PageDown"
            ];
            if (keys.indexOf(event.key) === -1) return;
            if (onSlider(event.target)) pauseIfPlaying();
        },
        true
    );
})();
