# Runtime Bridge Design (Phase 6)

## Scope
Define how Bedrock script runtime consumes exported runtime JSON from Python and runs update passes.

This document does not claim full Bedrock API completeness.
Predicate/runtime parity with the Python simulator is staged and may differ by phase.

## Current MVP Script
- `runtime_bridge_mvp.js` is the active bridge entry in behavior pack manifest.
- It provides:
  - runtime bundle ingestion (`runtime_rules`, `runtime_conditions`, `runtime_assets`),
  - condition evaluation (`ALL`, `ANY`, `NOT`, `REF`, `PRED` subset),
  - channel-aware selection,
  - cooldown and anti-repeat behavior,
  - preemption decision logic,
  - state updates and dispatch action diff (`play`/`stop` conceptual actions).
  - narrow Bedrock API binding helpers (tick scheduling + context/dispatch hooks).

## Data Inputs
Behavior pack data path:
- `data/runtime/runtime_rules.json`
- `data/runtime/runtime_conditions.json`
- `data/runtime/runtime_assets.json`
- `data/runtime/manifest.json` (optional verification/diagnostics)

Runtime bundle shape consumed by MVP:
```json
{
  "runtime_rules": [...],
  "runtime_conditions": [...],
  "runtime_assets": [...]
}
```

## Bridge Responsibilities
1. Load runtime data on script init.
2. Build in-memory indexes:
   - `rulesByChannel`
   - `conditionsById`
   - `assetsById`
3. Track per-player/per-world runtime state:
   - rule/asset last played timestamps
   - recent asset history
   - active channel selections
4. On update tick/window:
   - collect context (biome/time/weather/player health/etc.)
   - run evaluator pass
   - compare previous vs new channel selections
   - dispatch start/stop/replace audio events
5. Emit optional debug/diagnostic counters in development mode.

## Channel Mapping Guidance
Python runtime channels map to Bedrock dispatch categories:
- `music`
- `ambient_noise`
- `context_oneshot`
- `event_alert`

Bridge should keep this mapping centralized in one script object so changes are easy.

## One Update Pass (Conceptual)
1. Snapshot context.
2. Evaluate candidates.
3. Apply cooldown/no-repeat/channel conflict rules.
4. Produce channel `selections[]`.
5. Compute delta from `active_channel_selections`.
6. Dispatch sound play/stop actions.
7. Persist updated state.

Implementation note:
- Bedrock file I/O strategy is still environment-dependent.
- MVP bridge currently supports injection via `globalThis.AAT_RUNTIME_BUNDLE`.
- See `runtime_bundle_injection.example.js`.
- API binding notes: `bedrock_api_binding_flow.md`.

## Event-Driven vs Polled
Polled:
- time of day
- weather
- health/state snapshots

Event-driven:
- custom events (from Bedrock gameplay hooks or script-internal triggers)
- transition markers (enter/leave biome) when available

Fallback:
- if event hooks are unavailable, derive transitions by comparing snapshots over time.

## Deferred in This Phase
- Final Bedrock event catalog and exact API calls by game version.
- Final sound dispatch implementation in script.
- Full resource pack sound definition wiring.
- Multiplayer authority/ownership model.
