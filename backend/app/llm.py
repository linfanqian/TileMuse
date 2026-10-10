"""Idea -> spec. The only module allowed to call the Claude API. It never produces maps."""

from app.spec import MapSpec


async def idea_to_spec(idea: str) -> MapSpec:
    # Stub: ignores the idea and returns the default spec.
    return MapSpec()
