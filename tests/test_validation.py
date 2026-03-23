from __future__ import annotations

import json
from pathlib import Path

import pytest

from ambient_audio_tool.validation import validate_authoring_project_file


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@pytest.mark.parametrize(
    "example_name",
    [
        "biome_music_ref.json",
        "underwater_ambient_noise.json",
        "low_health_alert.json",
        "custom_event_example.json",
        "night_swamp_ref_chain.json",
    ],
)
def test_valid_project_loads(example_name: str) -> None:
    report = validate_authoring_project_file(EXAMPLES / example_name)
    assert report.is_valid, report.to_text()


def test_missing_ref_fails(tmp_path: Path) -> None:
    payload = {
        "project_id": "missing_ref",
        "audio_assets": [{"id": "a1", "path": "assets/a1.ogg"}],
        "conditions": [
            {
                "id": "c1",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:plains"},
                },
            }
        ],
        "rules": [
            {
                "id": "r1",
                "channel": "music",
                "condition_ref": "c_missing",
                "asset_ids": ["a1"],
            }
        ],
    }
    project_file = tmp_path / "missing_ref.json"
    project_file.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_authoring_project_file(project_file)
    assert not report.is_valid
    assert any(issue.code == "missing_condition_ref" for issue in report.issues)


def test_cycle_detection_works(tmp_path: Path) -> None:
    payload = {
        "project_id": "cycle_ref",
        "audio_assets": [{"id": "a1", "path": "assets/a1.ogg"}],
        "conditions": [
            {"id": "c1", "root": {"op": "REF", "ref_id": "c2"}},
            {"id": "c2", "root": {"op": "REF", "ref_id": "c1"}},
        ],
        "rules": [
            {
                "id": "r1",
                "channel": "music",
                "condition_ref": "c1",
                "asset_ids": ["a1"],
            }
        ],
    }
    project_file = tmp_path / "cycle.json"
    project_file.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_authoring_project_file(project_file)
    assert not report.is_valid
    assert any(issue.code == "cyclic_condition_ref" for issue in report.issues)


def test_duplicate_ids_fail(tmp_path: Path) -> None:
    payload = {
        "project_id": "dup_ids",
        "audio_assets": [
            {"id": "a1", "path": "assets/a1.ogg"},
            {"id": "a1", "path": "assets/a2.ogg"},
        ],
        "conditions": [
            {
                "id": "c1",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "biome_is", "biome": "minecraft:forest"},
                },
            }
        ],
        "rules": [
            {
                "id": "r1",
                "channel": "music",
                "condition_ref": "c1",
                "asset_ids": ["a1"],
            }
        ],
    }
    project_file = tmp_path / "dup_ids.json"
    project_file.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_authoring_project_file(project_file)
    assert not report.is_valid
    assert any(issue.code == "duplicate_id" for issue in report.issues)


def test_predicate_payload_validation(tmp_path: Path) -> None:
    payload = {
        "project_id": "bad_predicate_payload",
        "audio_assets": [{"id": "a1", "path": "assets/a1.ogg"}],
        "conditions": [
            {
                "id": "c1",
                "root": {
                    "op": "PRED",
                    "predicate": {"type": "weather_is", "weather": "storm"},
                },
            }
        ],
        "rules": [
            {
                "id": "r1",
                "channel": "music",
                "condition_ref": "c1",
                "asset_ids": ["a1"],
            }
        ],
    }
    project_file = tmp_path / "bad_predicate.json"
    project_file.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_authoring_project_file(project_file)
    assert not report.is_valid
    assert any(issue.code == "schema_validation_error" for issue in report.issues)
