# AmbientAudioTool

AmbientAudioTool is a desktop-first authoring toolkit for **Minecraft Bedrock add-on audio design**.
It helps modders and game designers define ambient music/noise logic, validate rules, simulate runtime behavior, and export runtime bundles for Bedrock script integration.

> Repository: https://github.com/Djoystick/AmbientAudioTool

## Overview
AmbientAudioTool combines a practical GUI workspace with a strongly-typed backend pipeline:
- authoring model + validation,
- deterministic export pipeline,
- runtime simulation (including stateful/channel-aware logic),
- Bedrock bridge scaffold and contract artifacts,
- curated template catalog for common scenarios.

The project is intended to be useful **today** for authoring and simulation, while keeping clear boundaries around what is still MVP/deferred.

## Key Features
- Desktop GUI workspace (PySide6): open, inspect, edit, validate, simulate, and export projects.
- Rule/condition editing loop: `edit -> save -> validate -> simulate`.
- Multi-format project flows:
  - JSON (primary, safest),
  - JS Wrapper,
  - Legacy `AMBIENT_CONFIG` import/export path (best-effort with warnings).
- Deterministic runtime export bundle generation.
- Stateful runtime simulator with cooldown/no-repeat and channel-aware conflict handling.
- Bedrock runtime MVP + API binding scaffold (architecture and contract artifacts).
- Template catalog with ready-to-adapt scenarios.

## Supported Formats

### Authoring/Input
- `JSON` (`.json`) — primary stable format.
- data-only `JavaScript` (`.js`) wrappers:
  - `module.exports = { ... }`
  - `export default { ... }`
  - `export const project = { ... }`
- legacy import:
  - `export const AMBIENT_CONFIG = { ambient_sound_definitions: ... }`

### Save/Export
- `JSON` (recommended default).
- `JS Wrapper`:
  - `export const PROJECT = { ... };`
- `Legacy AMBIENT_CONFIG` (lossy/best-effort downgrade, explicit warning flow).
- Runtime bundle export:
  - `manifest.json`
  - `runtime_rules.json`
  - `runtime_conditions.json`
  - `runtime_assets.json`
  - `export_summary.json`

## Template Catalog / Examples
Use curated templates from:
- `examples/template_catalog/authoring/`
- matching runtime examples in `examples/template_catalog/runtime/`

Included scenario starters:
- day music,
- night music,
- biome ambient,
- weather ambient,
- underwater layer,
- low-health tension,
- contextual one-shot event cue.

Template behavior notes are documented in:
- `docs/event_template_catalog.md`

## Bedrock-Oriented Workflow
1. Author or edit project in GUI (or JSON/JS source file).
2. Validate project consistency (IDs, references, cycles, predicate payloads).
3. Simulate selection behavior locally (context + timeline).
4. Export runtime bundle from tool.
5. Use Bedrock bridge scaffold/contracts in `bedrock/` to wire runtime data into script-side update flow.

Current Bedrock integration is MVP/contract-oriented, not final production gameplay integration.

## Installation / Getting Started

### Prerequisites
- Windows (primary target)
- Python `3.11+`

### Clone and install
```powershell
git clone https://github.com/Djoystick/AmbientAudioTool.git
cd AmbientAudioTool

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e .[dev,gui,build]
```

### Quick start
Validate example:
```powershell
ambient-audio-tool validate examples/biome_music_ref.json
```

Export runtime bundle:
```powershell
ambient-audio-tool export examples/biome_music_ref.json --out out/biome_music_ref
```

Launch GUI:
```powershell
python -m ambient_audio_tool.gui
```

## Build From Source (Developer Workflow)
Run tests:
```powershell
python -m pytest -q
```

Useful CLI commands:
```powershell
ambient-audio-tool summarize <project.json|project.js>
ambient-audio-tool validate <project.json|project.js>
ambient-audio-tool export <project> --out <target> --format runtime|json|js-wrapper|legacy-ambient
ambient-audio-tool simulate <runtime-folder> --biome minecraft:forest --time 12 --weather clear --player-health 20 --seed 7
```

## Build Windows EXE
Build packaged GUI executable with PyInstaller:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
```

Expected output:
- `dist/AmbientAudioTool/AmbientAudioTool.exe`

Bundled data locations in one-dir build:
- `dist/AmbientAudioTool/_internal/assets/ui_audio/`
- `dist/AmbientAudioTool/_internal/examples/`

Optional override path checked first by app:
- `dist/AmbientAudioTool/assets/ui_audio/background_loop.mp3`

Note:
- the repository does **not** ship a music track by default,
- place your own `background_loop.mp3` in `assets/ui_audio/` (source mode) or the override path above (packaged mode) if you want UI background music enabled.

## Uninstall

### Portable/packaged app removal
1. Delete the packaged folder, for example:
   - `dist/AmbientAudioTool/`
2. (Optional) remove persisted GUI config:
   - `%USERPROFILE%\.ambient_audio_tool_gui_config.json`

### Source install removal
If installed in a virtual environment:
1. Deactivate env (if active).
2. Remove project folder and virtual environment.

If installed into a shared Python environment:
```powershell
pip uninstall ambient-audio-tool
```

Optional cleanup:
- remove `%USERPROFILE%\.ambient_audio_tool_gui_config.json`

## Current Status / Verification Notes
Last local verification evidence (March 2026):
- `python -m pytest -q` -> `72 passed`
- PyInstaller packaging rebuild succeeded.
- EXE startup sanity succeeded (`dist/AmbientAudioTool/AmbientAudioTool.exe`).

Known limitations (honest status):
- Bedrock runtime integration is still MVP/bridge-level, not final production runtime.
- Python simulator predicate support is intentionally narrower than full authoring predicate catalog.
- Installer/signing/auto-update flow is not implemented.

## Repository Structure
```text
assets/      UI assets/placeholders (user-supplied GUI background music track)
bedrock/     Bedrock scaffold + bridge/binding artifacts
docs/        public-facing docs/specs for users and contributors
examples/    sample projects + template catalog
scripts/     helper scripts (including EXE build/GUI launch)
src/         application source code
tests/       automated tests
```

## Screenshots / Demo Placeholders
> Add screenshots/gifs in a future docs/media pass.

Suggested placeholders:
- GUI Project tab
- Rule editor dialog
- Simulation timeline output
- Export result summary

## License / Credits
- **License:** not finalized in repository yet (add `LICENSE` before public release policy finalization).
- Project by `Djoystick`.
- Thanks to Minecraft Bedrock modding/community ecosystem and open-source tooling maintainers.
