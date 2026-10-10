from fastapi.testclient import TestClient

from app.main import app
from app.spec import MapSpec

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_spec_returns_valid_spec():
    res = client.post("/api/spec", json={"idea": "a small dungeon room"})
    assert res.status_code == 200
    MapSpec.model_validate(res.json())


def test_generate_requires_seed():
    res = client.post("/api/generate", json={"spec": MapSpec().model_dump()})
    assert res.status_code == 422


def test_generate_then_validate_roundtrip():
    spec = MapSpec().model_dump()
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


def test_rejects_map_whose_tiles_do_not_match_its_size():
    bad_map = {"width": 3, "height": 2, "tiles": [[0, 0, 0], [0, 0]]}
    res = client.post("/api/export", json={"map": bad_map})
    assert res.status_code == 422
    res = client.post("/api/validate", json={"spec": MapSpec().model_dump(), "map": bad_map})
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


def test_rejects_map_larger_than_max_size():
    huge = {"width": 129, "height": 1, "tiles": [[0] * 129]}
    res = client.post("/api/export", json={"map": huge})
    assert res.status_code == 422


def test_validate_rejects_map_that_does_not_match_spec():
    spec = MapSpec(width=4, height=4).model_dump()
    small_map = {"width": 2, "height": 1, "tiles": [[0, 0]]}
    res = client.post("/api/validate", json={"spec": spec, "map": small_map})
    assert res.status_code == 422
