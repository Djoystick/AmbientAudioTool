from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BEDROCK_SCRIPTS = ROOT / "bedrock" / "behavior_pack" / "scripts"
EXAMPLES = BEDROCK_SCRIPTS / "examples"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_runtime_bridge_mvp_exposes_binding_entry_points() -> None:
    source = _read_text(BEDROCK_SCRIPTS / "runtime_bridge_mvp.js")
    assert "function createBedrockHooks(options = {})" in source
    assert "function bindBedrockRuntimeLoop(runtimeBridge, hooks, options = {})" in source
    assert "function tryAutoBindBedrockRuntime(runtimeBridge, options = {})" in source
    assert "globalThis.AAT_BEDROCK_BINDING" in source


def test_binding_options_example_has_expected_fields() -> None:
    payload = _read_json(EXAMPLES / "binding_options_mvp_example.json")
    assert payload["auto_bind"] is True
    assert isinstance(payload["tick_interval_ticks"], int)
    assert payload["tick_interval_ticks"] >= 1
    assert isinstance(payload["single_player_only"], bool)
