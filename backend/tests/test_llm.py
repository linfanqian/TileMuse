import asyncio

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


def test_complete_fails_after_second_invalid_reply(fake_llm):
    fake_llm.reply('{"word": "hi"}')
    fake_llm.reply("not json")
    with pytest.raises(llm.LLMError) as excinfo:
        complete()
    assert isinstance(excinfo.value.__cause__, ValidationError)
    assert len(fake_llm.requests) == 2


def test_complete_text_returns_text(fake_llm):
    fake_llm.reply("Hello.")
    assert asyncio.run(llm.complete_text(SYSTEM, MESSAGES)) == "Hello."
    (request,) = fake_llm.requests
    assert request["output_config"] is anthropic.omit  # The SDK leaves it out of the request.


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


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_rejects_refusal_and_truncation(fake_llm, stop_reason):
    fake_llm.reply('{"word": "hello"}', stop_reason=stop_reason)
    with pytest.raises(llm.LLMError, match=stop_reason):
        complete()
    assert len(fake_llm.requests) == 1
