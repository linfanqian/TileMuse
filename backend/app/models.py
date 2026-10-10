"""Shared contracts between pipeline stages. Imports nothing from app."""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel


class Tile(IntEnum):
    FLOOR = 0
    WALL = 1
    DOOR = 2


class MapObject(BaseModel):
    kind: str
    x: int
    y: int


class GameMap(BaseModel):
    width: int
    height: int
    tiles: list[list[Tile]]  # tiles[y][x]
    objects: list[MapObject] = []


class Violation(BaseModel):
    code: str
    x: int | None = None
    y: int | None = None
    details: dict[str, Any] = {}


class Explanation(BaseModel):
    code: str
    text: str
