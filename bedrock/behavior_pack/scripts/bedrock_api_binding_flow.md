# Bedrock API Binding Flow (Narrow MVP Pass)

## Purpose
Describe the minimal Bedrock-side wiring around `runtime_bridge_mvp.js`:
- scheduling loop,
- context collection hooks,
- play/stop dispatch hooks.

This pass does not change exporter/runtime bundle schema.

## Preserved Runtime Bundle Contract
Injected bundle shape (unchanged):
```js
globalThis.AAT_RUNTIME_BUNDLE = {
  runtime_rules: [...],
  runtime_conditions: [...],
  runtime_assets: [...],
};
```

## Binding Entry Points Exposed by MVP Script
- `globalThis.AAT_RUNTIME_BRIDGE`
- `globalThis.AAT_CREATE_BEDROCK_HOOKS(options)`
- `globalThis.AAT_BIND_BEDROCK_RUNTIME_LOOP(options)`
- `globalThis.AAT_BEDROCK_BINDING` (auto-bind result)

## Auto-Bind Behavior
On script startup, bridge attempts:
1. read `globalThis.AAT_BEDROCK_BINDING_OPTIONS` (optional),
2. detect Bedrock `system` and `world`,
3. if available, bind `system.runInterval(...)`,
4. each tick:
   - get players (`world.getAllPlayers`),
   - build context,
   - evaluate and dispatch.

If APIs are unavailable, binding result is non-fatal:
- `{ bound: false, reason: "bedrock_api_unavailable" }`

## Hook Points
### Context hook
- `collectContext(playerRef, worldRef)` via options override.
- Default collector uses conservative fallbacks:
  - time from `world.getTimeOfDay()` when available,
  - health from `player.getComponent("minecraft:health")` when available,
  - underwater from player flags when available.

### Dispatch hooks
- `dispatchPlay(action, playerRef)` override
- `dispatchStop(action, playerRef)` override
- default behavior:
  - play: `player.playSound(...)` when available, otherwise log fallback,
  - stop: `player.stopSound(...)` when available, otherwise log fallback.

## Binding Options (MVP)
Supported keys:
- `auto_bind: boolean` (default `true`)
- `tick_interval_ticks: number` (default `20`)
- `single_player_only: boolean` (default `false`)
- `collectContext(playerRef, worldRef)` custom function
- `getPlayers()` custom function
- `getNowMs(systemRef)` custom function
- `dispatchPlay(action, playerRef)` custom function
- `dispatchStop(action, playerRef)` custom function
- `system_ref` / `world_ref` for explicit runtime injection

## Example
See:
- `scripts/examples/binding_options_mvp_example.json`
- `scripts/runtime_bundle_injection.example.js`
