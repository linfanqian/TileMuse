from random import Random

from app.generator import generate
from app.models import GameMap, Tile
from app.spec import MapSpec


def door_cells(game_map: GameMap) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile == Tile.DOOR
    ]


def test_same_seed_identical_map():
    spec = MapSpec()
    assert generate(spec, Random(42)) == generate(spec, Random(42))
    doors = {tuple(door_cells(generate(spec, Random(seed)))) for seed in range(10)}
    assert len(doors) > 1


def test_map_matches_spec_size():
    spec = MapSpec(width=10, height=6)
    game_map = generate(spec, Random(0))
    assert (game_map.width, game_map.height) == (10, 6)
    assert len(game_map.tiles) == 6
    assert all(len(row) == 10 for row in game_map.tiles)
