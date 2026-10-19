"""Shared Claude API client. The only module that calls the Claude API. Imports nothing from app."""

import logging
from functools import cache
from pathlib import Path

import anthropic
from anthropic import Omit, omit
from anthropic.types.beta import BetaMessage, BetaMessageParam, BetaOutputConfigParam
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
TIMEOUT_SECONDS = 60.0  # Per request; bounds load on the backend.
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


async def _create(
    system: str,
    messages: list[BetaMessageParam],
    output_config: BetaOutputConfigParam | Omit = omit,
) -> BetaMessage:
    """Sends one request. Raises LLMError on API errors, refusals and truncation."""
    try:
        response = await _client().beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        logger.warning("Claude rejected the API key: %s", _describe(e))
        raise LLMUnavailable("ANTHROPIC_API_KEY in backend/.env was rejected") from e
    except anthropic.APIError as e:  # Includes timeouts and connection errors.
        logger.warning("Claude request failed: %s", _describe(e))
        raise LLMError(f"Claude request failed: {type(e).__name__}") from e
    if response.stop_reason in ("refusal", "max_tokens"):
        logger.warning("Claude returned no usable output: stop_reason=%s", response.stop_reason)
        raise LLMError(f"Claude returned no usable output (stop_reason={response.stop_reason})")
    return response


def _describe(e: anthropic.APIError) -> str:
    """Error type, status, request ID and the API's message. These never contain the key."""
    if isinstance(e, anthropic.APIStatusError):
        return (
            f"{type(e).__name__} (status {e.status_code}, request_id {e.request_id}): {e.message}"
        )
    return f"{type(e).__name__}: {e.message}"


def _text(response: BetaMessage) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


async def complete_text(system: str, messages: list[BetaMessageParam]) -> str:
    return _text(await _create(system, messages))


async def complete[T: BaseModel](
    system: str, messages: list[BetaMessageParam], output: type[T]
) -> T:
    """Asks for JSON matching `output` and validates it, retrying once with the errors."""
    output_config: BetaOutputConfigParam = {
        "format": {"type": "json_schema", "schema": anthropic.transform_schema(output)}
    }
    response = await _create(system, messages, output_config)
    try:
        return output.model_validate_json(_text(response))
    except ValidationError as e:
        messages = [
            *messages,
            # The full reply, unchanged, as the API requires for thinking blocks.
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": f"That JSON failed validation:\n{e}\nReply with corrected JSON.",
            },
        ]
    response = await _create(system, messages, output_config)
    try:
        return output.model_validate_json(_text(response))
    except ValidationError as e:
        logger.warning("Claude's %s output failed validation twice: %s", output.__name__, e)
        raise LLMError("Claude's output failed validation twice") from e
