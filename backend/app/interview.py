"""Idea -> spec. The LLM only fills in the spec; it never produces maps."""

from app.spec import MapSpec, ObjectKind, ObjectRequirement


async def idea_to_spec(idea: str) -> MapSpec:
    # Stub: ignores the idea and returns a fixed example spec.
    return MapSpec(
        theme="dungeon",
        mood="quiet",
        width=16,
        height=12,
        objects=[
            ObjectRequirement(kind=ObjectKind.PLAYER_SPAWN, count=1),
            ObjectRequirement(kind=ObjectKind.EXIT, count=1),
        ],
    )
