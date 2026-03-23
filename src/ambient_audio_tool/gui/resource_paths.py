from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def is_frozen_bundle() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen_bundle():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return executable_dir()


def resolve_runtime_path(relative_path: str | Path) -> Path:
    rel = Path(relative_path)
    candidates: list[Path] = []
    for candidate in (executable_dir() / rel, bundle_dir() / rel, PROJECT_ROOT / rel):
        if candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
