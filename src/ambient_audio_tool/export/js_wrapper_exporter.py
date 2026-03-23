from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ambient_audio_tool.models import AuthoringProject


def render_js_wrapper_source(project: AuthoringProject | dict[str, Any]) -> str:
    """Render a deterministic data-only JavaScript wrapper for a project."""
    payload = _to_payload(project)
    json_text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    return f"export const PROJECT = {json_text};\n"


def write_js_wrapper_source(
    project: AuthoringProject | dict[str, Any],
    output_path: str | Path,
) -> Path:
    target = Path(output_path)
    source = render_js_wrapper_source(project)
    target.write_text(source, encoding="utf-8")
    return target


def _to_payload(project: AuthoringProject | dict[str, Any]) -> dict[str, Any]:
    if isinstance(project, AuthoringProject):
        return project.model_dump(mode="json")
    if isinstance(project, dict):
        return project
    raise TypeError("project must be AuthoringProject or dict payload.")
