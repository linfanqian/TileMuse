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


def test_fixed_seed_golden_map():
    # Golden output: catches changes across processes, machines and Python versions that
    # comparing two runs in one process cannot. Update it only on an intended generator change.
    game_map = generate(MapSpec(width=5, height=4), Random(42))
    assert game_map.tiles == [
        [1, 1, 1, 2, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1],
    ]
    assert game_map.objects == []


def test_map_matches_spec_size():
    spec = MapSpec(width=10, height=6)
    game_map = generate(spec, Random(0))
    assert (game_map.width, game_map.height) == (10, 6)
    assert len(game_map.tiles) == 6
    assert all(len(row) == 10 for row in game_map.tiles)
