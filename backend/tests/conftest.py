from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from app import llm
from app.spec import MapSpec


@pytest.fixture
def make_spec() -> Callable[..., MapSpec]:
    """Builds a valid spec; keyword arguments override its fields."""

    def make(**overrides: Any) -> MapSpec:
        return MapSpec(
            **{"theme": "dungeon", "mood": "quiet", "width": 16, "height": 12, **overrides}
        )

    return make


class FakeLLM:
    """Stands in for `anthropic.AsyncAnthropic`. Returns scripted replies in order."""

    def __init__(self) -> None:
        self.client_kwargs: dict[str, Any] = {}
        self.requests: list[dict[str, Any]] = []
        self._replies: list[SimpleNamespace | Exception] = []

    def reply(self, text: str, stop_reason: str = "end_turn") -> None:
        content = [SimpleNamespace(type="text", text=text)]
        self._replies.append(SimpleNamespace(stop_reason=stop_reason, content=content))

    def fail(self, error: Exception) -> None:
        self._replies.append(error)

    def client(self, **kwargs: Any) -> SimpleNamespace:
        self.client_kwargs = kwargs
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=self._create)))

    async def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fails any test that would build a real Claude client, even with a key in backend/.env."""

    def refuse(**kwargs: Any) -> None:
        pytest.fail("Tests must not call the Claude API; use the fake_llm fixture")

    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", refuse)
    llm._client.cache_clear()
    yield
    llm._client.cache_clear()


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", fake.client)
    return fake
