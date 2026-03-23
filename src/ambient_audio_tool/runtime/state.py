from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuntimeState:
    current_time_ms: int = 0
    rule_last_played_at: dict[str, int] = field(default_factory=dict)
    asset_last_played_at: dict[str, int] = field(default_factory=dict)
    recent_asset_history: list[str] = field(default_factory=list)
    rule_asset_history: dict[str, list[str]] = field(default_factory=dict)
    active_channel_selections: dict[str, list[dict[str, object]]] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "current_time_ms": self.current_time_ms,
            "rule_last_played_at": dict(self.rule_last_played_at),
            "asset_last_played_at": dict(self.asset_last_played_at),
            "recent_asset_history": list(self.recent_asset_history),
            "rule_asset_history": {
                rule_id: list(history)
                for rule_id, history in self.rule_asset_history.items()
            },
            "active_channel_selections": {
                channel: [dict(item) for item in selections]
                for channel, selections in self.active_channel_selections.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> "RuntimeState":
        if payload is None:
            return cls()
        rule_last_played_at = payload.get("rule_last_played_at") or {}
        asset_last_played_at = payload.get("asset_last_played_at") or {}
        recent_asset_history = payload.get("recent_asset_history") or []
        rule_asset_history = payload.get("rule_asset_history") or {}
        active_channel_selections = payload.get("active_channel_selections") or {}
        return cls(
            current_time_ms=int(payload.get("current_time_ms", 0)),
            rule_last_played_at={
                str(key): int(value)
                for key, value in dict(rule_last_played_at).items()
            },
            asset_last_played_at={
                str(key): int(value)
                for key, value in dict(asset_last_played_at).items()
            },
            recent_asset_history=[str(item) for item in list(recent_asset_history)],
            rule_asset_history={
                str(rule_id): [str(item) for item in list(history)]
                for rule_id, history in dict(rule_asset_history).items()
            },
            active_channel_selections={
                str(channel): [dict(item) for item in list(selections)]
                for channel, selections in dict(active_channel_selections).items()
            },
        )

    def record_selection(
        self,
        *,
        timestamp_ms: int,
        rule_id: str | None,
        asset_id: str | None,
    ) -> None:
        self.current_time_ms = timestamp_ms
        if rule_id:
            self.rule_last_played_at[rule_id] = timestamp_ms
        if asset_id:
            self.asset_last_played_at[asset_id] = timestamp_ms
            self.recent_asset_history.append(asset_id)
            if rule_id:
                if rule_id not in self.rule_asset_history:
                    self.rule_asset_history[rule_id] = []
                self.rule_asset_history[rule_id].append(asset_id)

    def record_started_selections(
        self,
        *,
        timestamp_ms: int,
        started_selections: list[dict[str, object]],
    ) -> None:
        self.current_time_ms = timestamp_ms
        for selection in started_selections:
            rule_id_raw = selection.get("selected_rule_id")
            asset_id_raw = selection.get("selected_asset_id")
            rule_id = rule_id_raw if isinstance(rule_id_raw, str) else None
            asset_id = asset_id_raw if isinstance(asset_id_raw, str) else None
            if rule_id:
                self.rule_last_played_at[rule_id] = timestamp_ms
            if asset_id:
                self.asset_last_played_at[asset_id] = timestamp_ms
                self.recent_asset_history.append(asset_id)
                if rule_id:
                    if rule_id not in self.rule_asset_history:
                        self.rule_asset_history[rule_id] = []
                    self.rule_asset_history[rule_id].append(asset_id)
