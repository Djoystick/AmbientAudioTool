from __future__ import annotations

import json
from pathlib import Path

from .compiler import EXPORT_FILENAMES
from .models import ExportBundle


def write_export_bundle(bundle: ExportBundle, out_dir: str | Path) -> list[Path]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle.export_summary.output_folder = str(output_dir)

    payload_map = {
        "manifest.json": bundle.manifest.model_dump(mode="json"),
        "runtime_rules.json": [item.model_dump(mode="json") for item in bundle.runtime_rules],
        "runtime_conditions.json": [
            item.model_dump(mode="json") for item in bundle.runtime_conditions
        ],
        "runtime_assets.json": [item.model_dump(mode="json") for item in bundle.runtime_assets],
        "export_summary.json": bundle.export_summary.model_dump(mode="json"),
    }

    written_files: list[Path] = []
    for filename in EXPORT_FILENAMES:
        payload = payload_map[filename]
        destination = output_dir / filename
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written_files.append(destination)
    return written_files
