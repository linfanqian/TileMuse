"""Idea -> spec. The LLM only fills in the spec; it never produces maps."""

from app.llm import complete
from app.spec import MapSpec

# The JSON schema carries field names and enums; this states the checks in spec.py.
SYSTEM = """\
You turn a rough idea for a top-down 2D game map into a design spec for one walled room.
Fill every field from the idea. Where the idea says nothing, choose values that fit its theme \
and mood.

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


async def idea_to_spec(idea: str) -> MapSpec:
    return await complete(SYSTEM, [{"role": "user", "content": idea}], output=MapSpec)
