from random import Random

from app.generator import generate
from app.models import GameMap, MapObject, Tile
from app.spec import MapSpec
from app.tiled import TILE_SIZE, to_tiled


def test_export_shape_and_gids():
    game_map = generate(MapSpec(width=8, height=5), Random(0))
    out = to_tiled(game_map)

    for key in ("width", "height", "tilewidth", "tileheight", "orientation", "layers", "tilesets"):
        assert key in out
    tile_layer = next(layer for layer in out["layers"] if layer["type"] == "tilelayer")
    assert len(tile_layer["data"]) == 8 * 5

    tileset = out["tilesets"][0]
    first, last = tileset["firstgid"], tileset["firstgid"] + tileset["tilecount"] - 1
    assert all(first <= gid <= last for gid in tile_layer["data"])


def test_export_objects():
    game_map = GameMap(
        width=3,
        height=2,
        tiles=[[Tile.FLOOR] * 3, [Tile.FLOOR] * 3],
        objects=[MapObject(kind="chest", x=2, y=1), MapObject(kind="key", x=0, y=0)],
    )
    out = to_tiled(game_map)

    group = next(layer for layer in out["layers"] if layer["type"] == "objectgroup")
    assert [(o["id"], o["type"], o["x"], o["y"]) for o in group["objects"]] == [
        (1, "chest", 2 * TILE_SIZE, 1 * TILE_SIZE),
        (2, "key", 0, 0),
    ]
    assert all(o["width"] == o["height"] == TILE_SIZE for o in group["objects"])
    assert out["nextobjectid"] == 3
