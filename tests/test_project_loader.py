from __future__ import annotations

from pathlib import Path

import pytest

from ambient_audio_tool.gui.workspace import WorkspaceSession
from ambient_audio_tool.io import ProjectLoadError, load_project_data


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


JS_OBJECT_BODY = """
{
  project_id: "js_project",
  project_name: "JS Project",
  version: "1.0",
  audio_assets: [
    { id: "a1", path: "assets/a1.ogg", },
  ],
  conditions: [
    {
      id: "c1",
      root: {
        op: "PRED",
        predicate: { type: "biome_is", biome: "minecraft:forest", },
      },
    },
  ],
  rules: [
    {
      id: "r1",
      channel: "music",
      condition_ref: "c1",
      asset_ids: ["a1",],
    },
  ],
}
""".strip()


def _write_js_project(tmp_path: Path, wrapper: str) -> Path:
    file_path = tmp_path / "project.js"
    if wrapper == "module_exports":
        content = f"module.exports = {JS_OBJECT_BODY};"
    elif wrapper == "export_default":
        content = f"export default {JS_OBJECT_BODY};"
    elif wrapper == "export_const_project":
        content = f"export const project = {JS_OBJECT_BODY};"
    else:  # pragma: no cover
        raise ValueError(wrapper)
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_load_module_exports_js_project(tmp_path: Path) -> None:
    path = _write_js_project(tmp_path, "module_exports")
    payload, source_format = load_project_data(path)
    assert source_format == "js"
    assert payload["project_id"] == "js_project"


def test_load_export_default_js_project(tmp_path: Path) -> None:
    path = _write_js_project(tmp_path, "export_default")
    payload, source_format = load_project_data(path)
    assert source_format == "js"
    assert payload["rules"][0]["id"] == "r1"


def test_load_export_const_project_js_project(tmp_path: Path) -> None:
    path = _write_js_project(tmp_path, "export_const_project")
    payload, source_format = load_project_data(path)
    assert source_format == "js"
    assert payload["conditions"][0]["id"] == "c1"


def test_reject_unsupported_js_execution_pattern(tmp_path: Path) -> None:
    path = tmp_path / "bad_project.js"
    path.write_text(
        "module.exports = { project_id: computeId(), audio_assets: [], conditions: [], rules: [] };",
        encoding="utf-8",
    )
    with pytest.raises(ProjectLoadError) as exc_info:
        load_project_data(path)
    assert "Unsupported identifier" in str(exc_info.value)


def test_json_loading_still_works() -> None:
    payload, source_format = load_project_data(EXAMPLES / "biome_music_ref.json")
    assert source_format == "json"
    assert payload["project_id"] == "example_biome_music_ref"


def test_workspace_loads_js_project(tmp_path: Path) -> None:
    path = _write_js_project(tmp_path, "module_exports")
    session = WorkspaceSession()
    report = session.load_project(path)
    assert report.is_valid
    assert session.has_project
    assert session.source_format == "js"


def test_workspace_blocks_direct_save_to_js_and_allows_save_as_json(tmp_path: Path) -> None:
    source_path = _write_js_project(tmp_path, "export_default")
    session = WorkspaceSession()
    report = session.load_project(source_path)
    assert report.is_valid

    try:
        session.save_project()
    except ValueError as exc:
        assert "Save As JSON" in str(exc)
    else:
        assert False, "Expected ValueError for direct .js save."

    output_path = tmp_path / "converted_project.json"
    session.save_project_as_json(output_path)
    assert output_path.exists()
