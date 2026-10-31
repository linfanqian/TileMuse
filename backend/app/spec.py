"""Map spec schema: what the LLM produces, and the source of truth for generation and validation.

Pydantic checks the spec's own consistency here. Whether a map satisfies the spec is the
validator's job.
"""

from collections import Counter
from enum import StrEnum
from typing import Annotated, Literal, Self, get_args

from pydantic import BaseModel, Field, model_validator


class ObjectKind(StrEnum):
    """The fixed object set the generator can place."""

    PLAYER_SPAWN = "player_spawn"
    EXIT = "exit"
    CHEST = "chest"
    GUARD = "guard"
    COVER = "cover"
    KEY = "key"
    LIGHT = "light"


class ObjectRequirement(BaseModel):
    kind: ObjectKind
    count: int = Field(ge=1, le=64)


class MaxDensityRule(BaseModel):
    """`objects / interior` may be at most `max`.

    `interior` is the (width - 2) * (height - 2) tiles inside the outer walls, whatever is on them.
    """

    type: Literal["max_density"] = "max_density"
    max: float = Field(gt=0, le=1)


class MinDistanceRule(BaseModel):
    """Every two distinct objects, one `a` and one `b`, are at least `tiles` apart.

    Distance is Manhattan. With `a == b`, this spaces out objects of that kind.
    """

    type: Literal["min_distance"] = "min_distance"
    a: ObjectKind
    b: ObjectKind
    tiles: int = Field(ge=1, le=256)


# Add a rule type here, then a validator rule and an explainer template for it.
LayoutRule = Annotated[MaxDensityRule | MinDistanceRule, Field(discriminator="type")]


# Field constraints shared by MapSpec and SpecDraft.
Label = Annotated[str, Field(min_length=1, max_length=200)]
Size = Annotated[int, Field(ge=4, le=128)]
Doors = Annotated[int, Field(ge=1, le=8)]

SpecField = Literal["theme", "mood", "width", "height", "doors", "objects", "rules"]


class MapSpec(BaseModel):
    theme: Label
    mood: Label
    width: Size
    height: Size
    doors: Doors = 1
    objects: list[ObjectRequirement] = []
    rules: list[LayoutRule] = []

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        dupes = [kind for kind, n in Counter(o.kind for o in self.objects).items() if n > 1]
        if dupes:
            raise ValueError(f"each object kind may appear once in objects: {', '.join(dupes)}")
        interior = (self.width - 2) * (self.height - 2)
        total = sum(o.count for o in self.objects)
        if total > interior:
            raise ValueError(f"{total} objects do not fit in {interior} interior tiles")
        counts = {o.kind: o.count for o in self.objects}
        # One max_density, and one min_distance per unordered pair of kinds.
        keys = [
            frozenset((r.a, r.b)) if isinstance(r, MinDistanceRule) else r.type for r in self.rules
        ]
        if len(set(keys)) != len(keys):
            raise ValueError("rules may not repeat a max_density or a min_distance pair")
        # Farthest apart two interior tiles can be. Only rules out specs where no single pair
        # fits; whether all `count` objects fit at once is left to the validator.
        max_distance = (self.width - 3) + (self.height - 3)
        for rule in self.rules:
            # The validator must compute this same ratio so both agree on boundary values.
            if isinstance(rule, MaxDensityRule) and total / interior > rule.max:
                raise ValueError(
                    f"max_density {rule.max} allows fewer than the {total} required objects"
                )
            if isinstance(rule, MinDistanceRule):
                missing = sorted({rule.a, rule.b} - counts.keys())
                if missing:
                    raise ValueError(
                        f"min_distance uses kinds not in objects: {', '.join(missing)}"
                    )
                if rule.a == rule.b and counts[rule.a] < 2:
                    raise ValueError(f"min_distance between {rule.a} objects needs at least 2")
                if rule.tiles > max_distance:
                    raise ValueError(
                        f"min_distance of {rule.tiles} exceeds the room's {max_distance}"
                    )
        return self


class SpecDraft(BaseModel):
    """A MapSpec being filled in by the interview. None means not decided yet.

    Each field is checked on its own. Whether the fields fit together is checked by `to_spec`.
    """

    theme: Label | None = None
    mood: Label | None = None
    width: Size | None = None
    height: Size | None = None
    doors: Doors | None = None
    objects: list[ObjectRequirement] | None = None
    rules: list[LayoutRule] | None = None

    def missing(self) -> list[SpecField]:
        return [field for field in get_args(SpecField) if getattr(self, field) is None]

    def to_spec(self) -> MapSpec | None:
        """The spec once every field is set. Raises ValidationError if they don't fit together."""
        if self.missing():
            return None
        return MapSpec.model_validate(self.model_dump())
