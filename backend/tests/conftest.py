from collections.abc import Callable
from typing import Any

import pytest

from app.spec import MapSpec


@pytest.fixture
def make_spec() -> Callable[..., MapSpec]:
    """Builds a valid spec; keyword arguments override its fields."""

    def make(**overrides: Any) -> MapSpec:
        return MapSpec(
            **{"theme": "dungeon", "mood": "quiet", "width": 16, "height": 12, **overrides}
        )

    return make
