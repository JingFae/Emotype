"""Central paths and environment-backed application settings.

Keep path calculation here so moving implementation modules does not move the
database, static assets, shared lexicon, or local model by accident.
"""

from __future__ import annotations

import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parent
STATIC_DIR = PACKAGE_DIR / "static"
SHARED_DIR = PACKAGE_DIR / "shared"
MODELS_DIR = PACKAGE_DIR / "models"
DEFAULT_DATABASE_PATH = PACKAGE_DIR / "emomirror_data.sqlite3"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "Wav2vec-2.0"


def env_float(name: str, default: float) -> float:
    """Read a float setting while preserving a safe default on bad input."""
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def env_int(name: str, default: int) -> int:
    """Read an integer setting while preserving a safe default on bad input."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool = False) -> bool:
    """Read a conventional truthy/falsey environment setting."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}

