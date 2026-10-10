"""Violations -> human-readable explanations. One template per violation code."""

import logging

from app.models import Explanation, Violation

logger = logging.getLogger(__name__)

# Violation code -> str.format template filled from details plus x and y.
TEMPLATES: dict[str, str] = {}

# Used when a code has no template yet or its template can't be filled,
# so a violation is never dropped or crashes the request.
FALLBACK_TEMPLATE = "Rule '{code}' was violated."


def explain(violations: list[Violation]) -> list[Explanation]:
    return [Explanation(code=v.code, text=_render(v)) for v in violations]


def _render(v: Violation) -> str:
    template = TEMPLATES.get(v.code)
    if template is not None:
        try:
            return template.format(**{**v.details, "x": v.x, "y": v.y})
        except (KeyError, IndexError, AttributeError, ValueError, TypeError) as e:
            logger.warning("Template for %r could not be filled: %r", v.code, e)
    return FALLBACK_TEMPLATE.format(code=v.code)
