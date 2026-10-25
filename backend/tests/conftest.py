import inspect
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from anthropic.resources.beta.messages import AsyncMessages

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


class FakeStream:
    """Stands in for the SDK's message stream: events from the reply's blocks, then the reply."""

    def __init__(self, reply: SimpleNamespace | Exception) -> None:
        self._reply = reply

    async def __aenter__(self) -> "FakeStream":
        if isinstance(self._reply, Exception):
            raise self._reply
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        for block in self._reply.content:
            yield SimpleNamespace(type="content_block_start", content_block=block)
            if block.type == "text":
                yield SimpleNamespace(type="text", text=block.text)
        self._raise_midway()

    async def get_final_message(self) -> SimpleNamespace:
        self._raise_midway()
        return self._reply

    def _raise_midway(self) -> None:
        if (error := getattr(self._reply, "error", None)) is not None:
            raise error


class FakeLLM:
    """Stands in for `anthropic.AsyncAnthropic`. Returns scripted replies in order."""

    def __init__(self) -> None:
        self.client_kwargs: dict[str, Any] = {}
        self.requests: list[dict[str, Any]] = []
        self._replies: list[SimpleNamespace | Exception] = []

    def reply(
        self,
        text: str = "",
        *,
        submit: dict[str, Any] | list[dict[str, Any]] | None = None,
        before_fallback: Sequence[SimpleNamespace] = (),
        stop_reason: str | None = None,
    ) -> None:
        """Scripts one reply: declined blocks and a `fallback` block, text, submit calls."""
        content = [*before_fallback, SimpleNamespace(type="fallback")] if before_fallback else []
        if text:
            content.append(SimpleNamespace(type="text", text=text))
        submits = [submit] if isinstance(submit, dict) else submit or []
        for n, args in enumerate(submits):
            call_id = f"toolu_{len(self._replies)}_{n}"
            call = SimpleNamespace(type="tool_use", id=call_id, name="submit", input=args)
            content.append(call)
        if stop_reason is None:
            stop_reason = "tool_use" if submit is not None else "end_turn"
        self._replies.append(SimpleNamespace(stop_reason=stop_reason, content=content))

    def fail(self, error: Exception, *, midway: bool = False) -> None:
        """Scripts a failure on connecting, or, with `midway`, after some text has streamed."""
        if midway:
            text = SimpleNamespace(type="text", text="Hel")
            self._replies.append(SimpleNamespace(content=[text], error=error))
        else:
            self._replies.append(error)

    def client(self, **kwargs: Any) -> SimpleNamespace:
        self.client_kwargs = kwargs
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=self._stream)))

    def _stream(self, **kwargs: Any) -> FakeStream:
        # Fails on a parameter the real SDK method doesn't take.
        inspect.signature(AsyncMessages.stream).bind(None, **kwargs)
        self.requests.append(kwargs)
        return FakeStream(self._replies.pop(0))


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
