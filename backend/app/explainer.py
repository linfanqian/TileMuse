"""Violations -> human-readable explanations. One template per violation code."""

from app.models import Explanation, Violation

# Violation code -> str.format template filled from x, y and details.
TEMPLATES: dict[str, str] = {}


def explain(violations: list[Violation]) -> list[Explanation]:
    return [
        Explanation(code=v.code, text=TEMPLATES[v.code].format(x=v.x, y=v.y, **v.details))
        for v in violations
    ]
