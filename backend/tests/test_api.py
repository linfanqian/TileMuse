import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.spec import MapSpec

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_spec_returns_valid_spec(fake_llm, make_spec):
    fake_llm.reply(make_spec().model_dump_json())
    res = client.post("/api/spec", json={"idea": "a small dungeon room"})
    assert res.status_code == 200
    assert MapSpec.model_validate(res.json()) == make_spec()


def test_spec_returns_503_without_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    res = client.post("/api/spec", json={"idea": "a small dungeon room"})
    assert res.status_code == 503
    assert "ANTHROPIC_API_KEY is not set" in res.json()["detail"]


def test_spec_returns_502_after_two_invalid_specs(fake_llm, make_spec):
    # Valid JSON, but min_distance names a kind that isn't in objects.
    bad = make_spec().model_dump(mode="json")
    bad["rules"] = [{"type": "min_distance", "a": "guard", "b": "key", "tiles": 3}]
    fake_llm.reply(json.dumps(bad))
    fake_llm.reply(json.dumps(bad))
    res = client.post("/api/spec", json={"idea": "a small dungeon room"})
    assert res.status_code == 502
    assert len(fake_llm.requests) == 2


@pytest.mark.parametrize("idea", ["", "x" * 2001])
def test_spec_rejects_bad_idea_length(fake_llm, idea):
    res = client.post("/api/spec", json={"idea": idea})
    assert res.status_code == 422
    assert fake_llm.requests == []


def test_spec_accepts_idea_at_length_limit(fake_llm, make_spec):
    fake_llm.reply(make_spec().model_dump_json())
    res = client.post("/api/spec", json={"idea": "x" * 2000})
    assert res.status_code == 200


def test_generate_requires_seed(make_spec):
    res = client.post("/api/generate", json={"spec": make_spec().model_dump(mode="json")})
    assert res.status_code == 422


def test_generate_then_validate_roundtrip(make_spec):
    spec = make_spec().model_dump(mode="json")
    res = client.post("/api/generate", json={"spec": spec, "seed": 1})
    assert res.status_code == 200
    generated = res.json()
    assert generated["violations"] == []
    assert generated["explanations"] == []

    res = client.post("/api/validate", json={"spec": spec, "map": generated["map"]})
    assert res.status_code == 200
    assert res.json()["violations"] == []

    res = client.post("/api/export", json={"map": generated["map"]})
    assert res.status_code == 200
    assert res.json()["type"] == "map"


def test_rejects_map_whose_tiles_do_not_match_its_size(make_spec):
    bad_map = {"width": 3, "height": 2, "tiles": [[0, 0, 0], [0, 0]]}
    res = client.post("/api/export", json={"map": bad_map})
    assert res.status_code == 422
    res = client.post(
        "/api/validate", json={"spec": make_spec().model_dump(mode="json"), "map": bad_map}
    )
    assert res.status_code == 422


def test_rejects_map_with_object_outside_it():
    bad_map = {
        "width": 2,
        "height": 1,
        "tiles": [[0, 0]],
        "objects": [{"kind": "chest", "x": 2, "y": 0}],
    }
    res = client.post("/api/export", json={"map": bad_map})
    assert res.status_code == 422


def test_generate_rejects_invalid_spec(make_spec):
    spec = make_spec().model_dump(mode="json")
    spec["objects"] = [{"kind": "dragon", "count": 1}]
    res = client.post("/api/generate", json={"spec": spec, "seed": 1})
    assert res.status_code == 422
