from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .context import RuntimeContext
from .selector import select_channels_stateful, select_channels_stateless
from .state import RuntimeState


def load_runtime_bundle(runtime_folder: str | Path) -> dict[str, Any]:
    folder = Path(runtime_folder)
    runtime_rules = _load_json_file(folder / "runtime_rules.json")
    runtime_conditions = _load_json_file(folder / "runtime_conditions.json")
    runtime_assets = _load_json_file(folder / "runtime_assets.json")

    if not isinstance(runtime_rules, list):
        raise ValueError("runtime_rules.json must contain a JSON array.")
    if not isinstance(runtime_conditions, list):
        raise ValueError("runtime_conditions.json must contain a JSON array.")
    if not isinstance(runtime_assets, list):
        raise ValueError("runtime_assets.json must contain a JSON array.")

    return {
        "runtime_rules": runtime_rules,
        "runtime_conditions": runtime_conditions,
        "runtime_assets": runtime_assets,
    }


def simulate_from_runtime_bundle(
    runtime_bundle: dict[str, Any],
    context: RuntimeContext,
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    runtime_rules = runtime_bundle.get("runtime_rules", [])
    runtime_conditions = runtime_bundle.get("runtime_conditions", [])

    conditions_by_id = {
        condition["id"]: condition
        for condition in runtime_conditions
        if isinstance(condition, dict) and isinstance(condition.get("id"), str)
    }

    rng = random.Random(seed)
    channel_result = select_channels_stateless(runtime_rules, conditions_by_id, context, rng)
    return {"selections": channel_result.get("selections", [])}


def simulate_from_folder(
    runtime_folder: str | Path,
    context: RuntimeContext,
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    bundle = load_runtime_bundle(runtime_folder)
    return simulate_from_runtime_bundle(bundle, context, seed=seed)


def simulate_stateful_step(
    runtime_bundle: dict[str, Any],
    context: RuntimeContext,
    state: RuntimeState | None = None,
    *,
    timestamp_ms: int | None = None,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    state_obj = state if state is not None else RuntimeState()
    step_time_ms = state_obj.current_time_ms if timestamp_ms is None else int(timestamp_ms)
    state_obj.current_time_ms = step_time_ms

    runtime_rules = runtime_bundle.get("runtime_rules", [])
    runtime_conditions = runtime_bundle.get("runtime_conditions", [])
    conditions_by_id = {
        condition["id"]: condition
        for condition in runtime_conditions
        if isinstance(condition, dict) and isinstance(condition.get("id"), str)
    }

    rng_obj = rng if rng is not None else random.Random(seed)
    channel_result = select_channels_stateful(
        runtime_rules,
        conditions_by_id,
        context,
        state_obj,
        timestamp_ms=step_time_ms,
        rng=rng_obj,
    )

    selections = channel_result.get("selections", [])
    started_selections = channel_result.get("started_selections", [])
    active_channel_selections = channel_result.get("active_channel_selections", {})
    state_obj.active_channel_selections = {
        str(channel): [dict(item) for item in selections_for_channel]
        for channel, selections_for_channel in active_channel_selections.items()
    }
    state_obj.record_started_selections(
        timestamp_ms=step_time_ms,
        started_selections=[dict(item) for item in started_selections],
    )

    return {
        "selections": [dict(item) for item in selections],
        "timestamp_ms": step_time_ms,
        "state": state_obj.to_dict(),
    }


def simulate_stateful_step_from_folder(
    runtime_folder: str | Path,
    context: RuntimeContext,
    state: RuntimeState | None = None,
    *,
    timestamp_ms: int | None = None,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    bundle = load_runtime_bundle(runtime_folder)
    return simulate_stateful_step(
        bundle,
        context,
        state,
        timestamp_ms=timestamp_ms,
        seed=seed,
        rng=rng,
    )


def simulate_timeline(
    runtime_bundle: dict[str, Any],
    contexts_with_timestamps: list[tuple[int, RuntimeContext]],
    *,
    seed: int | None = None,
    initial_state: RuntimeState | None = None,
) -> list[dict[str, Any]]:
    state = initial_state if initial_state is not None else RuntimeState()
    rng = random.Random(seed)
    results: list[dict[str, Any]] = []

    for step_index, (timestamp_ms, context) in enumerate(contexts_with_timestamps, start=1):
        step_result = simulate_stateful_step(
            runtime_bundle,
            context,
            state,
            timestamp_ms=timestamp_ms,
            rng=rng,
        )
        step_result["step_index"] = step_index
        results.append(step_result)
    return results


def _load_json_file(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing runtime file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc.msg}") from exc
