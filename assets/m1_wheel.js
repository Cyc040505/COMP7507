/* Consume wheel scrolling only inside an interactive map. Do not stop propagation:
 * Plotly still receives the same event and handles its own zoom gesture. */
(function () {
    document.addEventListener('wheel', function (event) {
        const map = event.target instanceof Element && event.target.closest(
            '#M1-map, #new-map, #old-map'
        );
        if (map && map.offsetParent && event.cancelable) event.preventDefault();
    }, {capture: true, passive: false});
})();
