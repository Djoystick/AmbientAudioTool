from __future__ import annotations

import json
from pathlib import Path

from ambient_audio_tool.gui.workspace import (
    SimulationRequest,
    WorkspaceSession,
    build_project_view_data,
    export_project,
    load_authoring_project,
    parse_seed_text,
    run_simulation,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def test_build_project_view_data_for_loaded_project() -> None:
    project, report = load_authoring_project(EXAMPLES / "biome_music_ref.json")
    assert project is not None, report.to_text()

    view = build_project_view_data(project)
    assert view["metadata"]["project_id"] == "example_biome_music_ref"
    assert view["metadata"]["assets"] == 2
    assert len(view["assets"]) == 2
    assert len(view["conditions"]) == 3
    assert len(view["rules"]) == 1
    assert view["rules"][0]["channel"] == "music"


def test_parse_seed_text() -> None:
    assert parse_seed_text("") is None
    assert parse_seed_text("  ") is None
    assert parse_seed_text("7") == 7


def test_parse_seed_text_invalid_raises() -> None:
    try:
        parse_seed_text("abc")
    except ValueError:
        return
    assert False, "Expected ValueError for invalid seed text."


def test_run_simulation_returns_timeline_steps() -> None:
    project, report = load_authoring_project(EXAMPLES / "biome_music_ref.json")
    assert project is not None, report.to_text()
    request = SimulationRequest(
        biome="minecraft:forest",
        time=12,
        weather="clear",
        player_health=20,
        is_underwater=False,
        timestamp_ms=0,
        repeat=3,
        step_ms=1000,
        seed=7,
    )

    result = run_simulation(project, EXAMPLES / "biome_music_ref.json", request)
    assert result["request"]["repeat"] == 3
    assert len(result["steps"]) == 3
    assert result["steps"][0]["timestamp_ms"] == 0
    assert result["steps"][2]["timestamp_ms"] == 2000
    assert "active_channel_selections" in result["final_state"]


def test_export_project_writes_expected_files(tmp_path: Path) -> None:
    project, report = load_authoring_project(EXAMPLES / "biome_music_ref.json")
    assert project is not None, report.to_text()

    output_dir = tmp_path / "gui_export"
    result = export_project(project, EXAMPLES / "biome_music_ref.json", output_dir)

    assert result["output_folder"] == str(output_dir)
    assert result["generated_files"] == [
        "manifest.json",
        "runtime_rules.json",
        "runtime_conditions.json",
        "runtime_assets.json",
        "export_summary.json",
    ]


def test_workspace_rule_edit_updates_project_structure() -> None:
    session = WorkspaceSession()
    report = session.load_project(EXAMPLES / "biome_music_ref.json")
    assert report.is_valid

    existing = session.get_rule_by_id("rule_forest_day_music")
    assert existing is not None
    payload = existing.model_dump(mode="json")
    payload["priority"]["base_priority"] = 77
    payload["randomness"]["no_repeat_window"] = 3

    session.upsert_rule(payload, original_rule_id="rule_forest_day_music")
    updated = session.get_rule_by_id("rule_forest_day_music")
    assert updated is not None
    assert updated.priority.base_priority == 77
    assert updated.randomness.no_repeat_window == 3
    assert session.is_dirty


def test_workspace_save_writes_file(tmp_path: Path) -> None:
    source = EXAMPLES / "biome_music_ref.json"
    target = tmp_path / "editable_project.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    session = WorkspaceSession()
    report = session.load_project(target)
    assert report.is_valid

    existing = session.get_rule_by_id("rule_forest_day_music")
    assert existing is not None
    payload = existing.model_dump(mode="json")
    payload["priority"]["base_priority"] = 88
    session.upsert_rule(payload, original_rule_id="rule_forest_day_music")
    session.save_project()

    saved_data = json.loads(target.read_text(encoding="utf-8"))
    saved_rule = next(
        item for item in saved_data["rules"] if item["id"] == "rule_forest_day_music"
    )
    assert saved_rule["priority"]["base_priority"] == 88


def test_workspace_invalid_rule_edit_raises_value_error() -> None:
    session = WorkspaceSession()
    report = session.load_project(EXAMPLES / "biome_music_ref.json")
    assert report.is_valid

    existing = session.get_rule_by_id("rule_forest_day_music")
    assert existing is not None
    payload = existing.model_dump(mode="json")
    payload["channel"] = "invalid_channel"

    try:
        session.upsert_rule(payload, original_rule_id="rule_forest_day_music")
    except ValueError as exc:
        assert "channel" in str(exc)
        return

    assert False, "Expected ValueError for invalid rule edit."


def test_workspace_delete_rule_removes_rule() -> None:
    session = WorkspaceSession()
    report = session.load_project(EXAMPLES / "biome_music_ref.json")
    assert report.is_valid

    assert session.get_rule_by_id("rule_forest_day_music") is not None
    session.delete_rule("rule_forest_day_music")
    assert session.get_rule_by_id("rule_forest_day_music") is None
    assert session.is_dirty


def test_workspace_delete_condition_blocked_when_rule_references_it() -> None:
    session = WorkspaceSession()
    report = session.load_project(EXAMPLES / "biome_music_ref.json")
    assert report.is_valid

    try:
        session.delete_condition("expr_forest_day_music")
    except ValueError as exc:
        assert "used by rule" in str(exc)
        return

    assert False, "Expected ValueError when deleting condition referenced by a rule."


def test_workspace_delete_condition_succeeds_when_not_rule_referenced() -> None:
    session = WorkspaceSession()
    report = session.load_project(EXAMPLES / "biome_music_ref.json")
    assert report.is_valid

    assert session.get_condition_by_id("expr_is_forest") is not None
    session.delete_condition("expr_is_forest")
    assert session.get_condition_by_id("expr_is_forest") is None
    assert session.is_dirty


def test_workspace_save_as_js_wrapper_and_legacy_export(tmp_path: Path) -> None:
    session = WorkspaceSession()
    report = session.load_project(EXAMPLES / "biome_music_ref.json")
    assert report.is_valid

    js_path = tmp_path / "project_wrapper.js"
    legacy_path = tmp_path / "legacy_ambient.js"

    saved_js = session.save_project_as_js_wrapper(js_path)
    saved_legacy, warnings = session.save_project_as_legacy_ambient(legacy_path)

    assert saved_js == js_path
    assert saved_js.exists()
    assert saved_js.read_text(encoding="utf-8").startswith("export const PROJECT = ")

    assert saved_legacy == legacy_path
    assert saved_legacy.exists()
    assert saved_legacy.read_text(encoding="utf-8").startswith(
        "export const AMBIENT_CONFIG = "
    )
    assert warnings
