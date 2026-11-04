"""Map -> Tiled JSON export (https://doc.mapeditor.org/en/stable/reference/json-map-format/).

The map is drawn with its kit's tiles (see drawing.py), on three layers: floor, walls, and
objects. The tileset points to `tilesheet.png`, which must sit next to the exported file.
"""

from typing import Any

from app.drawing import Layer, draw
from app.models import GameMap
from app.tileset import load_tileset

FIRST_GID = 1  # Tiled's gid for sheet id 0. 0 means an empty cell.


def to_tiled(game_map: GameMap, kit: str) -> dict[str, Any]:
    catalog = load_tileset().catalog
    size = catalog.tile_size
    drawing = draw(game_map, kit)

    def tile_layer(layer_id: int, name: str, layer: Layer) -> dict[str, Any]:
        return {
            "id": layer_id,
            "name": name,
            "type": "tilelayer",
            "x": 0,
            "y": 0,
            "width": drawing.width,
            "height": drawing.height,
            "opacity": 1,
            "visible": True,
            "data": [0 if tile is None else FIRST_GID + tile for row in layer for tile in row],
        }

    objects = []
    for i, obj in enumerate(drawing.objects, start=1):
        shape: dict[str, Any] = {"x": obj.x * size, "y": obj.y * size}
        if obj.tile is not None:
            # A tile object's y is its bottom edge.
            shape = {"gid": FIRST_GID + obj.tile, "x": obj.x * size, "y": (obj.y + 1) * size}
        objects.append(
            {
                "id": i,
                "name": obj.kind,
                "type": obj.kind,
                **shape,
                "width": size,
                "height": size,
                "rotation": 0,
                "visible": True,
            }
        )

    return {
        "type": "map",
        "version": "1.10",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "infinite": False,
        "width": drawing.width,
        "height": drawing.height,
        "tilewidth": size,
        "tileheight": size,
        "nextlayerid": 4,
        "nextobjectid": len(objects) + 1,
        "layers": [
            tile_layer(1, "floor", drawing.floor),
            tile_layer(2, "walls", drawing.walls),
            {
                "id": 3,
                "name": "objects",
                "type": "objectgroup",
                "x": 0,
                "y": 0,
                "opacity": 1,
                "visible": True,
                "draworder": "topdown",
                "objects": objects,
            },
        ],
        "tilesets": [
            {
                "firstgid": FIRST_GID,
                "name": "tilemuse",
                "image": catalog.image,
                "imagewidth": catalog.columns * size,
                "imageheight": catalog.rows * size,
                "tilewidth": size,
                "tileheight": size,
                "tilecount": catalog.columns * catalog.rows,
                "columns": catalog.columns,
                "margin": 0,
                "spacing": 0,
            }
        ],
    }
