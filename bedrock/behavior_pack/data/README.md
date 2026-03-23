# Behavior Pack Data Contract (Scaffold)

This directory is the script-consumable data location for exported runtime payloads.

## Expected Runtime Payload Placement
Copy generated files from Python export output into `data/runtime/`:
- `runtime_rules.json`
- `runtime_conditions.json`
- `runtime_assets.json`
- `manifest.json` (optional, recommended)

## Ownership
- Python side owns generation and normalization.
- Bedrock script side owns runtime consumption and in-game dispatch.
- Runtime bridge MVP expects exported arrays as:
  - `runtime_rules`
  - `runtime_conditions`
  - `runtime_assets`

See:
- `runtime_file_mapping.example.json`
- `scripts/runtime_bridge_design.md`
