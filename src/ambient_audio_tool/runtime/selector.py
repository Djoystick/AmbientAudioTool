from __future__ import annotations

import random
from typing import Any

from .condition_eval import evaluate_condition
from .context import RuntimeContext
from .state import RuntimeState


def select_channels_stateless(
    runtime_rules: list[dict[str, Any]],
    conditions_by_id: dict[str, dict[str, Any]],
    context: RuntimeContext,
    rng: random.Random,
) -> dict[str, Any]:
    temp_state = RuntimeState()
    return select_channels_stateful(
        runtime_rules,
        conditions_by_id,
        context,
        temp_state,
        timestamp_ms=0,
        rng=rng,
    )


def select_channels_stateful(
    runtime_rules: list[dict[str, Any]],
    conditions_by_id: dict[str, dict[str, Any]],
    context: RuntimeContext,
    state: RuntimeState,
    *,
    timestamp_ms: int,
    rng: random.Random,
) -> dict[str, Any]:
    condition_cache: dict[str, bool] = {}
    candidates_by_channel: dict[str, list[dict[str, Any]]] = {}

    for rule in runtime_rules:
        if not rule.get("enabled", True):
            continue

        rule_id = rule.get("id")
        if not isinstance(rule_id, str):
            continue

        channel = rule.get("channel")
        if not isinstance(channel, str) or not channel:
            continue

        condition_ref = rule.get("condition_ref")
        if not isinstance(condition_ref, str):
            continue
        if not evaluate_condition(condition_ref, conditions_by_id, context, condition_cache):
            continue

        priority = rule.get("priority")
        if not isinstance(priority, dict):
            priority = {}
        randomness = rule.get("randomness")
        if not isinstance(randomness, dict):
            randomness = {}
        cooldown = rule.get("cooldown")
        if not isinstance(cooldown, dict):
            cooldown = {}
        conflict = rule.get("conflict")
        if not isinstance(conflict, dict):
            conflict = {}

        probability = _as_float(randomness.get("probability"), 1.0)
        if probability <= 0:
            continue
        if probability < 1.0 and rng.random() > probability:
            continue

        rule_cooldown_ms = max(0, _as_int(cooldown.get("rule_cooldown_ms"), 0))
        if _is_in_cooldown(
            timestamp_ms,
            state.rule_last_played_at.get(rule_id),
            rule_cooldown_ms,
        ):
            continue

        asset_ids = rule.get("asset_ids", [])
        if not isinstance(asset_ids, list):
            asset_ids = []
        asset_ids = [asset_id for asset_id in asset_ids if isinstance(asset_id, str)]
        if not asset_ids:
            continue

        asset_cooldown_ms = max(0, _as_int(cooldown.get("asset_cooldown_ms"), 0))
        cooldown_eligible_assets = [
            asset_id
            for asset_id in asset_ids
            if not _is_in_cooldown(
                timestamp_ms,
                state.asset_last_played_at.get(asset_id),
                asset_cooldown_ms,
            )
        ]
        if not cooldown_eligible_assets:
            continue

        no_repeat_window = max(0, _as_int(randomness.get("no_repeat_window"), 0))
        final_assets = cooldown_eligible_assets
        no_repeat_applied = False
        if no_repeat_window > 0 and len(cooldown_eligible_assets) > 1:
            rule_recent_history = state.rule_asset_history.get(rule_id, [])
            preferred_assets = [
                asset_id
                for asset_id in cooldown_eligible_assets
                if not _was_played_recently(
                    rule_recent_history,
                    asset_id,
                    no_repeat_window,
                )
            ]
            if preferred_assets:
                no_repeat_applied = len(preferred_assets) != len(cooldown_eligible_assets)
                final_assets = preferred_assets

        base_priority = _as_int(priority.get("base_priority"), 50)
        weight = max(1, _as_int(randomness.get("weight"), 1))
        tie_breaker = conflict.get("tie_breaker")
        if not isinstance(tie_breaker, str):
            tie_breaker = "priority_then_weight"
        if tie_breaker not in {"priority_then_weight", "priority_then_oldest"}:
            tie_breaker = "priority_then_weight"
        max_concurrent = max(1, _as_int(conflict.get("max_concurrent"), 1))
        can_preempt_lower_priority = bool(conflict.get("can_preempt_lower_priority", False))

        candidate_reason = "selected"
        if len(cooldown_eligible_assets) != len(asset_ids):
            candidate_reason = "selected_after_cooldown_filter"
        elif no_repeat_applied:
            candidate_reason = "selected_after_no_repeat_filter"

        candidate = {
            "channel": channel,
            "rule_id": rule_id,
            "base_priority": base_priority,
            "weight": weight,
            "eligible_assets": final_assets,
            "last_played_at": state.rule_last_played_at.get(rule_id),
            "max_concurrent": max_concurrent,
            "tie_breaker": tie_breaker,
            "can_preempt_lower_priority": can_preempt_lower_priority,
            "reason": candidate_reason,
        }
        if channel not in candidates_by_channel:
            candidates_by_channel[channel] = []
        candidates_by_channel[channel].append(candidate)

    all_channels = sorted(
        set(candidates_by_channel.keys()) | set(state.active_channel_selections.keys())
    )
    selections: list[dict[str, object]] = []
    started_selections: list[dict[str, object]] = []
    new_active_channel_selections: dict[str, list[dict[str, object]]] = {}

    for channel in all_channels:
        channel_candidates = candidates_by_channel.get(channel, [])
        existing_active = _state_items_to_internal(
            state.active_channel_selections.get(channel, []),
            fallback_channel=channel,
        )
        proposed = _select_proposed_for_channel(channel_candidates, rng)

        final_channel_selections, started_channel_selections = _apply_channel_preemption(
            existing_active,
            proposed,
        )

        if final_channel_selections:
            new_active_channel_selections[channel] = [
                _selection_to_state_item(item) for item in final_channel_selections
            ]
            selections.extend(_strip_internal_fields(item) for item in final_channel_selections)
        if started_channel_selections:
            started_selections.extend(
                _strip_internal_fields(item) for item in started_channel_selections
            )

    return {
        "selections": selections,
        "started_selections": started_selections,
        "active_channel_selections": new_active_channel_selections,
    }


def select_rule_and_asset(
    runtime_rules: list[dict[str, Any]],
    conditions_by_id: dict[str, dict[str, Any]],
    context: RuntimeContext,
    rng: random.Random,
) -> dict[str, str | None]:
    channel_result = select_channels_stateless(
        runtime_rules,
        conditions_by_id,
        context,
        rng,
    )
    selections = channel_result.get("selections", [])
    if not selections:
        return {
            "selected_rule_id": None,
            "selected_asset_id": None,
            "reason": "no_match",
        }
    first = selections[0]
    return {
        "selected_rule_id": first.get("selected_rule_id"),
        "selected_asset_id": first.get("selected_asset_id"),
        "reason": first.get("reason"),
    }


def select_rule_and_asset_stateful(
    runtime_rules: list[dict[str, Any]],
    conditions_by_id: dict[str, dict[str, Any]],
    context: RuntimeContext,
    state: RuntimeState,
    *,
    timestamp_ms: int,
    rng: random.Random,
) -> dict[str, str | None]:
    channel_result = select_channels_stateful(
        runtime_rules,
        conditions_by_id,
        context,
        state,
        timestamp_ms=timestamp_ms,
        rng=rng,
    )
    selections = channel_result.get("selections", [])
    if not selections:
        return {
            "selected_rule_id": None,
            "selected_asset_id": None,
            "reason": "no_match",
        }
    first = selections[0]
    return {
        "selected_rule_id": first.get("selected_rule_id"),
        "selected_asset_id": first.get("selected_asset_id"),
        "reason": first.get("reason"),
    }


def _select_proposed_for_channel(
    channel_candidates: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, object]]:
    if not channel_candidates:
        return []

    policy_sorted = sorted(
        channel_candidates,
        key=lambda item: (-item["base_priority"], item["rule_id"]),
    )
    policy = policy_sorted[0]
    tie_breaker = policy["tie_breaker"]
    max_concurrent = max(1, policy["max_concurrent"])

    ranked = sorted(
        channel_candidates,
        key=lambda item: _channel_sort_key(item, tie_breaker),
    )
    top_ranked = ranked[:max_concurrent]

    proposed: list[dict[str, object]] = []
    for candidate in top_ranked:
        selected_asset_id = (
            rng.choice(candidate["eligible_assets"]) if candidate["eligible_assets"] else None
        )
        proposed.append(
            {
                "channel": candidate["channel"],
                "selected_rule_id": candidate["rule_id"],
                "selected_asset_id": selected_asset_id,
                "reason": candidate["reason"],
                "_base_priority": candidate["base_priority"],
                "_can_preempt_lower_priority": candidate["can_preempt_lower_priority"],
                "_max_concurrent": max_concurrent,
            }
        )
    return proposed


def _apply_channel_preemption(
    existing_active: list[dict[str, object]],
    proposed: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not existing_active:
        return proposed, proposed

    if not proposed:
        kept = []
        for item in existing_active:
            updated = dict(item)
            updated["reason"] = "kept_previous_no_candidates"
            kept.append(updated)
        return kept, []

    max_concurrent = max(1, _as_int(proposed[0].get("_max_concurrent"), 1))
    proposed = proposed[:max_concurrent]
    existing_active = existing_active[:max_concurrent]

    existing_rule_ids = [
        item.get("selected_rule_id")
        for item in existing_active
        if isinstance(item.get("selected_rule_id"), str)
    ]
    proposed_rule_ids = [
        item.get("selected_rule_id")
        for item in proposed
        if isinstance(item.get("selected_rule_id"), str)
    ]
    if existing_rule_ids == proposed_rule_ids:
        # Same rule-set on the channel: allow refreshed selection (asset/cooldown/no-repeat updates).
        return proposed, proposed

    new_priority = max(_as_int(item.get("_base_priority"), 0) for item in proposed)
    existing_priority = max(
        _as_int(item.get("_base_priority"), 0) for item in existing_active
    )
    can_preempt = any(
        _as_int(item.get("_base_priority"), 0) == new_priority
        and bool(item.get("_can_preempt_lower_priority"))
        for item in proposed
    )

    if new_priority > existing_priority and can_preempt:
        replaced = []
        for item in proposed:
            updated = dict(item)
            updated["reason"] = "preempted_by_higher_priority"
            replaced.append(updated)
        return replaced, replaced

    kept = []
    for item in existing_active:
        updated = dict(item)
        updated["reason"] = "kept_previous_no_preemption"
        kept.append(updated)
    return kept, []


def _state_items_to_internal(
    state_items: list[dict[str, object]],
    *,
    fallback_channel: str,
) -> list[dict[str, object]]:
    internal: list[dict[str, object]] = []
    for state_item in state_items:
        internal.append(
            {
                "channel": state_item.get("channel", fallback_channel),
                "selected_rule_id": state_item.get("selected_rule_id"),
                "selected_asset_id": state_item.get("selected_asset_id"),
                "reason": "kept_previous",
                "_base_priority": _as_int(state_item.get("base_priority"), 0),
                "_can_preempt_lower_priority": bool(
                    state_item.get("can_preempt_lower_priority", False)
                ),
                "_max_concurrent": max(1, _as_int(state_item.get("max_concurrent"), 1)),
            }
        )
    return internal


def _selection_to_state_item(selection: dict[str, object]) -> dict[str, object]:
    return {
        "channel": selection.get("channel"),
        "selected_rule_id": selection.get("selected_rule_id"),
        "selected_asset_id": selection.get("selected_asset_id"),
        "base_priority": _as_int(selection.get("_base_priority"), 0),
        "can_preempt_lower_priority": bool(
            selection.get("_can_preempt_lower_priority", False)
        ),
        "max_concurrent": max(1, _as_int(selection.get("_max_concurrent"), 1)),
    }


def _strip_internal_fields(selection: dict[str, object]) -> dict[str, object]:
    return {
        "channel": selection.get("channel"),
        "selected_rule_id": selection.get("selected_rule_id"),
        "selected_asset_id": selection.get("selected_asset_id"),
        "reason": selection.get("reason"),
    }


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _channel_sort_key(
    candidate: dict[str, Any],
    tie_breaker: str,
) -> tuple[object, ...]:
    if tie_breaker == "priority_then_oldest":
        return (
            -candidate["base_priority"],
            _oldest_sort_key(candidate.get("last_played_at")),
            -candidate["weight"],
            candidate["rule_id"],
        )
    return (
        -candidate["base_priority"],
        -candidate["weight"],
        _oldest_sort_key(candidate.get("last_played_at")),
        candidate["rule_id"],
    )


def _oldest_sort_key(last_played_at: Any) -> int:
    if last_played_at is None:
        return -1
    return _as_int(last_played_at, 0)


def _is_in_cooldown(
    now_ms: int,
    last_played_at_ms: int | None,
    cooldown_ms: int,
) -> bool:
    if cooldown_ms <= 0:
        return False
    if last_played_at_ms is None:
        return False
    return (now_ms - last_played_at_ms) < cooldown_ms


def _was_played_recently(
    recent_asset_history: list[str],
    asset_id: str,
    no_repeat_window: int,
) -> bool:
    if no_repeat_window <= 0:
        return False
    if not recent_asset_history:
        return False
    recent_window = recent_asset_history[-no_repeat_window:]
    return asset_id in recent_window
