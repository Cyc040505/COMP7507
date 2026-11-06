"""Browser acceptance checks; run the M2 launcher first (default port 8052 here)."""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8052")
    args = parser.parse_args()
    libs = ROOT / ".venv/browser-libs/usr/lib/x86_64-linux-gnu"
    if libs.exists():
        os.environ["LD_LIBRARY_PATH"] = str(libs) + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
    screenshots = ROOT / "docs/screenshots"
    screenshots.mkdir(exist_ok=True)
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.goto(args.url, wait_until="networkidle")
        expect(page.locator("#M2-finding")).to_contain_text("Japan")
        expect(page.locator("#M2-cards")).to_contain_text("35.27%")
        expect(page.locator("#M2-cards")).to_contain_text("18.70%")
        expect(page.locator("#M2-relative")).to_contain_text("5.5% lower")
        expect(page.locator("#M2-relative")).to_contain_text("49.9% lower")
        expect(page.locator("#M2-relative")).to_contain_text("16.57 percentage points lower")
        page.wait_for_function("document.querySelector('#M2-relative-graph .js-plotly-plot')?._fullLayout")
        def check_reference_edges():
            page.wait_for_function("""() => {
                const g = document.querySelector('#M2-graph .js-plotly-plot');
                const x = g._fullLayout.xaxis.range, y = g._fullLayout.yaxis.range;
                const traces = g.data.filter(t => t.meta?.m2_ratio);
                if (traces.length !== 3) return false;
                return traces.every(t => {
                    const offset = Math.log10(t.meta.m2_ratio);
                    const lo = Math.max(x[0], y[0]-offset), hi = Math.min(x[1], y[1]-offset);
                    if (hi < lo) return true;
                    return Math.log10(t.x[0]) <= lo && Math.log10(t.x[1]) >= hi &&
                        t.x.every((v,i) => Math.abs(Math.log10(t.y[i]/v)-offset) < 1e-7);
                });
            }""")
        check_reference_edges()
        page.screenshot(path=str(screenshots / "M2_desktop.png"), full_page=True)
        checks.append("Default Germany/Japan cards, finding and desktop screenshot")

        def ranges():
            return page.locator("#M2-graph .js-plotly-plot").evaluate(
                "e => ({x: [...e._fullLayout.xaxis.range], y: [...e._fullLayout.yaxis.range]})")

        def check_live_alignment():
            # Check rendered SVG coordinates while the mouse is still down,
            # including the transform Plotly applies before a final replot.
            page.wait_for_function("""() => {
                const g = document.querySelector('#M2-graph .js-plotly-plot');
                const rect = g.querySelector('.nsewdrag').getBoundingClientRect();
                const xr = g._fullLayout.xaxis.range, yr = g._fullLayout.yaxis.range;
                const traces = [...g.querySelectorAll('.scatterlayer .trace')];
                return g.data.slice(0,3).every((t,i) => {
                    const path = traces[i].querySelector('.js-line');
                    if (!path) return false;
                    const offset = Math.log10(t.meta.m2_ratio);
                    const lo = Math.max(xr[0], yr[0]-offset), hi = Math.min(xr[1], yr[1]-offset);
                    if (hi < lo) return true;
                    const x = (lo+hi)/2, y = x+offset;
                    const expected = {x: rect.x+(x-xr[0])/(xr[1]-xr[0])*rect.width,
                                      y: rect.bottom-(y-yr[0])/(yr[1]-yr[0])*rect.height};
                    const matrix = path.getScreenCTM();
                    const a = path.getPointAtLength(0).matrixTransform(matrix);
                    const b = path.getPointAtLength(path.getTotalLength()).matrixTransform(matrix);
                    const error = Math.abs((b.x-a.x)*(a.y-expected.y)-(a.x-expected.x)*(b.y-a.y)) / Math.hypot(b.x-a.x,b.y-a.y);
                    return error < 1;
                });
            }""")

        def wait_range_change(before, shrink=False):
            page.wait_for_function("""({before, shrink}) => {
                const g = document.querySelector('#M2-graph .js-plotly-plot');
                const x = g._fullLayout.xaxis.range;
                return shrink ? x[1]-x[0] < (before.x[1]-before.x[0]) * .98
                    : Math.abs(x[0]-before.x[0]) > .001;
            }""", arg={"before": before, "shrink": shrink})

        def reset_view():
            page.locator('#M2-graph [data-title="Reset axes"]').click()
            page.wait_for_function("""before => {
                const x = document.querySelector('#M2-graph .js-plotly-plot')._fullLayout.xaxis.range;
                return Math.abs(x[0]-before.x[0]) < 1e-6 && Math.abs(x[1]-before.x[1]) < 1e-6;
            }""", arg=initial)

        page.locator("#M2-graph").scroll_into_view_if_needed()
        initial = ranges()
        status = page.locator("#M2-match-status").inner_text()
        plot = page.locator("#M2-graph .nsewdrag").bounding_box()
        page.locator("#M2-graph .js-plotly-plot").evaluate("""g => {
            g._m2TestUpdates = {afterplot: 0, restyle: 0};
            g.on('plotly_afterplot', () => g._m2TestUpdates.afterplot++);
            g.on('plotly_restyle', () => g._m2TestUpdates.restyle++);
        }""")
        cx, cy = plot["x"] + plot["width"] * .65, plot["y"] + plot["height"] * .5
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, -400)
        wait_range_change(initial, shrink=True)
        check_reference_edges()
        check_live_alignment()
        zoomed = ranges()
        page.locator("#M2-comparator").click()
        page.get_by_role("dialog").get_by_text("India · IND", exact=True).click()
        expect(page.locator("#M2-finding")).to_contain_text("India")
        assert ranges() == zoomed, "Selecting a comparison must preserve zoom"
        page.locator("#M2-comparator").click()
        page.get_by_role("dialog").get_by_text("Japan · JPN", exact=True).click()
        expect(page.locator("#M2-finding")).to_contain_text("Japan")
        page.locator("#nav-M4").click()
        expect(page.locator("#M4-panel")).to_be_visible()
        page.locator("#nav-M2").click()
        expect(page.locator("#M2-panel")).to_be_visible()
        page.wait_for_load_state("networkidle")
        assert ranges() == zoomed, "Navigation must preserve zoom"
        page.locator("#M2-graph").scroll_into_view_if_needed()
        assert page.locator("#M2-graph .js-plotly-plot").evaluate("e => e._context.scrollZoom")
        reset_view()
        # Exercise successive wheel events, checking the actual rendered line
        # between events rather than only after a final settled view.
        wheel_restyles = page.locator("#M2-graph .js-plotly-plot").evaluate("g => g._m2TestUpdates.restyle")
        plot = page.locator("#M2-graph .nsewdrag").bounding_box()
        page.mouse.move(plot["x"] + plot["width"] * .6, plot["y"] + plot["height"] * .5)
        for delta in [-180, -180, 180, 180]:
            before_wheel = ranges()
            page.mouse.wheel(0, delta)
            wait_range_change(before_wheel)
            check_live_alignment()
        assert page.locator("#M2-graph .js-plotly-plot").evaluate("g => g._m2TestUpdates.restyle") == wheel_restyles
        reset_view()
        plot = page.locator("#M2-graph .nsewdrag").bounding_box()
        page.mouse.move(plot["x"] + plot["width"] * .3, plot["y"] + plot["height"] * .25)
        page.mouse.down()
        page.mouse.move(plot["x"] + plot["width"] * .8, plot["y"] + plot["height"] * .8, steps=12)
        page.mouse.up()
        wait_range_change(initial, shrink=True)
        boxed = ranges()
        page.locator('#M2-graph [data-title="Pan"]').click()
        page.mouse.move(plot["x"] + plot["width"] * .5, plot["y"] + plot["height"] * .5)
        page.mouse.down()
        before_drag = page.locator("#M2-graph .js-plotly-plot").evaluate("g => ({...g._m2TestUpdates})")
        for fraction in [.025, .05, .075, .1]:
            page.mouse.move(plot["x"] + plot["width"] * (.5 + fraction),
                            plot["y"] + plot["height"] * (.5 + fraction/2), steps=3)
            check_live_alignment()
        during_drag = page.locator("#M2-graph .js-plotly-plot").evaluate("g => ({...g._m2TestUpdates})")
        assert during_drag == before_drag, "Dragging should transform traces without extra replot/restyle"
        page.mouse.up()
        wait_range_change(boxed)
        check_reference_edges()
        panned = ranges()
        assert abs((panned['x'][1]-panned['x'][0]) - (boxed['x'][1]-boxed['x'][0])) < 1e-6
        reset_view()
        page.locator('#M2-graph [data-title="Zoom"]').click()
        assert page.locator("#M2-match-status").inner_text() == status
        checks.append("Wheel zoom, box zoom, pan and reset; comparison/navigation preserve zoom; matching remains unchanged")
        check_reference_edges()
        checks.append("All three ratio lines reach viewport edges with correct ratios after zoom, pan and reset")
        checks.append("Rendered lines align within 1px during mouse-down pan and successive wheel zoom; no extra redraws during dragging or endpoint restyles during ordinary zoom")

        # Force a distant view to exercise endpoint extension, not just the
        # initial spare coverage. Reset must still return to country extents.
        page.locator("#M2-graph .js-plotly-plot").evaluate("g => Plotly.relayout(g, {'xaxis.range': [30,34], 'yaxis.range': [29,33], 'xaxis.autorange': false, 'yaxis.autorange': false})")
        check_reference_edges()
        check_live_alignment()
        reset_view()
        check_reference_edges()
        checks.append("Distant viewport extends native reference endpoints; reset ignores extended endpoints")

        page.locator("#M2-mode").get_by_text("Similar exports", exact=True).click()
        expect(page.locator("#M2-finding")).to_contain_text("USA")
        expect(page.locator("#M2-comparator")).to_contain_text("USA")
        expect(page.locator("#M2-relative")).to_contain_text("USA compared with Germany")
        page.wait_for_function("""() => {
            const g = document.querySelector('#M2-relative-graph .js-plotly-plot');
            return g.data[0].x[0] > 600 && g._fullLayout.xaxis.range[1] > Math.max(...g.data[0].x);
        }""")
        page.locator("#M2-factor").get_by_text("1.5×", exact=True).click()
        expect(page.locator("#M2-match-status")).to_contain_text("1.5]")
        page.locator("#M2-mode").get_by_text("Similar GDP", exact=True).click()
        expect(page.locator("#M2-match-status")).to_contain_text("4 other economies")
        checks.append("Both matching dimensions and both threshold choices")

        # Click an actual SVG scatter point, not the callback endpoint.
        page.locator("#M2-factor").get_by_text("1.25×", exact=True).click()
        expect(page.locator("#M2-match-status")).to_contain_text("2 other economies")
        page.wait_for_load_state("networkidle")
        page.locator("#M2-graph").scroll_into_view_if_needed()
        page.wait_for_function("Array.from(document.querySelectorAll('#M2-graph .point')).some(e => e.__data__?.data?.[0] === 'IND')")
        point = page.locator("#M2-graph .point").all()
        for element in point:
            if element.evaluate("e => e.__data__?.data?.[0]") == "IND":
                element.click(force=True)
                break
        expect(page.locator("#M2-finding")).to_contain_text("India")
        expect(page.locator("#M2-relative")).to_contain_text("India compared with Germany")
        checks.append("Actual India scatter point click updates comparison")

        page.locator("#M2-factor").get_by_text("1.5×", exact=True).click()
        expect(page.locator("#M2-match-status")).to_contain_text("4 other economies")
        page.locator("#M2-year").click()
        page.get_by_role("dialog").get_by_text("2010", exact=True).click()
        expect(page.locator("#M2-scope")).to_contain_text("2010")
        expect(page.locator("#M2-finding")).to_contain_text("2010")
        assert "India" not in page.locator("#M2-comparator").inner_text()
        checks.append("Year change clears an ineligible comparison and stale point selection")

        page.locator("#M2-year").click()
        page.get_by_role("dialog").get_by_text("2023", exact=True).click()
        page.locator("#M2-factor").get_by_text("1.25×", exact=True).click()
        page.locator("#M2-anchor").get_by_text("United States", exact=True).click()
        expect(page.locator("#M2-match-status")).to_contain_text("No matching economy")
        expect(page.locator("#M2-finding")).to_contain_text("No two-country finding")
        expect(page.locator("#M2-relative-graph")).to_have_count(0)
        page.screenshot(path=str(screenshots / "M2_no_match.png"), full_page=True)
        checks.append("No-match state without automatic widening or stale cards")

        assert page.locator('#M2-anchor input[type="radio"]').count() == 6
        assert page.locator('[id^="M2-case-"]').count() == 0
        for code, name in [("CHN", "China"), ("MEX", "Mexico"), ("NLD", "Netherlands"), ("ITA", "Italy"), ("DEU", "Germany")]:
            page.locator("#M2-anchor").get_by_text(name, exact=True).click()
            expect(page.locator(f'#M2-anchor input[value="{code}"]')).to_be_checked()
            expect(page.locator("#M2-cards")).to_contain_text(code)
        expect(page.locator("#M2-finding")).to_contain_text("Japan")
        checks.append("Single six-country anchor selector with selected state; global comparison candidates")
        page.locator("#nav-M4").click()
        expect(page.locator("#M4-panel")).to_be_visible()
        page.locator("#nav-M2").click()
        expect(page.locator("#M2-finding")).to_contain_text("Japan")
        checks.append("Navigation away and back preserves M2 state")

        page.get_by_text("All matches, data coverage and sources", exact=True).click()
        expect(page.locator("#M2-table")).to_contain_text("India")
        with page.expect_download() as event:
            page.locator("#M2-export").click()
        download = event.value
        destination = ROOT / "docs/M2_export_sample.csv"
        download.save_as(destination)
        data = pd.read_csv(destination)
        assert set(data[data.is_match].country) == {"JPN", "IND"}
        assert data[data.is_comparator].country.tolist() == ["JPN"]
        jp = data[data.is_comparator].iloc[0]
        assert abs(jp.gdp_anchor_100 - 100 * 4212944.753 / 4456081.017) < 1e-8
        assert abs(jp.export_gdp_gap_pp + 16.5673056073) < 1e-7
        checks.append("Downloaded CSV agrees with visible matches and selected comparison")
        checks.append("Relative GDP/export bars, percentage-point gap and CSV agree; >100 values remain visible; empty comparisons clear the chart")

        page.get_by_text("All matches, data coverage and sources", exact=True).click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#M2-graph").scroll_into_view_if_needed()
        page.wait_for_function("document.querySelector('#M2-graph .js-plotly-plot')._fullLayout.width < 450")
        page.wait_for_function("""() => {
            const graph = document.querySelector('#M2-graph');
            const plot = graph.querySelector('.svg-container');
            return graph.getBoundingClientRect().height >= 510 &&
                plot.getBoundingClientRect().bottom <= graph.closest('.card').getBoundingClientRect().bottom;
        }""")
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        page.wait_for_function("document.querySelector('#M2-relative-graph .js-plotly-plot')._fullLayout.width < 450")
        page.screenshot(path=str(screenshots / "M2_mobile.png"), full_page=True)
        checks.append("390px viewport without horizontal page overflow or graph/card overlap; mobile screenshot")
        assert not errors, errors
        browser.close()
    report = {"checks_passed": checks, "browser_errors": errors}
    (ROOT / "docs/M2_browser_checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
