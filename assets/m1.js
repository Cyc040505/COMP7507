/* Partner selection changes stroke styles locally, preserving geographic view. */
(function () {
    const noUpdate = () => window.dash_clientside.no_update;
    const component = (type, children, className) => ({namespace: 'dash_html_components', type,
        props: {children, ...(className ? {className} : {})}});
    const rendered = new WeakMap();
    let generation = 0;

    function highlightMap(context, code, attempt, token) {
        if (token !== generation) return;
        const gd = document.querySelector('#M1-map .js-plotly-plot');
        if (!gd || !gd.offsetParent || !window.Plotly) return;
        const index = gd.data.findIndex(t => t.name === 'Trade partners');
        if (index < 0) return;
        const codes = context.mapCodes;
        if (JSON.stringify(gd.data[index].locations) !== JSON.stringify(codes)) {
            if (attempt < 12) setTimeout(() => highlightMap(context, code, attempt + 1, token), 50);
            return;
        }
        const signature = context.key + ':' + code;
        const previous = rendered.get(gd);
        if (previous?.signature === signature) return;
        const outside = code && !codes.includes(code) ? code : null;
        rendered.set(gd, {signature, outside});
        Plotly.restyle(gd, {
            'marker.line.color': [codes.map(p => p === code ? '#b27a2a' : '#ffffff')],
            'marker.line.width': [codes.map(p => p === code ? 2.4 : .7)]
        }, [index]);
        if (outside !== (previous?.outside || null)) {
            const overlay = gd.data.findIndex(t => t.name === 'Selected outside scope');
            const row = context.rows[outside];
            if (overlay >= 0) Plotly.restyle(gd, {
                locations: [outside ? [outside] : []], z: [outside ? [1] : []],
                text: [row ? [row.name + ' · ' + row.share + ' · ' + row.distance + ' · ' + row.usd] : []],
                hovertemplate: '%{text}<extra></extra>'
            }, [overlay]);
        }
    }

    window.dash_clientside = Object.assign({}, window.dash_clientside, {m1: {
        choose: function (mapClick, scatterClick, clicks, clear, exporter, year, product, scope, context, rowIds, active) {
            if (active !== 'M1') return noUpdate();
            const trigger = window.dash_clientside.callback_context.triggered?.[0];
            if (!trigger) return noUpdate();
            const raw = trigger.prop_id.slice(0, trigger.prop_id.lastIndexOf('.'));
            if (['M1-clear-selection', 'M1-exporter', 'M1-year', 'M1-product', 'M1-show'].includes(raw)) return null;
            let code;
            if (raw.startsWith('{')) {
                code = JSON.parse(raw).code;
                const index = (rowIds || []).findIndex(id => id.code === code);
                if (index < 0 || !clicks[index]) return noUpdate();
            } else {
                const point = (raw === 'M1-map' ? mapClick : scatterClick)?.points?.[0];
                if (!point) return noUpdate();
                code = point.location || (Array.isArray(point.customdata) ? point.customdata[0] : point.customdata);
            }
            return context?.rows[code] ? code : noUpdate();
        },
        highlight: function (selected, context, rowIds) {
            if (!context) return [noUpdate(), noUpdate(), noUpdate()];
            const row = context.rows[selected];
            const code = row ? selected : null;
            const detail = row ? [
                component('Span', context.exporter + ' → ' + code, 'm1-detail-code'),
                component('Strong', row.name, 'm1-detail-name'),
                ...[['Export share', row.share], ['Distance', row.distance], ['Exports', row.usd]].map(([label, value]) =>
                    component('Span', [component('Small', label), component('B', value)], 'm1-detail-metric'))
            ] : [component('Span', 'PARTNER DETAIL', 'm1-map-eyebrow'),
                 component('P', 'Select a map country, partner row or scatter point to compare share and distance.')];
            const token = ++generation;
            requestAnimationFrame(() => highlightMap(context, code, 0, token));
            return [detail, (rowIds || []).map(id => 'm1-partner-row' + (id.code === code ? ' active' : '')), token];
        },
        rememberView: function (relayout, exporter, previous) {
            if (!previous || previous.exporter !== exporter) return {exporter, gesture: {}};
            const gesture = Object.assign({}, previous.gesture);
            Object.entries(relayout || {}).forEach(([key, value]) => {
                if (/^geo\.(projection\.(scale|rotation(\.(lon|lat))?)|center(\.(lon|lat))?)$/.test(key)) gesture[key] = value;
            });
            return {exporter, gesture};
        }
    }});
})();
