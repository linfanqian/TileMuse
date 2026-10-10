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
    generated = client.post("/api/generate", json={"spec": spec, "seed": 1}).json()
    assert isinstance(generated["violations"], list)
    assert isinstance(generated["explanations"], list)

    res = client.post("/api/validate", json={"spec": spec, "map": generated["map"]})
    assert res.status_code == 200
    assert isinstance(res.json()["violations"], list)

    res = client.post("/api/export", json={"map": generated["map"]})
    assert res.status_code == 200
    assert res.json()["type"] == "map"
