from __future__ import annotations

from pathlib import Path

from ambient_audio_tool.validation import load_project_with_report_and_meta


def test_load_legacy_ambient_config_js_and_map_channels(tmp_path: Path) -> None:
    legacy_js = tmp_path / "SoundEventDefinitions.js"
    legacy_js.write_text(
        """
export const AMBIENT_CONFIG = {
  ambient_sound_definitions: {
    global: {
      music: [
        {
          weight: 60,
          source_sound: {
            event_name: "global_music_theme",
            length_seconds: 12,
            min_delay_seconds: 2,
            max_delay_seconds: 6,
          },
          filter: { test: "is_day", operator: "==", value: true },
        },
      ],
      noise: [
        {
          weight: 30,
          source_sound: {
            event_name: "global_noise_wind",
            length_seconds: 4,
          },
        },
      ],
    },
    "minecraft:forest": {
      sounds: [
        {
          weight: 80,
          source_sound: {
            event_name: "forest_birds",
            min_delay_seconds: 1,
            max_delay_seconds: 3,
          },
          filter: {
            all_of: [
              { test: "is_day", operator: "==", value: false },
              { test: "height", operator: ">=", value: 60 },
            ],
          },
        },
      ],
    },
  },
};
""".strip(),
        encoding="utf-8",
    )

    project, report, meta = load_project_with_report_and_meta(legacy_js)
    assert project is not None, report.to_text()
    assert meta["source_format"] == "legacy_js"
    assert report.is_valid
    assert report.warning_count >= 1
    assert any(issue.code == "legacy_import_warning" for issue in report.issues)

    channels = {rule.channel.value for rule in project.rules}
    assert channels == {"music", "ambient_noise", "context_oneshot"}

    assert len(project.rules) == 3
    assert len(project.audio_assets) == 3


def test_workspace_metadata_for_legacy_project(tmp_path: Path) -> None:
    from ambient_audio_tool.gui.workspace import WorkspaceSession

    legacy_js = tmp_path / "legacy.js"
    legacy_js.write_text(
        """
export const AMBIENT_CONFIG = {
  ambient_sound_definitions: {
    global: {
      music: [
        {
          source_sound: { event_name: "legacy_theme" },
          weight: 40,
        },
      ],
    },
  },
};
""".strip(),
        encoding="utf-8",
    )

    session = WorkspaceSession()
    report = session.load_project(legacy_js)
    assert report.is_valid
    assert session.source_format == "legacy_js"
    assert "legacy" in session.source_note.lower()
