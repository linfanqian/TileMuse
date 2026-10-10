"""Violations -> human-readable explanations. One template per violation code."""

from app.models import Explanation, Violation

# Violation code -> str.format template, filled from details plus code, x and y.
TEMPLATES: dict[str, str] = {}

# Codes without a template still get explained, never dropped.
FALLBACK_TEMPLATE = "Rule '{code}' was violated."


def explain(violations: list[Violation]) -> list[Explanation]:
    return [
        Explanation(
            code=v.code,
            text=TEMPLATES.get(v.code, FALLBACK_TEMPLATE).format(
                **{**v.details, "code": v.code, "x": v.x, "y": v.y}
            ),
        )
        for v in violations
    ]
