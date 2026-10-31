"""HTTP routes. The only module that wires pipeline stages together."""

from collections.abc import AsyncIterable
from contextlib import aclosing
from random import Random
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.explainer import explain
from app.generator import generate
from app.interview import ChatMessage, InterviewResult, idea_to_spec, interview
from app.llm import LLMError, LLMUnavailable, TextDelta
from app.models import Explanation, GameMap, Violation
from app.spec import MapSpec, SpecDraft
from app.tiled import to_tiled
from app.validator import validate

router = APIRouter()


class SpecRequest(BaseModel):
    # Bounds the LLM's token cost. A blank idea would still cost a call.
    idea: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class InterviewRequest(BaseModel):
    """The whole chat so far, which the frontend keeps, and the draft from the last turn."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    draft: SpecDraft = Field(default_factory=SpecDraft)

    @model_validator(mode="after")
    def check_turns(self) -> Self:
        # Claude replies to the user's latest message, so turns alternate from user to user.
        for i, message in enumerate(self.messages):
            if message.role != ("user" if i % 2 == 0 else "assistant"):
                raise ValueError("messages must alternate user and assistant, starting with user")
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return self


# Responses always include `type`, so the schema marks it required for the frontend to narrow on.
_EVENT_CONFIG = ConfigDict(json_schema_serialization_defaults_required=True)


class InterviewText(BaseModel):
    """The next piece of the message to the user."""

    model_config = _EVENT_CONFIG
    type: Literal["text"] = "text"
    text: str


class InterviewDone(InterviewResult):
    model_config = _EVENT_CONFIG
    type: Literal["done"] = "done"


class InterviewError(BaseModel):
    """The turn failed. The client discards any text streamed before it."""

    model_config = _EVENT_CONFIG
    type: Literal["error"] = "error"
    message: str


InterviewEvent = Annotated[
    InterviewText | InterviewDone | InterviewError, Field(discriminator="type")
]


class GenerateRequest(BaseModel):
    spec: MapSpec
    seed: int


class ValidateRequest(BaseModel):
    spec: MapSpec
    map: GameMap


class ExportRequest(BaseModel):
    map: GameMap


class ValidationResult(BaseModel):
    violations: list[Violation]
    explanations: list[Explanation]


class GenerateResult(ValidationResult):
    map: GameMap


def check(game_map: GameMap, spec: MapSpec) -> ValidationResult:
    violations = validate(game_map, spec)
    return ValidationResult(violations=violations, explanations=explain(violations))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/spec")
async def spec(req: SpecRequest) -> MapSpec:
    try:
        return await idea_to_spec(req.idea)
    except LLMUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except LLMError as e:
        raise HTTPException(
            502, "Couldn't get a valid spec from the LLM. Try again or rephrase the idea."
        ) from e


@router.post("/interview")
async def interview_turn(req: InterviewRequest) -> AsyncIterable[InterviewEvent]:
    """Streams JSON Lines: text events, then done. The status is sent before Claude replies,
    so LLM failures arrive as an error event instead of a 502 or 503."""
    try:
        async with aclosing(interview(req.messages, req.draft)) as events:
            async for event in events:
                if isinstance(event, TextDelta):
                    yield InterviewText(text=event.text)
                else:
                    yield InterviewDone(**dict(event))
    except LLMUnavailable as e:
        yield InterviewError(message=str(e))
    except LLMError:
        yield InterviewError(message="Couldn't get the next question from the LLM. Try again.")


@router.post("/generate")
def generate_map(req: GenerateRequest) -> GenerateResult:
    game_map = generate(req.spec, Random(req.seed))
    return GenerateResult(map=game_map, **check(game_map, req.spec).model_dump())


@router.post("/validate")
def validate_map(req: ValidateRequest) -> ValidationResult:
    return check(req.map, req.spec)


@router.post("/export")
def export_map(req: ExportRequest) -> dict[str, Any]:
    return to_tiled(req.map)
