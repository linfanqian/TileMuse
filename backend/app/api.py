"""HTTP routes. The only module that wires pipeline stages together."""

import io
import json
import logging
import zipfile
from collections.abc import AsyncIterable
from contextlib import aclosing
from random import Random
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.explainer import explain
from app.generator import generate
from app.interview import ChatMessage, InterviewResult, interview
from app.kits import ASSETS
from app.llm import LLMError, LLMUnavailable, TextDelta
from app.models import Explanation, GameMap, Violation
from app.spec import MapSpec, SpecDraft
from app.tiled import to_tiled
from app.tileset import load_tileset
from app.validator import validate

router = APIRouter()
logger = logging.getLogger(__name__)


MAX_MESSAGES = 39


class InterviewRequest(BaseModel):
    """The whole chat so far, which the frontend keeps, and the draft from the last turn.

    At the message cap the frontend drops the oldest question and answer after the first idea.
    """

    # Odd, since turns alternate and both start and end with the user.
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
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
    spec: MapSpec  # Its kit picks the tiles.
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


@router.post("/interview")
async def interview_turn(req: InterviewRequest) -> AsyncIterable[InterviewEvent]:
    """Streams JSON Lines: text events, then done or error. The status is sent before Claude
    replies, so failures arrive as an error event instead of a 5xx."""
    try:
        async with aclosing(interview(req.messages, req.draft)) as events:
            async for event in events:
                if isinstance(event, TextDelta):
                    yield InterviewText(text=event.text)
                else:
                    yield InterviewDone.model_validate(event, from_attributes=True)
    except LLMUnavailable as e:
        yield InterviewError(message=str(e))
    except LLMError:
        yield InterviewError(message="Couldn't get the next question from the LLM. Try again.")
    except Exception:
        # Every stream still ends in done or error, so the client needn't handle a cut-off one.
        logger.exception("Interview turn failed")
        yield InterviewError(message="Something went wrong. Try again.")


@router.post("/generate")
def generate_map(req: GenerateRequest) -> GenerateResult:
    game_map = generate(req.spec, Random(req.seed))
    return GenerateResult(map=game_map, **check(game_map, req.spec).model_dump())


@router.post("/validate")
def validate_map(req: ValidateRequest) -> ValidationResult:
    return check(req.map, req.spec)


EXPORT_NAME = "tilemuse-map"


@router.post(
    "/export",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "The map and its sheet"}},
)
def export_map(req: ExportRequest) -> Response:
    """A zip with the Tiled map and the tile sheet it points to, ready to open in Tiled."""
    image = load_tileset().catalog.image
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{EXPORT_NAME}.tmj", json.dumps(to_tiled(req.map, req.spec.kit), indent=2)
        )
        archive.write(ASSETS / image, image)
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{EXPORT_NAME}.zip"'},
    )
