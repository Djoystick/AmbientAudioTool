# Update Pass Mapping (Python Runtime -> Bedrock Script)

## Purpose
Show how one Python runtime simulation step maps to a future Bedrock script update pass.

## Mapping
1. Read context from player/world snapshot.
2. Read current in-script runtime state.
3. Evaluate selections using runtime rules/conditions/assets.
4. Produce channel `selections[]`.
5. Compare with `active_channel_selections`:
   - unchanged -> keep playing
   - replaced -> stop old, start new
   - removed -> stop old
6. Persist updated state.

MVP script mapping:
- `runtime_bridge_mvp.js` performs steps 2-6 directly.
- Input bundle is injected as:
  - `globalThis.AAT_RUNTIME_BUNDLE = { runtime_rules, runtime_conditions, runtime_assets }`.

## Input Files
- `data/runtime/runtime_rules.json`
- `data/runtime/runtime_conditions.json`
- `data/runtime/runtime_assets.json`

## Output Events (Conceptual)
- `play_sound(channel, asset_id, player_scope)`
- `stop_channel(channel, player_scope)`

These are conceptual and require verified Bedrock API binding in a later phase.
