import struct
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from app.spec import ObjectKind
from app.tileset import (
    ASSETS,
    OBJECT_TILE_KINDS,
    Catalog,
    Kind,
    ThemeKit,
    TileEntry,
    Tileset,
    load_tileset,
)


def entry(name: str = "tile", **overrides: Any) -> dict[str, Any]:
    return {
        "id": 0,
        "name": name,
        "kind": "floor",
        "themes": ["dungeon"],
        "blocking": False,
        "confidence": "high",
        **overrides,
    }


def catalog(*entries: dict[str, Any]) -> dict[str, Any]:
    return {
        "image": "tilesheet.png",
        "tile_size": 16,
        "columns": 4,
        "rows": 2,
        "entries": list(entries),
    }


def tiles(**overrides: Any) -> list[dict[str, Any]]:
    """One catalog entry per kind, named after its kind, each on its own tile. Walls and objects
    block, since the kit below uses `object` only for kinds that block."""
    return [
        entry(kind, kind=kind, id=i, blocking=kind in ("wall", "object"), **overrides)
        for i, kind in enumerate(get_args(Kind))
    ]


def kit(**overrides: Any) -> dict[str, Any]:
    """A complete kit that uses the entries from `tiles`."""
    pieces = ("top", "bottom", "left", "right")
    corners = ("corner_tl", "corner_tr", "corner_bl", "corner_br")
    return {
        "description": "a kit",
        "floor": "floor",
        "walls": dict.fromkeys(pieces + corners, "wall"),
        "doors": dict.fromkeys(pieces, "door"),
        "objects": dict(OBJECT_TILE_KINDS),
        **overrides,
    }


def test_load_tileset_keeps_the_first_kits():
    assert {"dungeon", "town", "farm", "factory"} <= set(load_tileset().kits)


def test_sheet_image_matches_catalog():
    sheet = load_tileset().catalog
    with (ASSETS / sheet.image).open("rb") as image:
        header = image.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", header[16:24])
    assert (width, height) == (sheet.columns * sheet.tile_size, sheet.rows * sheet.tile_size)


def test_valid_tileset_passes():
    Tileset(catalog=catalog(*tiles()), kits={"dungeon": kit()})


def test_entry_rejects_wrong_part_count():
    with pytest.raises(ValidationError, match="2 parts"):
        TileEntry(**entry(footprint=(1, 3), parts=[0, 1]))


def test_entry_rejects_multi_cell_without_parts():
    with pytest.raises(ValidationError, match="0 parts for a 2x2 entry"):
        TileEntry(**entry(footprint=(2, 2)))


def test_catalog_rejects_duplicate_name():
    with pytest.raises(ValidationError, match="unique: tile"):
        Catalog(**catalog(entry(), entry()))


@pytest.mark.parametrize("tiles", [{"id": 8}, {"footprint": (2, 1), "parts": [0, 8]}])
def test_catalog_rejects_id_outside_sheet(tiles):
    with pytest.raises(ValidationError, match="outside"):
        Catalog(**catalog(entry(**tiles)))


def test_kit_rejects_missing_description():
    no_description = {k: v for k, v in kit().items() if k != "description"}
    with pytest.raises(ValidationError, match="description"):
        ThemeKit(**no_description)


def test_kit_rejects_missing_wall_piece():
    walls = kit()["walls"]
    del walls["corner_br"]
    with pytest.raises(ValidationError, match="missing wall piece: corner_br"):
        ThemeKit(**kit(walls=walls))


def test_kit_rejects_missing_door_side():
    doors = kit()["doors"]
    del doors["left"]
    with pytest.raises(ValidationError, match="missing door side: left"):
        ThemeKit(**kit(doors=doors))


def test_kit_rejects_missing_object_kind():
    objects = kit()["objects"]
    del objects[ObjectKind.KEY]
    with pytest.raises(ValidationError, match="missing object kind: key"):
        ThemeKit(**kit(objects=objects))


def test_every_object_kind_has_a_tile_kind():
    assert set(OBJECT_TILE_KINDS) == set(ObjectKind)


def test_tileset_rejects_unknown_tile_name():
    with pytest.raises(ValidationError, match="no catalog entry named nope"):
        Tileset(catalog=catalog(*tiles()), kits={"dungeon": kit(floor="nope")})


def test_tileset_rejects_unreviewed_tile():
    with pytest.raises(ValidationError, match="has not been reviewed"):
        Tileset(catalog=catalog(*tiles(confidence="medium")), kits={"dungeon": kit()})


@pytest.mark.parametrize(
    ("slot", "message"),
    [
        ({"floor": "object"}, "object is object, not floor"),
        ({"floor_shadow_top": "wall"}, "wall is wall, not floor"),
        ({"face_end_left": "floor"}, "floor is floor, not wall"),
        ({"face_end_right": "door"}, "door is door, not wall"),
        ({"walls": {**kit()["walls"], "left": "door"}}, "door is door, not wall"),
        ({"doors": {**kit()["doors"], "top": "wall"}}, "wall is wall, not door"),
        ({"objects": {**kit()["objects"], ObjectKind.KEY: "object"}}, "object is object, not item"),
        (
            {"objects": {**kit()["objects"], ObjectKind.GUARD: "item"}},
            "item is item, not character",
        ),
    ],
)
def test_tileset_rejects_tile_of_wrong_kind(slot, message):
    with pytest.raises(ValidationError, match=message):
        Tileset(catalog=catalog(*tiles()), kits={"dungeon": kit(**slot)})


def test_tileset_allows_tile_from_another_pack():
    knight = entry("knight", kind="character", themes=["dungeon"])
    objects = {**kit()["objects"], ObjectKind.GUARD: "knight"}
    Tileset(catalog=catalog(*tiles(), knight), kits={"town": kit(objects=objects)})


def test_tileset_rejects_multi_cell_object():
    wide = entry("wide", kind="object", footprint=(2, 1), parts=[0, 1])
    objects = {**kit()["objects"], ObjectKind.CHEST: "wide"}
    with pytest.raises(ValidationError, match="chest tile wide must fill one cell"):
        Tileset(catalog=catalog(*tiles(), wide), kits={"dungeon": kit(objects=objects)})


@pytest.mark.parametrize(
    ("name", "blocking"),
    [("object", False), ("item", True)],  # Chest and cover use "object"; key uses "item".
)
def test_tileset_rejects_object_tile_that_disagrees_with_the_game(name, blocking):
    # The generator and validator decide what blocks by object kind, so the tile must agree.
    flipped = [{**e, "blocking": blocking} if e["name"] == name else e for e in tiles()]
    with pytest.raises(ValidationError, match=f"tile {name} must have blocking {not blocking}"):
        Tileset(catalog=catalog(*flipped), kits={"dungeon": kit()})


@pytest.mark.parametrize(("name", "role"), [("wall", "wall"), ("floor", "floor or door")])
def test_tileset_rejects_catalog_flag_that_disagrees_with_the_kit(name, role):
    flipped = [{**e, "blocking": not e["blocking"]} if e["name"] == name else e for e in tiles()]
    with pytest.raises(ValidationError, match=f"{name} is a {role}"):
        Tileset(catalog=catalog(*flipped), kits={"dungeon": kit()})


def test_tileset_rejects_tile_that_both_blocks_and_is_walked_on():
    # The opening's ends stand where walls are, but its first part is the floor's tile.
    opening = entry("opening", kind="door", footprint=(3, 1), parts=[0, 2, 1])
    doors = {**kit()["doors"], "bottom": "opening"}
    with pytest.raises(ValidationError, match=r"tiles \[0\] both block and can be walked on"):
        Tileset(catalog=catalog(*tiles(), opening), kits={"dungeon": kit(doors=doors)})


def test_blocking_tiles_follow_how_the_kit_uses_them():
    # Tile 1 is a wall here, though a walkable entry elsewhere shares it.
    end = entry("end", kind="decor", id=1)
    opening = entry("opening", kind="door", footprint=(3, 1), parts=[1, 0, 1])
    doors = {**kit()["doors"], "left": "opening"}
    tileset = Tileset(catalog=catalog(*tiles(), end, opening), kits={"dungeon": kit(doors=doors)})
    # Wall (1) and object (3) block; the opening's middle (floor, 0) and the door (2) don't.
    assert tileset.blocking_tiles("dungeon") == [1, 3]
