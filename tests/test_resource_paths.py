from __future__ import annotations

from pathlib import Path

from ambient_audio_tool.gui import resource_paths


def test_resolve_runtime_path_prefers_existing_source_path() -> None:
    resolved = resource_paths.resolve_runtime_path("examples/biome_music_ref.json")
    assert resolved.exists()
    assert resolved.name == "biome_music_ref.json"


def test_executable_dir_uses_project_root_when_not_frozen(monkeypatch) -> None:
    monkeypatch.setattr(resource_paths.sys, "frozen", False, raising=False)
    path = resource_paths.executable_dir()
    assert isinstance(path, Path)
    assert path == resource_paths.PROJECT_ROOT


def test_executable_dir_uses_executable_parent_when_frozen(monkeypatch) -> None:
    fake_exe = Path("C:/Temp/App/AmbientAudioTool.exe")
    monkeypatch.setattr(resource_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(resource_paths.sys, "executable", str(fake_exe), raising=False)
    path = resource_paths.executable_dir()
    assert path == fake_exe.parent
