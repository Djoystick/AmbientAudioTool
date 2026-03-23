from __future__ import annotations

import json
from pathlib import Path

from ambient_audio_tool.validation import load_project_with_report


ROOT = Path(__file__).resolve().parents[1]
AUTHORING_DIR = ROOT / "examples" / "template_catalog" / "authoring"
RUNTIME_DIR = ROOT / "examples" / "template_catalog" / "runtime"

TEMPLATE_BASENAMES = [
    "day_music_forest",
    "night_music_swamp",
    "biome_ambient_forest_birds",
    "weather_rain_ambient",
    "underwater_layer",
    "low_health_tension_layer",
    "contextual_oneshot_enter_cave",
]


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_template_catalog_authoring_files_load_and_validate() -> None:
    for name in TEMPLATE_BASENAMES:
        path = AUTHORING_DIR / f"{name}.json"
        assert path.exists(), f"Missing template authoring file: {path}"

        project, report = load_project_with_report(path)
        assert project is not None, report.to_text()
        assert report.is_valid, report.to_text()

        assert len(project.audio_assets) >= 1
        assert len(project.conditions) >= 1
        assert len(project.rules) >= 1


def test_template_catalog_runtime_examples_match_authoring_ids() -> None:
    for name in TEMPLATE_BASENAMES:
        authoring = _load_json(AUTHORING_DIR / f"{name}.json")
        runtime = _load_json(RUNTIME_DIR / f"{name}.runtime.json")

        assert sorted(runtime.keys()) == [
            "runtime_assets",
            "runtime_conditions",
            "runtime_rules",
        ]

        runtime_rules = runtime["runtime_rules"]
        runtime_conditions = runtime["runtime_conditions"]
        runtime_assets = runtime["runtime_assets"]

        assert isinstance(runtime_rules, list) and runtime_rules
        assert isinstance(runtime_conditions, list) and runtime_conditions
        assert isinstance(runtime_assets, list) and runtime_assets

        authoring_rule_ids = {item["id"] for item in authoring["rules"]}
        runtime_rule_ids = {item["id"] for item in runtime_rules}
        assert runtime_rule_ids == authoring_rule_ids

        authoring_condition_ids = {item["id"] for item in authoring["conditions"]}
        runtime_condition_ids = {item["id"] for item in runtime_conditions}
        assert runtime_condition_ids == authoring_condition_ids

        authoring_asset_ids = {item["id"] for item in authoring["audio_assets"]}
        runtime_asset_ids = {item["id"] for item in runtime_assets}
        assert runtime_asset_ids == authoring_asset_ids
