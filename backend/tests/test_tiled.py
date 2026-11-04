import pytest

from app.kits import ASSETS
from app.models import GameMap, MapObject, Tile
from app.spec import ObjectKind
from app.tiled import FIRST_GID, to_tiled
from app.tileset import load_tileset
from app.walkable import BLOCKING_KINDS

TILESET = load_tileset()
ENTRIES = {e.name: e for e in TILESET.catalog.entries}
SIZE = TILESET.catalog.tile_size
W, H = 9, 7
DOORS = {"top": (4, 0), "bottom": (4, H - 1), "left": (0, 3), "right": (W - 1, 3)}


def room() -> GameMap:
    """A walled room with a door on each wall, one object of each kind, a wall painted inside
    at (2, 2), and a door tile inside at (6, 2)."""
    tiles = [
        [Tile.WALL if x in (0, W - 1) or y in (0, H - 1) else Tile.FLOOR for x in range(W)]
        for y in range(H)
    ]
    for x, y in DOORS.values():
        tiles[y][x] = Tile.DOOR
    tiles[2][2] = Tile.WALL
    tiles[2][6] = Tile.DOOR
    objects = [MapObject(kind=kind.value, x=1 + i, y=4) for i, kind in enumerate(ObjectKind)]
    return GameMap(width=W, height=H, tiles=tiles, objects=objects)


def gids(name: str) -> list[int]:
    entry = ENTRIES[name]
    return [FIRST_GID + part for part in entry.parts or [entry.id]]


def layer(out: dict, name: str) -> list[list[int]]:
    found = next(layer for layer in out["layers"] if layer["name"] == name)
    width = found["width"]
    return [found["data"][i : i + width] for i in range(0, len(found["data"]), width)]


@pytest.mark.parametrize("kit_name", list(TILESET.kits))
def test_every_kit_draws_each_cell_with_its_tiles(kit_name):
    kit = TILESET.kits[kit_name]
    out = to_tiled(room(), kit_name)
    rows = len(gids(kit.walls["top"]))  # The top wall's height in tiles.
    shift = rows - 1
    floor, walls = layer(out, "floor"), layer(out, "walls")
    floor_gid = FIRST_GID + ENTRIES[kit.floor].id
    assert (out["width"], out["height"]) == (W, H + shift)
    assert out["tilewidth"] == out["tileheight"] == SIZE == 16

    # Floor everywhere, with the shadow row under a two-row top wall.
    for y, row in enumerate(floor):
        shadow = kit.floor_shadow_top and y == 1 + shift
        for x, gid in enumerate(row):
            expected = gids(kit.floor_shadow_top)[0] if shadow and 0 < x < W - 1 else floor_gid
            assert gid == expected, (x, y)

    def column(x: int, y: int, count: int) -> list[int]:
        return [walls[y + i][x] for i in range(count)]

    # Corners and the top wall fill every top-wall row; other walls take one row.
    assert column(0, 0, rows) == gids(kit.walls["corner_tl"])
    assert column(W - 1, 0, rows) == gids(kit.walls["corner_tr"])
    assert column(2, 0, rows) == gids(kit.walls["top"])
    assert walls[H - 1 + shift][0] == gids(kit.walls["corner_bl"])[0]
    assert walls[H - 1 + shift][W - 1] == gids(kit.walls["corner_br"])[0]
    assert walls[H - 1 + shift][1] == gids(kit.walls["bottom"])[0]
    assert walls[1 + shift][0] == gids(kit.walls["left"])[0]
    assert walls[1 + shift][W - 1] == gids(kit.walls["right"])[0]
    if kit.face_end_left:
        assert walls[1][1] == gids(kit.face_end_left)[0]
        assert walls[1][W - 2] == gids(kit.face_end_right)[0]

    # Each door is centered on its map cell. The middle of an opening shows the floor.
    for side, (x, y) in DOORS.items():
        parts = [0 if gid == floor_gid else gid for gid in gids(kit.doors[side])]
        width, tall = ENTRIES[kit.doors[side]].footprint
        if side in ("top", "bottom"):
            drawn = walls[y + shift][x - width // 2 : x - width // 2 + width]
        else:
            drawn = column(x, y + shift - tall // 2, tall)
        assert drawn == parts, side
    if shift:  # Above a top door, the top wall's upper rows stay.
        assert walls[0][DOORS["top"][0]] == gids(kit.walls["top"])[0]

    # A wall painted inside uses the bottom piece; a door tile inside draws nothing.
    assert walls[2 + shift][2] == gids(kit.walls["bottom"])[0]
    assert walls[2 + shift][6] == 0
    assert all(walls[y][x] == 0 for y in range(2 + shift, H - 1 + shift) for x in (3, 4, 5))

    # Each object is a tile object on its cell. A tile object's y is its bottom edge.
    group = next(layer for layer in out["layers"] if layer["name"] == "objects")
    for obj, kind in zip(group["objects"], ObjectKind, strict=True):
        assert (obj["type"], obj["gid"]) == (kind.value, gids(kit.objects[kind])[0])
        assert obj["y"] == (4 + shift + 1) * SIZE
    assert [obj["x"] for obj in group["objects"]] == [(1 + i) * SIZE for i in range(6)]

    # Every gid points at a tile on the sheet, and object ids count up from 1.
    last_gid = FIRST_GID + out["tilesets"][0]["tilecount"] - 1
    for name in ("floor", "walls"):
        assert all(0 <= gid <= last_gid for row in layer(out, name) for gid in row)
    assert all(FIRST_GID <= obj["gid"] <= last_gid for obj in group["objects"])
    assert [obj["id"] for obj in group["objects"]] == list(range(1, 7))


@pytest.mark.parametrize("kit_name", list(TILESET.kits))
def test_each_door_that_leads_out_is_marked(kit_name):
    out = to_tiled(room(), kit_name)
    shift = out["height"] - H
    doors = next(layer for layer in out["layers"] if layer["name"] == "doors")
    assert doors["type"] == "objectgroup"
    # One door object on each outer door's cell. The door tile inside the room isn't one.
    marked = {(obj["x"] // SIZE, obj["y"] // SIZE - shift) for obj in doors["objects"]}
    assert marked == set(DOORS.values())
    for obj in doors["objects"]:
        assert (obj["name"], obj["type"]) == ("door", "door")
        assert (obj["width"], obj["height"]) == (SIZE, SIZE)
        assert "gid" not in obj  # A plain rectangle, so its y is its top edge.
    # Object ids go on from the objects layer's, and stay unique.
    assert [obj["id"] for obj in doors["objects"]] == list(range(7, 11))
    assert out["nextobjectid"] == 11
    assert out["nextlayerid"] == 5


@pytest.mark.parametrize("kit_name", list(TILESET.kits))
def test_tiles_that_block_movement_say_so(kit_name):
    out = to_tiled(room(), kit_name)
    shift = out["height"] - H
    (tileset,) = out["tilesets"]
    blocking = set()
    for tile in tileset["tiles"]:
        assert tile["properties"] == [{"name": "blocking", "type": "bool", "value": True}]
        blocking.add(tileset["firstgid"] + tile["id"])

    # Floor never blocks. Every wall tile does, door ends included, but not a door's own cell.
    assert not blocking & {gid for row in layer(out, "floor") for gid in row}
    door_cells = {(x, y + shift) for x, y in DOORS.values()}
    for y, row in enumerate(layer(out, "walls")):
        for x, gid in enumerate(row):
            if gid:
                assert (gid in blocking) == ((x, y) not in door_cells), (x, y)

    # Objects block just as they do for the generator and the validator.
    group = next(layer for layer in out["layers"] if layer["name"] == "objects")
    for obj in group["objects"]:
        assert (obj["gid"] in blocking) == (ObjectKind(obj["type"]) in BLOCKING_KINDS), obj["type"]


def test_tileset_points_at_the_sheet():
    (tileset,) = to_tiled(room(), "town")["tilesets"]
    catalog = TILESET.catalog
    assert (ASSETS / tileset["image"]).is_file()
    assert tileset["firstgid"] == FIRST_GID
    assert (tileset["columns"], tileset["tilecount"]) == (
        catalog.columns,
        catalog.columns * catalog.rows,
    )
    assert (tileset["imagewidth"], tileset["imageheight"]) == (192, 704)


def test_unknown_object_kind_stays_a_plain_object():
    game_map = room().model_copy(update={"objects": [MapObject(kind="statue", x=3, y=2)]})
    group = to_tiled(game_map, "dungeon")["layers"][2]
    (obj,) = group["objects"]
    assert "gid" not in obj
    assert (obj["type"], obj["x"], obj["y"]) == ("statue", 3 * SIZE, (2 + 1) * SIZE)


@pytest.mark.parametrize("kit_name", list(TILESET.kits))
@pytest.mark.parametrize(
    "tiles",
    [
        [[Tile.DOOR]],
        [[Tile.WALL, Tile.DOOR], [Tile.DOOR, Tile.FLOOR]],
        [[Tile.DOOR] * 4] * 4,
        [[Tile.FLOOR] * 5] * 3,
    ],
    ids=["1x1 door", "2x2", "all doors", "no walls"],
)
def test_odd_edited_maps_still_export(kit_name, tiles):
    # The editor can paint any tile anywhere, so export must not assume a walled room.
    game_map = GameMap(width=len(tiles[0]), height=len(tiles), tiles=tiles)
    out = to_tiled(game_map, kit_name)
    assert len(layer(out, "walls")) == out["height"]
