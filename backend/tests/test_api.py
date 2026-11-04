import io
import json
import zipfile

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from app import api
from app.api import MAX_MESSAGES
from app.interview import MAX_MESSAGE
from app.llm import TextDelta
from app.main import app
from app.spec import MapSpec, SpecDraft

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


def test_spec_returns_503_when_key_is_rejected(fake_llm):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(401, request=request)
    fake_llm.fail(anthropic.AuthenticationError("invalid x-api-key", response=response, body=None))
    res = client.post("/api/spec", json={"idea": "a small dungeon room"})
    assert res.status_code == 503
    assert "rejected" in res.json()["detail"]


def test_spec_returns_502_after_two_invalid_specs(fake_llm, make_spec):
    # Valid JSON, but min_distance names a kind that isn't in objects.
    bad = make_spec().model_dump(mode="json")
    bad["rules"] = [{"type": "min_distance", "a": "guard", "b": "key", "tiles": 3}]
    fake_llm.reply(json.dumps(bad))
    fake_llm.reply(json.dumps(bad))
    res = client.post("/api/spec", json={"idea": "a small dungeon room"})
    assert res.status_code == 502
    assert len(fake_llm.requests) == 2


def test_spec_returns_502_when_the_connection_drops_mid_reply(fake_llm):
    fake_llm.fail(httpx2.ReadTimeout("timed out"), midway=True)
    res = client.post("/api/spec", json={"idea": "a small dungeon room"})
    assert res.status_code == 502


@pytest.mark.parametrize("idea", ["", "   ", "\n\t", "x" * (MAX_MESSAGE + 1)])
def test_spec_rejects_bad_idea_length(fake_llm, idea):
    res = client.post("/api/spec", json={"idea": idea})
    assert res.status_code == 422
    assert fake_llm.requests == []


def test_spec_strips_whitespace_from_the_idea(fake_llm, make_spec):
    fake_llm.reply(make_spec().model_dump_json())
    res = client.post("/api/spec", json={"idea": "  a small dungeon room\n"})
    assert res.status_code == 200
    (request,) = fake_llm.requests
    assert request["messages"] == [{"role": "user", "content": "a small dungeon room"}]


def test_spec_accepts_idea_at_length_limit(fake_llm, make_spec):
    fake_llm.reply(make_spec().model_dump_json())
    res = client.post("/api/spec", json={"idea": "x" * 2000})
    assert res.status_code == 200


def test_generate_requires_seed(make_spec):
    res = client.post("/api/generate", json={"spec": make_spec().model_dump(mode="json")})
    assert res.status_code == 422


def test_generate_then_validate_roundtrip(make_spec):
    spec = make_spec().model_dump(mode="json")  # No spawn: a map may have none.
    res = client.post("/api/generate", json={"spec": spec, "seed": 1})
    assert res.status_code == 200
    generated = res.json()
    assert generated["violations"] == []
    assert generated["explanations"] == []

    res = client.post("/api/validate", json={"spec": spec, "map": generated["map"]})
    assert res.status_code == 200
    assert res.json()["violations"] == []

    res = client.post("/api/export", json={"spec": spec, "map": generated["map"]})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert 'filename="tilemuse-map.zip"' in res.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        assert sorted(archive.namelist()) == ["tilemuse-map.tmj", "tilesheet.png"]
        tiled = json.loads(archive.read("tilemuse-map.tmj"))
    assert tiled["type"] == "map"
    assert tiled["tilesets"][0]["image"] == "tilesheet.png"


def test_validate_explains_each_violation(make_spec):
    # No interior at all, so the density is infinite. The response must still be valid JSON.
    spec = make_spec(
        objects=[{"kind": "player_spawn", "count": 1}],
        rules=[{"type": "max_density", "max": 0.5}],
    ).model_dump(mode="json")
    tiny = {
        "width": 2,
        "height": 2,
        "tiles": [[1, 1], [1, 1]],
        "objects": [{"kind": "key", "x": 0, "y": 0}],
    }
    res = client.post("/api/validate", json={"spec": spec, "map": tiny})
    assert res.status_code == 200
    body = res.json()
    assert [v["code"] for v in body["violations"]] == [
        "missing_object",
        "door_count",
        "object_on_wall",
        "max_density",
    ]
    assert body["explanations"][0]["text"].startswith("Too few of player spawn")


def test_rejects_map_whose_tiles_do_not_match_its_size(make_spec):
    bad_map = {"width": 3, "height": 2, "tiles": [[0, 0, 0], [0, 0]]}
    spec = make_spec().model_dump(mode="json")
    for route in ("/api/export", "/api/validate"):
        res = client.post(route, json={"spec": spec, "map": bad_map})
        assert res.status_code == 422


def test_rejects_map_with_object_outside_it(make_spec):
    bad_map = {
        "width": 2,
        "height": 1,
        "tiles": [[0, 0]],
        "objects": [{"kind": "chest", "x": 2, "y": 0}],
    }
    spec = make_spec().model_dump(mode="json")
    res = client.post("/api/export", json={"spec": spec, "map": bad_map})
    assert res.status_code == 422


def test_generate_rejects_invalid_spec(make_spec):
    spec = make_spec().model_dump(mode="json")
    spec["objects"] = [{"kind": "dragon", "count": 1}]
    res = client.post("/api/generate", json={"spec": spec, "seed": 1})
    assert res.status_code == 422


IDEA = {"role": "user", "content": "a creepy library where the player sneaks past guards"}
QUESTION = {"field": "mood", "reason": "Mood sets the lighting.", "suggestions": ["creepy", "calm"]}


def interview_events(body):
    res = client.post("/api/interview", json=body)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/jsonl")
    return [json.loads(line) for line in res.text.splitlines()]


def test_interview_streams_text_then_done(fake_llm):
    draft = SpecDraft(theme="abandoned library").model_dump()
    fake_llm.reply("What mood?", submit={"draft": draft, "question": QUESTION})
    text, done = interview_events({"messages": [IDEA]})
    assert text == {"type": "text", "text": "What mood?"}
    assert done["type"] == "done"
    assert (done["message"], done["question"], done["spec"]) == ("What mood?", QUESTION, None)
    assert done["draft"]["theme"] == "abandoned library"


def test_interview_done_carries_the_spec(fake_llm, make_spec):
    spec = make_spec()
    fake_llm.reply("Ready.", submit={"draft": spec.model_dump(), "question": None})
    *_, done = interview_events({"messages": [IDEA], "draft": {"theme": "dungeon"}})
    assert MapSpec.model_validate(done["spec"]) == spec


def test_interview_reports_a_missing_key_as_an_error_event(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    (error,) = interview_events({"messages": [IDEA]})
    assert error["type"] == "error"
    assert "ANTHROPIC_API_KEY is not set" in error["message"]


def test_interview_reports_a_failure_mid_reply_after_the_text(fake_llm):
    fake_llm.fail(httpx2.ReadTimeout("timed out"), midway=True)
    text, error = interview_events({"messages": [IDEA]})
    assert text == {"type": "text", "text": "Hel"}
    assert error == {
        "type": "error",
        "message": "Couldn't get the next question from the LLM. Try again.",
    }


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "assistant", "content": "Hi!"}, IDEA],
        [IDEA, IDEA],
        [IDEA, {"role": "assistant", "content": "What mood?"}],
        [{"role": "user", "content": "   "}],
        [{"role": "user", "content": "x" * (MAX_MESSAGE + 1)}],
        [IDEA, {"role": "assistant", "content": "?"}] * (MAX_MESSAGES // 2 + 1) + [IDEA],
    ],
)
def test_interview_rejects_bad_history(fake_llm, messages):
    res = client.post("/api/interview", json={"messages": messages})
    assert res.status_code == 422
    assert fake_llm.requests == []


def test_interview_accepts_history_at_the_cap(fake_llm):
    fake_llm.reply("What mood?", submit={"draft": SpecDraft().model_dump(), "question": QUESTION})
    messages = [IDEA, {"role": "assistant", "content": "?"}] * (MAX_MESSAGES // 2) + [IDEA]
    assert len(messages) == MAX_MESSAGES
    *_, done = interview_events({"messages": messages})
    assert done["type"] == "done"


def test_interview_reports_an_unexpected_failure_as_an_error_event(monkeypatch, caplog):
    async def broken(messages, draft):
        yield TextDelta("Hel")
        raise RuntimeError("bug")

    monkeypatch.setattr(api, "interview", broken)
    text, error = interview_events({"messages": [IDEA]})
    assert text == {"type": "text", "text": "Hel"}
    assert error == {"type": "error", "message": "Something went wrong. Try again."}
    assert "Interview turn failed" in caplog.text


def test_interview_accepts_a_draft_that_does_not_fit(fake_llm, make_spec):
    # A stale draft from the client mustn't block the session: Claude asks how to fix it.
    crowded = {
        **make_spec(width=4, height=5).model_dump(),
        "objects": [{"kind": "chest", "count": 7}],
    }
    fake_llm.reply("Which should go?", submit={"draft": crowded, "question": QUESTION})
    *_, done = interview_events({"messages": [IDEA], "draft": crowded})
    assert done["type"] == "done"
    assert done["spec"] is None


@pytest.mark.parametrize("draft", [{"width": 200}, {"theme": ""}, {"rules": [{"type": "nope"}]}])
def test_interview_rejects_an_invalid_draft_field(fake_llm, draft):
    res = client.post("/api/interview", json={"messages": [IDEA], "draft": draft})
    assert res.status_code == 422
    assert fake_llm.requests == []
