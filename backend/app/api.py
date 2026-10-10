"""HTTP routes. The only module that wires pipeline stages together."""

from random import Random
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.explainer import explain
from app.generator import generate
from app.llm import idea_to_spec
from app.models import Explanation, GameMap, Violation
from app.spec import MapSpec
from app.tiled import to_tiled
from app.validator import validate

router = APIRouter()


class SpecRequest(BaseModel):
    idea: str


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
    return await idea_to_spec(req.idea)


@router.post("/generate")
def generate_map(req: GenerateRequest) -> GenerateResult:
    game_map = generate(req.spec, Random(req.seed))
    result = check(game_map, req.spec)
    return GenerateResult(
        map=game_map, violations=result.violations, explanations=result.explanations
    )


@router.post("/validate")
def validate_map(req: ValidateRequest) -> ValidationResult:
    if (req.map.width, req.map.height) != (req.spec.width, req.spec.height):
        raise HTTPException(422, "map size does not match spec")
    return check(req.map, req.spec)


@router.post("/export")
def export_map(req: ExportRequest) -> dict[str, Any]:
    return to_tiled(req.map)
