from __future__ import annotations

import json
from pathlib import Path

from ambient_audio_tool.runtime import RuntimeContext, RuntimeState, simulate_stateful_step


ROOT = Path(__file__).resolve().parents[1]
BEDROCK = ROOT / "bedrock" / "behavior_pack"
EXAMPLES = BEDROCK / "scripts" / "examples"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_bedrock_manifest_points_to_mvp_bridge_script() -> None:
    manifest = _load_json(BEDROCK / "manifest.json")
    script_modules = [
        item for item in manifest.get("modules", []) if item.get("type") == "script"
    ]
    assert script_modules
    assert script_modules[0]["entry"] == "scripts/runtime_bridge_mvp.js"


def test_mvp_contract_examples_align_with_python_runtime() -> None:
    bundle = _load_json(EXAMPLES / "runtime_bundle_mvp_example.json")
    context_payload = _load_json(EXAMPLES / "context_mvp_example.json")
    expected = _load_json(EXAMPLES / "expected_step_mvp_example.json")

    context = RuntimeContext(
        biome=context_payload["biome"],
        time=int(context_payload["time"]),
        weather=context_payload["weather"],
        player_health=int(context_payload["player_health"]),
        is_underwater=bool(context_payload["is_underwater"]),
    )
    state = RuntimeState()
    result = simulate_stateful_step(
        bundle,
        context,
        state,
        timestamp_ms=int(context_payload["timestamp_ms"]),
        seed=7,
    )

    assert result["timestamp_ms"] == expected["timestamp_ms"]
    assert result["selections"] == expected["selections"]
