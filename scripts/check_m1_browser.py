"""Browser acceptance checks; run app.py first (default port 8050)."""

import argparse
import json
import os
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8050")
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
        page.locator("#nav-M1").click()

        def choose(control, option):
            page.locator(f"#M1-{control}").click()
            page.get_by_role("dialog").get_by_text(option, exact=True).click()

        def expect_match_count(count):
            page.wait_for_function("""count => {
                const graph = document.querySelector('#M1-graph .js-plotly-plot');
                return graph?.data
                    ?.filter(trace => ['Matches', 'Comparison'].includes(trace.name))
                    .reduce((n, trace) => n + trace.customdata.length, 0) === count;
            }""", arg=count)

        expect(page.locator("#M1-anchor")).to_contain_text("United States (USA)")
        expect(page.locator("#M1-comparator")).to_contain_text("Germany")
        expect(page.locator("#M1-question")).to_have_text("Similar exports. Similar GDP?")
        expect(page.locator("#M1-finding")).to_contain_text("6.14 times")
        expect_match_count(1)
        checks.append("US/Germany default, export match and GDP comparison")
        choose("anchor", "Germany (DEU)")
        page.locator("#M1-mode").get_by_text("Similar GDP", exact=True).click()
        expect(page.locator("#M1-question")).to_have_text("Similar GDP. Similar exports?")
        expect(page.locator("#M1-finding")).to_contain_text("Japan")

        scope = page.locator("#M1-scope")
        finding = page.locator("#M1-finding")
        expect(scope).to_contain_text("24 economies shown")
        expect(page.locator("#M1-match-status")).to_have_count(0)
        expect_match_count(2)
        expect(page.locator("#M1-cards")).to_contain_text("35.27%")
        expect(page.locator("#M1-cards")).to_contain_text("18.70%")
        expect(page.locator("#M1-relative")).to_contain_text("5.5% lower")
        expect(page.locator("#M1-relative")).to_contain_text("49.9% lower")
        expect(page.locator("#M1-relative p.m1-note")).to_have_text("Germany = 100")
        expect(page.locator("#M1-relative")).not_to_contain_text("percentage points lower")
        page.wait_for_function("document.querySelector('#M1-relative-graph .js-plotly-plot')?._fullLayout")
        def check_reference_edges():
            page.wait_for_function("""() => {
                const g = document.querySelector('#M1-graph .js-plotly-plot');
                const x = g._fullLayout.xaxis.range, y = g._fullLayout.yaxis.range;
                const traces = g.data.filter(t => t.meta?.m1_ratio);
                if (traces.length !== 3) return false;
                return traces.every(t => {
                    const offset = Math.log10(t.meta.m1_ratio);
                    const lo = Math.max(x[0], y[0]-offset), hi = Math.min(x[1], y[1]-offset);
                    if (hi < lo) return true;
                    return Math.log10(t.x[0]) <= lo && Math.log10(t.x[1]) >= hi &&
                        t.x.every((v,i) => Math.abs(Math.log10(t.y[i]/v)-offset) < 1e-7);
                });
            }""")
        check_reference_edges()
        page.screenshot(path=str(screenshots / "M1_desktop.png"), full_page=True)
        checks.append("Alternate Germany/Japan cards, finding and desktop screenshot")
        expect(page.locator("#M1-customize")).to_have_count(0)
        dropdowns = [page.locator(f"#M1-{control}") for control in ("year", "anchor", "factor")]
        for dropdown in dropdowns:
            expect(dropdown).to_be_visible()
        boxes = [dropdown.bounding_box() for dropdown in dropdowns]
        assert [round(box["height"]) for box in boxes] == [36, 36, 36]
        assert len({round(box["y"]) for box in boxes}) == 1
        mode = page.locator("#M1-mode").bounding_box()
        assert abs(mode["y"] + mode["height"] - boxes[0]["y"] - boxes[0]["height"]) < 4
        expect(page.locator("#M1-data-details")).not_to_have_attribute("open", "")
        expect(page.locator("#M1-relative-graph")).to_be_visible()
        expect(page.locator("#M1-relative + #M1-amounts")).to_be_visible()
        expect(page.locator("#M1-cards")).to_be_visible()
        expect(page.locator("#M1-takeaway")).to_have_count(0)
        expect(page.locator("#M1-anchor")).to_contain_text("Germany (DEU)")
        expect(page.locator("#nav-M4")).to_be_visible()
        checks.append("Three aligned dropdowns, Match by below, exact values visible under the bars, and data details collapsed")


        def ranges():
            return page.locator("#M1-graph .js-plotly-plot").evaluate(
                "e => ({x: [...e._fullLayout.xaxis.range], y: [...e._fullLayout.yaxis.range]})")

        def check_live_alignment():
            # Check rendered SVG coordinates while the mouse is still down,
            # including the transform Plotly applies before a final replot.
            page.wait_for_function("""() => {
                const g = document.querySelector('#M1-graph .js-plotly-plot');
                const rect = g.querySelector('.nsewdrag').getBoundingClientRect();
                const xr = g._fullLayout.xaxis.range, yr = g._fullLayout.yaxis.range;
                const traces = [...g.querySelectorAll('.scatterlayer .trace')];
                return g.data.slice(0,3).every((t,i) => {
                    const path = traces[i].querySelector('.js-line');
                    if (!path) return false;
                    const offset = Math.log10(t.meta.m1_ratio);
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

        def wait_range_change(before, completed, shrink=False):
            page.wait_for_function("""({before, completed, shrink}) => {
                const g = document.querySelector('#M1-graph .js-plotly-plot');
                if (g.completedGestures <= completed) return false;
                const x = g._fullLayout.xaxis.range;
                return shrink ? x[1]-x[0] < (before.x[1]-before.x[0]) * .98
                    : Math.abs(x[0]-before.x[0]) > .001;
            }""", arg={"before": before, "completed": completed, "shrink": shrink})

        page.locator("#M1-graph").scroll_into_view_if_needed()
        graph = page.locator("#M1-graph .js-plotly-plot")
        expect(page.locator("#M1-graph .modebar-btn")).to_have_count(0)
        assert graph.evaluate("g => g._fullLayout.dragmode === 'pan' && g._context.scrollZoom && g._context.doubleClick === 'reset'")
        # The axis can change before Plotly commits the wheel or drag gesture.
        graph.evaluate("""g => {
            g.completedGestures = 0;
            g.on('plotly_relayout', event => {
                if (Object.keys(event).some(key => key.startsWith('xaxis.range'))) {
                    g.completedGestures += 1;
                }
            });
        }""")
        initial = ranges()
        initial_finding = finding.inner_text()
        plot = page.locator("#M1-graph .nsewdrag").bounding_box()
        page.mouse.move(plot["x"] + plot["width"]*.5, plot["y"] + plot["height"]*.5)
        completed = graph.evaluate("g => g.completedGestures")
        page.mouse.wheel(0, -400)
        wait_range_change(initial, completed, shrink=True)
        zoomed = ranges()
        page.locator("#M1-graph").scroll_into_view_if_needed()
        plot = page.locator("#M1-graph .nsewdrag").bounding_box()
        page.mouse.move(plot["x"] + plot["width"]*.5, plot["y"] + plot["height"]*.5)
        completed = graph.evaluate("g => g.completedGestures")
        page.mouse.down()
        for fraction in [.025, .05, .075, .1]:
            page.mouse.move(plot["x"] + plot["width"]*(.5+fraction), plot["y"] + plot["height"]*(.5+fraction/2), steps=3)
            check_live_alignment()
        page.mouse.up()
        wait_range_change(zoomed, completed)
        panned = ranges()
        for axis in ['x', 'y']:
            assert abs((panned[axis][1]-panned[axis][0]) - (zoomed[axis][1]-zoomed[axis][0])) < 1e-6
        check_reference_edges()
        page.locator("#M1-comparator").click()
        page.get_by_role("dialog").get_by_text("India · IND", exact=True).click()
        expect(page.locator("#M1-finding")).to_contain_text("India")
        assert ranges() == panned, (ranges(), panned)
        page.locator("#M1-comparator").click()
        page.get_by_role("dialog").get_by_text("Japan · JPN", exact=True).click()
        expect(page.locator("#M1-finding")).to_contain_text("Japan")
        page.locator("#nav-M4").click()
        expect(page.locator("#M4-panel")).to_be_visible()
        page.locator("#nav-M1").click()
        expect(page.locator("#M1-panel")).to_be_visible()
        expect(finding).to_have_text(initial_finding)
        assert ranges() == panned, (ranges(), panned)
        page.locator("#M1-graph").scroll_into_view_if_needed()
        plot = page.locator("#M1-graph .nsewdrag").bounding_box()
        page.mouse.dblclick(plot["x"] + plot["width"]*.5, plot["y"] + plot["height"]*.5)
        page.wait_for_function("""initial => {
            const g = document.querySelector('#M1-graph .js-plotly-plot');
            return ['x','y'].every(a => g._fullLayout[a+'axis'].range.every((v,i) => Math.abs(v-initial[a][i]) < 1e-6));
        }""", arg=initial)
        checks.append("Toolbar hidden; drag pans, wheel zooms and double-click restores the initial view")
        checks.append("Comparison and navigation preserve panned view; reference lines align during dragging and reach viewport edges")
        graph.evaluate("g => Plotly.relayout(g, {'xaxis.range': [30,34], 'yaxis.range': [29,33], 'xaxis.autorange': false, 'yaxis.autorange': false})")
        check_reference_edges()
        check_live_alignment()
        checks.append("Distant viewport extends native reference endpoints")

        page.locator("#M1-mode").get_by_text("Similar exports", exact=True).click()
        expect(page.locator("#M1-finding")).to_contain_text("USA")
        expect(page.locator("#M1-comparator")).to_contain_text("USA")
        expect(page.locator("#M1-relative p.m1-note")).to_have_text("Germany = 100")
        def check_usa_label():
            page.wait_for_function("""() => {
                const graph = document.querySelector('#M1-graph');
                const plot = graph.querySelector('.nsewdrag').getBoundingClientRect();
                const label = [...graph.querySelectorAll('.textpoint text')]
                    .find(t => t.textContent === 'United States');
                if (!label) return false;
                const box = label.getBoundingClientRect();
                return box.width > 0 && box.left >= plot.left &&
                    box.right <= plot.right - 2 && box.top >= plot.top && box.bottom <= plot.bottom;
            }""")
        # This case puts the comparison at the largest GDP. Check actual SVG
        # text bounds: data-point visibility alone missed the clipped label.
        check_usa_label()
        for width in [1280, 1440]:
            page.set_viewport_size({"width": width, "height": 1100})
            page.wait_for_load_state("networkidle")
            page.wait_for_function("""() => {
                const graph = document.querySelector('#M1-graph');
                return Math.abs(graph.clientWidth - graph.querySelector('.js-plotly-plot')._fullLayout.width) < 2;
            }""")
            check_usa_label()
        check_usa_label()
        check_reference_edges()
        page.screenshot(path=str(screenshots / "M1_similar_exports.png"), full_page=True)
        checks.append("USA label stays inside the plot at 1440px and 1280px in Similar exports 1.25x after changing filters")
        page.wait_for_function("""() => {
            const g = document.querySelector('#M1-relative-graph .js-plotly-plot');
            return g.data[0].x[0] > 600 && g._fullLayout.xaxis.range[1] > Math.max(...g.data[0].x);
        }""")
        choose("factor", "1.5×")
        expect(page.locator("#M1-factor")).to_contain_text("1.5×")
        page.locator("#M1-mode").get_by_text("Similar GDP", exact=True).click()
        expect_match_count(4)
        checks.append("Both matching dimensions and both threshold choices")

        # Click an actual SVG scatter point, not the callback endpoint.
        choose("factor", "1.25×")
        expect_match_count(2)
        page.wait_for_load_state("networkidle")
        page.locator("#M1-graph").scroll_into_view_if_needed()
        page.wait_for_function("Array.from(document.querySelectorAll('#M1-graph .point')).some(e => e.__data__?.data?.[0] === 'IND')")
        point = page.locator("#M1-graph .point").all()
        for element in point:
            if element.evaluate("e => e.__data__?.data?.[0]") == "IND":
                element.click(force=True)
                break
        expect(page.locator("#M1-finding")).to_contain_text("India")
        expect(page.locator("#M1-relative p.m1-note")).to_have_text("Germany = 100")
        checks.append("Actual India scatter point click updates comparison")

        choose("factor", "1.5×")
        expect_match_count(4)
        page.locator("#M1-year").click()
        page.get_by_role("dialog").get_by_text("2010", exact=True).click()
        expect(page.locator("#M1-year")).to_contain_text("2010")
        expect(page.locator("#M1-finding")).to_contain_text("2010")
        assert "India" not in page.locator("#M1-comparator").inner_text()
        checks.append("Year change clears an ineligible comparison and stale point selection")

        page.locator("#M1-year").click()
        page.get_by_role("dialog").get_by_text("2023", exact=True).click()
        choose("factor", "1.25×")
        choose("anchor", "United States (USA)")
        expect(page.locator("#M1-comparator")).to_be_disabled()
        expect(scope).to_contain_text("24 economies shown")
        expect_match_count(0)
        expect(page.locator("#M1-finding")).to_contain_text("No two-country finding")
        expect(page.locator("#M1-relative-graph")).to_have_count(0)
        page.screenshot(path=str(screenshots / "M1_no_match.png"), full_page=True)
        checks.append("No-match state without automatic widening or stale cards")

        page.locator("#M1-anchor").click()
        expect(page.get_by_role("dialog").get_by_role("option")).to_have_count(6)
        page.keyboard.press("Escape")
        assert page.locator('[id^="M1-case-"]').count() == 0
        for code, name in [("CHN", "China"), ("MEX", "Mexico"), ("NLD", "Netherlands"), ("ITA", "Italy"), ("DEU", "Germany")]:
            choose("anchor", f"{name} ({code})")
            expect(page.locator("#M1-anchor")).to_contain_text(f"{name} ({code})")
            expect(page.locator("#M1-cards")).to_contain_text(code)
        expect(page.locator("#M1-finding")).to_contain_text("Japan")
        checks.append("Single six-country anchor selector with selected state; global comparison candidates")
        page.locator("#nav-M4").click()
        expect(page.locator("#M4-panel")).to_be_visible()
        page.locator("#nav-M1").click()
        expect(page.locator("#M1-finding")).to_contain_text("Japan")
        checks.append("Navigation away and back preserves M1 state")

        page.locator("#M1-data-details > summary").click()
        expect(page.locator("#M1-table")).to_contain_text("India")
        with page.expect_download() as event:
            page.locator("#M1-export").click()
        download = event.value
        destination = ROOT / "docs/M1_export_sample.csv"
        download.save_as(destination)
        data = pd.read_csv(destination)
        assert set(data[data.is_match].country) == {"JPN", "IND"}
        assert data[data.is_comparator].country.tolist() == ["JPN"]
        jp = data[data.is_comparator].iloc[0]
        assert abs(jp.gdp_anchor_100 - 100 * 4212944.753 / 4456081.017) < 1e-8
        assert abs(jp.export_gdp_gap_pp + 16.5673056073) < 1e-7
        checks.append("Downloaded CSV agrees with visible matches and selected comparison")
        checks.append("Relative GDP/export bars agree with CSV indices; CSV retains the percentage-point gap")

        page.locator("#M1-data-details > summary").click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("#M1-graph").scroll_into_view_if_needed()
        page.wait_for_function("document.querySelector('#M1-graph .js-plotly-plot')._fullLayout.width < 450")
        page.wait_for_function("""() => {
            const graph = document.querySelector('#M1-graph');
            const plot = graph.querySelector('.svg-container');
            return graph.getBoundingClientRect().height >= 510 &&
                plot.getBoundingClientRect().bottom <= graph.closest('.card').getBoundingClientRect().bottom;
        }""")
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        page.wait_for_function("document.querySelector('#M1-relative-graph .js-plotly-plot')._fullLayout.width < 450")
        page.screenshot(path=str(screenshots / "M1_mobile.png"), full_page=True)
        checks.append("390px viewport without horizontal page overflow or graph/card overlap; mobile screenshot")

        page.set_viewport_size({"width": 1440, "height": 1100})
        choose("comparator", "India · IND")
        expect(finding).to_contain_text("India")
        page.locator("#nav-M0").click()
        expect(page.locator("#M0-panel").get_by_text("Focus economy", exact=True)).to_have_count(0)
        page.locator("#nav-M1").click()
        expect(page.locator("#M1-year")).to_be_visible()
        for module in ("M1", "M2", "M3"):
            expect(page.locator(f"#{module}-handoff")).to_have_count(0)
            expect(page.locator(f"#{module}-handoff-undo")).to_have_count(0)
        page.locator("#nav-M2").click()
        expect(page.locator("#M2-stats")).not_to_contain_text("have no distance record")
        expect(page.locator("#M2-stats")).not_to_contain_text("Top partner:")
        page.locator("#nav-M1").click()
        expect(page.locator("#M1-year")).to_contain_text("2023")
        expect(finding).to_contain_text("Germany")
        expect(finding).to_contain_text("India")
        expect(page.locator("#M1-anchor")).to_contain_text("Germany (DEU)")
        expect(page.locator("#M1-comparator")).to_contain_text("India")
        checks.append("M1–M3 have independent controls and navigation preserves the Economy comparison")
        assert not errors, errors
        browser.close()
    report = {"checks_passed": checks, "browser_errors": errors}
    (ROOT / "docs/M1_browser_checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
