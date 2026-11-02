"""Idea -> spec. The LLM only fills in the spec; it never produces maps.

`interview` asks one question per turn. `idea_to_spec` is the one-shot path behind /api/spec,
removed once the frontend moves to the interview (#23).
"""

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import aclosing
from typing import Annotated, Literal, Self

from anthropic.types.beta import BetaMessageParam
from pydantic import BaseModel, Field, StringConstraints, ValidationError, model_validator

from app.llm import Done, LLMError, TextDelta, complete, stream
from app.spec import (
    Doors,
    Label,
    MapSpec,
    Objects,
    Rules,
    Size,
    SpecDraft,
    SpecField,
)

logger = logging.getLogger(__name__)

# The JSON schema carries field names and enums; this states the checks in spec.py. The
# player_spawn/exit line is a design requirement that nothing checks yet.
_SPEC_RULES = """\
The spec must be consistent:
- width and height are 4-128 tiles, including the outer walls. Objects go on the \
(width - 2) * (height - 2) interior tiles.
- doors is 1-8.
- objects lists each kind at most once, and the counts must fit in the interior.
- Include one player_spawn and at least one exit.
- Every rule needs its type field: "type": "max_density" or "type": "min_distance".
- rules are optional. At most one max_density: objects / interior tiles <= max. \
At most one min_distance per pair of kinds: both kinds are in objects, a pair of the same kind \
needs a count of at least 2, and tiles is at most (width - 3) + (height - 3)."""

SYSTEM = f"""\
You turn a rough idea for a top-down 2D game map into a design spec for one walled room.
Fill every field from the idea. Where the idea says nothing, choose values that fit its theme \
and mood.

{_SPEC_RULES}"""

INTERVIEW_SYSTEM = f"""\
You interview a user, who may have no design training, to turn their rough idea for a top-down \
2D game map into a design spec for one walled room.

Each turn:
- Update the draft from the whole conversation. Set every field the user's answers settle, even \
ones you didn't ask about, and keep decided fields unless the user changes them. Leave a field \
null until it is decided. "rules": [] means no layout rules.
- Then ask about the one most important field that is still null or vague. Your message is that \
question alone, in one short sentence. Don't list options or examples in it: the suggested \
answers show next to it. In the submitted question, give the field, a one-line reason it \
matters, and 2-4 concrete suggested answers that fit the idea so far.
- If set fields don't fit together, for example the objects no longer fit after the user \
shrinks the room, ask the user how to resolve it.
- Once every field is set and the spec is consistent, either ask about a field that is still \
vague, or set question to null and tell the user in a sentence or two that the spec is ready to \
generate. The spec panel already shows every field, so don't list them.
- Write plain text with no Markdown: the chat shows it as is.

{_SPEC_RULES}"""


async def idea_to_spec(idea: str) -> MapSpec:
    return await complete(SYSTEM, [{"role": "user", "content": idea}], output=MapSpec)


# Characters per chat message. Bounds the LLM's token cost, with the API's cap on the number of
# messages. Applies to both roles, so `interview` keeps its own messages within it.
MAX_MESSAGE = 2000


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE)
    ]


class Question(BaseModel):
    field: SpecField
    reason: str = Field(min_length=1, max_length=200)
    suggestions: list[Annotated[str, StringConstraints(min_length=1, max_length=100)]] = Field(
        min_length=2, max_length=4
    )


class _SubmittedDraft(SpecDraft):
    """SpecDraft with every key required, so Claude restates each field instead of dropping one
    it didn't touch this turn. Null still means not decided yet."""

    theme: Label | None
    mood: Label | None
    width: Size | None
    height: Size | None
    doors: Doors | None
    objects: Objects | None
    rules: Rules | None


class _Turn(BaseModel):
    """What Claude submits each turn. The backend, not Claude, decides when the spec is ready."""

    draft: _SubmittedDraft
    question: Question | None

    @model_validator(mode="after")
    def check_ready(self) -> Self:
        # While asking, the draft may not fit together yet, e.g. right after the user shrinks the
        # room. Claude asks how to resolve it instead of failing the turn.
        if self.question is not None:
            return self
        try:
            spec = self.draft.to_spec()
        except ValidationError as e:
            # Raised as a ValueError so the retry feedback says what doesn't fit.
            raise ValueError(
                f"question is null, but the draft fields don't fit together: {e}"
            ) from None
        if spec is None:
            missing = ", ".join(self.draft.missing())
            raise ValueError(
                f"question may be null only once every field is set; missing: {missing}"
            )
        return self


class InterviewResult(BaseModel):
    # The whole message to the user. The client shows it in place of the streamed text, which
    # it differs from when Claude wrote none or rewrote it on a retry.
    message: str
    question: Question | None  # None once Claude has nothing left to ask.
    draft: SpecDraft
    spec: MapSpec | None  # Set exactly when every draft field is set and they fit together.


async def interview(
    messages: Sequence[ChatMessage], draft: SpecDraft
) -> AsyncIterator[TextDelta | InterviewResult]:
    """Streams the next question to the user, then the updated draft.

    Raises LLMUnavailable or LLMError, possibly after text was yielded. A caller that may stop
    early wraps it in `contextlib.aclosing`.
    """
    system = f"{INTERVIEW_SYSTEM}\n\nThe current draft:\n{draft.model_dump_json()}"
    history: list[BetaMessageParam] = [{"role": m.role, "content": m.content} for m in messages]
    async with aclosing(stream(system, history, output=_Turn)) as events:
        async for event in events:
            if isinstance(event, Done):
                turn = event.result
                draft = SpecDraft(**dict(turn.draft))  # Not the subclass, for callers.
                yield InterviewResult(
                    message=_message(event.text, turn.question),
                    question=turn.question,
                    draft=draft,
                    spec=_ready_spec(draft),
                )
            else:
                yield event


def _ready_spec(draft: SpecDraft) -> MapSpec | None:
    try:
        return draft.to_spec()
    except ValidationError:
        return None  # Claude's question is about resolving the conflict.


def _message(text: str, question: Question | None) -> str:
    """Claude's message, valid as the next turn's history. A fallback if Claude wrote none."""
    text = text.strip()  # As ChatMessage stores it.
    if len(text) > MAX_MESSAGE:
        logger.warning(
            "Claude's interview message is %d characters, over %d", len(text), MAX_MESSAGE
        )
        raise LLMError(f"Claude's message is over {MAX_MESSAGE} characters")
    if text:
        return text
    return f"What should the {question.field} be?" if question else "The spec is ready."
