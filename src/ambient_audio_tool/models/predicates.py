from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from .enums import DangerState, WeatherType


class BiomeIsPredicate(BaseModel):
    type: Literal["biome_is"]
    biome: str = Field(min_length=1)


class BiomeInGroupPredicate(BaseModel):
    type: Literal["biome_in_group"]
    group_id: str = Field(min_length=1)


class TimeBetweenPredicate(BaseModel):
    type: Literal["time_between"]
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)


class WeatherIsPredicate(BaseModel):
    type: Literal["weather_is"]
    weather: WeatherType


class PlayerHealthRangePredicate(BaseModel):
    type: Literal["player_health_range"]
    min_health: float = Field(ge=0)
    max_health: float = Field(ge=0)

    @model_validator(mode="after")
    def check_min_max(self) -> "PlayerHealthRangePredicate":
        if self.max_health < self.min_health:
            raise ValueError("max_health must be greater than or equal to min_health")
        return self


class IsUnderwaterPredicate(BaseModel):
    type: Literal["is_underwater"]
    value: bool = True


class IsUndergroundPredicate(BaseModel):
    type: Literal["is_underground"]
    value: bool = True


class DangerStateIsPredicate(BaseModel):
    type: Literal["danger_state_is"]
    state: DangerState


class CustomEventPredicate(BaseModel):
    type: Literal["custom_event"]
    event_id: str = Field(min_length=1)


Predicate = Annotated[
    BiomeIsPredicate
    | BiomeInGroupPredicate
    | TimeBetweenPredicate
    | WeatherIsPredicate
    | PlayerHealthRangePredicate
    | IsUnderwaterPredicate
    | IsUndergroundPredicate
    | DangerStateIsPredicate
    | CustomEventPredicate,
    Field(discriminator="type"),
]
