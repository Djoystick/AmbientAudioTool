from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import PlaybackChannel


class RuntimeRule(BaseModel):
    rule_id: str = Field(min_length=1)
    channel: PlaybackChannel
    condition_expr_id: str = Field(min_length=1)
    asset_pool: list[str] = Field(min_length=1)
    base_priority: int = 50
    probability: float = 1.0
    cooldown_ms: int = 0


class RuntimeProject(BaseModel):
    spec_version: str = "2.0"
    generated_at_utc: str
    rules: list[RuntimeRule] = Field(default_factory=list)
