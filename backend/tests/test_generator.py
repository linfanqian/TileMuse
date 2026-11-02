from collections import Counter
from random import Random
from time import perf_counter

import pytest

from app.generator import generate
from app.models import GameMap, Tile
from app.walkable import BLOCKING_KINDS, Cell, reachable

SEEDS = range(40)


@pytest.fixture
def busy_spec(make_spec):
    """A spec with doors, blocking and walkable objects, and distance rules."""

    def make(**overrides):
        fields = {
            "width": 14,
            "height": 10,
            "doors": 3,
            "objects": [
                {"kind": "player_spawn", "count": 1},
                {"kind": "guard", "count": 3},
                {"kind": "cover", "count": 12},
                {"kind": "chest", "count": 2},
                {"kind": "key", "count": 1},
                {"kind": "light", "count": 2},
            ],
            "rules": [
                {"type": "min_distance", "a": "guard", "b": "player_spawn", "tiles": 5},
                {"type": "min_distance", "a": "guard", "b": "guard", "tiles": 3},
            ],
        }
        return make_spec(**{**fields, **overrides})

    return make


def doors_of(game_map: GameMap) -> list[Cell]:
    return [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile == Tile.DOOR
    ]


def cells_of(game_map: GameMap, kind: str) -> list[Cell]:
    return [(obj.x, obj.y) for obj in game_map.objects if obj.kind == kind]


def walkable_from(game_map: GameMap, start: Cell) -> set[Cell]:
    blocked = {(obj.x, obj.y) for obj in game_map.objects if obj.kind in BLOCKING_KINDS}
    return reachable(game_map.tiles, blocked, start)


def test_same_seed_identical_map(busy_spec):
    assert generate(busy_spec(), Random(42)) == generate(busy_spec(), Random(42))


def test_different_seeds_give_different_maps(busy_spec):
    assert generate(busy_spec(), Random(1)) != generate(busy_spec(), Random(2))


def test_fixed_seed_golden_map(make_spec):
    # Golden output: catches changes across processes, machines and Python versions that
    # comparing two runs in one process cannot. Update it only on an intended generator change.
    spec = make_spec(
        width=8,
        height=6,
        doors=2,
        objects=[
            {"kind": "player_spawn", "count": 1},
            {"kind": "guard", "count": 1},
            {"kind": "cover", "count": 2},
            {"kind": "key", "count": 1},
        ],
        rules=[{"type": "min_distance", "a": "guard", "b": "player_spawn", "tiles": 3}],
    )
    game_map = generate(spec, Random(42))
    assert game_map.tiles == [
        [1, 1, 2, 1, 1, 1, 1, 1],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 2],
        [1, 0, 0, 0, 0, 0, 0, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    ]
    assert [(o.kind, o.x, o.y) for o in game_map.objects] == [
        ("player_spawn", 1, 4),
        ("cover", 3, 3),
        ("cover", 5, 2),
        ("guard", 5, 4),
        ("key", 4, 4),
    ]


@pytest.mark.parametrize(
    ("width", "height", "doors"), [(4, 5, 2), (5, 5, 4), (8, 8, 8), (16, 12, 3), (11, 4, 4)]
)
def test_places_exactly_the_spec_doors(make_spec, width, height, doors):
    spec = make_spec(width=width, height=height, doors=doors)
    for seed in SEEDS:
        assert len(doors_of(generate(spec, Random(seed)))) == doors


@pytest.mark.parametrize(("width", "height", "doors"), [(8, 8, 8), (20, 14, 8), (5, 8, 6)])
def test_doors_leave_room_for_their_wall_ends(make_spec, width, height, doors):
    spec = make_spec(width=width, height=height, doors=doors)
    for seed in SEEDS:
        doors_found = doors_of(generate(spec, Random(seed)))
        walls = {
            "top": [x for x, y in doors_found if y == 0],
            "bottom": [x for x, y in doors_found if y == height - 1],
            "left": [y for x, y in doors_found if x == 0],
            "right": [y for x, y in doors_found if x == width - 1],
        }
        for wall, centers in walls.items():
            length = width if wall in ("top", "bottom") else height
            assert all(2 <= center <= length - 3 for center in centers)
            ordered = sorted(centers)
            assert all(b - a >= 3 for a, b in zip(ordered, ordered[1:], strict=False))


def test_doors_can_land_on_every_wall(make_spec):
    spec = make_spec(width=20, height=14, doors=1)
    walls = set()
    for seed in SEEDS:
        ((x, y),) = doors_of(generate(spec, Random(seed)))
        walls.add("top" if y == 0 else "bottom" if y == 13 else "left" if x == 0 else "right")
    assert walls == {"top", "bottom", "left", "right"}


def test_room_is_walled_with_floor_inside(make_spec):
    game_map = generate(make_spec(width=8, height=6), Random(3))
    for y, row in enumerate(game_map.tiles):
        for x, tile in enumerate(row):
            if x in (0, 7) or y in (0, 5):
                assert tile in (Tile.WALL, Tile.DOOR)
            else:
                assert tile == Tile.FLOOR


def test_places_every_object_on_its_own_interior_cell(busy_spec):
    spec = busy_spec()
    wanted = {o.kind.value: o.count for o in spec.objects}
    for seed in SEEDS:
        game_map = generate(spec, Random(seed))
        assert Counter(obj.kind for obj in game_map.objects) == wanted
        cells = [(obj.x, obj.y) for obj in game_map.objects]
        assert len(set(cells)) == len(cells)
        assert all(0 < x < spec.width - 1 and 0 < y < spec.height - 1 for x, y in cells)


def test_every_door_stays_reachable_from_the_spawn(busy_spec):
    many_covers = [{"kind": "player_spawn", "count": 1}, {"kind": "cover", "count": 50}]
    for spec in (busy_spec(), busy_spec(objects=many_covers, rules=[])):
        for seed in SEEDS:
            game_map = generate(spec, Random(seed))
            ((spawn),) = cells_of(game_map, "player_spawn")
            assert set(doors_of(game_map)) <= walkable_from(game_map, spawn)


def test_every_spawn_reaches_every_door(busy_spec):
    objects = [{"kind": "player_spawn", "count": 3}, {"kind": "cover", "count": 30}]
    for seed in SEEDS:
        game_map = generate(busy_spec(objects=objects, rules=[]), Random(seed))
        spawns = cells_of(game_map, "player_spawn")
        assert set(doors_of(game_map)) | set(spawns) <= walkable_from(game_map, spawns[0])


def test_doors_stay_connected_without_a_spawn(busy_spec):
    objects = [{"kind": "cover", "count": 40}]
    for seed in SEEDS:
        game_map = generate(busy_spec(objects=objects, rules=[]), Random(seed))
        doors = doors_of(game_map)
        x, y = doors[0]
        inside = (min(max(x, 1), 12), min(max(y, 1), 8))
        assert set(doors) <= walkable_from(game_map, inside)


def test_walkable_objects_can_be_reached(busy_spec):
    for seed in SEEDS:
        game_map = generate(busy_spec(), Random(seed))
        ((spawn),) = cells_of(game_map, "player_spawn")
        cells = {(o.x, o.y) for o in game_map.objects if o.kind not in BLOCKING_KINDS}
        assert cells <= walkable_from(game_map, spawn)


def test_keeps_min_distance_when_it_fits(busy_spec):
    for seed in SEEDS:
        game_map = generate(busy_spec(), Random(seed))
        guards = cells_of(game_map, "guard")
        ((sx, sy),) = cells_of(game_map, "player_spawn")
        assert all(abs(x - sx) + abs(y - sy) >= 5 for x, y in guards)
        for i, (x, y) in enumerate(guards):
            assert all(abs(x - ox) + abs(y - oy) >= 3 for ox, oy in guards[i + 1 :])


def test_impossible_min_distance_still_places_every_object(make_spec):
    # The spec only rules out a pair that can't fit. Reporting the rest is the validator's job.
    spec = make_spec(
        width=8,
        height=8,
        objects=[{"kind": "guard", "count": 6}],
        rules=[{"type": "min_distance", "a": "guard", "b": "guard", "tiles": 10}],
    )
    for seed in SEEDS:
        assert len(generate(spec, Random(seed)).objects) == 6


def test_full_room_places_every_object_and_keeps_the_door_reachable(make_spec):
    spec = make_spec(
        width=5,
        height=5,
        objects=[{"kind": "player_spawn", "count": 1}, {"kind": "cover", "count": 8}],
    )
    for seed in SEEDS:
        game_map = generate(spec, Random(seed))
        assert len(game_map.objects) == 9
        ((spawn),) = cells_of(game_map, "player_spawn")
        assert set(doors_of(game_map)) <= walkable_from(game_map, spawn)


def test_impossible_rules_on_the_largest_map_finish_quickly(make_spec):
    kinds = ["player_spawn", "guard", "cover", "chest", "key", "light"]
    spec = make_spec(
        width=128,
        height=128,
        doors=8,
        objects=[{"kind": kind, "count": 64} for kind in kinds],
        rules=[
            {"type": "min_distance", "a": a, "b": b, "tiles": 250}
            for i, a in enumerate(kinds)
            for b in kinds[i:]
        ],
    )
    began = perf_counter()
    assert len(generate(spec, Random(1)).objects) == 384
    assert perf_counter() - began < 20  # Far above normal, so a slow CI machine still passes.
