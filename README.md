# Global Trade Over Three Decades (1995–2024)

Interactive visual-analytics application for **COMP7507 Visualization & Visual Analytics, Group 7**.

Data sources: CEPII **BACI** (bilateral goods trade) / **CHELEM** (macroeconomic indicators) /
**GeoDist** (geographic distances).
Stack: Plotly Dash single-page app + DuckDB offline pre-aggregation. One app, six analysis
modules (M0–M5) reached from a shared top navigation; each module owns its own controls.

> Status: **M0–M5 integrated for final review.** All six modules run on real data in a single
> `app.py`. See [final review & demo guide](docs/FINAL_REVIEW.md) for evidence, acceptance
> records and the 6-minute demo path.

## Quick start

```bash
# 1) Dependencies — one human-readable file, one lock file
pip install -r requirements.txt      # minimum versions
pip install -r requirements-lock.txt # exact pinned set (includes Playwright for browser checks)

# 2) Start from the project root
python app.py
# open http://127.0.0.1:8050, then pick a module from the top navigation
```

Every module is reached from **Overview (M0)** via the top nav — there is a single entry point.
The per-module launchers that existed during independent development have been removed in the
consolidation.

```bash
# Optional: run the test suite
python -m unittest discover -s tests
```

## Modules

One feature module per file under `src/modules/`, all registered in `src/modules/__init__.py`:

| Id   | Nav label          | Focus |
|------|--------------------|-------|
| M0   | Overview           | Global export growth, Top-10 world shares, six focal economies |
| M1   | Geography          | Distance–share scatter, directed map, partner ranking |
| M2   | Economy            | GDP vs. export scale, similar-income matching |
| M3   | Network & Partners | Bilateral flows, regions, partner matrix |
| M4   | Product Structure  | Composition & RCA heatmaps, linked product detail |
| M5   | Time Change        | Recovery index, product & regional-share change around events |

Each module reads the compact `data/processed/*.parquet` tables produced by the pipeline and
renders into its own cards. Modules never modify shared state — they own their own controls.

## Directory layout

```
app.py                       # single entry point: build the shell, register all callbacks
assets/
  styles.css                 # shared shell styles (blue/white design)
  m1.css … m5.css, m2.js    # per-module local styles / client-side scripts
  world_*.json               # offline GeoJSON basemap for the maps
src/
  config.py                  # paths, year range, DATA_READY flag
  ids.py                     # id-namespacing helper mid(MODULE_ID, name)
  theme.py                   # colours / Plotly template / placeholder
  components.py              # reusable building blocks: card / KPI / field / verify panel
  module_base.py             # shared helpers: guard_active / describe_filters
  layout.py                  # app shell: header + top nav + right view area, global stores
  data_loader.py             # data access layer: real parquet only (lru_cache)
  analytics/                 # pure calculation functions per module (geography, economy, …)
  modules/                   # one file per module + registry
scripts/                     # offline build & source-audit (run manually, see below)
tests/                       # unittest suite (calculation, data integrity, HTTP callbacks)
data/                        # reference files + processed analysis tables (shipped)
```

## Module development conventions

Every `src/modules/<mod>.py` exposes the same contract:

| Name | Description |
|---|---|
| `MODULE_ID` | Unique id, also the component-id prefix (**do not change after release**), e.g. `"M1"` |
| `NAV_LABEL` | Text shown in the top navigation, e.g. `"M1  Geography"` |
| `ORDER` | Navigation sort order (overview is 0) |
| `layout()` | Returns the module's right-column panel: its control bar + cards |
| `register_callbacks(app)` | Registers the module's callbacks via `@app.callback` |

**Adding a module** = create one new file + add one entry to the `MODULES` list in
`src/modules/__init__.py`. The shell never needs to know the module's internals.

### Module-local controls (the current model)

The shared global console was removed. The sidebar now carries navigation only; **each module
owns its controls** (year, country, product, indicator, …) through a module-prefixed store such
as `M4-filters`. Guided cases never change another module's state. The only cross-module
transfer is an **explicit, user-initiated** action (M5 → "use current M4 selection").

`dcc.Store(id="global-filters")` still exists in `src/layout.py` **only as a read-only
compatibility snapshot** for unfinished placeholder modules — implemented modules do not write it.

### Three hard rules

1. **id namespacing** — the shell reserves `global-*` / `nav-*`; each module exclusively owns
   `{MODULE_ID}-*`, always generated through `src.ids.mid(MODULE_ID, name)`. A global
   id-uniqueness assertion runs at startup.
2. **Modules never write global state** — the nav buttons are the *sole writer* of
   `active-module`; modules only **read** it (and their own filter store) via `Input`/`State`,
   which makes circular callbacks structurally impossible.
3. **Hidden modules do not recompute** — the first line of a module callback calls
   `module_base.guard_active(MODULE_ID, active_module)`. Switching to the module triggers one
   render; staying put is blocked by `PreventUpdate`.

## Data pipeline

The app only ever reads the compact analysis tables under `data/processed/*.parquet` (shipped
with the repo). The raw CEPII sources (~10 GB) and the full 23-million-row bilateral table are
**optional** — needed only for independent rebuild/audit, never for running or demoing the app.
Missing tables raise an explicit `FileNotFoundError`; there is no synthetic fallback in
production.

| Loader in `src/data_loader.py` | Table |
|---|---|
| `load_flow_year` | `flow_year.parquet` |
| `load_country_year` | `country_year.parquet` |
| `load_country_pair_year` | `country_pair_year.parquet` |
| `load_exporter_hs2_year` | `exporter_hs2_year.parquet` |
| `load_country_pair_hs2_year` | `country_pair_hs2_year.parquet` |
| `load_gdp_year` | `gdp_year.parquet` |
| `load_geodist` | `geodist.parquet` |
| `load_country_meta` | `country_meta.parquet` |

### Rebuild & audit scripts (manual)

All under `scripts/`, run from the project root. They aggregate raw sources into the compact
tables and independently re-verify the numbers that appear on the pages — they are **not**
invoked by the app.

```bash
# Full offline pre-aggregation (staging → all analysis tables)
python scripts/build_analytics.py            # build/refresh everything
python scripts/build_analytics.py --only gdp # materialise a single table
python scripts/build_analytics.py --force    # re-scan raw sources into staging

# Module-specific builders (regenerate one module's inputs + source manifest)
python scripts/build_m4_data.py
python scripts/build_m5_data.py

# Official bilateral & regional rebuild + audit (needs a raw-source directory)
python scripts/prepare_final_data.py --source-root /path/to/CEPII-data
python scripts/audit_final_examples.py  --source-root /path/to/CEPII-data
python scripts/verify_m2_sources.py     --source-root /path/to/CEPII-data
python scripts/verify_m4_sources.py     --source-root /path/to/CEPII-data
```

Raw-source paths default to `data/BACI`, `data/CHELEM`, `data/GEODIST` and can be overridden
via `COMP7507_BACI_DIR` / `COMP7507_CHELEM_DIR` / `COMP7507_GEODIST_DIR`. SHA256 of the shipped
inputs and per-year reconciliation counts are recorded in
`data/processed/m5_source_manifest.json`, `docs/M2_source_audit.json` and `docs/M4_source_audit.json`.

## Tests

```bash
python -m unittest discover -s tests
```

Covers calculation correctness, data integrity (zero/negative/missing handling), and live Dash
HTTP callbacks per module. The lock file includes Playwright for one-off browser checks; those
artifacts are recorded in `docs/*_browser_checks.json` / `docs/screenshots/` rather than being
re-shipped as scripts.

## References

- Final review & demo guide: [docs/FINAL_REVIEW.md](docs/FINAL_REVIEW.md)
- Data sources & layout: [docs/DATA.md](docs/DATA.md)
- Module handoffs: `docs/M*_README.md`, `docs/M*_validation.md`, `docs/M*_source_audit.json`
- Report page structure: `documents/COMP7507_报告_Group7.html`, section 4
- Proposal: `documents/proposal_Group7.pdf`
