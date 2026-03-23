from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeContext:
    biome: str
    time: int
    weather: str
    player_health: int
    is_underwater: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.time <= 23:
            raise ValueError("time must be in range 0..23")
