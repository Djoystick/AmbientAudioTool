from __future__ import annotations

from dataclasses import dataclass

from ambient_audio_tool.models.predicates import (
    BiomeInGroupPredicate,
    BiomeIsPredicate,
    CustomEventPredicate,
    DangerStateIsPredicate,
    IsUndergroundPredicate,
    IsUnderwaterPredicate,
    PlayerHealthRangePredicate,
    TimeBetweenPredicate,
    WeatherIsPredicate,
)


@dataclass(frozen=True)
class PredicateDescriptor:
    name: str
    description: str
    model_name: str


PREDICATE_CATALOG: dict[str, PredicateDescriptor] = {
    "biome_is": PredicateDescriptor(
        name="biome_is",
        description="Match a single biome identifier.",
        model_name=BiomeIsPredicate.__name__,
    ),
    "biome_in_group": PredicateDescriptor(
        name="biome_in_group",
        description="Match if current biome belongs to a named biome group.",
        model_name=BiomeInGroupPredicate.__name__,
    ),
    "time_between": PredicateDescriptor(
        name="time_between",
        description="Match if current hour is in a configured [start, end] window.",
        model_name=TimeBetweenPredicate.__name__,
    ),
    "weather_is": PredicateDescriptor(
        name="weather_is",
        description="Match current weather state.",
        model_name=WeatherIsPredicate.__name__,
    ),
    "player_health_range": PredicateDescriptor(
        name="player_health_range",
        description="Match if player health is in a numeric range.",
        model_name=PlayerHealthRangePredicate.__name__,
    ),
    "is_underwater": PredicateDescriptor(
        name="is_underwater",
        description="Match underwater state.",
        model_name=IsUnderwaterPredicate.__name__,
    ),
    "is_underground": PredicateDescriptor(
        name="is_underground",
        description="Match underground state.",
        model_name=IsUndergroundPredicate.__name__,
    ),
    "danger_state_is": PredicateDescriptor(
        name="danger_state_is",
        description="Match danger/combat/peaceful state.",
        model_name=DangerStateIsPredicate.__name__,
    ),
    "custom_event": PredicateDescriptor(
        name="custom_event",
        description="Match a custom runtime event ID.",
        model_name=CustomEventPredicate.__name__,
    ),
}


def supported_predicate_types() -> list[str]:
    return sorted(PREDICATE_CATALOG.keys())
