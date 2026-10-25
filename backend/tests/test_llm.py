import asyncio
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import BaseModel, Field, ValidationError

from app import llm

SYSTEM = "Answer with one word."
MESSAGES = [{"role": "user", "content": "Say hello."}]
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class Answer(BaseModel):
    word: str = Field(min_length=3)


def complete():
    return asyncio.run(llm.complete(SYSTEM, MESSAGES, output=Answer))


def status_error(cls, status, message):
    response = httpx2.Response(status, request=REQUEST, headers={"request-id": "req_123"})
    return cls(message, response=response, body=None)


def test_client_uses_timeout_and_one_retry(fake_llm):
    fake_llm.reply('{"word": "hello"}')
    complete()
    assert fake_llm.client_kwargs == {"api_key": "test-key", "timeout": 60.0, "max_retries": 1}


def test_complete_returns_validated_output(fake_llm):
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    (request,) = fake_llm.requests
    assert request["model"] == llm.MODEL
    assert (request["system"], request["messages"]) == (SYSTEM, MESSAGES)
    assert request["output_config"] == {
        "format": {"type": "json_schema", "schema": anthropic.transform_schema(Answer)}
    }
    assert request["fallbacks"] == "default"


def test_complete_retries_once_with_validation_feedback(fake_llm):
    fake_llm.reply('{"word": "hi"}')
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    first, second = fake_llm.requests
    assert first["messages"] == MESSAGES
    *history, assistant, feedback = second["messages"]
    assert history == MESSAGES
    assert assistant["role"] == "assistant"
    assert [block.text for block in assistant["content"]] == ['{"word": "hi"}']
    assert feedback["role"] == "user"
    assert "at least 3 characters" in feedback["content"]


def test_complete_fails_after_second_invalid_reply(fake_llm, caplog):
    fake_llm.reply('{"word": "hi"}')
    fake_llm.reply("not json")
    with pytest.raises(llm.LLMError) as excinfo:
        complete()
    assert isinstance(excinfo.value.__cause__, ValidationError)
    assert len(fake_llm.requests) == 2
    assert "Answer output failed validation twice" in caplog.text


def test_complete_joins_text_across_a_fallback(fake_llm):
    # On a stream, the fallback model continues the declined model's partial text.
    declined = SimpleNamespace(type="text", text='{"word": "he')
    fake_llm.reply('llo"}', before_fallback=[declined])
    assert complete() == Answer(word="hello")
    assert len(fake_llm.requests) == 1


def test_retry_echo_drops_blocks_before_fallback(fake_llm):
    declined = [SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text='{"word": ')]
    fake_llm.reply('"hi"}', before_fallback=declined)
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    *_, assistant, _feedback = fake_llm.requests[1]["messages"]
    assert [block.type for block in assistant["content"]] == ["text", "fallback", "text"]


def test_retry_echo_keeps_every_fallback_block(fake_llm):
    # Two hops: the API validates thinking around each fallback block by its position.
    declined = [
        SimpleNamespace(type="text", text='{"word": '),
        SimpleNamespace(type="fallback"),
        SimpleNamespace(type="thinking"),
    ]
    fake_llm.reply('"hi"}', before_fallback=declined)
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    *_, assistant, _feedback = fake_llm.requests[1]["messages"]
    assert [block.type for block in assistant["content"]] == [
        "text",
        "fallback",
        "fallback",
        "text",
    ]


def test_config_errors_are_not_reported_as_llm_errors(monkeypatch):
    # A ValueError from settings is a local bug, not an unreadable reply.
    def broken_settings():
        raise ValueError("bad config")

    monkeypatch.setattr(llm, "_Settings", broken_settings)
    with pytest.raises(ValueError, match="bad config"):
        complete()


def test_complete_text_returns_text(fake_llm):
    fake_llm.reply("Hello.")
    assert asyncio.run(llm.complete_text(SYSTEM, MESSAGES)) == "Hello."
    (request,) = fake_llm.requests
    assert "output_config" not in request


def test_without_key_raises_unavailable(monkeypatch):
    # The environment overrides backend/.env, so this holds even with a local key.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(llm.LLMUnavailable):
        complete()


@pytest.mark.parametrize(
    "error",
    [anthropic.APIConnectionError(request=REQUEST), anthropic.APITimeoutError(REQUEST)],
)
def test_wraps_api_errors(fake_llm, error):
    fake_llm.fail(error)
    with pytest.raises(llm.LLMError) as excinfo:
        complete()
    assert excinfo.value.__cause__ is error
    assert len(fake_llm.requests) == 1


MIDWAY_ERRORS = [
    httpx2.ReadTimeout("timed out"),
    httpx2.RemoteProtocolError("peer closed"),
    httpx2.DecodingError("bad gzip chunk"),
]


@pytest.mark.parametrize("error", MIDWAY_ERRORS)
def test_wraps_network_errors_mid_reply(fake_llm, caplog, error):
    # The SDK wraps network errors only until the reply starts streaming.
    fake_llm.fail(error, midway=True)
    with pytest.raises(llm.LLMError) as excinfo:
        complete()
    assert excinfo.value.__cause__ is error
    assert len(fake_llm.requests) == 1
    assert type(error).__name__ in caplog.text


def test_logs_api_errors_without_the_key(fake_llm, caplog):
    fake_llm.fail(status_error(anthropic.BadRequestError, 400, "fallbacks: unknown field"))
    with pytest.raises(llm.LLMError):
        complete()
    for part in ("BadRequestError", "status 400", "req_123", "fallbacks: unknown field"):
        assert part in caplog.text
    assert "test-key" not in caplog.text


def test_rejected_key_raises_unavailable(fake_llm, caplog):
    error = status_error(anthropic.AuthenticationError, 401, "invalid x-api-key")
    fake_llm.fail(error)
    with pytest.raises(llm.LLMUnavailable, match="rejected") as excinfo:
        complete()
    assert excinfo.value.__cause__ is error
    assert "AuthenticationError" in caplog.text


def test_fixed_key_is_used_after_a_rejected_one(fake_llm, monkeypatch):
    fake_llm.fail(status_error(anthropic.AuthenticationError, 401, "invalid x-api-key"))
    with pytest.raises(llm.LLMUnavailable):
        complete()
    # The user fixes backend/.env without restarting the server.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixed-key")
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    assert fake_llm.client_kwargs["api_key"] == "fixed-key"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens", "model_context_window_exceeded"])
def test_rejects_refusal_and_truncation(fake_llm, caplog, stop_reason):
    fake_llm.reply('{"word": "hello"}', stop_reason=stop_reason)
    with pytest.raises(llm.LLMError, match=stop_reason):
        complete()
    assert len(fake_llm.requests) == 1
    assert f"stop_reason={stop_reason}" in caplog.text


def stream_events():
    async def collect():
        return [event async for event in llm.stream(SYSTEM, MESSAGES, output=Answer)]

    return asyncio.run(collect())


def test_stream_yields_text_then_done(fake_llm):
    fake_llm.reply("Hello there.", submit={"word": "hello"})
    events = stream_events()
    assert events == [llm.TextDelta("Hello there."), llm.Done(Answer(word="hello"), "Hello there.")]
    (request,) = fake_llm.requests
    (tool,) = request["tools"]
    assert tool["name"] == "submit"
    assert tool["strict"] is True
    assert tool["input_schema"] == anthropic.transform_schema(Answer)
    assert request["system"].startswith(SYSTEM)


def test_stream_continues_across_a_fallback(fake_llm):
    # Nothing already streamed is invalidated; the fallback model continues the text.
    declined = SimpleNamespace(type="text", text="Hel")
    fake_llm.reply("lo.", submit={"word": "hello"}, before_fallback=[declined])
    events = stream_events()
    assert events == [
        llm.TextDelta("Hel"),
        llm.TextDelta("lo."),
        llm.Done(Answer(word="hello"), "Hello."),
    ]


def test_stream_ignores_a_submit_before_a_fallback(fake_llm):
    declined = SimpleNamespace(type="tool_use", id="toolu_x", name="submit", input={"word": "hey"})
    fake_llm.reply("Hello.", before_fallback=[declined])
    fake_llm.reply(submit={"word": "hello"})
    assert stream_events()[-1] == llm.Done(Answer(word="hello"), "Hello.")
    *_, assistant, feedback = fake_llm.requests[1]["messages"]
    assert [block.type for block in assistant["content"]] == ["fallback", "text"]
    assert "submit" in feedback["content"]


def test_stream_retries_invalid_submission_with_tool_result(fake_llm):
    fake_llm.reply("Hello.", submit={"word": "hi"})
    fake_llm.reply("Not shown.", submit={"word": "hello"})
    events = stream_events()
    assert events == [llm.TextDelta("Hello."), llm.Done(Answer(word="hello"), "Hello.")]
    first, second = fake_llm.requests
    *history, assistant, feedback = second["messages"]
    assert history == MESSAGES
    assert [block.type for block in assistant["content"]] == ["text", "tool_use"]
    (result,) = feedback["content"]
    call_id = assistant["content"][1].id
    assert result["type"] == "tool_result"
    assert (result["tool_use_id"], result["is_error"]) == (call_id, True)
    assert "at least 3 characters" in result["content"]
    assert second["tools"] == first["tools"]


def test_stream_uses_the_first_valid_submission(fake_llm):
    fake_llm.reply("Hello.", submit=[{"word": "hi"}, {"word": "hello"}])
    assert stream_events()[-1] == llm.Done(Answer(word="hello"), "Hello.")
    assert len(fake_llm.requests) == 1


def test_stream_asks_for_submit_when_missing(fake_llm):
    fake_llm.reply("Hello.")
    fake_llm.reply(submit={"word": "hello"})
    events = stream_events()
    assert events[-1] == llm.Done(Answer(word="hello"), "Hello.")
    feedback = fake_llm.requests[1]["messages"][-1]
    assert feedback["role"] == "user"
    assert "submit" in feedback["content"]


def test_stream_fails_after_second_invalid_submission(fake_llm, caplog):
    fake_llm.reply("Hello.", submit={"word": "hi"})
    fake_llm.reply(submit={"word": "no"})
    with pytest.raises(llm.LLMError):
        stream_events()
    assert len(fake_llm.requests) == 2
    assert "Answer submission failed validation twice" in caplog.text


def test_stream_wraps_api_errors(fake_llm):
    error = anthropic.APIConnectionError(request=REQUEST)
    fake_llm.fail(error)
    with pytest.raises(llm.LLMError) as excinfo:
        stream_events()
    assert excinfo.value.__cause__ is error


@pytest.mark.parametrize("error", MIDWAY_ERRORS)
def test_stream_wraps_network_errors_mid_reply(fake_llm, error):
    fake_llm.fail(error, midway=True)
    events = []

    async def collect():
        async for event in llm.stream(SYSTEM, MESSAGES, output=Answer):
            events.append(event)

    with pytest.raises(llm.LLMError) as excinfo:
        asyncio.run(collect())
    assert excinfo.value.__cause__ is error
    assert events == [llm.TextDelta("Hel")]


def test_stream_wraps_unparsable_tool_input(fake_llm, caplog):
    error = ValueError("Unable to parse tool parameter JSON from model.")
    fake_llm.fail(error, midway=True)
    with pytest.raises(llm.LLMError) as excinfo:
        stream_events()
    assert excinfo.value.__cause__ is error
    assert "Unable to parse tool parameter JSON" in caplog.text


def test_stream_rejects_refusal(fake_llm):
    fake_llm.reply("Hel", stop_reason="refusal")
    with pytest.raises(llm.LLMError, match="refusal"):
        stream_events()
    assert len(fake_llm.requests) == 1


def test_complete_retry_skips_an_empty_reply(fake_llm):
    # The API rejects an assistant turn with no content.
    fake_llm.reply("")
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    *history, feedback = fake_llm.requests[1]["messages"]
    assert history == MESSAGES
    assert feedback["role"] == "user"


def test_retry_skips_a_reply_with_only_a_fallback_left(fake_llm):
    # A fallback block isn't rendered into the prompt, so the turn would be empty.
    fake_llm.reply(before_fallback=[SimpleNamespace(type="thinking")])
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    *history, feedback = fake_llm.requests[1]["messages"]
    assert history == MESSAGES
    assert feedback["role"] == "user"


@pytest.mark.parametrize("blank", ["", " \n"])
def test_retry_echo_drops_blank_text(fake_llm, blank):
    # The API rejects whitespace-only text blocks.
    fake_llm.reply('{"word": "hi"}', before_fallback=[SimpleNamespace(type="text", text=blank)])
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    *_, assistant, _feedback = fake_llm.requests[1]["messages"]
    assert [block.type for block in assistant["content"]] == ["fallback", "text"]


def test_complete_retry_skips_a_blank_reply(fake_llm):
    fake_llm.reply("\n")
    fake_llm.reply('{"word": "hello"}')
    assert complete() == Answer(word="hello")
    *history, feedback = fake_llm.requests[1]["messages"]
    assert history == MESSAGES
    assert feedback["role"] == "user"


def test_stream_retry_skips_an_empty_reply(fake_llm):
    fake_llm.reply("")
    fake_llm.reply(submit={"word": "hello"})
    assert stream_events() == [llm.Done(Answer(word="hello"), "")]
    *history, feedback = fake_llm.requests[1]["messages"]
    assert history == MESSAGES
    assert feedback["role"] == "user"
