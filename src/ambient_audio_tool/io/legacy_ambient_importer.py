from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GROUP_TO_CHANNEL = {
    "music": "music",
    "noise": "ambient_noise",
    "sounds": "context_oneshot",
}


@dataclass(frozen=True)
class LegacyImportResult:
    project_payload: dict[str, Any]
    warnings: list[str]


def import_ambient_config(
    ambient_config: dict[str, Any],
    *,
    source_path: str | Path,
) -> LegacyImportResult:
    warnings: list[str] = []
    source = Path(source_path)
    used_asset_ids: set[str] = set()
    used_condition_ids: set[str] = set()
    used_rule_ids: set[str] = set()
    event_asset_map: dict[str, str] = {}

    assets: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []

    ambient_defs_raw = ambient_config.get("ambient_sound_definitions")
    if not isinstance(ambient_defs_raw, dict):
        warnings.append(
            "Legacy config is missing 'ambient_sound_definitions'. "
            "Imported project will contain no rules."
        )
        ambient_defs: dict[str, Any] = {}
    else:
        ambient_defs = ambient_defs_raw

    always_condition_id: str | None = None

    def ensure_always_condition() -> str:
        nonlocal always_condition_id
        if always_condition_id is not None:
            return always_condition_id
        always_condition_id = _unique_id("expr_legacy_always_true", used_condition_ids)
        conditions.append(
            {
                "id": always_condition_id,
                "name": "Legacy always-true condition",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "time_between", "start_hour": 0, "end_hour": 23},
                },
            }
        )
        return always_condition_id

    for scope_key, scope_value in ambient_defs.items():
        if not isinstance(scope_value, dict):
            warnings.append(f"Scope '{scope_key}' is not an object and was skipped.")
            continue

        events_value = scope_value.get("events")
        if events_value is not None and not isinstance(events_value, dict):
            warnings.append(f"{scope_key}.events is not an object and was ignored.")
            events_groups: dict[str, Any] = {}
        elif isinstance(events_value, dict):
            events_groups = events_value
        else:
            events_groups = {}

        biome_node: dict[str, Any] | None = None
        if scope_key != "global":
            biome_node = {
                "op": "PRED",
                "predicate": {"type": "biome_is", "biome": str(scope_key)},
            }

        scope_filter_node = _parse_legacy_filter(
            scope_value.get("filter"),
            warnings,
            context=f"{scope_key}.filter",
        )

        for legacy_group, channel in GROUP_TO_CHANNEL.items():
            entries: list[dict[str, Any]] = []
            if legacy_group in scope_value:
                entries.extend(
                    _coerce_legacy_entries(
                        scope_value.get(legacy_group),
                        warnings,
                        context=f"{scope_key}.{legacy_group}",
                    )
                )
            if legacy_group in events_groups:
                entries.extend(
                    _coerce_legacy_entries(
                        events_groups.get(legacy_group),
                        warnings,
                        context=f"{scope_key}.events.{legacy_group}",
                    )
                )
            if not entries:
                continue

            for index, entry in enumerate(entries, start=1):
                source_sound = (
                    entry.get("source_sound") if isinstance(entry.get("source_sound"), dict) else {}
                )
                event_name_raw = source_sound.get("event_name") or entry.get("event_name")
                event_name = str(event_name_raw).strip() if event_name_raw else ""
                if not event_name:
                    event_name = f"legacy_event_{len(event_asset_map) + 1}"
                    warnings.append(
                        f"{scope_key}.{legacy_group}[{index}] has no event_name; "
                        f"generated '{event_name}'."
                    )

                asset_id = event_asset_map.get(event_name)
                if asset_id is None:
                    asset_id = _unique_id(f"asset_{_slug(event_name)}", used_asset_ids)
                    event_asset_map[event_name] = asset_id
                    path_value = (
                        source_sound.get("path")
                        or source_sound.get("file_path")
                        or source_sound.get("asset_path")
                    )
                    if not isinstance(path_value, str) or not path_value.strip():
                        path_value = f"legacy/{event_name}.ogg"
                        warnings.append(
                            f"Placeholder asset path created for event '{event_name}'."
                        )
                    duration_ms = _seconds_to_ms(source_sound.get("length_seconds"))
                    assets.append(
                        {
                            "id": asset_id,
                            "path": path_value,
                            "duration_ms": duration_ms,
                            "tags": ["legacy_import"],
                        }
                    )

                min_delay_ms = _seconds_to_ms(source_sound.get("min_delay_seconds")) or 0
                max_delay_ms = _seconds_to_ms(source_sound.get("max_delay_seconds")) or 0
                if max_delay_ms < min_delay_ms:
                    max_delay_ms = min_delay_ms
                    warnings.append(
                        f"{scope_key}.{legacy_group}[{index}] had max_delay < min_delay; "
                        "max_delay was adjusted."
                    )

                entry_filter_node = _parse_legacy_filter(
                    entry.get("filter"),
                    warnings,
                    context=f"{scope_key}.{legacy_group}[{index}].filter",
                )
                combined_nodes = [
                    node
                    for node in (biome_node, scope_filter_node, entry_filter_node)
                    if node is not None
                ]

                if not combined_nodes:
                    condition_ref = ensure_always_condition()
                else:
                    if len(combined_nodes) == 1:
                        root_node = combined_nodes[0]
                    else:
                        root_node = {"op": "ALL", "nodes": combined_nodes}
                    condition_id = _unique_id(
                        f"expr_legacy_{channel}_{scope_key}_{index}",
                        used_condition_ids,
                    )
                    conditions.append(
                        {
                            "id": condition_id,
                            "name": f"Legacy imported condition {scope_key} {legacy_group} #{index}",
                            "root": root_node,
                        }
                    )
                    condition_ref = condition_id

                weight = _coerce_int(entry.get("weight"), default=50)
                if weight <= 0:
                    weight = 1

                rule_id = _unique_id(
                    f"rule_legacy_{channel}_{scope_key}_{_slug(event_name)}_{index}",
                    used_rule_ids,
                )
                rules.append(
                    {
                        "id": rule_id,
                        "name": f"Legacy {legacy_group} {event_name}",
                        "enabled": True,
                        "channel": channel,
                        "condition_ref": condition_ref,
                        "asset_ids": [asset_id],
                        "priority": {
                            "base_priority": weight,
                            "contextual_boosts": {},
                            "suppression_threshold": 0,
                        },
                        "randomness": {
                            "probability": 1.0,
                            "weight": 1,
                            "no_repeat_window": 0,
                            "jitter_ms": 0,
                            "rotation_pool": None,
                        },
                        "cooldown": {
                            "rule_cooldown_ms": 0,
                            "asset_cooldown_ms": 0,
                            "min_delay_ms": min_delay_ms,
                            "max_delay_ms": max_delay_ms,
                        },
                        "conflict": {
                            "scope": "channel",
                            "max_concurrent": 1,
                            "tie_breaker": "priority_then_weight",
                            "can_preempt_lower_priority": False,
                        },
                    }
                )

    project_payload: dict[str, Any] = {
        "project_id": _unique_id(f"legacy_{_slug(source.stem)}", set()),
        "project_name": f"Imported Legacy Ambient Config ({source.stem})",
        "version": "1.0",
        "audio_assets": assets,
        "biome_groups": [],
        "custom_events": [],
        "conditions": conditions,
        "rules": rules,
    }
    if not rules:
        warnings.append("Legacy import produced no rules.")

    return LegacyImportResult(project_payload=project_payload, warnings=warnings)


def _coerce_legacy_entries(
    value: Any,
    warnings: list[str],
    *,
    context: str,
) -> list[dict[str, Any]]:
    if isinstance(value, list):
        entries = [item for item in value if isinstance(item, dict)]
        if len(entries) != len(value):
            warnings.append(f"{context} contains non-object entries that were skipped.")
        return entries

    if isinstance(value, dict):
        if "events" in value:
            return _coerce_legacy_entries(value["events"], warnings, context=f"{context}.events")
        if "entries" in value:
            return _coerce_legacy_entries(value["entries"], warnings, context=f"{context}.entries")
        if "source_sound" in value or "event_name" in value:
            return [value]
        nested_entries = [item for item in value.values() if isinstance(item, dict)]
        if nested_entries:
            return nested_entries
        warnings.append(f"{context} has no recognizable event entries.")
        return []

    warnings.append(f"{context} is not a list/object and was skipped.")
    return []


def _parse_legacy_filter(
    filter_value: Any,
    warnings: list[str],
    *,
    context: str,
) -> dict[str, Any] | None:
    if filter_value is None:
        return None
    if isinstance(filter_value, list):
        children = [
            _parse_legacy_filter(item, warnings, context=f"{context}[{index}]")
            for index, item in enumerate(filter_value, start=1)
        ]
        valid_children = [item for item in children if item is not None]
        if not valid_children:
            warnings.append(f"{context} filter list had no supported conditions.")
            return None
        if len(valid_children) == 1:
            return valid_children[0]
        return {"op": "ALL", "nodes": valid_children}

    if not isinstance(filter_value, dict):
        warnings.append(f"{context} filter is not an object and was ignored.")
        return None

    if "all_of" in filter_value:
        all_of = filter_value.get("all_of")
        if not isinstance(all_of, list):
            warnings.append(f"{context}.all_of is not a list and was ignored.")
            return None
        children = [
            _parse_legacy_filter(item, warnings, context=f"{context}.all_of[{index}]")
            for index, item in enumerate(all_of, start=1)
        ]
        valid_children = [item for item in children if item is not None]
        if not valid_children:
            warnings.append(f"{context}.all_of had no supported conditions.")
            return None
        if len(valid_children) == 1:
            return valid_children[0]
        return {"op": "ALL", "nodes": valid_children}

    if "any_of" in filter_value:
        any_of = filter_value.get("any_of")
        if not isinstance(any_of, list):
            warnings.append(f"{context}.any_of is not a list and was ignored.")
            return None
        children = [
            _parse_legacy_filter(item, warnings, context=f"{context}.any_of[{index}]")
            for index, item in enumerate(any_of, start=1)
        ]
        valid_children = [item for item in children if item is not None]
        if not valid_children:
            warnings.append(f"{context}.any_of had no supported conditions.")
            return None
        if len(valid_children) == 1:
            return valid_children[0]
        return {"op": "ANY", "nodes": valid_children}

    if "test" not in filter_value:
        warnings.append(f"{context} filter object missing 'test' and was ignored.")
        return None

    test_name = str(filter_value.get("test"))
    operator = str(filter_value.get("operator", "=="))
    value = filter_value.get("value")

    if test_name == "is_day":
        return _map_is_day_filter(operator, value, warnings, context=context)

    if test_name in {"height", "distance_from_spawn_point"}:
        warnings.append(
            f"{context}: test '{test_name}' is not supported in this importer and was skipped."
        )
        return None

    warnings.append(f"{context}: unsupported legacy test '{test_name}' was skipped.")
    return None


def _map_is_day_filter(
    operator: str,
    value: Any,
    warnings: list[str],
    *,
    context: str,
) -> dict[str, Any] | None:
    normalized_operator = operator.strip()
    if normalized_operator not in {"==", "=", "!=", "not"}:
        warnings.append(f"{context}: unsupported operator '{operator}' for is_day.")
        return None

    if isinstance(value, bool):
        is_day_value = value
    elif isinstance(value, (int, float)):
        is_day_value = bool(value)
    else:
        warnings.append(f"{context}: is_day value is missing/invalid.")
        return None

    if normalized_operator in {"!=", "not"}:
        is_day_value = not is_day_value

    if is_day_value:
        return {
            "op": "PRED",
            "predicate": {"type": "time_between", "start_hour": 6, "end_hour": 17},
        }

    return {
        "op": "ANY",
        "nodes": [
            {
                "op": "PRED",
                "predicate": {"type": "time_between", "start_hour": 18, "end_hour": 23},
            },
            {
                "op": "PRED",
                "predicate": {"type": "time_between", "start_hour": 0, "end_hour": 5},
            },
        ],
    }


def _seconds_to_ms(value: Any) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return int(round(float(value) * 1000))


def _coerce_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except Exception:
        return default


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "item"


def _unique_id(base: str, used: set[str]) -> str:
    candidate = _slug(base)
    if candidate not in used:
        used.add(candidate)
        return candidate
    index = 2
    while True:
        attempt = f"{candidate}_{index}"
        if attempt not in used:
            used.add(attempt)
            return attempt
        index += 1
