from app.models import Tile
from app.tileset import load_tileset
from app.walkable import BLOCKING_KINDS, reachable

F, W, D = Tile.FLOOR, Tile.WALL, Tile.DOOR
ROOM = [
    [W, W, D, W],
    [W, F, F, W],
    [W, F, F, W],
    [W, W, W, W],
]


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
