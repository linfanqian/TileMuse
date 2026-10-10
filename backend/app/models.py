"""Shared contracts between pipeline stages. Imports nothing from app."""

from enum import IntEnum
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

MAX_MAP_SIZE = 128  # same cap as MapSpec


class Tile(IntEnum):
    FLOOR = 0
    WALL = 1
    DOOR = 2


class MapObject(BaseModel):
    kind: str
    x: int
    y: int


class GameMap(BaseModel):
    width: int = Field(ge=1, le=MAX_MAP_SIZE)
    height: int = Field(ge=1, le=MAX_MAP_SIZE)
    tiles: list[list[Tile]]  # tiles[y][x]
    objects: list[MapObject] = []

    @model_validator(mode="after")
    def check_shape(self) -> Self:
        if len(self.tiles) != self.height or any(len(row) != self.width for row in self.tiles):
            raise ValueError(f"tiles must be {self.height} rows of {self.width}")
        for obj in self.objects:
            if not (0 <= obj.x < self.width and 0 <= obj.y < self.height):
                raise ValueError(f"object {obj.kind!r} at ({obj.x}, {obj.y}) is outside the map")
        return self


class Violation(BaseModel):
    code: str
    x: int | None = None
    y: int | None = None
    details: dict[str, Any] = {}


class Explanation(BaseModel):
    code: str
    text: str
