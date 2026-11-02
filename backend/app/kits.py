"""Reads kits.yaml, the one list of kits. Imports nothing from app, so spec.py can use it.

The spec's allowed values and the LLM prompts come from this file, so a new kit needs no code
change. `tileset.py` checks the kits in full.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "tileset"


@lru_cache
def read_kits() -> dict[str, Any]:
    return yaml.safe_load((ASSETS / "kits.yaml").read_text(encoding="utf-8"))
