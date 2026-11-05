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
        def check_reference_edges():
            page.wait_for_function("""() => {
                const g = document.querySelector('#M2-graph .js-plotly-plot');
                const x = g._fullLayout.xaxis.range, y = g._fullLayout.yaxis.range;
                const shapes = g.layout.shapes.filter(s => (s.name || '').startsWith('m2-ratio-'));
                if (shapes.length !== 3) return false;
                return shapes.every(s => {
                    const offset = Math.log10(Number(s.name.slice('m2-ratio-'.length)));
                    const lo = Math.max(x[0], y[0]-offset), hi = Math.min(x[1], y[1]-offset);
                    if (hi < lo) return s.visible === false;
                    if (!s.visible) return false;
                    return [[s.x0,s.y0],[s.x1,s.y1]].every(([u,v]) => {
                        const onEdge = Math.min(Math.abs(u),Math.abs(u-1),Math.abs(v),Math.abs(v-1)) < 1e-7;
                        const actual = (y[0]+v*(y[1]-y[0])) - (x[0]+u*(x[1]-x[0]));
                        return onEdge && Math.abs(actual-offset) < 1e-7;
                    });
                });
            }""")
        check_reference_edges()
        page.screenshot(path=str(screenshots / "M2_desktop.png"), full_page=True)
        checks.append("Default Germany/Japan cards, finding and desktop screenshot")

        def ranges():
            return page.locator("#M2-graph .js-plotly-plot").evaluate(
                "e => ({x: [...e._fullLayout.xaxis.range], y: [...e._fullLayout.yaxis.range]})")

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
        cx, cy = plot["x"] + plot["width"] * .65, plot["y"] + plot["height"] * .5
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, -400)
        wait_range_change(initial, shrink=True)
        check_reference_edges()
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
        page.mouse.move(plot["x"] + plot["width"] * .6, plot["y"] + plot["height"] * .55, steps=12)
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

        page.locator("#M2-mode").get_by_text("Similar exports", exact=True).click()
        expect(page.locator("#M2-finding")).to_contain_text("USA")
        expect(page.locator("#M2-comparator")).to_contain_text("USA")
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

        page.get_by_text("Matching list, exclusions and source evidence", exact=True).click()
        expect(page.locator("#M2-table")).to_contain_text("India")
        with page.expect_download() as event:
            page.locator("#M2-export").click()
        download = event.value
        destination = ROOT / "docs/M2_export_sample.csv"
        download.save_as(destination)
        data = pd.read_csv(destination)
        assert set(data[data.is_match].country) == {"JPN", "IND"}
        assert data[data.is_comparator].country.tolist() == ["JPN"]
        checks.append("Downloaded CSV agrees with visible matches and selected comparison")

        page.get_by_text("Matching list, exclusions and source evidence", exact=True).click()
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
        page.screenshot(path=str(screenshots / "M2_mobile.png"), full_page=True)
        checks.append("390px viewport without horizontal page overflow or graph/card overlap; mobile screenshot")
        assert not errors, errors
        browser.close()
    report = {"checks_passed": checks, "browser_errors": errors}
    (ROOT / "docs/M2_browser_checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
