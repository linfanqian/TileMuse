"""Shared Claude API client. The only module that calls the Claude API. Imports nothing from app."""

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import anthropic
import httpx2
from anthropic.lib.streaming import BetaAsyncMessageStreamManager
from anthropic.types.beta import (
    BetaContentBlock,
    BetaMessage,
    BetaMessageParam,
    BetaOutputConfigParam,
)
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
TIMEOUT_SECONDS = 60.0  # Requests stream, so this bounds the gap between chunks.
SDK_RETRIES = 1  # Network, 429 and 5xx retries, separate from the validation retry.


logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """No API key is configured, or the API rejected it."""


class LLMError(Exception):
    """The call failed, was refused or truncated, or its output didn't validate twice."""


class _Settings(BaseSettings):
    # The environment overrides backend/.env.
    model_config = SettingsConfigDict(env_file=Path(__file__).parents[1] / ".env", extra="ignore")
    anthropic_api_key: SecretStr | None = None


@cache
def _client() -> anthropic.AsyncAnthropic:
    key = _Settings().anthropic_api_key
    if key is None or not key.get_secret_value():
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set in backend/.env")
    return anthropic.AsyncAnthropic(
        api_key=key.get_secret_value(), timeout=TIMEOUT_SECONDS, max_retries=SDK_RETRIES
    )


@contextmanager
def _api_errors() -> Iterator[None]:
    """Logs SDK errors and turns them into LLMUnavailable or LLMError."""
    try:
        yield
    except anthropic.AuthenticationError as e:
        logger.warning("Claude rejected the API key: %s", _describe(e))
        _client.cache_clear()  # Pick up a fixed backend/.env without a restart.
        raise LLMUnavailable("ANTHROPIC_API_KEY in backend/.env was rejected") from e
    except anthropic.APIError as e:  # Includes timeouts and connection errors.
        logger.warning("Claude request failed: %s", _describe(e))
        raise LLMError(f"Claude request failed: {type(e).__name__}") from e
    except httpx2.TransportError as e:  # The SDK passes these through once the reply streams.
        logger.warning("Claude request failed mid-reply: %s: %s", type(e).__name__, e)
        raise LLMError(f"Claude request failed: {type(e).__name__}") from e


def _describe(e: anthropic.APIError) -> str:
    """Error type, status, request ID and the API's message. These never contain the key."""
    if isinstance(e, anthropic.APIStatusError):
        return (
            f"{type(e).__name__} (status {e.status_code}, request_id {e.request_id}): {e.message}"
        )
    return f"{type(e).__name__}: {e.message}"


def _stream(
    system: str, messages: list[BetaMessageParam], **params: Any
) -> BetaAsyncMessageStreamManager:
    return _client().beta.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        **params,
    )


def _check(response: BetaMessage) -> BetaMessage:
    if response.stop_reason in ("refusal", "max_tokens", "model_context_window_exceeded"):
        logger.warning("Claude returned no usable output: stop_reason=%s", response.stop_reason)
        raise LLMError(f"Claude returned no usable output (stop_reason={response.stop_reason})")
    return response


async def _create(system: str, messages: list[BetaMessageParam], **params: Any) -> BetaMessage:
    """Sends one request and waits for the whole reply. Raises LLMError on any failure."""
    with _api_errors():
        async with _stream(system, messages, **params) as events:
            response = await events.get_final_message()
    return _check(response)


def _last_fallback(content: list[BetaContentBlock]) -> int:
    """Index of the last `fallback` block, or -1. What comes before it was declined."""
    return max((i for i, block in enumerate(content) if block.type == "fallback"), default=-1)


def _after_fallback(content: list[BetaContentBlock]) -> list[BetaContentBlock]:
    return content[_last_fallback(content) + 1 :]


def _text(response: BetaMessage) -> str:
    return "".join(b.text for b in _after_fallback(response.content) if b.type == "text")


def _retry(
    messages: list[BetaMessageParam], response: BetaMessage, feedback: BetaMessageParam
) -> list[BetaMessageParam]:
    """The conversation for a retry: the reply as an assistant turn, then the feedback.

    Before a fallback, the API accepts only text back. The API rejects empty text blocks and
    an assistant turn with no content, so empty text is dropped, and a reply with nothing left
    but `fallback` blocks (which aren't rendered into the prompt) is left out.
    """
    last = _last_fallback(response.content)
    content = [
        b
        for i, b in enumerate(response.content)
        if (i >= last or b.type == "text") and not (b.type == "text" and not b.text)
    ]
    rendered = any(b.type != "fallback" for b in content)
    echo: list[BetaMessageParam] = [{"role": "assistant", "content": content}] if rendered else []
    return [*messages, *echo, feedback]


async def complete_text(system: str, messages: list[BetaMessageParam]) -> str:
    return _text(await _create(system, messages))


async def complete[T: BaseModel](
    system: str, messages: list[BetaMessageParam], output: type[T]
) -> T:
    """Asks for JSON matching `output` and validates it, retrying once with the errors."""
    output_config: BetaOutputConfigParam = {
        "format": {"type": "json_schema", "schema": anthropic.transform_schema(output)}
    }
    response = await _create(system, messages, output_config=output_config)
    try:
        return output.model_validate_json(_text(response))
    except ValidationError as e:
        feedback: BetaMessageParam = {
            "role": "user",
            "content": f"That JSON failed validation:\n{e}\nReply with corrected JSON.",
        }
        messages = _retry(messages, response, feedback)
    response = await _create(system, messages, output_config=output_config)
    try:
        return output.model_validate_json(_text(response))
    except ValidationError as e:
        logger.warning("Claude's %s output failed validation twice: %s", output.__name__, e)
        raise LLMError("Claude's output failed validation twice") from e


@dataclass(frozen=True)
class TextDelta:
    """The next piece of the message to the user."""

    text: str


@dataclass(frozen=True)
class Reset:
    """A server-side fallback switched models mid-output. Discard the text shown so far."""


@dataclass(frozen=True)
class Done[T]:
    """The validated structured result, and the whole message without any declined part."""

    result: T
    text: str


SUBMIT = "submit"
_SUBMIT_INSTRUCTION = (
    f"Write your message to the user as plain text, then call the {SUBMIT} tool once "
    "with the structured result."
)


def _tool_calls(response: BetaMessage) -> list[BetaContentBlock]:
    return [b for b in _after_fallback(response.content) if b.type == "tool_use"]


def _submission[T: BaseModel](response: BetaMessage, output: type[T]) -> T:
    """The validated `submit` input. Raises ValidationError, or LookupError if it's missing."""
    for call in _tool_calls(response):
        if call.name == SUBMIT:
            return output.model_validate(call.input)
    raise LookupError(f"The {SUBMIT} tool wasn't called")


def _feedback(response: BetaMessage, error: Exception) -> BetaMessageParam:
    """The user turn asking for a corrected submission, without repeating the message."""
    calls = _tool_calls(response)
    if not calls:
        return {
            "role": "user",
            "content": f"Call the {SUBMIT} tool with the structured result. "
            "Don't repeat your message.",
        }
    # Every tool_use needs a matching tool_result.
    text = (
        f"Invalid input:\n{error}\nCall {SUBMIT} again with corrected input. "
        "Don't repeat your message."
    )
    results = [
        {"type": "tool_result", "tool_use_id": call.id, "is_error": True, "content": text}
        for call in calls
    ]
    return {"role": "user", "content": results}


async def stream[T: BaseModel](
    system: str, messages: list[BetaMessageParam], output: type[T]
) -> AsyncIterator[TextDelta | Reset | Done[T]]:
    """Streams the message to the user, then yields the validated `output` from a `submit` call.

    An invalid submission is retried once with the errors. The retry's text isn't yielded.
    LLMError can be raised after text was yielded, with no Reset first. Callers discard that
    text.
    """
    system = f"{system}\n\n{_SUBMIT_INSTRUCTION}"
    tools = [
        {
            "name": SUBMIT,
            "description": "Submit the structured result.",
            "input_schema": anthropic.transform_schema(output),
            "strict": True,
        }
    ]
    with _api_errors():
        async with _stream(system, messages, tools=tools) as events:
            async for event in events:
                if event.type == "text":
                    yield TextDelta(event.text)
                elif event.type == "content_block_start" and event.content_block.type == "fallback":
                    yield Reset()
            response = await events.get_final_message()
    text = _text(_check(response))
    try:
        result = _submission(response, output)
    except (ValidationError, LookupError) as e:
        retry = _retry(messages, response, _feedback(response, e))
        response = await _create(system, retry, tools=tools)
        try:
            result = _submission(response, output)
        except (ValidationError, LookupError) as e:
            logger.warning("Claude's %s submission failed validation twice: %s", output.__name__, e)
            raise LLMError("Claude's submission failed validation twice") from e
    yield Done(result, text)
