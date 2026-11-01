"""Recorded TMDB/OMDb responses (see scripts/catalog_spike.py record)."""

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
