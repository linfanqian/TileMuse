"""Violations -> human-readable explanations. One template per violation code."""

from typing import Any

from app.models import Explanation, Violation

# Violation code -> str.format template, filled from details plus code, x and y.
TEMPLATES: dict[str, str] = {
    "missing_object": "Not enough {kind}: the spec asks for {expected}, but the map has {found}.",
    "door_count": "The spec asks for {expected} doors, but the map has {found}.",
    "object_on_wall": "The {kind} at ({x}, {y}) is inside a wall.",
    "door_unreachable": "The door at ({x}, {y}) can't be reached.",
    "object_unreachable": "The {kind} at ({x}, {y}) can't be reached.",
    "max_density": "The map has too many objects ({objects}) for its max_density of {max}.",
    "min_distance": (
        "The {kind} at ({x}, {y}) is {distance} tiles from the {other} at "
        "({other_x}, {other_y}). They must be at least {tiles} apart."
    ),
}

# Codes without a template still get explained, never dropped.
FALLBACK_TEMPLATE = "Rule '{code}' was violated."


def _plain(value: Any) -> Any:
    """Text details are code names, like player_spawn. Show them as words: player spawn."""
    return value.replace("_", " ") if isinstance(value, str) else value


def explain(violations: list[Violation]) -> list[Explanation]:
    return [
        Explanation(
            code=v.code,
            text=TEMPLATES.get(v.code, FALLBACK_TEMPLATE).format(
                **{
                    **{key: _plain(value) for key, value in v.details.items()},
                    "code": v.code,
                    "x": v.x,
                    "y": v.y,
                }
            ),
        )
        for v in violations
    ]
