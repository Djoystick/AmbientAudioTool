# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


ROOT = Path.cwd()
APP_NAME = "AmbientAudioTool"
ICON_PATH = ROOT / "assets" / "app_icon.ico"
ICON = str(ICON_PATH) if ICON_PATH.exists() else None

datas = [
    (str(ROOT / "assets" / "ui_audio"), "assets/ui_audio"),
    (str(ROOT / "examples"), "examples"),
]

hiddenimports = [
    "PySide6.QtMultimedia",
    "shiboken6",
]


a = Analysis(
    [str(ROOT / "scripts" / "launch_gui.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
