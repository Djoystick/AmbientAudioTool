from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .conditions import ConditionExpression
from .enums import ConflictScope, PlaybackChannel, TieBreaker


class AudioAsset(BaseModel):
    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    duration_ms: int | None = Field(default=None, ge=1)
    tags: list[str] = Field(default_factory=list)


class PriorityConfig(BaseModel):
    base_priority: int = 50
    contextual_boosts: dict[str, int] = Field(default_factory=dict)
    suppression_threshold: int = 0


class RandomnessConfig(BaseModel):
    probability: float = Field(default=1.0, ge=0.0, le=1.0)
    weight: int = Field(default=1, ge=1)
    no_repeat_window: int = Field(default=0, ge=0)
    jitter_ms: int = Field(default=0, ge=0)
    rotation_pool: str | None = None


class CooldownConfig(BaseModel):
    rule_cooldown_ms: int = Field(default=0, ge=0)
    asset_cooldown_ms: int = Field(default=0, ge=0)
    min_delay_ms: int = Field(default=0, ge=0)
    max_delay_ms: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_delays(self) -> "CooldownConfig":
        if self.max_delay_ms < self.min_delay_ms:
            raise ValueError("max_delay_ms must be greater than or equal to min_delay_ms")
        return self


class ConflictConfig(BaseModel):
    scope: ConflictScope = ConflictScope.CHANNEL
    max_concurrent: int = Field(default=1, ge=1)
    tie_breaker: TieBreaker = TieBreaker.PRIORITY_THEN_WEIGHT
    can_preempt_lower_priority: bool = False


class Rule(BaseModel):
    id: str = Field(min_length=1)
    name: str | None = None
    enabled: bool = True
    channel: PlaybackChannel
    condition_ref: str = Field(min_length=1)
    asset_ids: list[str] = Field(min_length=1)
    priority: PriorityConfig = Field(default_factory=PriorityConfig)
    randomness: RandomnessConfig = Field(default_factory=RandomnessConfig)
    cooldown: CooldownConfig = Field(default_factory=CooldownConfig)
    conflict: ConflictConfig = Field(default_factory=ConflictConfig)


class BiomeGroup(BaseModel):
    id: str = Field(min_length=1)
    name: str | None = None
    biomes: list[str] = Field(min_length=1)


class CustomEvent(BaseModel):
    id: str = Field(min_length=1)
    name: str | None = None
    description: str | None = None


class AuthoringProject(BaseModel):
    project_id: str = Field(min_length=1)
    project_name: str | None = None
    version: str = "1.0"
    audio_assets: list[AudioAsset] = Field(default_factory=list)
    biome_groups: list[BiomeGroup] = Field(default_factory=list)
    custom_events: list[CustomEvent] = Field(default_factory=list)
    conditions: list[ConditionExpression] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
