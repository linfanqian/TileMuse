"""Shared tile data: the labeled catalog and one kit per theme.

The catalog says what each tile is. A kit says which tiles a theme uses, and may pick tiles from
any pack. Loading runs every check, so bad data fails here and not in a later stage.
"""

from functools import lru_cache
from typing import Any, Literal, Self, get_args

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from app.kits import ASSETS, read_kits
from app.spec import ObjectKind
from app.walkable import BLOCKING_KINDS

Kind = Literal["floor", "wall", "door", "object", "decor", "character", "item"]
Confidence = Literal["high", "medium", "low"]
Side = Literal["top", "bottom", "left", "right"]
WallPiece = Literal[
    "top", "bottom", "left", "right", "corner_tl", "corner_tr", "corner_bl", "corner_br"
]

# The catalog kind each object's tile must have.
OBJECT_TILE_KINDS: dict[ObjectKind, Kind] = {
    ObjectKind.PLAYER_SPAWN: "character",
    ObjectKind.CHEST: "object",
    ObjectKind.GUARD: "character",
    ObjectKind.COVER: "object",
    ObjectKind.KEY: "item",
    ObjectKind.LIGHT: "object",
}


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
    confidence: Confidence  # kits may only use high entries
    note: str = ""

    @model_validator(mode="after")
    def check_parts(self) -> Self:
        width, height = self.footprint
        if len(self.parts) != width * height and (self.parts or (width, height) != (1, 1)):
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
    description: str = Field(min_length=1)  # shown to the LLM to choose a kit
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
        return _require_all(objects, OBJECT_TILE_KINDS, "object kind")

    def slots(self) -> list[tuple[str, Kind]]:
        """Every catalog entry this kit uses, with the kind its slot needs."""
        slots: list[tuple[str | None, Kind]] = [
            (self.floor, "floor"),
            (self.floor_shadow_top, "floor"),
            (self.face_end_left, "wall"),
            (self.face_end_right, "wall"),
            *((name, "wall") for name in self.walls.values()),
            *((name, "door") for name in self.doors.values()),
            *((name, OBJECT_TILE_KINDS[kind]) for kind, name in self.objects.items()),
        ]
        return [(name, kind) for name, kind in slots if name is not None]


class Tileset(BaseModel):
    catalog: Catalog
    kits: dict[str, ThemeKit]

    @model_validator(mode="after")
    def check_kits(self) -> Self:
        entries = {e.name: e for e in self.catalog.entries}
        for theme, kit in self.kits.items():
            for name, kind in kit.slots():
                if name not in entries:
                    raise ValueError(f"{theme} kit: no catalog entry named {name}")
                if entries[name].confidence != "high":
                    raise ValueError(f"{theme} kit: {name} has not been reviewed")
                if entries[name].kind != kind:
                    raise ValueError(f"{theme} kit: {name} is {entries[name].kind}, not {kind}")
            # A MapObject fills one cell, so a larger tile would cover cells that look free.
            for kind, name in kit.objects.items():
                if entries[name].footprint != (1, 1):
                    raise ValueError(f"{theme} kit: {kind} tile {name} must fill one cell")
            _check_blocking(theme, kit, entries)
        return self

    def blocking_tiles(self, kit_name: str) -> list[int]:
        """The sheet ids that block movement where this kit draws them, in order."""
        entries = {e.name: e for e in self.catalog.entries}
        return sorted(_tile_use(self.kits[kit_name], entries)[0])


def _tile_use(kit: ThemeKit, entries: dict[str, TileEntry]) -> tuple[set[int], set[int]]:
    """The sheet ids this kit draws where a player can't walk, and where one can. Walls block. So
    do an opening's ends, which stand where wall cells are; its middle is the way through.
    Entries share tiles, so this follows how the kit uses each one, not every entry that has it.
    """

    def tiles(name: str) -> list[int]:
        return entries[name].parts or [entries[name].id]

    blocking: set[int] = set()
    walkable: set[int] = set()
    for name in (*kit.walls.values(), kit.face_end_left, kit.face_end_right):
        if name:
            blocking.update(tiles(name))
    for name in (kit.floor, kit.floor_shadow_top):
        if name:
            walkable.update(tiles(name))
    for name in kit.doors.values():
        parts = tiles(name)
        middle = len(parts) // 2  # The part drawn on the door's own cell.
        walkable.add(parts[middle])
        blocking.update(part for i, part in enumerate(parts) if i != middle)
    for name in kit.objects.values():
        (blocking if entries[name].blocking else walkable).update(tiles(name))
    return blocking, walkable


def _check_blocking(theme: str, kit: ThemeKit, entries: dict[str, TileEntry]) -> None:
    """The catalog's `blocking` must match how the kit uses each entry, and how the generator
    and validator treat each object. A tile can't both block and be walked on in one kit, since
    the export gives each tile one `blocking` property."""
    walls = (*kit.walls.values(), kit.face_end_left, kit.face_end_right)
    open_ground = (kit.floor, kit.floor_shadow_top, *kit.doors.values())
    for names, blocks, role in ((walls, True, "wall"), (open_ground, False, "floor or door")):
        for name in names:
            if name and entries[name].blocking != blocks:
                raise ValueError(f"{theme} kit: {name} is a {role}, so blocking must be {blocks}")
    for kind, name in kit.objects.items():
        blocks = kind in BLOCKING_KINDS
        if entries[name].blocking != blocks:
            raise ValueError(f"{theme} kit: {kind} tile {name} must have blocking {blocks}")
    blocking, walkable = _tile_use(kit, entries)
    if both := blocking & walkable:
        raise ValueError(f"{theme} kit: tiles {sorted(both)} both block and can be walked on")


def _require_all[T, V](found: dict[T, V], wanted: Any, label: str) -> dict[T, V]:
    missing = [str(item) for item in wanted if item not in found]
    if missing:
        raise ValueError(f"missing {label}: {', '.join(missing)}")
    return found


@lru_cache
def load_tileset() -> Tileset:
    catalog = yaml.safe_load((ASSETS / "catalog.yaml").read_text(encoding="utf-8"))
    return Tileset(catalog=catalog, kits=read_kits())
