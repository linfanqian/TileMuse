"""Map -> violations. Gameplay rules only; spec schema validation lives in spec.py."""

from collections.abc import Callable

from app.models import GameMap, Violation
from app.spec import MapSpec

Rule = Callable[[GameMap, MapSpec], list[Violation]]

# Add a rule here, a template for each code it emits in explainer.TEMPLATES,
# and a passing-map and violating-map test.
RULES: list[Rule] = []


def validate(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    return [v for rule in RULES for v in rule(game_map, spec)]
