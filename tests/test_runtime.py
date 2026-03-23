from __future__ import annotations

from ambient_audio_tool.runtime import (
    RuntimeContext,
    RuntimeState,
    evaluate_condition,
    simulate_from_runtime_bundle,
    simulate_stateful_step,
    simulate_timeline,
)


def _selection_rules(result: dict[str, object]) -> set[str]:
    selections = result.get("selections", [])
    return {
        item.get("selected_rule_id")
        for item in selections
        if isinstance(item, dict) and isinstance(item.get("selected_rule_id"), str)
    }


def _selection_for_rule(result: dict[str, object], rule_id: str) -> dict[str, object] | None:
    for item in result.get("selections", []):
        if isinstance(item, dict) and item.get("selected_rule_id") == rule_id:
            return item
    return None


def _selection_for_channel(
    result: dict[str, object], channel: str
) -> list[dict[str, object]]:
    return [
        item
        for item in result.get("selections", [])
        if isinstance(item, dict) and item.get("channel") == channel
    ]


def test_condition_evaluation_all_any_not_and_ref() -> None:
    conditions_by_id = {
        "expr_weather_ok": {
            "id": "expr_weather_ok",
            "root": {
                "op": "ANY",
                "nodes": [
                    {
                        "op": "PRED",
                        "predicate": {"type": "weather_is", "weather": "clear"},
                    },
                    {
                        "op": "NOT",
                        "node": {
                            "op": "PRED",
                            "predicate": {
                                "type": "time_between",
                                "start_hour": 0,
                                "end_hour": 5,
                            },
                        },
                    },
                ],
            },
        },
        "expr_main": {
            "id": "expr_main",
            "root": {
                "op": "ALL",
                "nodes": [
                    {
                        "op": "PRED",
                        "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                    },
                    {"op": "REF", "ref_id": "expr_weather_ok"},
                    {
                        "op": "PRED",
                        "predicate": {
                            "type": "player_health_range",
                            "min_health": 0,
                            "max_health": 20,
                        },
                    },
                ],
            },
        },
    }

    context_ok = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=10,
    )
    context_bad = RuntimeContext(
        biome="minecraft:desert",
        time=2,
        weather="rain",
        player_health=10,
    )
    assert evaluate_condition("expr_main", conditions_by_id, context_ok)
    assert not evaluate_condition("expr_main", conditions_by_id, context_bad)


def test_music_and_ambient_both_selected() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_forest",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_music",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_forest",
                "asset_ids": ["asset_music"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            },
            {
                "id": "rule_ambient",
                "enabled": True,
                "channel": "ambient_noise",
                "condition_ref": "expr_forest",
                "asset_ids": ["asset_ambient"],
                "priority": {"base_priority": 40},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            },
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    result = simulate_from_runtime_bundle(bundle, context, seed=10)
    channels = {item["channel"] for item in result["selections"]}
    assert channels == {"music", "ambient_noise"}


def test_same_channel_respects_max_concurrent() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_top",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_top"],
                "priority": {"base_priority": 90},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 2, "tie_breaker": "priority_then_weight"},
            },
            {
                "id": "rule_mid",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_mid"],
                "priority": {"base_priority": 80},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 2, "tie_breaker": "priority_then_weight"},
            },
            {
                "id": "rule_low",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_low"],
                "priority": {"base_priority": 70},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 2, "tie_breaker": "priority_then_weight"},
            },
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    result = simulate_from_runtime_bundle(bundle, context, seed=10)
    music_rules = {
        item["selected_rule_id"] for item in _selection_for_channel(result, "music")
    }
    assert music_rules == {"rule_top", "rule_mid"}


def test_tie_breaker_priority_then_oldest() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_oldest",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_oldest"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_oldest"},
            },
            {
                "id": "rule_newer",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_newer"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_oldest"},
            },
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState(
        rule_last_played_at={
            "rule_oldest": 1000,
            "rule_newer": 9000,
        }
    )
    result = simulate_stateful_step(bundle, context, state, timestamp_ms=10000, seed=5)
    assert _selection_rules(result) == {"rule_oldest"}


def test_preemption_works_when_allowed() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_forest",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            },
            {
                "id": "expr_desert",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:desert"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            },
        ],
        "runtime_rules": [
            {
                "id": "rule_low",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_forest",
                "asset_ids": ["asset_low"],
                "priority": {"base_priority": 40},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {
                    "max_concurrent": 1,
                    "tie_breaker": "priority_then_weight",
                    "can_preempt_lower_priority": True,
                },
            },
            {
                "id": "rule_high",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_desert",
                "asset_ids": ["asset_high"],
                "priority": {"base_priority": 90},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {
                    "max_concurrent": 1,
                    "tie_breaker": "priority_then_weight",
                    "can_preempt_lower_priority": True,
                },
            },
        ],
        "runtime_assets": [],
    }
    forest_context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    desert_context = RuntimeContext(
        biome="minecraft:desert",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState()

    first = simulate_stateful_step(bundle, forest_context, state, timestamp_ms=0, seed=1)
    second = simulate_stateful_step(bundle, desert_context, state, timestamp_ms=1000, seed=1)

    assert _selection_rules(first) == {"rule_low"}
    selection = _selection_for_rule(second, "rule_high")
    assert selection is not None
    assert selection["reason"] == "preempted_by_higher_priority"


def test_no_preemption_when_not_allowed() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_forest",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            },
            {
                "id": "expr_desert",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:desert"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            },
        ],
        "runtime_rules": [
            {
                "id": "rule_low",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_forest",
                "asset_ids": ["asset_low"],
                "priority": {"base_priority": 40},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {
                    "max_concurrent": 1,
                    "tie_breaker": "priority_then_weight",
                    "can_preempt_lower_priority": False,
                },
            },
            {
                "id": "rule_high",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_desert",
                "asset_ids": ["asset_high"],
                "priority": {"base_priority": 90},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {
                    "max_concurrent": 1,
                    "tie_breaker": "priority_then_weight",
                    "can_preempt_lower_priority": False,
                },
            },
        ],
        "runtime_assets": [],
    }
    forest_context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    desert_context = RuntimeContext(
        biome="minecraft:desert",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState()

    first = simulate_stateful_step(bundle, forest_context, state, timestamp_ms=0, seed=1)
    second = simulate_stateful_step(bundle, desert_context, state, timestamp_ms=1000, seed=1)

    assert _selection_rules(first) == {"rule_low"}
    selection = _selection_for_rule(second, "rule_low")
    assert selection is not None
    assert selection["reason"] == "kept_previous_no_preemption"
    assert _selection_for_rule(second, "rule_high") is None


def test_rule_cooldown_blocks_immediate_repeat() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_with_cooldown",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_1"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 5000, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            }
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState()

    first = simulate_stateful_step(bundle, context, state, timestamp_ms=0, seed=1)
    second = simulate_stateful_step(bundle, context, state, timestamp_ms=1000, seed=1)
    third = simulate_stateful_step(bundle, context, state, timestamp_ms=6000, seed=1)

    assert _selection_rules(first) == {"rule_with_cooldown"}
    assert _selection_for_rule(second, "rule_with_cooldown") is not None
    assert _selection_for_rule(second, "rule_with_cooldown")["reason"] in {
        "kept_previous_no_candidates",
        "kept_previous_no_preemption",
    }
    assert _selection_rules(third) == {"rule_with_cooldown"}


def test_asset_cooldown_blocks_immediate_repeat() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_asset_cooldown",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_1", "asset_2"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 4000},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            }
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState()

    first = simulate_stateful_step(bundle, context, state, timestamp_ms=0, seed=2)
    second = simulate_stateful_step(bundle, context, state, timestamp_ms=1000, seed=2)
    first_sel = _selection_for_rule(first, "rule_asset_cooldown")
    second_sel = _selection_for_rule(second, "rule_asset_cooldown")
    assert first_sel is not None and second_sel is not None
    assert first_sel["selected_asset_id"] != second_sel["selected_asset_id"]
    assert second_sel["reason"] == "selected_after_cooldown_filter"


def test_no_repeat_window_prefers_different_asset_when_available() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_no_repeat",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_1", "asset_2"],
                "priority": {"base_priority": 50},
                "randomness": {
                    "probability": 1.0,
                    "weight": 1,
                    "no_repeat_window": 1,
                },
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            }
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState()

    first = simulate_stateful_step(bundle, context, state, timestamp_ms=0, seed=3)
    second = simulate_stateful_step(bundle, context, state, timestamp_ms=1000, seed=3)
    first_sel = _selection_for_rule(first, "rule_no_repeat")
    second_sel = _selection_for_rule(second, "rule_no_repeat")
    assert first_sel is not None and second_sel is not None
    assert first_sel["selected_asset_id"] != second_sel["selected_asset_id"]
    assert second_sel["reason"] == "selected_after_no_repeat_filter"


def test_no_repeat_window_falls_back_when_single_asset() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_single_asset",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_only"],
                "priority": {"base_priority": 50},
                "randomness": {
                    "probability": 1.0,
                    "weight": 1,
                    "no_repeat_window": 3,
                },
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            }
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState()

    first = simulate_stateful_step(bundle, context, state, timestamp_ms=0, seed=4)
    second = simulate_stateful_step(bundle, context, state, timestamp_ms=1000, seed=4)
    assert _selection_for_rule(first, "rule_single_asset")["selected_asset_id"] == "asset_only"
    assert _selection_for_rule(second, "rule_single_asset")["selected_asset_id"] == "asset_only"


def test_timeline_simulation_updates_state_correctly() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_timeline_music",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_1"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            },
            {
                "id": "rule_timeline_ambient",
                "enabled": True,
                "channel": "ambient_noise",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_2"],
                "priority": {"base_priority": 40},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            },
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    state = RuntimeState()
    timeline = [(0, context), (1000, context), (2000, context)]

    results = simulate_timeline(bundle, timeline, seed=7, initial_state=state)
    assert len(results) == 3
    assert results[-1]["timestamp_ms"] == 2000
    assert state.current_time_ms == 2000
    assert set(state.active_channel_selections.keys()) == {"music", "ambient_noise"}


def test_deterministic_behavior_with_seed_still_works() -> None:
    bundle = {
        "runtime_conditions": [
            {
                "id": "expr_match",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
                "direct_ref_ids": [],
                "transitive_ref_ids": [],
            }
        ],
        "runtime_rules": [
            {
                "id": "rule_1",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_a", "asset_b"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 1},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            },
            {
                "id": "rule_2",
                "enabled": True,
                "channel": "music",
                "condition_ref": "expr_match",
                "asset_ids": ["asset_c", "asset_d"],
                "priority": {"base_priority": 50},
                "randomness": {"probability": 1.0, "weight": 3},
                "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                "conflict": {"max_concurrent": 1, "tie_breaker": "priority_then_weight"},
            },
        ],
        "runtime_assets": [],
    }
    context = RuntimeContext(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
    )
    timeline = [(0, context), (1000, context), (2000, context)]

    run_one = simulate_timeline(bundle, timeline, seed=99)
    run_two = simulate_timeline(bundle, timeline, seed=99)
    assert run_one == run_two
