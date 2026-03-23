# Bedrock Integration Scaffold

This folder is the Phase 6 integration target for Minecraft Bedrock add-on runtime bridging.

It is intentionally a scaffold, not a complete in-game runtime.

## Purpose
- Define where exported runtime files from Python should be placed in a Bedrock behavior pack.
- Define the script bridge boundary (load data, collect context, evaluate selection, dispatch sounds).
- Reduce uncertainty before full Bedrock runtime implementation.

## Current Status
- Structure and contract artifacts are present.
- Script bridge now includes a controlled MVP runtime layer (`runtime_bridge_mvp.js`).
- Manifest files are scaffolding placeholders and may require UUID/version updates for real deployment.

## Python Export -> Bedrock Copy Target
Copy exported files into:
- `bedrock/behavior_pack/data/runtime/runtime_rules.json`
- `bedrock/behavior_pack/data/runtime/runtime_conditions.json`
- `bedrock/behavior_pack/data/runtime/runtime_assets.json`
- `bedrock/behavior_pack/data/runtime/manifest.json` (optional for diagnostics/version checks)

See:
- `bedrock/behavior_pack/data/runtime_file_mapping.example.json`
- `bedrock/behavior_pack/scripts/runtime_bridge_design.md`
- `bedrock/behavior_pack/scripts/runtime_bundle_injection.example.js`
- `bedrock/behavior_pack/scripts/bedrock_api_binding_flow.md`
