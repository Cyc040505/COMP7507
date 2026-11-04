# M5 Implementation Plan

Goal: complete proposal-aligned annual recovery and structural change analysis in the existing Dash app.
Architecture: pure validated annual calculations in src/analytics/time_change.py; provenance-aware compact inputs; isolated M5 controls and callbacks; Plotly aligned views.
Tech Stack: Python, pandas, pyarrow, Plotly Dash. Spec: M5_实施方案.md.

## Constraints and review focus
No synthetic evidence; missing years remain missing; all-product denominators are fixed; unknown regions retain an explicit coverage field; no changes to M1/M4 formulas or shell state ownership; nominal USD and descriptive event comparison only. Review: partial coverage, baseline missing/zero, event/window validity, recovery then relapse, module switching and empty selections.

## Tasks
- [x] 1. Data: download pinned same-version bilateral HS2 and country dimensions, validate against existing full annual product and country tables; build small regional year×exporter×HS2 table and provenance manifest. Fail closed on mismatch.
- [x] 2. Analytics: tests first for build_timeline and summarize_recovery; implement complete-year grids, fixed denominators, coverage and conditional recovery status; run tests.
- [x] 3. UI: tests first for callback payload, figures and downloads; replace M5 placeholder, add scoped CSS, local presets, explicit context import, aligned graphs and dynamic findings. Run entire suite.
- [x] 4. Verification: actual desktop/narrow browser, preset/product/empty/baseline/click/download flows; audit source hashes; independent whole-branch review; fix substantive issues; document examples and launch instructions.

Execution: inline in an isolated clone on feat/m5-time-change, using test-first implementation. No remote push/merge. Ledger: M5_work_log.md.
