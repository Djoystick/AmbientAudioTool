from __future__ import annotations

from enum import StrEnum


class PlaybackChannel(StrEnum):
    MUSIC = "music"
    AMBIENT_NOISE = "ambient_noise"
    CONTEXT_ONESHOT = "context_oneshot"
    EVENT_ALERT = "event_alert"


class ConflictScope(StrEnum):
    CHANNEL = "channel"
    GLOBAL = "global"


class TieBreaker(StrEnum):
    PRIORITY_THEN_WEIGHT = "priority_then_weight"
    PRIORITY_THEN_OLDEST = "priority_then_oldest"
    STABLE_RULE_ID = "stable_rule_id"


class WeatherType(StrEnum):
    CLEAR = "clear"
    RAIN = "rain"
    THUNDER = "thunder"
    SNOW = "snow"


class DangerState(StrEnum):
    PEACEFUL = "peaceful"
    DANGER = "danger"
    COMBAT = "combat"
