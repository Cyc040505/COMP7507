# Global Trade Over Three Decades (1995–2024)

## M5 delivered locally (2026-11-04)

M5 now has reconciled real-data annual recovery and product/regional-share views,
explicit M4 context import, missingness-aware recovery status, and evidence CSVs.
Run `python launch_m5.py` (or `启动M5.bat`) to open directly on M5.
See [M5 usage, findings and provenance](docs/M5_README.md) and
[concise module plan for Feishu](docs/M5_Feishu_notes.md).
The M1/M2/M3 modules remain at their upstream state. The older status below predates M5.

Interactive visual-analytics application for **COMP7507 Visualization & Visual Analytics, Group 7**.

Data sources: CEPII **BACI** (bilateral goods trade) / **CHELEM** (macroeconomic indicators) /
**GeoDist** (geographic distances).
Stack: Plotly Dash single-page app + dash-cytoscape (M3 force-directed network) + DuckDB offline
pre-aggregation.

> Status: **partially implemented**. Overview (M0), Product Structure (M4), and Time Change (M5) have data-backed views; M1, M2 and M3 retain their framework placeholders. M4 includes its required compact inputs and a separate validation record.

## Quick start

```bash
# 1) Dependencies (use the course conda env `vis_env` if it already has them)
pip install -r requirements.txt

# 2) Start (from the project root)
python app.py
# open http://127.0.0.1:8050
```

## Directory layout

```
app.py                 # entry point: create Dash app, assemble the shell, register all callbacks
assets/styles.css      # styles auto-served by Dash (blue/white design from the report, section 4)
src/
  config.py            # path constants, year range, DATA_READY flag
  ids.py               # id-namespacing helper mid(MODULE_ID, name)
  theme.py             # colours / Plotly template / empty_figure placeholder
  components.py        # reusable building blocks: card / KPI / module control bar / verification panel
  module_base.py       # shared module helpers: guard_active / describe_filters
  layout.py            # app shell: header + left column (nav + global console) + right view area
  data_loader.py       # data access layer: parquet first, demo fallback (lru_cache)
  modules/             # one file per module + registry
scripts/build_analytics.py   # DuckDB offline pre-aggregation (run manually)
data/                  # raw sources (already present)
data/processed/        # analysis tables produced by the pipeline (created after a run)
```

## Data pipeline

Offline, the ~10 GB of raw data is aggregated into compact analysis tables under
`data/processed/*.parquet`:

```bash
python scripts/build_analytics.py            # build everything
python scripts/build_analytics.py --only gdp # build a single dataset
```

Each output maps to a loader in `src/data_loader.py`: `flow_year`, `country_year`,
`country_pair_year`, `exporter_hs2_year`, `country_pair_hs2_year`, `gdp_year`, `geodist`,
`country_meta`.

When a table is missing, `data_loader` returns a deterministic demo frame with the **same column
schema**, so the skeleton always runs. After building the tables, set `DATA_READY = True` in
`src/config.py`.

## Module development conventions

Every `src/modules/<mod>.py` exposes the same contract:

| Name | Description |
|---|---|
| `MODULE_ID` | Unique id, also the component-id prefix (**do not change after release**), e.g. `"M1"` |
| `NAV_LABEL` | Text shown in the left navigation, e.g. `"M1  Geography"` |
| `ORDER` | Navigation sort order (overview is 0) |
| `layout()` | Returns the module's right-column panel: its control bar + three cards (main view / statistics / verification panel) |
| `register_callbacks(app)` | Registers the module's callbacks via `@app.callback` |

**Adding a module** = create one new file + add one entry to the `MODULES` list in
`src/modules/__init__.py`. The shell never needs to know the module's internals.

### Three hard rules

1. **id namespacing** — the shell reserves `global-*` / `nav-*`; each module exclusively owns
   `{MODULE_ID}-*`, always generated through `src.ids.mid(MODULE_ID, name)`. A global
   id-uniqueness assertion runs at startup.
2. **Single writer** — the global console widgets are the *sole* writer of `global-filters`; the
   nav buttons are the *sole* writer of `active-module`. Modules only **read** these two stores
   (`Input`/`State`) and never write them, which makes circular callbacks structurally impossible.
3. **Hidden modules do not recompute** — the first line of a module callback calls
   `module_base.guard_active(MODULE_ID, active_module)`. Since `active-module` is also a callback
   `Input`, switching to the module triggers one render, while staying put is blocked by
   `PreventUpdate`.

### Global state

`dcc.Store(id="global-filters")` = `{year, country, product, indicator}` (mirrors the report's
section-4 console); `dcc.Store(id="active-module")` = the active module id. Both are written only
by the shell callbacks in `src/layout.py`.

> Escape hatch (in use for M4): modules must not write `global-filters` directly. They publish a
> small intent store (currently `M4-intent`); a shell callback in `src/layout.py` updates the
> global console widgets, and the existing console callback remains the sole writer of
> `global-filters`. Other modules can reuse the same pattern later without becoming writers.

## References

- Proposal: `documents/proposal_Group7.pdf`
- Report page structure: `documents/COMP7507_报告_Group7.html`, section 4
- Course example architecture: `Lab2/example_dashboard`

## M4 Product Structure

M4 now includes real-data composition/RCA heatmaps, linked product detail,
similar-income comparisons (CHELEM GDP-CAP), and evidence downloads. The two
required compact analysis inputs are included; large raw files are not required
to run the module. See [M4 usage and analysis](docs/M4_README.md),
[validation](docs/M4_validation.md), and [Feishu summary](docs/M4_Feishu_notes.md).

## Module-local controls (2026-11-02)

The team agreed to remove the global console. The sidebar now contains navigation only. Overview retains its own year slider; M4 owns its year, income anchor and other controls through M4-filters. Guided cases never change another module. GLOBAL_FILTERS remains only as a read-only compatibility snapshot for unfinished placeholder modules; new module implementations must own their controls. Explicit cross-module transfer can be added by a visible action when required; no automatic transfer is active. This supersedes the earlier global-console and M4-intent rules above.
