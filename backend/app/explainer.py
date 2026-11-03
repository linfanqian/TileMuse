"""Violations -> human-readable explanations. One template per violation code."""

from typing import Any

from app.models import Explanation, Violation

# Violation code -> str.format template, filled from details plus code, x and y.
TEMPLATES: dict[str, str] = {
    "missing_object": "Not enough {kind}: the spec asks for {expected}, but the map has {found}.",
    "door_count": "Wrong number of doors: the spec asks for {expected}, but the map has {found}.",
    "object_on_wall": "The {kind} at ({x}, {y}) is inside a wall.",
    "door_unreachable": "The door at ({x}, {y}) can't be reached.",
    "object_unreachable": "The {kind} at ({x}, {y}) can't be reached.",
    "max_density": (
        "Too many objects ({objects}): the spec allows at most {max} objects per tile inside "
        "the outer walls."
    ),
    "min_distance": (
        "The {kind} at ({x}, {y}) is too close to the {other} at ({other_x}, {other_y}): "
        "distance {distance}, but the spec asks for at least {tiles}."
    ),
}

# Codes without a template still get explained, never dropped.
FALLBACK_TEMPLATE = "Rule '{code}' was violated."


# Details that hold an object kind, like player_spawn. They are shown as words: player spawn.
KIND_DETAILS = {"kind", "other"}


def _plain(key: str, value: Any) -> Any:
    return value.replace("_", " ") if key in KIND_DETAILS and isinstance(value, str) else value


def explain(violations: list[Violation]) -> list[Explanation]:
    return [
        Explanation(
            code=v.code,
            text=TEMPLATES.get(v.code, FALLBACK_TEMPLATE).format(
                **{
                    **{key: _plain(key, value) for key, value in v.details.items()},
                    "code": v.code,
                    "x": v.x,
                    "y": v.y,
                }
            ),
        )
        for v in violations
    ]
