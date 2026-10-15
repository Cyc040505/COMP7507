"""Global configuration: filesystem paths, year bounds, and readiness flags.

This module is intentionally dependency-free so every other module can import it
without creating an import cycle (see README "Module development conventions").
"""

from __future__ import annotations

from pathlib import Path

# Project root = the directory that contains this ``src`` package.
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
ASSETS_DIR = BASE_DIR / "assets"

# Raw CEPII sources (already present under data/).
BACI_DIR = DATA_DIR / "BACI"
CHELEM_DIR = DATA_DIR / "CHELEM"
GEODIST_DIR = DATA_DIR / "GEODIST"

# Global year domain (column selector for wide CHELEM files, row filter for BACI).
YEAR_MIN = 1995
YEAR_MAX = 2024
DEFAULT_YEAR = YEAR_MAX

# Flip to True once ``scripts/build_analytics.py`` has produced
# ``data/processed/*.parquet``. While False the loaders fall back to deterministic
# demo data and the UI labels itself accordingly.
DATA_READY = False

DEMO_TAG = "Demo data"
ANALYTIC_TAG = "Analysis tables"


def processed_path(filename: str) -> Path:
    """Absolute path to an analysis table under ``data/processed/``."""
    return PROCESSED_DIR / filename
