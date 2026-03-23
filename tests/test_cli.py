from __future__ import annotations

import json
from pathlib import Path

from ambient_audio_tool.cli.main import main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_cli_validate_success(capsys) -> None:
    code = main(["validate", str(EXAMPLES / "biome_music_ref.json")])
    captured = capsys.readouterr()
    assert code == 0
    assert "Validation succeeded" in captured.out


def test_cli_validate_failure(capsys, tmp_path: Path) -> None:
    invalid_payload = {
        "project_id": "cli_invalid",
        "audio_assets": [{"id": "a1", "path": "assets/a1.ogg"}],
        "conditions": [{"id": "c1", "root": {"op": "REF", "ref_id": "missing"}}],
        "rules": [
            {
                "id": "r1",
                "channel": "music",
                "condition_ref": "c1",
                "asset_ids": ["a1"],
            }
        ],
    }
    project_file = tmp_path / "invalid_cli.json"
    project_file.write_text(json.dumps(invalid_payload), encoding="utf-8")

    code = main(["validate", str(project_file)])
    captured = capsys.readouterr()
    assert code == 1
    assert "missing_expression_ref" in captured.out


def test_cli_simulate_success(capsys, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    (runtime_dir / "runtime_conditions.json").write_text(
        json.dumps(
            [
                {
                    "id": "expr_match",
                    "root": {
                        "op": "PRED",
                        "predicate": {
                            "type": "biome_is",
                            "biome": "minecraft:forest",
                        },
                    },
                    "direct_ref_ids": [],
                    "transitive_ref_ids": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (runtime_dir / "runtime_rules.json").write_text(
        json.dumps(
            [
                {
                    "id": "rule_match",
                    "enabled": True,
                    "channel": "music",
                    "condition_ref": "expr_match",
                    "asset_ids": ["asset_1"],
                    "priority": {"base_priority": 50},
                    "randomness": {"probability": 1.0, "weight": 1},
                    "cooldown": {},
                    "conflict": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    (runtime_dir / "runtime_assets.json").write_text(
        json.dumps([{"id": "asset_1", "path": "assets/audio/asset_1.ogg"}]),
        encoding="utf-8",
    )

    code = main(
        [
            "simulate",
            str(runtime_dir),
            "--biome",
            "minecraft:forest",
            "--time",
            "12",
            "--weather",
            "clear",
            "--player-health",
            "20",
            "--seed",
            "7",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Simulation result:" in captured.out
    assert "rule_match" in captured.out
    assert "\"channel\": \"music\"" in captured.out


def test_cli_simulate_failure_when_runtime_file_missing(capsys, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime_incomplete"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    code = main(["simulate", str(runtime_dir)])
    captured = capsys.readouterr()
    assert code == 1
    assert "Simulation aborted:" in captured.out


def test_cli_simulate_timeline_mode(capsys, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime_timeline"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    (runtime_dir / "runtime_conditions.json").write_text(
        json.dumps(
            [
                {
                    "id": "expr_match",
                    "root": {
                        "op": "PRED",
                        "predicate": {
                            "type": "biome_is",
                            "biome": "minecraft:forest",
                        },
                    },
                    "direct_ref_ids": [],
                    "transitive_ref_ids": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (runtime_dir / "runtime_rules.json").write_text(
        json.dumps(
            [
                {
                    "id": "rule_match",
                    "enabled": True,
                    "channel": "music",
                    "condition_ref": "expr_match",
                    "asset_ids": ["asset_1", "asset_2"],
                    "priority": {"base_priority": 50},
                    "randomness": {"probability": 1.0, "weight": 1, "no_repeat_window": 1},
                    "cooldown": {"rule_cooldown_ms": 0, "asset_cooldown_ms": 0},
                    "conflict": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    (runtime_dir / "runtime_assets.json").write_text(
        json.dumps(
            [
                {"id": "asset_1", "path": "assets/audio/asset_1.ogg"},
                {"id": "asset_2", "path": "assets/audio/asset_2.ogg"},
            ]
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "simulate",
            str(runtime_dir),
            "--biome",
            "minecraft:forest",
            "--time",
            "12",
            "--weather",
            "clear",
            "--player-health",
            "20",
            "--timestamp-ms",
            "0",
            "--repeat",
            "3",
            "--step-ms",
            "1000",
            "--seed",
            "42",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Timeline simulation results:" in captured.out
    assert "Final state:" in captured.out


def test_cli_export_json_format(capsys, tmp_path: Path) -> None:
    output_file = tmp_path / "project_export.json"
    code = main(
        [
            "export",
            str(EXAMPLES / "biome_music_ref.json"),
            "--out",
            str(output_file),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Format: json" in captured.out
    assert output_file.exists()
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["project_id"] == "example_biome_music_ref"


def test_cli_export_js_wrapper_format(capsys, tmp_path: Path) -> None:
    output_file = tmp_path / "project_export.js"
    code = main(
        [
            "export",
            str(EXAMPLES / "biome_music_ref.json"),
            "--out",
            str(output_file),
            "--format",
            "js-wrapper",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Format: js-wrapper" in captured.out
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert content.startswith("export const PROJECT = ")


def test_cli_export_legacy_ambient_format(capsys, tmp_path: Path) -> None:
    output_file = tmp_path / "legacy_ambient.js"
    code = main(
        [
            "export",
            str(EXAMPLES / "biome_music_ref.json"),
            "--out",
            str(output_file),
            "--format",
            "legacy-ambient",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "Format: legacy-ambient" in captured.out
    assert "Legacy export warnings:" in captured.out
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert content.startswith("export const AMBIENT_CONFIG = ")
