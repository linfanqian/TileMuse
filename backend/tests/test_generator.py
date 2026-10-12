from random import Random

from app.generator import generate


def test_same_seed_identical_map(make_spec):
    spec = make_spec()
    assert generate(spec, Random(42)) == generate(spec, Random(42))


def test_fixed_seed_golden_map(make_spec):
    # Golden output: catches changes across processes, machines and Python versions that
    # comparing two runs in one process cannot. Update it only on an intended generator change.
    game_map = generate(make_spec(width=5, height=4), Random(42))
    assert game_map.tiles == [
        [1, 1, 1, 2, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1],
    ]
    assert game_map.objects == []
