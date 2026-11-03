"""Map -> violations. Gameplay rules only; spec schema validation lives in spec.py."""

from collections import Counter
from collections.abc import Callable

from app.models import GameMap, MapObject, Tile, Violation
from app.spec import MapSpec, MaxDensityRule, MinDistanceRule, ObjectKind, density
from app.walkable import BLOCKING_KINDS, reachable

Rule = Callable[[GameMap, MapSpec], list[Violation]]


def _spawns(game_map: GameMap) -> list[MapObject]:
    return [o for o in game_map.objects if o.kind == ObjectKind.PLAYER_SPAWN]


def no_spawn(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    return [] if _spawns(game_map) else [Violation(code="no_spawn")]


def missing_objects(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    found = Counter(o.kind for o in game_map.objects)
    return [
        Violation(
            code="missing_object",
            details={"kind": req.kind.value, "expected": req.count, "found": found[req.kind]},
        )
        for req in spec.objects
        if found[req.kind] < req.count
    ]


def unreachable(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    """Doors and objects the player can't walk to from the first spawn. A chest blocks movement,
    so it counts as reachable when the player can stand next to it."""
    spawns = _spawns(game_map)
    if not spawns:
        return []  # no_spawn reports it.
    blocked = {(o.x, o.y) for o in game_map.objects if o.kind in BLOCKING_KINDS}
    walkable = reachable(game_map.tiles, blocked, (spawns[0].x, spawns[0].y))
    violations = [
        Violation(code="door_unreachable", x=x, y=y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile == Tile.DOOR and (x, y) not in walkable
    ]
    for obj in game_map.objects:
        x, y = obj.x, obj.y
        if obj.kind == ObjectKind.CHEST:
            cut_off = walkable.isdisjoint({(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)})
        else:
            cut_off = obj.kind not in BLOCKING_KINDS and (x, y) not in walkable
        if cut_off:
            violations.append(
                Violation(code="object_unreachable", x=x, y=y, details={"kind": obj.kind})
            )
    return violations


def max_density(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    objects = len(game_map.objects)
    # The density itself stays out of details: it is infinite for a map with no interior, and
    # JSON has no infinity.
    filled = density(objects, game_map.width, game_map.height)
    return [
        Violation(code="max_density", details={"objects": objects, "max": rule.max})
        for rule in spec.rules
        if isinstance(rule, MaxDensityRule) and filled > rule.max
    ]


def min_distance(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    """One violation for each pair of objects that is too close."""
    violations = []
    objects = game_map.objects
    for rule in spec.rules:
        if not isinstance(rule, MinDistanceRule):
            continue
        for i, one in enumerate(objects):
            for other in objects[i + 1 :]:
                if {one.kind, other.kind} != {rule.a, rule.b}:
                    continue
                distance = abs(one.x - other.x) + abs(one.y - other.y)
                if distance < rule.tiles:
                    violations.append(
                        Violation(
                            code="min_distance",
                            x=one.x,
                            y=one.y,
                            details={
                                "kind": one.kind,
                                "other": other.kind,
                                "other_x": other.x,
                                "other_y": other.y,
                                "distance": distance,
                                "tiles": rule.tiles,
                            },
                        )
                    )
    return violations


# Add a rule here, a template for each code it emits in explainer.TEMPLATES,
# and a passing-map and violating-map test.
RULES: list[Rule] = [no_spawn, missing_objects, unreachable, max_density, min_distance]


def validate(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    return [v for rule in RULES for v in rule(game_map, spec)]
