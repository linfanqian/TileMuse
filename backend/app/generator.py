"""Spec -> map. Deterministic: all randomness comes from the rng argument.

Every map has a one-row top wall. A kit with a taller wall adds the rest when it is drawn, so the
spec's interior stays true for every kit.

Each layout starts with a network: connected cells that join every door, spawn, and chest.
Other blocking objects stay off it, so they can't cut the player off.
"""

from random import Random

from app.models import GameMap, MapObject, Tile
from app.spec import MapSpec, MinDistanceRule, ObjectKind, doors_on_wall
from app.walkable import BLOCKING_KINDS, Cell, reachable

ATTEMPTS = 20  # Layouts to try before keeping the one with the fewest misses.
CANDIDATES = 100  # Cells to compare for each object, once one fits. Bounds the time.
# Distance rules may be impossible to meet, so retry those misses only while
# (tries * objects^2) stays below this. Walkable misses always get every attempt.
RULE_RETRY_LIMIT = 200_000


def generate(spec: MapSpec, rng: Random) -> GameMap:
    total = sum(o.count for o in spec.objects)
    best, best_misses = _layout(spec, rng)
    for attempt in range(2, ATTEMPTS + 1):
        if best_misses == (0, 0):
            break
        if best_misses[0] == 0 and attempt * total**2 > RULE_RETRY_LIMIT:
            break
        game_map, misses = _layout(spec, rng)
        if misses < best_misses:
            best, best_misses = game_map, misses
    return best


def _layout(spec: MapSpec, rng: Random) -> tuple[GameMap, tuple[int, int]]:
    """One map, and its misses: objects the player can't reach, then distance rule breaks."""
    w, h = spec.width, spec.height
    tiles = [
        [Tile.WALL if x in (0, w - 1) or y in (0, h - 1) else Tile.FLOOR for x in range(w)]
        for y in range(h)
    ]
    doors = _place_doors(spec, rng)
    for x, y in doors:
        tiles[y][x] = Tile.DOOR

    free = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1)]
    interior = set(free)
    rng.shuffle(free)

    counts = {o.kind: o.count for o in spec.objects}
    gaps = _min_distances(spec)
    blockers = sum(n for kind, n in counts.items() if kind in BLOCKING_KINDS)
    walkers = sum(n for kind, n in counts.items() if kind not in BLOCKING_KINDS)
    room = len(interior) - blockers  # The most cells the network can take.

    # Insertion-ordered, so ties never depend on how a set hashes.
    entrance = _inside(doors[0], w, h)
    network: dict[Cell, None] = {entrance: None}
    for door in doors[1:]:
        cell = _inside(door, w, h)
        for step in (cell, *(_path(cell, network, set(), rng) or ())):
            network[step] = None

    blocked: set[Cell] = set()
    walkable: set[Cell] = set()  # Set once every blocking object is down.
    placed: list[tuple[ObjectKind, Cell]] = []
    unreachable = too_close = 0

    def steps_to_add(kind: ObjectKind, cell: Cell) -> list[Cell] | None:
        """The network cells this spot needs, or None if the object can't go there."""
        if kind not in (ObjectKind.PLAYER_SPAWN, ObjectKind.CHEST):
            if kind in BLOCKING_KINDS:
                return None if cell in network else []
            return [] if cell in walkable else None
        if cell in network:
            return [] if kind == ObjectKind.PLAYER_SPAWN else None
        if kind == ObjectKind.CHEST and not network.keys().isdisjoint(_neighbors(cell)):
            return []
        if len(network) >= room:  # Skips the slow path search once nothing more can join.
            return None
        path = _path(cell, network, blocked, rng)
        if path is None:
            return None
        steps = [cell, *path] if kind == ObjectKind.PLAYER_SPAWN else path
        return steps if len(network) + len(steps) <= room else None

    def place(kind: ObjectKind) -> None:
        nonlocal unreachable, too_close
        for _ in range(counts.get(kind, 0)):
            best: tuple[int, Cell, list[Cell]] | None = None
            for tried, cell in enumerate(free):
                if best is not None and tried >= CANDIDATES:
                    break
                breaks = _distance_breaks(kind, cell, placed, gaps)
                if best is None or breaks < best[0]:
                    steps = steps_to_add(kind, cell)
                    if steps is not None:
                        best = (breaks, cell, steps)
                        if breaks == 0:
                            break
            if best is None:
                unreachable += 1
                best = (_distance_breaks(kind, free[0], placed, gaps), free[0], [])
            breaks, cell, steps = best
            too_close += breaks
            network.update(dict.fromkeys(steps))
            free.remove(cell)
            placed.append((kind, cell))
            if kind in BLOCKING_KINDS:
                blocked.add(cell)

    place(ObjectKind.PLAYER_SPAWN)
    place(ObjectKind.CHEST)
    _grow(network, walkers, interior, blocked, rng)  # So every walking object has a reachable cell.
    for kind in ObjectKind:
        if kind in BLOCKING_KINDS and kind != ObjectKind.CHEST:
            place(kind)
    walkable.update(reachable(tiles, blocked, entrance))
    for kind in ObjectKind:
        if kind not in BLOCKING_KINDS and kind != ObjectKind.PLAYER_SPAWN:
            place(kind)

    objects = [MapObject(kind=kind.value, x=x, y=y) for kind, (x, y) in placed]
    return GameMap(width=w, height=h, tiles=tiles, objects=objects), (unreachable, too_close)


def _place_doors(spec: MapSpec, rng: Random) -> list[Cell]:
    w, h = spec.width, spec.height
    walls = (("top", w), ("bottom", w), ("left", h), ("right", h))
    pool = [wall for wall, length in walls for _ in range(doors_on_wall(length))]
    chosen = rng.sample(pool, spec.doors)
    return [
        *((x, 0) for x in _door_positions(w, chosen.count("top"), rng)),
        *((x, h - 1) for x in _door_positions(w, chosen.count("bottom"), rng)),
        *((0, y) for y in _door_positions(h, chosen.count("left"), rng)),
        *((w - 1, y) for y in _door_positions(h, chosen.count("right"), rng)),
    ]


def _door_positions(length: int, count: int, rng: Random) -> list[int]:
    """Door centers along a wall, spaced as `doors_on_wall` needs. `slack` is the spare cells."""
    slack = length - 2 - 3 * count
    shifts = sorted(rng.randint(0, slack) for _ in range(count))
    return [2 + 3 * i + shift for i, shift in enumerate(shifts)]


def _inside(door: Cell, width: int, height: int) -> Cell:
    """The interior cell next to a door."""
    x, y = door
    return min(max(x, 1), width - 2), min(max(y, 1), height - 2)


def _path(
    cell: Cell, network: dict[Cell, None], blocked: set[Cell], rng: Random
) -> list[Cell] | None:
    """The cells between `cell` and the nearest network cell, or None if blocked on the way."""
    x, y = cell
    target_x, target_y = min(network, key=lambda c: abs(c[0] - x) + abs(c[1] - y))
    path = []
    while (x, y) != (target_x, target_y):
        steps = []
        if x != target_x:
            steps.append((x + (1 if target_x > x else -1), y))
        if y != target_y:
            steps.append((x, y + (1 if target_y > y else -1)))
        steps = [step for step in steps if step not in blocked]
        if not steps:
            return None
        x, y = rng.choice(steps)
        path.append((x, y))
    return path[:-1]  # The last step is already in the network.


def _grow(
    network: dict[Cell, None], size: int, interior: set[Cell], blocked: set[Cell], rng: Random
) -> None:
    """Add cells next to the network, at random, until it has `size` cells."""
    frontier = list(network)
    while len(network) < size and frontier:
        for cell in _neighbors(frontier.pop(rng.randrange(len(frontier)))):
            if (
                len(network) < size
                and cell in interior
                and cell not in blocked
                and cell not in network
            ):
                network[cell] = None
                frontier.append(cell)


def _neighbors(cell: Cell) -> tuple[Cell, Cell, Cell, Cell]:
    x, y = cell
    return (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)


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
