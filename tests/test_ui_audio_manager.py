from __future__ import annotations

import json
from pathlib import Path

from ambient_audio_tool.gui.ui_audio_manager import UiAudioManager


def test_ui_audio_manager_reads_persisted_enabled_state(tmp_path: Path) -> None:
    config_path = tmp_path / "user_config.json"
    config_path.write_text(
        json.dumps({"music_enabled": True}, indent=2),
        encoding="utf-8",
    )
    manager = UiAudioManager(
        config_path=config_path,
        audio_path=tmp_path / "missing_background_loop.mp3",
    )

    assert manager.is_enabled()
    assert not manager.is_available()


def test_ui_audio_manager_toggle_persists_state(tmp_path: Path) -> None:
    config_path = tmp_path / "user_config.json"
    config_path.write_text(
        json.dumps({"music_enabled": False}, indent=2),
        encoding="utf-8",
    )
    manager = UiAudioManager(
        config_path=config_path,
        audio_path=tmp_path / "missing_background_loop.mp3",
    )

    assert manager.toggle() is True
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["music_enabled"] is True

    assert manager.toggle() is False
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["music_enabled"] is False
