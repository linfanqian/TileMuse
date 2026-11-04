from app.models import Tile
from app.tileset import load_tileset
from app.walkable import BLOCKING_KINDS, exits, reachable

F, W, D = Tile.FLOOR, Tile.WALL, Tile.DOOR
ROOM = [
    [W, W, D, W],
    [W, F, F, W],
    [W, F, F, W],
    [W, W, W, W],
]


def test_exits_are_the_doors_on_the_outer_wall():
    tiles = [
        [D, W, D, W],  # A corner door counts: it is on the outer wall.
        [W, D, F, D],  # The door at (1, 1) is inside the room, so it leads nowhere.
        [W, F, F, W],
        [W, D, W, W],
    ]
    assert exits(tiles) == [(0, 0), (2, 0), (3, 1), (1, 3)]
    assert exits(ROOM) == [(2, 0)]
    assert exits([[F, F], [F, F]]) == []


def test_reaches_floors_and_doors_but_not_walls():
    assert reachable(ROOM, set(), (1, 1)) == {(1, 1), (2, 1), (1, 2), (2, 2), (2, 0)}


def test_blocked_cells_stop_the_player():
    assert reachable(ROOM, {(2, 1), (1, 2)}, (1, 1)) == {(1, 1)}


def test_blocked_start_reaches_nothing():
    assert reachable(ROOM, {(1, 1)}, (1, 1)) == set()


def test_start_on_a_wall_reaches_nothing():
    assert reachable(ROOM, set(), (1, 0)) == set()


def test_blocking_kinds_match_the_kit_tiles():
    tileset = load_tileset()
    entries = {entry.name: entry for entry in tileset.catalog.entries}
    for kit in tileset.kits.values():
        for kind, name in kit.objects.items():
            assert entries[name].blocking == (kind in BLOCKING_KINDS), name
