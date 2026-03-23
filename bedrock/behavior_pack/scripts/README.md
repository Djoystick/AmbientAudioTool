# Scripts Folder (Bridge Scaffold)

This folder contains the Bedrock runtime bridge artifacts.

## Files
- `runtime_bridge_mvp.js`: controlled MVP runtime bridge layer (condition evaluation + channel selection + state updates + dispatch action diff).
- `runtime_bridge_stub.js`: legacy non-final pseudocode artifact kept for reference.
- `runtime_bridge_design.md`: contract notes for runtime loop and state ownership.
- `bedrock_api_binding_flow.md`: narrow Bedrock API scheduling/wiring flow for MVP bridge.
- `runtime_bundle_injection.example.js`: example injection pattern for exported runtime data.
- `examples/`: minimal contract examples (bundle/context/expected step).

## Important
- This is still not a final production-ready Bedrock runtime.
- API/event names are intentionally conservative and may need engine-version verification.
- Exported runtime JSON structure is treated as backward-compatible contract input.
