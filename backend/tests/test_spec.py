import anthropic
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
        MaxDensityRule(type="max_density", max=0.2),
        MinDistanceRule(
            type="min_distance", a=ObjectKind.GUARD, b=ObjectKind.PLAYER_SPAWN, tiles=5
        ),
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


@pytest.mark.parametrize("rule", [{"max": 0.2}, {"type": "max-density", "max": 0.2}])
def test_rejects_missing_or_misspelled_rule_type(rule):
    with pytest.raises(ValidationError):
        MapSpec.model_validate({**FULL_SPEC, "rules": [rule]})


@pytest.mark.parametrize(
    ("rule", "tag"), [("MaxDensityRule", "max_density"), ("MinDistanceRule", "min_distance")]
)
def test_schema_sent_to_claude_requires_rule_type(rule, tag):
    schema = anthropic.transform_schema(MapSpec)["$defs"][rule]
    assert "type" in schema["required"]
    assert schema["properties"]["type"]["enum"] == [tag]


def test_rejects_unknown_object_kind():
    with pytest.raises(ValidationError):
        MapSpec.model_validate({**FULL_SPEC, "objects": [{"kind": "dragon", "count": 1}]})


def test_rejects_duplicate_object_kinds():
    objects = [{"kind": "chest", "count": 1}, {"kind": "chest", "count": 2}]
    with pytest.raises(ValidationError, match="once in objects: chest"):
        MapSpec.model_validate({**FULL_SPEC, "objects": objects, "rules": []})


def test_rejects_too_many_objects_for_room(make_spec):
    # A 4x4 room has 2x2 = 4 interior tiles.
    make_spec(width=4, height=4, objects=[{"kind": "chest", "count": 4}])
    with pytest.raises(ValidationError, match="do not fit"):
        make_spec(width=4, height=4, objects=[{"kind": "chest", "count": 5}])


def test_rejects_min_distance_with_missing_kind():
    rules = [{"type": "min_distance", "a": "guard", "b": "key", "tiles": 3}]
    with pytest.raises(ValidationError, match="not in objects: key"):
        MapSpec.model_validate({**FULL_SPEC, "rules": rules})


def test_rejects_density_below_required_objects(make_spec):
    # 6x6 room: 16 interior tiles, so 4 objects need max >= 0.25.
    objects = [{"kind": "cover", "count": 4}]
    make_spec(width=6, height=6, objects=objects, rules=[{"type": "max_density", "max": 0.25}])
    with pytest.raises(ValidationError, match="max_density"):
        make_spec(width=6, height=6, objects=objects, rules=[{"type": "max_density", "max": 0.2}])


def test_density_boundary_is_not_rejected_by_rounding(make_spec):
    # 0.29 * 100 is 28.999999999999996 in floating point; 29 / 100 <= 0.29 must still pass.
    objects = [{"kind": "cover", "count": 29}]
    make_spec(width=12, height=12, objects=objects, rules=[{"type": "max_density", "max": 0.29}])


def test_rejects_same_kind_min_distance_with_one_object(make_spec):
    rule = {"type": "min_distance", "a": "guard", "b": "guard", "tiles": 3}
    make_spec(objects=[{"kind": "guard", "count": 2}], rules=[rule])
    with pytest.raises(ValidationError, match="at least 2"):
        make_spec(objects=[{"kind": "guard", "count": 1}], rules=[rule])


def test_rejects_min_distance_beyond_room(make_spec):
    # 6x6 room: interior corners are (1, 1) and (4, 4), 6 tiles apart.
    objects = [{"kind": "guard", "count": 2}]
    rule = {"type": "min_distance", "a": "guard", "b": "guard"}
    make_spec(width=6, height=6, objects=objects, rules=[{**rule, "tiles": 6}])
    with pytest.raises(ValidationError, match="exceeds"):
        make_spec(width=6, height=6, objects=objects, rules=[{**rule, "tiles": 7}])


@pytest.mark.parametrize(
    "rules",
    [
        [{"type": "max_density", "max": 0.5}, {"type": "max_density", "max": 0.4}],
        [
            {"type": "min_distance", "a": "guard", "b": "chest", "tiles": 2},
            {"type": "min_distance", "a": "chest", "b": "guard", "tiles": 3},
        ],
    ],
)
def test_rejects_repeated_rules(make_spec, rules):
    objects = [{"kind": "guard", "count": 1}, {"kind": "chest", "count": 1}]
    with pytest.raises(ValidationError, match="may not repeat"):
        make_spec(objects=objects, rules=rules)
