from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ambient_audio_tool.models import (
    AllNode,
    AnyNode,
    AuthoringProject,
    BiomeIsPredicate,
    ConditionExpression,
    ConditionNode,
    CustomEventPredicate,
    DangerStateIsPredicate,
    IsUndergroundPredicate,
    IsUnderwaterPredicate,
    NotNode,
    PlayerHealthRangePredicate,
    PredicateNode,
    RefNode,
    TimeBetweenPredicate,
    WeatherIsPredicate,
)


CHANNEL_TO_LEGACY_GROUP = {
    "music": "music",
    "ambient_noise": "noise",
    "context_oneshot": "sounds",
    "event_alert": "sounds",
}


@dataclass(frozen=True)
class LegacyAmbientExportResult:
    source: str
    ambient_config: dict[str, Any]
    warnings: list[str]


def render_legacy_ambient_config_source(
    project: AuthoringProject | dict[str, Any],
) -> LegacyAmbientExportResult:
    authoring_project = _to_project(project)
    warnings: list[str] = []
    condition_map = {expr.id: expr for expr in authoring_project.conditions}
    asset_map = {asset.id: asset for asset in authoring_project.audio_assets}

    scoped_groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    sorted_rules = sorted(authoring_project.rules, key=lambda rule: rule.id)
    for rule in sorted_rules:
        group = CHANNEL_TO_LEGACY_GROUP.get(rule.channel.value)
        if group is None:
            _add_warning(
                warnings,
                f"Rule '{rule.id}' has unsupported channel '{rule.channel.value}' and was skipped.",
            )
            continue
        if rule.channel.value == "event_alert":
            _add_warning(
                warnings,
                f"Rule '{rule.id}' channel 'event_alert' was downgraded to legacy 'sounds' group.",
            )

        condition_expr = condition_map.get(rule.condition_ref)
        if condition_expr is None:
            _add_warning(
                warnings,
                f"Rule '{rule.id}' references missing condition '{rule.condition_ref}' and was skipped.",
            )
            continue

        expanded = _expand_refs(condition_expr.root, condition_map, set(), warnings, rule.id)
        scope_biome = _extract_single_biome_scope(expanded, warnings, rule.id)
        legacy_filter = _to_legacy_filter(
            expanded,
            warnings,
            context=f"rule '{rule.id}'",
            drop_scoped_biome=scope_biome,
        )
        scope_key = scope_biome or "global"
        scope_bucket = scoped_groups.setdefault(scope_key, {})
        entry_list = scope_bucket.setdefault(group, [])

        if len(rule.asset_ids) > 1:
            _add_warning(
                warnings,
                f"Rule '{rule.id}' has {len(rule.asset_ids)} assets and was split into multiple legacy entries.",
            )

        for asset_id in rule.asset_ids:
            asset = asset_map.get(asset_id)
            if asset is None:
                _add_warning(
                    warnings,
                    f"Rule '{rule.id}' references missing asset '{asset_id}'. A placeholder source_sound was used.",
                )
            entry = _build_legacy_entry(
                _rule_id=rule.id,
                base_priority=rule.priority.base_priority,
                asset_id=asset_id,
                asset=asset,
                min_delay_ms=rule.cooldown.min_delay_ms,
                max_delay_ms=rule.cooldown.max_delay_ms,
            )
            if legacy_filter is not None:
                entry["filter"] = legacy_filter
            entry_list.append(entry)

    ambient_sound_definitions: dict[str, Any] = {}
    scope_order = sorted(scoped_groups.keys(), key=lambda scope: (scope != "global", scope))
    group_order = ["music", "noise", "sounds"]
    for scope in scope_order:
        groups = scoped_groups[scope]
        scope_payload: dict[str, Any] = {}
        for group in group_order:
            if group in groups and groups[group]:
                scope_payload[group] = groups[group]
        if scope_payload:
            ambient_sound_definitions[scope] = scope_payload

    if not ambient_sound_definitions:
        ambient_sound_definitions["global"] = {}
        _add_warning(
            warnings,
            "Legacy export produced no playable entries. Output contains empty global definitions.",
        )

    ambient_config = {"ambient_sound_definitions": ambient_sound_definitions}
    json_text = json.dumps(ambient_config, indent=2, ensure_ascii=False)
    source = f"export const AMBIENT_CONFIG = {json_text};\n"
    return LegacyAmbientExportResult(
        source=source,
        ambient_config=ambient_config,
        warnings=warnings,
    )


def write_legacy_ambient_config_source(
    project: AuthoringProject | dict[str, Any],
    output_path: str | Path,
) -> LegacyAmbientExportResult:
    result = render_legacy_ambient_config_source(project)
    target = Path(output_path)
    target.write_text(result.source, encoding="utf-8")
    return result


def _to_project(project: AuthoringProject | dict[str, Any]) -> AuthoringProject:
    if isinstance(project, AuthoringProject):
        return project
    if isinstance(project, dict):
        return AuthoringProject.model_validate(project)
    raise TypeError("project must be AuthoringProject or dict payload.")


def _add_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _expand_refs(
    node: ConditionNode,
    condition_map: dict[str, ConditionExpression],
    stack: set[str],
    warnings: list[str],
    rule_id: str,
) -> ConditionNode:
    if isinstance(node, RefNode):
        if node.ref_id in stack:
            _add_warning(
                warnings,
                f"Rule '{rule_id}' contains cyclic condition ref '{node.ref_id}'. Ref was skipped.",
            )
            return PredicateNode(
                op="PRED",
                predicate=TimeBetweenPredicate(type="time_between", start_hour=0, end_hour=23),
            )
        target = condition_map.get(node.ref_id)
        if target is None:
            _add_warning(
                warnings,
                f"Rule '{rule_id}' references missing expression '{node.ref_id}'. Ref was skipped.",
            )
            return PredicateNode(
                op="PRED",
                predicate=TimeBetweenPredicate(type="time_between", start_hour=0, end_hour=23),
            )
        stack.add(node.ref_id)
        expanded = _expand_refs(target.root, condition_map, stack, warnings, rule_id)
        stack.remove(node.ref_id)
        return expanded

    if isinstance(node, AllNode):
        return AllNode(
            op="ALL",
            nodes=[_expand_refs(item, condition_map, stack, warnings, rule_id) for item in node.nodes],
        )
    if isinstance(node, AnyNode):
        return AnyNode(
            op="ANY",
            nodes=[_expand_refs(item, condition_map, stack, warnings, rule_id) for item in node.nodes],
        )
    if isinstance(node, NotNode):
        return NotNode(
            op="NOT",
            node=_expand_refs(node.node, condition_map, stack, warnings, rule_id),
        )
    return node


def _extract_single_biome_scope(
    node: ConditionNode,
    warnings: list[str],
    rule_id: str,
) -> str | None:
    biomes = sorted(_collect_biome_values(node))
    if not biomes:
        return None
    if len(biomes) > 1:
        _add_warning(
            warnings,
            f"Rule '{rule_id}' contains multiple biome_is predicates ({', '.join(biomes)}). Exported under global scope.",
        )
        return None
    return biomes[0]


def _collect_biome_values(node: ConditionNode) -> set[str]:
    values: set[str] = set()
    if isinstance(node, PredicateNode) and isinstance(node.predicate, BiomeIsPredicate):
        values.add(node.predicate.biome)
        return values
    if isinstance(node, (AllNode, AnyNode)):
        for item in node.nodes:
            values.update(_collect_biome_values(item))
    elif isinstance(node, NotNode):
        values.update(_collect_biome_values(node.node))
    return values


def _to_legacy_filter(
    node: ConditionNode,
    warnings: list[str],
    *,
    context: str,
    drop_scoped_biome: str | None,
) -> dict[str, Any] | None:
    if isinstance(node, AllNode):
        children = [
            _to_legacy_filter(
                child,
                warnings,
                context=context,
                drop_scoped_biome=drop_scoped_biome,
            )
            for child in node.nodes
        ]
        valid = [item for item in children if item is not None]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]
        return {"all_of": valid}

    if isinstance(node, AnyNode):
        children = [
            _to_legacy_filter(
                child,
                warnings,
                context=context,
                drop_scoped_biome=drop_scoped_biome,
            )
            for child in node.nodes
        ]
        valid = [item for item in children if item is not None]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]
        return {"any_of": valid}

    if isinstance(node, NotNode):
        _add_warning(
            warnings,
            f"{context}: NOT node is unsupported in legacy format and was skipped.",
        )
        return None

    if isinstance(node, PredicateNode):
        return _predicate_to_legacy_filter(
            node.predicate,
            warnings,
            context=context,
            drop_scoped_biome=drop_scoped_biome,
        )

    _add_warning(warnings, f"{context}: REF node remained unresolved and was skipped.")
    return None


def _predicate_to_legacy_filter(
    predicate: Any,
    warnings: list[str],
    *,
    context: str,
    drop_scoped_biome: str | None,
) -> dict[str, Any] | None:
    if isinstance(predicate, BiomeIsPredicate):
        if drop_scoped_biome is not None and predicate.biome == drop_scoped_biome:
            return None
        _add_warning(
            warnings,
            f"{context}: biome_is predicate could not be represented in legacy filter and was skipped.",
        )
        return None

    if isinstance(predicate, TimeBetweenPredicate):
        if predicate.start_hour == 6 and predicate.end_hour == 17:
            return {"test": "is_day", "operator": "==", "value": True}
        _add_warning(
            warnings,
            f"{context}: time_between {predicate.start_hour}-{predicate.end_hour} is not directly representable in legacy filter.",
        )
        return None

    unsupported_label = type(predicate).__name__
    if isinstance(predicate, WeatherIsPredicate):
        unsupported_label = "weather_is"
    elif isinstance(predicate, PlayerHealthRangePredicate):
        unsupported_label = "player_health_range"
    elif isinstance(predicate, IsUnderwaterPredicate):
        unsupported_label = "is_underwater"
    elif isinstance(predicate, IsUndergroundPredicate):
        unsupported_label = "is_underground"
    elif isinstance(predicate, DangerStateIsPredicate):
        unsupported_label = "danger_state_is"
    elif isinstance(predicate, CustomEventPredicate):
        unsupported_label = "custom_event"

    _add_warning(
        warnings,
        f"{context}: unsupported predicate '{unsupported_label}' was skipped during legacy downgrade.",
    )
    return None


def _build_legacy_entry(
    _rule_id: str,
    base_priority: int,
    asset_id: str,
    asset: Any,
    min_delay_ms: int,
    max_delay_ms: int,
) -> dict[str, Any]:
    source_sound: dict[str, Any] = {
        "event_name": asset_id,
    }
    if asset is None:
        source_sound["path"] = f"legacy/{asset_id}.ogg"
    else:
        source_sound["path"] = asset.path
        if asset.duration_ms is not None:
            source_sound["length_seconds"] = round(asset.duration_ms / 1000, 3)
    source_sound["min_delay_seconds"] = round(min_delay_ms / 1000, 3)
    source_sound["max_delay_seconds"] = round(max_delay_ms / 1000, 3)

    return {
        "weight": max(1, int(base_priority)),
        "source_sound": source_sound,
    }
