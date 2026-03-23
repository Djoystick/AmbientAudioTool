from __future__ import annotations

import json
from pathlib import Path

from ambient_audio_tool.export import (
    render_js_wrapper_source,
    render_legacy_ambient_config_source,
    write_js_wrapper_source,
    write_legacy_ambient_config_source,
)
from ambient_audio_tool.gui.workspace import WorkspaceSession
from ambient_audio_tool.io import load_project_data
from ambient_audio_tool.models import AuthoringProject


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _load_example_project() -> AuthoringProject:
    payload = json.loads((EXAMPLES / "biome_music_ref.json").read_text(encoding="utf-8"))
    return AuthoringProject.model_validate(payload)


def _extract_wrapped_json(source: str, prefix: str) -> dict:
    assert source.startswith(prefix)
    assert source.endswith(";\n")
    payload = source[len(prefix) : -2]
    return json.loads(payload)


def test_js_wrapper_export_smoke(tmp_path: Path) -> None:
    project = _load_example_project()

    source_one = render_js_wrapper_source(project)
    source_two = render_js_wrapper_source(project)
    assert source_one == source_two

    wrapped = _extract_wrapped_json(source_one, "export const PROJECT = ")
    assert wrapped["project_id"] == "example_biome_music_ref"
    assert wrapped["rules"][0]["id"] == "rule_forest_day_music"

    out_file = tmp_path / "project_wrapper.js"
    write_js_wrapper_source(project, out_file)
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == source_one


def test_js_wrapper_export_file_reopens_via_loader(tmp_path: Path) -> None:
    project = _load_example_project()
    out_file = tmp_path / "project_wrapper.js"
    write_js_wrapper_source(project, out_file)

    payload, source_format = load_project_data(out_file)
    assert source_format == "js"
    assert payload["project_id"] == project.project_id


def test_legacy_ambient_export_smoke(tmp_path: Path) -> None:
    project = _load_example_project()

    result = render_legacy_ambient_config_source(project)
    wrapped = _extract_wrapped_json(result.source, "export const AMBIENT_CONFIG = ")
    assert "ambient_sound_definitions" in wrapped

    ambient_defs = wrapped["ambient_sound_definitions"]
    assert "minecraft:forest" in ambient_defs
    assert "music" in ambient_defs["minecraft:forest"]
    assert len(ambient_defs["minecraft:forest"]["music"]) == 2
    first_entry = ambient_defs["minecraft:forest"]["music"][0]
    assert first_entry["source_sound"]["min_delay_seconds"] == 5.0
    assert first_entry["source_sound"]["max_delay_seconds"] == 12.0

    out_file = tmp_path / "legacy_ambient.js"
    written = write_legacy_ambient_config_source(project, out_file)
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == written.source


def test_legacy_export_generates_lossy_warnings() -> None:
    project = _load_example_project()
    result = render_legacy_ambient_config_source(project)

    assert result.warnings, "Expected warnings for lossy legacy downgrade."
    assert any("unsupported predicate 'weather_is'" in warning for warning in result.warnings)


def test_json_save_pipeline_unaffected(tmp_path: Path) -> None:
    source = EXAMPLES / "biome_music_ref.json"
    target = tmp_path / "project.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    session = WorkspaceSession()
    report = session.load_project(target)
    assert report.is_valid, report.to_text()

    saved_path = session.save_project()
    assert saved_path == target
    saved_payload = json.loads(target.read_text(encoding="utf-8"))
    assert saved_payload["project_id"] == "example_biome_music_ref"
