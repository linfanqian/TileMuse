"""Map spec schema: what the LLM produces. Placeholder fields; real schema is issue #5."""

from pydantic import BaseModel, Field


class MapSpec(BaseModel):
    width: int = Field(16, ge=4, le=128)
    height: int = Field(12, ge=4, le=128)
