"""Spec -> map. Deterministic: all randomness comes from the rng argument.

Every map has a one-row top wall. A kit with a taller wall adds the rest when it is drawn, so the
spec's interior stays true for every kit.
"""

from collections import Counter
from random import Random

from app.models import GameMap, MapObject, Tile
from app.spec import MapSpec, MinDistanceRule, ObjectKind, doors_on_wall
from app.walkable import BLOCKING_KINDS, Cell, reachable

ATTEMPTS = 20  # Layouts to try before keeping the one with the fewest misses.
CANDIDATES = 50  # Cells to try for each object. Bounds the time on large maps.
# Rule breaks may be impossible to avoid, so retry them only while (tries * objects^2) stays below
# this. Walkable misses always get every attempt: they break a hard rule, and only dense rooms,
# which are cheap, have them.
RULE_RETRY_LIMIT = 200_000


def generate(spec: MapSpec, rng: Random) -> GameMap:
    w, h = spec.width, spec.height
    tiles = [
        [Tile.WALL if x in (0, w - 1) or y in (0, h - 1) else Tile.FLOOR for x in range(w)]
        for y in range(h)
    ]
    doors = _place_doors(spec, rng)
    for x, y in doors:
        tiles[y][x] = Tile.DOOR

    total = sum(o.count for o in spec.objects)
    objects, misses = _place_objects(spec, tiles, doors, rng, False)
    for attempt in range(2, ATTEMPTS + 1):
        if misses == (0, 0) or (misses[0] == 0 and attempt * total**2 > RULE_RETRY_LIMIT):
            break
        # A packed room may only work with the spawn right at a door, so try that later on.
        next_objects, next_misses = _place_objects(spec, tiles, doors, rng, attempt > ATTEMPTS // 2)
        if next_misses < misses:
            objects, misses = next_objects, next_misses
    return GameMap(width=w, height=h, tiles=tiles, objects=objects)


def _place_doors(spec: MapSpec, rng: Random) -> list[Cell]:
    w, h = spec.width, spec.height
    pool = [
        wall
        for wall, length in (("top", w), ("bottom", w), ("left", h), ("right", h))
        for _ in range(doors_on_wall(length))
    ]
    counts = Counter(rng.sample(pool, spec.doors))
    return [
        *((x, 0) for x in _door_positions(w, counts["top"], rng)),
        *((x, h - 1) for x in _door_positions(w, counts["bottom"], rng)),
        *((0, y) for y in _door_positions(h, counts["left"], rng)),
        *((w - 1, y) for y in _door_positions(h, counts["right"], rng)),
    ]


def _door_positions(length: int, count: int, rng: Random) -> list[int]:
    """Door centers along a wall, spaced as `doors_on_wall` needs. `slack` is the spare cells."""
    slack = length - 2 - 3 * count
    shifts = sorted(rng.randint(0, slack) for _ in range(count))
    return [2 + 3 * i + shift for i, shift in enumerate(shifts)]


def _place_objects(
    spec: MapSpec, tiles: list[list[Tile]], doors: list[Cell], rng: Random, spawn_at_door: bool
) -> tuple[list[MapObject], tuple[int, int]]:
    """One layout, and its misses: objects placed against the walkable rules, then rule breaks.

    The spawn goes first, then blocking objects, so that each one can keep the doors in reach.
    The rest go only where the player can walk.
    """
    gaps = _min_distances(spec)
    kinds = sorted(
        (o.kind for o in spec.objects for _ in range(o.count)),
        key=lambda kind: (kind != ObjectKind.PLAYER_SPAWN, kind not in BLOCKING_KINDS),
    )
    free = [(x, y) for y in range(1, spec.height - 1) for x in range(1, spec.width - 1)]
    rng.shuffle(free)

    # Without a spawn, the doors must still reach each other, starting just inside the first.
    door_x, door_y = doors[0]
    start = (min(max(door_x, 1), spec.width - 2), min(max(door_y, 1), spec.height - 2))
    if spawn_at_door:
        free.remove(start)
        free.insert(0, start)
    targets = set(doors)
    blocked: set[Cell] = set()
    placed: list[tuple[ObjectKind, Cell]] = []
    walkable: set[Cell] = set()  # Set once every blocking object is down.

    def allowed(kind: ObjectKind, cell: Cell) -> bool:
        if kind == ObjectKind.PLAYER_SPAWN:
            return True
        if kind not in BLOCKING_KINDS:
            return cell in walkable
        # Each BFS is slow on a large map, and a cell with open space all around can't cut a path.
        return _open_around(cell, tiles, blocked) or (
            targets <= reachable(tiles, blocked | {cell}, start)
        )

    unwalkable = too_close = 0
    for kind in kinds:
        if kind != ObjectKind.PLAYER_SPAWN and kind not in BLOCKING_KINDS and not walkable:
            walkable = reachable(tiles, blocked, start)
        best: tuple[int, Cell] | None = None
        for cell in free[:CANDIDATES]:
            breaks = _distance_breaks(kind, cell, placed, gaps)
            if (best is None or breaks < best[0]) and allowed(kind, cell):
                best = (breaks, cell)
                if breaks == 0:
                    break
        if best is None:
            unwalkable += 1
            best = (_distance_breaks(kind, free[0], placed, gaps), free[0])
        breaks, cell = best
        too_close += breaks

        free.remove(cell)
        placed.append((kind, cell))
        if kind == ObjectKind.PLAYER_SPAWN:
            start = placed[0][1]  # Spawns go first.
            targets.add(cell)
        if kind in BLOCKING_KINDS:
            blocked.add(cell)

    objects = [MapObject(kind=kind.value, x=x, y=y) for kind, (x, y) in placed]
    return objects, (unwalkable, too_close)


def _open_around(cell: Cell, tiles: list[list[Tile]], blocked: set[Cell]) -> bool:
    x, y = cell
    return all(
        tiles[y + dy][x + dx] != Tile.WALL and (x + dx, y + dy) not in blocked
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if dx or dy
    )


def _min_distances(spec: MapSpec) -> dict[ObjectKind, dict[ObjectKind, int]]:
    """For each kind, how far it must stay from each other kind."""
    gaps: dict[ObjectKind, dict[ObjectKind, int]] = {}
    for rule in spec.rules:
        if isinstance(rule, MinDistanceRule):
            gaps.setdefault(rule.a, {})[rule.b] = rule.tiles
            gaps.setdefault(rule.b, {})[rule.a] = rule.tiles
    return gaps


def _distance_breaks(
    kind: ObjectKind,
    cell: Cell,
    placed: list[tuple[ObjectKind, Cell]],
    gaps: dict[ObjectKind, dict[ObjectKind, int]],
) -> int:
    limits = gaps.get(kind)
    if not limits:
        return 0
    x, y = cell
    return sum(
        1
        for other, (ox, oy) in placed
        if other in limits and abs(x - ox) + abs(y - oy) < limits[other]
    )
