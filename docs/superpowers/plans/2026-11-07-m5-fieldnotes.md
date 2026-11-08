# M5 Fieldnotes Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement the approved design task-by-task.

**Goal:** Apply the approved country-card design to the live M5 module while preserving the existing project fonts, colors, analytics and controls.

**Architecture:** Keep M5's existing calculations and export rows. Add same-scale country portraits from those computed rows, and retain the combined index figure in a disclosure. Keep all six focal graph IDs mounted so a single year-selection callback can coordinate portraits, the original charts and an inspection slider without dynamic callback loops.

**Tech Stack:** Existing Python / Plotly Dash / pandas, scoped CSS; no new dependencies.

**Spec:** User approval in this conversation: use scheme 3 across M5, preserving the original project's fonts and colors. Figma reference: https://www.figma.com/design/0ll9s2DXyEUPMlCEVYPYD1?node-id=9-2908

## Global Constraints

- Preserve `theme.FONT`, CSS font inheritance, all existing theme colors and stable country colors.
- Scope layout changes to M5. Do not change M0–M4, global navigation, raw data or analytics formulas.
- Preserve all existing cases, module-local filters, explicit M4 import, source validation, missing values and CSV fields.
- Recovery summaries describe the entire visible window; inspected values describe the selected year.
- Keep 1–4 distinct focal economies, truthful empty states and regional lower–upper bounds.
- Local implementation and preview only; no GitHub or Feishu publication is requested in this turn.

## Review Focus

- Four countries must share a y-axis range and wrap into two columns, preserving input order.
- Missing values and no observed loss must not become zero values or invented recovery years.
- Redrawing portraits must not reset the inspected year or create a callback loop.
- Selecting a year from a card, structure plot, combined plot or slider must agree with exported rows.
- A case/window/import change must clear or clamp stale year selections correctly.

## Tasks

- [x] Confirm clean GitHub baseline `09eacd2`; 21 existing M5 tests pass.
- [x] Add meaningful failing tests for same-scale portraits, missing-data semantics and coordinated year selection.
- [x] Implement reusable portrait rendering and M5 layout, preserving the existing calculation/export contract.
- [x] Add scoped M5 styles using inherited fonts and existing CSS variables.
- [x] Pass targeted and full regression checks; inspect three cases, four-country customization, evidence disclosures and responsive M5 layout in the browser.
- [x] Open the finished local implementation and capture its actual appearance.

## Execution record · 2026-11-08

- Reused the existing isolated worktree; other pending work in COMP7507-review was preserved.
- Ruling: inherit the project's existing fonts rather than the serif display face in Figma, following the user's latest instruction.
- Seven new tests failed before implementation and passed after implementation. Existing M5 tests: 21; total M5: 28; complete regression suite: 116 passed.
- Ruling: Dash 4 returns an empty multi-output JSON response for all-no_update callbacks in this runtime. Assert no changed properties, accepting either HTTP 204 or an empty HTTP 200 response.
- Independent final review: no findings. New files pass Ruff; git diff has no whitespace errors. Pre-existing C408/TRY004 style warnings in the original module were not changed into unrelated behavioral edits.
- Browser: all three cases, card and structure clicks, year slider, four-country two-column layout, empty selection, expanded overlay/table/methods, CSV download, and explicit M4 import passed. Tested 1440/820/390 widths without whole-page horizontal overflow. Console errors: none.
- Preview runs at 8051 with M5 selected. Original 8050 process remains available for comparison. Screenshots are saved outside the repository in outputs/m5-live.
- No remote push, PR, merge or Feishu edit was requested for this implementation step.
