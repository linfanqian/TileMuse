import pytest
from pydantic import ValidationError

from app.spec import MapSpec, MaxDensityRule, MinDistanceRule, ObjectKind

FULL_SPEC = {
    "theme": "abandoned library",
    "mood": "creepy",
    "width": 20,
    "height": 14,
    "doors": 2,
    "objects": [
        {"kind": "player_spawn", "count": 1},
        {"kind": "guard", "count": 2},
        {"kind": "cover", "count": 6},
        {"kind": "exit", "count": 1},
    ],
    "rules": [
        {"type": "max_density", "max": 0.2},
        {"type": "min_distance", "a": "guard", "b": "player_spawn", "tiles": 5},
    ],
}


def test_valid_spec_roundtrips_json():
    spec = MapSpec.model_validate(FULL_SPEC)
    assert MapSpec.model_validate_json(spec.model_dump_json()) == spec


def test_rules_parse_by_type():
    spec = MapSpec.model_validate(FULL_SPEC)
    assert spec.rules == [
        MaxDensityRule(max=0.2),
        MinDistanceRule(a=ObjectKind.GUARD, b=ObjectKind.PLAYER_SPAWN, tiles=5),
    ]


def test_optional_fields_default_to_empty(make_spec):
    spec = make_spec()
    assert (spec.doors, spec.objects, spec.rules) == (1, [], [])


@pytest.mark.parametrize("field", ["theme", "mood", "width", "height"])
def test_requires_core_fields(field):
    data = {k: v for k, v in FULL_SPEC.items() if k != field}
    with pytest.raises(ValidationError):
        MapSpec.model_validate(data)


def test_rejects_unknown_rule_type():
    with pytest.raises(ValidationError):
        MapSpec.model_validate({**FULL_SPEC, "rules": [{"type": "no_such_rule"}]})


def test_rejects_unknown_object_kind():
    with pytest.raises(ValidationError):
        MapSpec.model_validate({**FULL_SPEC, "objects": [{"kind": "dragon", "count": 1}]})


def test_rejects_duplicate_object_kinds():
    objects = [{"kind": "chest", "count": 1}, {"kind": "chest", "count": 2}]
    with pytest.raises(ValidationError, match="once"):
        MapSpec.model_validate({**FULL_SPEC, "objects": objects, "rules": []})


def test_rejects_too_many_objects_for_room(make_spec):
    # A 4x4 room has 2x2 = 4 interior tiles.
    make_spec(width=4, height=4, objects=[{"kind": "chest", "count": 4}])
    with pytest.raises(ValidationError, match="do not fit"):
        make_spec(width=4, height=4, objects=[{"kind": "chest", "count": 5}])


def test_rejects_min_distance_with_missing_kind():
    rules = [{"type": "min_distance", "a": "guard", "b": "key", "tiles": 3}]
    with pytest.raises(ValidationError, match="not in objects"):
        MapSpec.model_validate({**FULL_SPEC, "rules": rules})
