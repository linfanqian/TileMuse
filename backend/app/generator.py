"""Spec -> map. Deterministic: all randomness comes from the rng argument."""

from random import Random

from app.models import GameMap, Tile
from app.spec import MapSpec


def generate(spec: MapSpec, rng: Random) -> GameMap:
    # Stub: a walled room with one door on the top wall.
    w, h = spec.width, spec.height
    tiles = [
        [Tile.WALL if x in (0, w - 1) or y in (0, h - 1) else Tile.FLOOR for x in range(w)]
        for y in range(h)
    ]
    tiles[0][rng.randrange(1, w - 1)] = Tile.DOOR
    return GameMap(width=w, height=h, tiles=tiles)
