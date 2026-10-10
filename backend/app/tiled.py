"""Map -> Tiled JSON export (https://doc.mapeditor.org/en/stable/reference/json-map-format/)."""

from typing import Any

from app.models import GameMap, Tile

TILE_SIZE = 32
FIRST_GID = 1


def to_tiled(game_map: GameMap) -> dict[str, Any]:
    return {
        "type": "map",
        "version": "1.10",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "infinite": False,
        "width": game_map.width,
        "height": game_map.height,
        "tilewidth": TILE_SIZE,
        "tileheight": TILE_SIZE,
        "nextlayerid": 3,
        "nextobjectid": len(game_map.objects) + 1,
        "layers": [
            {
                "id": 1,
                "name": "tiles",
                "type": "tilelayer",
                "x": 0,
                "y": 0,
                "width": game_map.width,
                "height": game_map.height,
                "opacity": 1,
                "visible": True,
                "data": [FIRST_GID + tile for row in game_map.tiles for tile in row],
            },
            {
                "id": 2,
                "name": "objects",
                "type": "objectgroup",
                "x": 0,
                "y": 0,
                "opacity": 1,
                "visible": True,
                "draworder": "topdown",
                "objects": [
                    {
                        "id": i,
                        "name": obj.kind,
                        "type": obj.kind,
                        "x": obj.x * TILE_SIZE,
                        "y": obj.y * TILE_SIZE,
                        "width": TILE_SIZE,
                        "height": TILE_SIZE,
                        "rotation": 0,
                        "visible": True,
                    }
                    for i, obj in enumerate(game_map.objects, start=1)
                ],
            },
        ],
        "tilesets": [
            {
                "firstgid": FIRST_GID,
                "name": "tiles",
                "tilewidth": TILE_SIZE,
                "tileheight": TILE_SIZE,
                "tilecount": len(Tile),
                "columns": len(Tile),
                "tiles": [{"id": t.value, "type": t.name.lower()} for t in Tile],
            }
        ],
    }
