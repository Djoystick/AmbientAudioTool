from __future__ import annotations

from typing import Any

from .context import RuntimeContext


def evaluate_condition(
    condition_id: str,
    conditions_by_id: dict[str, dict[str, Any]],
    context: RuntimeContext,
    cache: dict[str, bool] | None = None,
    active_stack: set[str] | None = None,
) -> bool:
    if cache is None:
        cache = {}
    if active_stack is None:
        active_stack = set()

    if condition_id in cache:
        return cache[condition_id]
    if condition_id in active_stack:
        # Cycles should already be blocked by validation, but fail safely.
        return False

    condition = conditions_by_id.get(condition_id)
    if condition is None:
        return False

    active_stack.add(condition_id)
    result = evaluate_node(condition.get("root", {}), conditions_by_id, context, cache, active_stack)
    active_stack.remove(condition_id)

    cache[condition_id] = result
    return result


def evaluate_node(
    node: dict[str, Any],
    conditions_by_id: dict[str, dict[str, Any]],
    context: RuntimeContext,
    cache: dict[str, bool],
    active_stack: set[str],
) -> bool:
    op = node.get("op")
    if op == "ALL":
        children = node.get("nodes", [])
        return all(
            evaluate_node(child, conditions_by_id, context, cache, active_stack)
            for child in children
        )
    if op == "ANY":
        children = node.get("nodes", [])
        return any(
            evaluate_node(child, conditions_by_id, context, cache, active_stack)
            for child in children
        )
    if op == "NOT":
        return not evaluate_node(
            node.get("node", {}),
            conditions_by_id,
            context,
            cache,
            active_stack,
        )
    if op == "REF":
        ref_id = node.get("ref_id")
        if not isinstance(ref_id, str):
            return False
        return evaluate_condition(ref_id, conditions_by_id, context, cache, active_stack)
    if op == "PRED":
        predicate = node.get("predicate", {})
        if not isinstance(predicate, dict):
            return False
        return evaluate_predicate(predicate, context)
    return False


def evaluate_predicate(predicate: dict[str, Any], context: RuntimeContext) -> bool:
    predicate_type = predicate.get("type")
    if predicate_type == "biome_is":
        biome = predicate.get("biome")
        return isinstance(biome, str) and context.biome == biome
    if predicate_type == "time_between":
        start_hour = predicate.get("start_hour")
        end_hour = predicate.get("end_hour")
        if not isinstance(start_hour, int) or not isinstance(end_hour, int):
            return False
        if start_hour <= end_hour:
            return start_hour <= context.time <= end_hour
        return context.time >= start_hour or context.time <= end_hour
    if predicate_type == "weather_is":
        weather = predicate.get("weather")
        return isinstance(weather, str) and context.weather == weather
    if predicate_type == "player_health_range":
        min_health = predicate.get("min_health")
        max_health = predicate.get("max_health")
        if not isinstance(min_health, (int, float)) or not isinstance(
            max_health, (int, float)
        ):
            return False
        return min_health <= context.player_health <= max_health
    return False
