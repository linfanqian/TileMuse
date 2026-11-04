"""Map -> Tiled JSON export (https://doc.mapeditor.org/en/stable/reference/json-map-format/).

The map is drawn with its kit's tiles (see drawing.py), on three layers: floor, walls, and
objects. A fourth layer, doors, marks each door that leads out with a `door` object on its
cell, so a game can find the exits. Tiles that block movement, by the catalog, carry a
`blocking` property, so a game can set up collision. The tileset points to `tilesheet.png`,
which must sit next to the exported file.

Checked with Tiled 1.12.2 for every kit: `tmxrasterizer` draws the export as expected, and
`tiled --export-map json` re-saves it with the same layers, tiles, and object types, and keeps
the door objects and the `blocking` properties.
"""

from typing import Any

from app.drawing import Layer, draw
from app.models import GameMap
from app.tileset import Catalog, load_tileset
from app.walkable import exits

FIRST_GID = 1  # Tiled's gid for sheet id 0. 0 means an empty cell.


def to_tiled(game_map: GameMap, kit: str) -> dict[str, Any]:
    catalog = load_tileset().catalog
    size = catalog.tile_size
    drawing = draw(game_map, kit)

    def plain_object(object_id: int, kind: str, x: int, y: int) -> dict[str, Any]:
        return {
            "id": object_id,
            "name": kind,
            "type": kind,
            "x": x * size,
            "y": y * size,
            "width": size,
            "height": size,
            "rotation": 0,
            "visible": True,
        }

    def object_layer(layer_id: int, name: str, objects: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "id": layer_id,
            "name": name,
            "type": "objectgroup",
            "x": 0,
            "y": 0,
            "opacity": 1,
            "visible": True,
            "draworder": "topdown",
            "objects": objects,
        }

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
        placed = plain_object(i, obj.kind, obj.x, obj.y)
        if obj.tile is not None:
            # A tile object's y is its bottom edge.
            placed |= {"gid": FIRST_GID + obj.tile, "y": (obj.y + 1) * size}
        objects.append(placed)
    # Object ids are unique across the whole map, so the doors count on from the objects.
    doors = [
        plain_object(i, "door", x, y + drawing.shift)
        for i, (x, y) in enumerate(exits(game_map.tiles), start=len(objects) + 1)
    ]

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
        "nextlayerid": 5,
        "nextobjectid": len(objects) + len(doors) + 1,
        "layers": [
            tile_layer(1, "floor", drawing.floor),
            tile_layer(2, "walls", drawing.walls),
            object_layer(3, "objects", objects),
            object_layer(4, "doors", doors),
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
                "tiles": [
                    {
                        "id": tile,
                        "properties": [{"name": "blocking", "type": "bool", "value": True}],
                    }
                    for tile in _blocking_tiles(catalog)
                ],
            }
        ],
    }


def _blocking_tiles(catalog: Catalog) -> list[int]:
    """Sheet ids that block movement. Entries share tiles: an opening's end is also a wall's
    corner. So a tile blocks if any entry that uses it blocks. No floor tile, door middle, or
    closed door shares a tile with a blocking entry, so none of them blocks. The per-kit export
    test checks this."""
    return sorted(
        {tile for entry in catalog.entries if entry.blocking for tile in entry.parts or [entry.id]}
    )
