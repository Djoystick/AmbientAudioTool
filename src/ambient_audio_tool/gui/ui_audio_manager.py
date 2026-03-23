from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .resource_paths import resolve_runtime_path


class UiAudioManager:
    """Simple UI background music manager for the desktop app."""

    DEFAULT_VOLUME = 0.4
    CONFIG_FILENAME = ".ambient_audio_tool_gui_config.json"
    RELATIVE_AUDIO_PATH = Path("assets/ui_audio/background_loop.mp3")

    def __init__(
        self,
        *,
        log_callback: Callable[[str], None] | None = None,
        config_path: Path | None = None,
        audio_path: Path | None = None,
    ) -> None:
        self._log_callback = log_callback
        self._config_path = config_path or (Path.home() / self.CONFIG_FILENAME)
        self._audio_path = audio_path or resolve_runtime_path(self.RELATIVE_AUDIO_PATH)

        self._enabled = False
        self._desired_enabled = False
        self._available = False
        self._disabled_reason: str | None = None
        self._playback_error_logged = False

        self._player = None
        self._audio_output = None
        self._media_status_end = None

        self._initialize_player()
        saved_enabled = self._load_config_enabled_default_false()
        self._desired_enabled = saved_enabled
        if saved_enabled:
            self.play()
        else:
            self.stop()

    def play(self) -> None:
        self._desired_enabled = True
        self._persist_enabled()
        if not self._available:
            self._enabled = False
            return
        try:
            self._player.play()
            self._enabled = True
        except Exception as exc:  # pragma: no cover - depends on multimedia backend
            self._disable_runtime(f"Playback failed: {exc}")

    def stop(self) -> None:
        self._desired_enabled = False
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
        self._enabled = False
        self._persist_enabled()

    def toggle(self) -> bool:
        if self._desired_enabled:
            self.stop()
            return self._desired_enabled
        self.play()
        return self._desired_enabled

    def is_enabled(self) -> bool:
        return self._desired_enabled

    def is_available(self) -> bool:
        return self._available

    def disabled_reason(self) -> str | None:
        return self._disabled_reason

    def shutdown(self) -> None:
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass

    def _initialize_player(self) -> None:
        if not self._audio_path.exists():
            self._disable_runtime(
                "UI music file is missing. Expected: assets/ui_audio/background_loop.mp3"
            )
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception as exc:  # pragma: no cover - environment-specific
            self._disable_runtime(f"Qt multimedia is unavailable: {exc}")
            return

        try:
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(self.DEFAULT_VOLUME)
            self._player.setAudioOutput(self._audio_output)
            self._player.setSource(QUrl.fromLocalFile(str(self._audio_path.resolve())))
            self._setup_looping()
            self._available = True
            self._disabled_reason = None
        except Exception as exc:  # pragma: no cover - depends on multimedia backend
            self._disable_runtime(f"Failed to initialize UI music playback: {exc}")

    def _setup_looping(self) -> None:
        if self._player is None:
            return
        loops_applied = False
        try:
            set_loops = getattr(self._player, "setLoops", None)
            loops_enum = getattr(type(self._player), "Loops", None)
            infinite_value = getattr(loops_enum, "Infinite", -1) if loops_enum else -1
            if callable(set_loops):
                set_loops(infinite_value)
                loops_applied = True
        except Exception:
            loops_applied = False

        if loops_applied:
            return

        try:
            media_status_enum = getattr(type(self._player), "MediaStatus", None)
            self._media_status_end = getattr(media_status_enum, "EndOfMedia", None)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        except Exception:
            self._log_once(
                "UI music loop fallback is unavailable; loop behavior may not work."
            )

    def _on_media_status_changed(self, status: object) -> None:
        if self._player is None or self._media_status_end is None:
            return
        if status != self._media_status_end:
            return
        try:
            self._player.setPosition(0)
            self._player.play()
        except Exception as exc:  # pragma: no cover - runtime backend-specific
            if not self._playback_error_logged:
                self._log_once(f"UI music loop restart failed: {exc}")
                self._playback_error_logged = True

    def _load_config_enabled_default_false(self) -> bool:
        if not self._config_path.exists():
            return False
        try:
            payload = json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        return bool(payload.get("music_enabled", True))

    def _persist_enabled(self) -> None:
        payload = {"music_enabled": self._desired_enabled}
        try:
            self._config_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            self._log_once(f"Could not write UI music config: {exc}")

    def _disable_runtime(self, reason: str) -> None:
        self._available = False
        self._enabled = False
        self._disabled_reason = reason
        self._log_once(f"UI music disabled: {reason}")

    def _log_once(self, message: str) -> None:
        if self._log_callback is not None:
            self._log_callback(message)
