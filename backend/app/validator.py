"""Map -> violations. Gameplay rules only; spec schema validation lives in spec.py."""

from collections import Counter, defaultdict
from collections.abc import Callable
from itertools import combinations, product

from app.models import GameMap, MapObject, Tile, Violation
from app.spec import MapSpec, MaxDensityRule, MinDistanceRule, ObjectKind, density
from app.walkable import BLOCKING_KINDS, Cell, neighbors, reachable

Rule = Callable[[GameMap, MapSpec], list[Violation]]


def _doors(game_map: GameMap) -> list[Cell]:
    return [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile == Tile.DOOR
    ]


def _on_wall(game_map: GameMap, obj: MapObject) -> bool:
    return game_map.tiles[obj.y][obj.x] == Tile.WALL


def _missing_objects(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    found = Counter(o.kind for o in game_map.objects)
    return [
        Violation(
            code="missing_object",
            details={"kind": req.kind.value, "expected": req.count, "found": found[req.kind]},
        )
        for req in spec.objects
        if found[req.kind] < req.count
    ]


def _door_count(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    found = len(_doors(game_map))
    if found == spec.doors:
        return []
    return [Violation(code="door_count", details={"expected": spec.doors, "found": found})]


def _objects_on_walls(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    return [
        Violation(code="object_on_wall", x=o.x, y=o.y, details={"kind": o.kind})
        for o in game_map.objects
        if _on_wall(game_map, o)
    ]


def _main_area(
    tiles: list[list[Tile]], blocked: set[Cell], starts: list[Cell], doors: set[Cell]
) -> set[Cell]:
    """The walkable area, from one of `starts`, that reaches the most doors, then the most cells.
    Ties go to the earlier start. Empty if no one can stand on any start."""
    best: set[Cell] = set()
    seen: set[Cell] = set()
    for start in starts:
        if start in seen:
            continue
        area = reachable(tiles, blocked, start)
        seen |= area
        if (len(doors & area), len(area)) > (len(doors & best), len(best)):
            best = area
    return best


def _unreachable(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    """Doors and objects the player can't walk to. The walk covers the area that reaches the most
    doors, starting from a spawn, or from a door if no spawn can be stood on. A chest blocks
    movement, so it counts as reachable when the player can stand next to it. Objects on walls are
    left to _objects_on_walls."""
    doors = _doors(game_map)
    blocked = {(o.x, o.y) for o in game_map.objects if o.kind in BLOCKING_KINDS}
    spawns = [(o.x, o.y) for o in game_map.objects if o.kind == ObjectKind.PLAYER_SPAWN]
    walkable = _main_area(game_map.tiles, blocked, spawns, set(doors)) or _main_area(
        game_map.tiles, blocked, doors, set(doors)
    )
    if not walkable:
        # Nowhere to start from, so nothing else can be judged. Only spawns stuck on a blocking
        # object are reported; those on walls and the missing doors have their own rules.
        return [
            Violation(code="object_unreachable", x=x, y=y, details={"kind": "player_spawn"})
            for x, y in spawns
            if game_map.tiles[y][x] != Tile.WALL
        ]
    violations = [
        Violation(code="door_unreachable", x=x, y=y) for x, y in doors if (x, y) not in walkable
    ]
    for obj in game_map.objects:
        if _on_wall(game_map, obj):
            continue
        if obj.kind == ObjectKind.CHEST:
            cut_off = walkable.isdisjoint(neighbors((obj.x, obj.y)))
        else:
            cut_off = obj.kind not in BLOCKING_KINDS and (obj.x, obj.y) not in walkable
        if cut_off:
            violations.append(
                Violation(code="object_unreachable", x=obj.x, y=obj.y, details={"kind": obj.kind})
            )
    return violations


def _max_density(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    objects = len(game_map.objects)
    # The density itself stays out of details: it is infinite for a map with no interior, and
    # JSON has no infinity.
    filled = density(objects, game_map.width, game_map.height)
    return [
        Violation(code="max_density", details={"objects": objects, "max": rule.max})
        for rule in spec.rules
        if isinstance(rule, MaxDensityRule) and filled > rule.max
    ]


def _min_distance(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    """One violation for each pair of objects that is too close, at the one listed first."""
    objects = game_map.objects
    by_kind: defaultdict[str, list[int]] = defaultdict(list)
    for i, obj in enumerate(objects):
        by_kind[obj.kind].append(i)
    violations = []
    for rule in spec.rules:
        if not isinstance(rule, MinDistanceRule):
            continue
        a, b = by_kind[rule.a], by_kind[rule.b]
        pairs = combinations(a, 2) if rule.a == rule.b else (sorted(p) for p in product(a, b))
        for i, j in sorted(pairs):
            one, other = objects[i], objects[j]
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
RULES: list[Rule] = [
    _missing_objects,
    _door_count,
    _objects_on_walls,
    _unreachable,
    _max_density,
    _min_distance,
]


def validate(game_map: GameMap, spec: MapSpec) -> list[Violation]:
    return [v for rule in RULES for v in rule(game_map, spec)]
