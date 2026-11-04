from random import Random

import pytest

from app.explainer import TEMPLATES, explain
from app.generator import generate
from app.models import GameMap, MapObject, Tile
from app.validator import validate

SPAWN = ("player_spawn", 1, 1)
SPAWN_SPEC = {"kind": "player_spawn", "count": 1}


def room(width=8, height=6, doors=((3, 0),), objects=(SPAWN,)):
    """A walled room with doors on the walls and objects as (kind, x, y)."""
    tiles = [
        [
            Tile.WALL if x in (0, width - 1) or y in (0, height - 1) else Tile.FLOOR
            for x in range(width)
        ]
        for y in range(height)
    ]
    for x, y in doors:
        tiles[y][x] = Tile.DOOR
    return GameMap(
        width=width,
        height=height,
        tiles=tiles,
        objects=[MapObject(kind=kind, x=x, y=y) for kind, x, y in objects],
    )


def codes(game_map, spec):
    return [v.code for v in validate(game_map, spec)]


def test_open_room_has_no_violations(make_spec):
    assert validate(room(), make_spec()) == []


def test_map_without_a_spawn_is_walked_from_its_doors(make_spec):
    # Cover and light close off (6, 1), the only way to the second door at (7, 1).
    doors = [(3, 0), (7, 1)]
    spec = make_spec(doors=2)
    assert validate(room(doors=doors, objects=[("guard", 2, 2)]), spec) == []

    cut = room(doors=doors, objects=[("cover", 5, 1), ("light", 6, 2), ("key", 6, 1)])
    assert [(v.code, v.x, v.y) for v in validate(cut, spec)] == [
        ("door_unreachable", 7, 1),
        ("object_unreachable", 6, 1),
    ]


def test_a_missing_spawn_is_reported_once(make_spec):
    spec = make_spec(objects=[{"kind": "player_spawn", "count": 1}])
    (violation,) = validate(room(objects=[]), spec)
    assert violation.details == {"kind": "player_spawn", "expected": 1, "found": 0}


def test_missing_object(make_spec):
    spec = make_spec(
        objects=[
            {"kind": "player_spawn", "count": 1},
            {"kind": "guard", "count": 2},
            {"kind": "key", "count": 1},
        ]
    )
    enough = room(objects=[SPAWN, ("guard", 3, 3), ("guard", 5, 3), ("key", 4, 4), ("key", 2, 4)])
    assert validate(enough, spec) == []

    (violation,) = validate(room(objects=[SPAWN, ("guard", 3, 3), ("key", 4, 4)]), spec)
    assert violation.code == "missing_object"
    assert violation.details == {"kind": "guard", "expected": 2, "found": 1}


def test_door_unreachable(make_spec):
    # Cover and light close off (6, 1), the only way to the door at (7, 1).
    walls_off = [SPAWN, ("cover", 5, 1), ("light", 6, 2)]
    open_side = [SPAWN, ("cover", 5, 1)]
    spec = make_spec()
    assert validate(room(doors=[(7, 1)], objects=open_side), spec) == []

    (violation,) = validate(room(doors=[(7, 1)], objects=walls_off), spec)
    assert (violation.code, violation.x, violation.y) == ("door_unreachable", 7, 1)


@pytest.mark.parametrize("kind", ["guard", "key", "player_spawn"])
def test_walking_object_unreachable(make_spec, kind):
    # Chests box in the cell (6, 1). The cover there is never reported: it blocks anyway.
    box = [("chest", 5, 1), ("chest", 6, 2)]
    assert validate(room(objects=[SPAWN, *box, ("cover", 6, 1)]), make_spec()) == []

    (violation,) = validate(room(objects=[SPAWN, *box, (kind, 6, 1)]), make_spec())
    assert (violation.code, violation.x, violation.y) == ("object_unreachable", 6, 1)
    assert violation.details == {"kind": kind}


def test_door_count(make_spec):
    assert validate(room(doors=[(3, 0), (7, 2)]), make_spec(doors=2)) == []

    for doors in ([(3, 0)], [(3, 0), (7, 2), (0, 2)]):
        (violation,) = validate(room(doors=doors), make_spec(doors=2))
        assert violation.code == "door_count"
        assert violation.details == {"expected": 2, "found": len(doors)}


@pytest.mark.parametrize("kind", ["player_spawn", "chest", "cover"])
def test_object_on_a_wall(make_spec, kind):
    assert validate(room(objects=[SPAWN, (kind, 2, 1)]), make_spec()) == []

    # Only object_on_wall is reported, even for a chest with an open side or a spawn.
    (violation,) = validate(room(objects=[SPAWN, (kind, 2, 0)]), make_spec())
    assert (violation.code, violation.x, violation.y) == ("object_on_wall", 2, 0)
    assert violation.details == {"kind": kind}


@pytest.mark.parametrize("wall", [(2, 0), (0, 2)])
def test_spawn_on_a_wall_is_reported_alone(make_spec, wall):
    # Doors and objects are judged from the next spawn, or from the door if there is none.
    stuck = ("player_spawn", *wall)
    for others in ([("player_spawn", 5, 3)], [("key", 2, 2)]):
        (violation,) = validate(room(objects=[stuck, *others]), make_spec())
        assert (violation.code, violation.x, violation.y) == ("object_on_wall", *wall)


def test_map_with_nowhere_to_start_reports_only_the_doors(make_spec):
    # No spawn and no doors: objects can't be judged, so only door_count is reported.
    objects = [("key", 2, 2), ("guard", 3, 3), ("chest", 4, 4)]
    assert codes(room(doors=[], objects=objects), make_spec()) == ["door_count"]


def test_door_inside_the_room_does_not_count(make_spec):
    assert codes(room(doors=[(3, 3)]), make_spec()) == ["door_count"]


def test_blocked_door_is_reported_when_there_is_no_spawn(make_spec):
    objects = [("cover", 3, 0), ("key", 4, 4)]
    assert [(v.code, v.x, v.y) for v in validate(room(objects=objects), make_spec())] == [
        ("door_unreachable", 3, 0)
    ]


@pytest.mark.parametrize("doors", [[(3, 0)], [(3, 0), (7, 2)]])
def test_door_walled_off_from_the_room_is_reported_when_there_is_no_spawn(make_spec, doors):
    # A wall at (3, 1) shuts the door at (3, 0) out of the room. Starting on that door must not
    # count as reaching it.
    game_map = room(doors=doors, objects=[])
    game_map.tiles[1][3] = Tile.WALL
    spec = make_spec(doors=len(doors))
    assert validate(room(doors=doors, objects=[]), spec) == []

    (violation,) = validate(game_map, spec)
    assert (violation.code, violation.x, violation.y) == ("door_unreachable", 3, 0)


def test_spawn_on_a_blocking_object_is_reported_alone(make_spec):
    (violation,) = validate(room(objects=[SPAWN, ("cover", 1, 1), ("key", 4, 4)]), make_spec())
    assert (violation.code, violation.details) == ("object_unreachable", {"kind": "player_spawn"})


def test_boxed_in_spawn_is_reported_whatever_the_order(make_spec):
    # Covers box in the spawn at (6, 1). The spawn at (1, 1) reaches the door.
    boxed = [("player_spawn", 6, 1), ("cover", 5, 1), ("cover", 6, 2)]
    for objects in ([SPAWN, *boxed], [*boxed, SPAWN]):
        (violation,) = validate(room(objects=objects), make_spec())
        assert (violation.code, violation.x, violation.y) == ("object_unreachable", 6, 1)


def test_chest_needs_a_reachable_side(make_spec):
    # The chest at (6, 1) sits in the corner behind the cover at (5, 1) and the light at (6, 2).
    beside = room(objects=[SPAWN, ("chest", 6, 1), ("cover", 5, 1)])
    assert validate(beside, make_spec()) == []

    boxed = room(objects=[SPAWN, ("chest", 6, 1), ("cover", 5, 1), ("light", 6, 2)])
    (violation,) = validate(boxed, make_spec())
    assert (violation.code, violation.details) == ("object_unreachable", {"kind": "chest"})


def test_max_density_matches_the_spec_at_the_limit(make_spec):
    # 8x6 has 24 interior tiles. 6 objects is exactly 0.25, which the spec also allows.
    spec = make_spec(
        width=8,
        height=6,
        objects=[{"kind": "player_spawn", "count": 1}, {"kind": "cover", "count": 5}],
        rules=[{"type": "max_density", "max": 0.25}],
    )
    covers = [("cover", x, 4) for x in range(2, 7)]
    assert validate(room(objects=[SPAWN, *covers]), spec) == []

    (violation,) = validate(room(objects=[SPAWN, *covers, ("cover", 3, 2)]), spec)
    assert violation.code == "max_density"
    assert violation.details == {"objects": 7, "max": 0.25}


def test_max_density_on_a_map_with_no_interior(make_spec):
    spec = make_spec(rules=[{"type": "max_density", "max": 0.5}])
    tiny = GameMap(
        width=2, height=2, tiles=[[0, 0], [0, 0]], objects=[{"kind": "key", "x": 0, "y": 0}]
    )
    assert "max_density" in codes(tiny, spec)


@pytest.mark.parametrize(
    ("a", "b", "first", "second"),
    [("guard", "guard", "guard", "guard"), ("guard", "player_spawn", "player_spawn", "guard")],
)
def test_min_distance(make_spec, a, b, first, second):
    spec = make_spec(
        objects=[{"kind": "player_spawn", "count": 1}, {"kind": "guard", "count": 2}],
        rules=[{"type": "min_distance", "a": a, "b": b, "tiles": 4}],
    )
    # The spawn is far from both guards unless it is one of the pair.
    far_spawn = [] if "player_spawn" in (first, second) else [("player_spawn", 1, 4)]
    far_guard = [("guard", 6, 4)] if "player_spawn" in (first, second) else []
    exactly_4 = [*far_spawn, (first, 1, 1), (second, 3, 3), *far_guard]
    assert validate(room(objects=exactly_4), spec) == []

    too_close = [*far_spawn, (first, 1, 1), (second, 2, 3), *far_guard]
    (violation,) = validate(room(objects=too_close), spec)
    assert (violation.code, violation.x, violation.y) == ("min_distance", 1, 1)
    assert violation.details == {
        "kind": first,
        "other": second,
        "other_x": 2,
        "other_y": 3,
        "distance": 3,
        "tiles": 4,
    }


def every_violation(make_spec):
    """Maps that between them break every rule, checked against one spec."""
    spec = make_spec(
        objects=[{"kind": "player_spawn", "count": 2}, {"kind": "guard", "count": 2}],
        rules=[
            {"type": "max_density", "max": 0.05},
            {"type": "min_distance", "a": "guard", "b": "guard", "tiles": 4},
        ],
    )
    broken = [
        room(objects=[]),
        room(doors=[], objects=[("key", 0, 2)]),
        room(
            doors=[(7, 1)],
            objects=[SPAWN, ("cover", 5, 1), ("light", 6, 2), ("guard", 6, 1), ("guard", 5, 2)],
        ),
    ]
    violations = [v for game_map in broken for v in validate(game_map, spec)]
    assert {v.code for v in violations} == set(TEMPLATES)
    return violations


def test_every_code_has_a_template_that_fills(make_spec):
    # Raises KeyError if a template names a detail its rule doesn't set.
    explain(every_violation(make_spec))


# Rules that make a map unplayable. The editor undoes an edit that breaks one.
HARD_CODES = {"missing_object", "object_on_wall", "door_unreachable", "object_unreachable"}


def test_only_hard_rules_are_blocking(make_spec):
    for violation in every_violation(make_spec):
        assert violation.blocking == (violation.code in HARD_CODES), violation.code


@pytest.mark.parametrize("spawns", [2, 0])
def test_generated_maps_pass(make_spec, spawns):
    objects = [
        {"kind": "guard", "count": 3},
        {"kind": "cover", "count": 12},
        {"kind": "chest", "count": 2},
        {"kind": "key", "count": 1},
        {"kind": "light", "count": 2},
    ]
    rules = [{"type": "max_density", "max": 0.3}]
    if spawns:
        objects.append({"kind": "player_spawn", "count": spawns})
        rules.append({"type": "min_distance", "a": "guard", "b": "player_spawn", "tiles": 5})
    spec = make_spec(width=14, height=10, doors=3, objects=objects, rules=rules)
    for seed in range(40):
        assert validate(generate(spec, Random(seed)), spec) == []


@pytest.mark.parametrize(
    "fields",
    [
        {"width": 5, "height": 5, "objects": [SPAWN_SPEC, {"kind": "cover", "count": 8}]},
        {
            "width": 8,
            "height": 8,
            "doors": 2,
            "objects": [SPAWN_SPEC, {"kind": "cover", "count": 30}],
        },
        {
            "width": 10,
            "height": 10,
            "objects": [
                SPAWN_SPEC,
                {"kind": "cover", "count": 60},
                {"kind": "chest", "count": 2},
                {"kind": "key", "count": 1},
            ],
        },
        {
            "width": 8,
            "height": 8,
            "doors": 3,
            "objects": [{"kind": "guard", "count": 6}],
            "rules": [{"type": "min_distance", "a": "guard", "b": "guard", "tiles": 10}],
        },
    ],
    ids=["full room", "tight doors", "packed", "spacing that can't hold"],
)
def test_generated_maps_never_break_a_hard_rule(make_spec, fields):
    # Spec rules may not hold in a crowded room, but the hard rules always do, so a new map
    # never starts out unplayable.
    spec = make_spec(**fields)
    for seed in range(40):
        blocking = [v for v in validate(generate(spec, Random(seed)), spec) if v.blocking]
        assert blocking == [], seed
