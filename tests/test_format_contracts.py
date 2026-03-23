from __future__ import annotations

import argparse
from pathlib import Path

from ambient_audio_tool.cli.main import build_parser


ROOT = Path(__file__).resolve().parents[1]


def test_cli_export_format_choices_are_stable() -> None:
    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    export_parser = subparsers_action.choices["export"]
    format_action = next(
        action for action in export_parser._actions if action.dest == "format"
    )
    assert format_action.choices == ["runtime", "json", "js-wrapper", "legacy-ambient"]


def test_event_template_docs_note_python_simulator_limits() -> None:
    content = (ROOT / "docs" / "event_template_catalog.md").read_text(encoding="utf-8")
    assert "current Python simulator does not evaluate `is_underwater` yet" in content
    assert "current Python simulator does not evaluate `custom_event` yet" in content
