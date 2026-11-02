import struct
from typing import Any

import pytest
from pydantic import ValidationError

from app.spec import ObjectKind
from app.tileset import ASSETS, KIT_OBJECTS, Catalog, ThemeKit, TileEntry, Tileset, load_tileset


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
        "columns": 2,
        "rows": 2,
        "entries": list(entries),
    }


def kit(**overrides: Any) -> dict[str, Any]:
    """A complete kit that uses one catalog entry, named `tile`, everywhere."""
    pieces = ("top", "bottom", "left", "right")
    corners = ("corner_tl", "corner_tr", "corner_bl", "corner_br")
    return {
        "floor": "tile",
        "walls": dict.fromkeys(pieces + corners, "tile"),
        "doors": dict.fromkeys(pieces, "tile"),
        "objects": dict.fromkeys(KIT_OBJECTS, "tile"),
        **overrides,
    }


def test_load_tileset_returns_all_themes():
    assert set(load_tileset().kits) == {"dungeon", "town", "farm", "factory"}


def test_sheet_image_matches_catalog():
    sheet = load_tileset().catalog
    with (ASSETS / sheet.image).open("rb") as image:
        header = image.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", header[16:24])
    assert (width, height) == (sheet.columns * sheet.tile_size, sheet.rows * sheet.tile_size)


def test_valid_tileset_passes():
    Tileset(catalog=catalog(entry()), kits={"dungeon": kit()})


def test_entry_rejects_wrong_part_count():
    with pytest.raises(ValidationError, match="2 parts"):
        TileEntry(**entry(footprint=(1, 3), parts=[0, 1]))


def test_catalog_rejects_duplicate_name():
    with pytest.raises(ValidationError, match="unique: tile"):
        Catalog(**catalog(entry(), entry()))


@pytest.mark.parametrize("tiles", [{"id": 4}, {"footprint": (2, 1), "parts": [0, 4]}])
def test_catalog_rejects_id_outside_sheet(tiles):
    with pytest.raises(ValidationError, match="outside"):
        Catalog(**catalog(entry(**tiles)))


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


def test_kit_needs_no_exit_tile():
    assert ObjectKind.EXIT not in ThemeKit(**kit()).objects


def test_tileset_rejects_unknown_tile_name():
    with pytest.raises(ValidationError, match="no catalog entry named nope"):
        Tileset(catalog=catalog(entry()), kits={"dungeon": kit(floor="nope")})


def test_tileset_rejects_unreviewed_tile():
    with pytest.raises(ValidationError, match="tile has not been reviewed"):
        Tileset(catalog=catalog(entry(confidence="medium")), kits={"dungeon": kit()})


def test_tileset_rejects_multi_cell_object():
    wide = entry("wide", footprint=(2, 1))
    objects = {**kit()["objects"], ObjectKind.CHEST: "wide"}
    with pytest.raises(ValidationError, match="chest tile wide must fill one cell"):
        Tileset(catalog=catalog(entry(), wide), kits={"dungeon": kit(objects=objects)})
