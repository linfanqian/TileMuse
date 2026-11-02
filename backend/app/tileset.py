"""Shared tile data: the labeled catalog and one kit per theme.

The catalog says what each tile is. A kit says which tiles a theme uses, and may pick tiles from
any pack. Loading runs every check, so bad data fails here and not in a later stage.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self, get_args

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from app.spec import ObjectKind

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "tileset"

Kind = Literal["floor", "wall", "door", "object", "decor", "character", "item"]
Confidence = Literal["high", "medium", "low"]
Side = Literal["top", "bottom", "left", "right"]
WallPiece = Literal[
    "top", "bottom", "left", "right", "corner_tl", "corner_tr", "corner_bl", "corner_br"
]

# Doors double as exits, so `exit` needs no tile of its own.
KIT_OBJECTS = [kind for kind in ObjectKind if kind != ObjectKind.EXIT]


class TileEntry(BaseModel):
    id: int = Field(ge=0)  # 0-based cell on the sheet. Not unique: openings share tiles.
    name: str  # The unique key. Kits refer to entries by this.
    kind: Kind
    themes: list[str]
    blocking: bool
    footprint: tuple[int, int] = (1, 1)  # width, height in tiles
    parts: list[int] = []  # left to right, top to bottom; empty for a one-tile entry
    wall_role: str | None = None
    tags: list[str] = []
    confidence: Confidence  # high means a person checked this entry
    note: str = ""

    @model_validator(mode="after")
    def check_parts(self) -> Self:
        width, height = self.footprint
        if self.parts and len(self.parts) != width * height:
            raise ValueError(f"{self.name}: {len(self.parts)} parts for a {width}x{height} entry")
        return self


class Catalog(BaseModel):
    image: str
    tile_size: int = Field(gt=0)
    columns: int = Field(gt=0)
    rows: int = Field(gt=0)
    entries: list[TileEntry]

    @model_validator(mode="after")
    def check_entries(self) -> Self:
        names = [e.name for e in self.entries]
        if len(set(names)) != len(names):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"entry names must be unique: {', '.join(dupes)}")
        tile_count = self.columns * self.rows
        for entry in self.entries:
            if not all(0 <= tile < tile_count for tile in (entry.id, *entry.parts)):
                raise ValueError(f"{entry.name}: uses a tile outside the {tile_count}-tile sheet")
        return self


class ThemeKit(BaseModel):
    floor: str
    floor_shadow_top: str | None = None  # floor row under a two-row top wall
    walls: dict[WallPiece, str]
    face_end_left: str | None = None  # ends of the lower row of a two-row top wall
    face_end_right: str | None = None
    doors: dict[Side, str]
    objects: dict[ObjectKind, str]

    @field_validator("walls")
    @classmethod
    def check_walls(cls, walls: dict[WallPiece, str]) -> dict[WallPiece, str]:
        return _require_all(walls, get_args(WallPiece), "wall piece")

    @field_validator("doors")
    @classmethod
    def check_doors(cls, doors: dict[Side, str]) -> dict[Side, str]:
        return _require_all(doors, get_args(Side), "door side")

    @field_validator("objects")
    @classmethod
    def check_objects(cls, objects: dict[ObjectKind, str]) -> dict[ObjectKind, str]:
        return _require_all(objects, KIT_OBJECTS, "object kind")

    def tile_names(self) -> set[str]:
        """Every catalog entry this kit uses."""
        single = (self.floor, self.floor_shadow_top, self.face_end_left, self.face_end_right)
        names = {name for name in single if name is not None}
        return (
            names | set(self.walls.values()) | set(self.doors.values()) | set(self.objects.values())
        )


class Tileset(BaseModel):
    catalog: Catalog
    kits: dict[str, ThemeKit]

    @model_validator(mode="after")
    def check_kits(self) -> Self:
        entries = {e.name: e for e in self.catalog.entries}
        for theme, kit in self.kits.items():
            for name in sorted(kit.tile_names()):
                if name not in entries:
                    raise ValueError(f"{theme} kit: no catalog entry named {name}")
                if entries[name].confidence != "high":
                    raise ValueError(f"{theme} kit: {name} has not been reviewed")
            # A MapObject fills one cell, so a larger tile would cover cells that look free.
            for kind, name in kit.objects.items():
                if entries[name].footprint != (1, 1):
                    raise ValueError(f"{theme} kit: {kind} tile {name} must fill one cell")
        return self


def _require_all[T, V](found: dict[T, V], wanted: Any, label: str) -> dict[T, V]:
    missing = [str(item) for item in wanted if item not in found]
    if missing:
        raise ValueError(f"missing {label}: {', '.join(missing)}")
    return found


@lru_cache
def load_tileset() -> Tileset:
    def read(name: str) -> Any:
        return yaml.safe_load((ASSETS / name).read_text(encoding="utf-8"))

    return Tileset(catalog=read("catalog.yaml"), kits=read("kits.yaml"))
