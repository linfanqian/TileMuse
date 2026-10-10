from random import Random

from app.generator import generate
from app.spec import MapSpec
from app.tiled import to_tiled


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
