# Event / Template Catalog

This catalog provides practical scenario templates aligned with the current authoring model, exporter, and runtime bundle contract.

## Template Index

| Template | Authoring File | Runtime Example | Purpose |
|---|---|---|---|
| Day music (forest) | `examples/template_catalog/authoring/day_music_forest.json` | `examples/template_catalog/runtime/day_music_forest.runtime.json` | Background daytime music in forest biome. |
| Night music (swamp) | `examples/template_catalog/authoring/night_music_swamp.json` | `examples/template_catalog/runtime/night_music_swamp.runtime.json` | Background nighttime music in swamp biome. |
| Biome ambient (forest birds) | `examples/template_catalog/authoring/biome_ambient_forest_birds.json` | `examples/template_catalog/runtime/biome_ambient_forest_birds.runtime.json` | Biome-local ambient noise layer. |
| Weather ambient (rain) | `examples/template_catalog/authoring/weather_rain_ambient.json` | `examples/template_catalog/runtime/weather_rain_ambient.runtime.json` | Rain-driven ambient layer. |
| Underwater layer | `examples/template_catalog/authoring/underwater_layer.json` | `examples/template_catalog/runtime/underwater_layer.runtime.json` | Underwater ambience when submerged. |
| Low-health tension layer | `examples/template_catalog/authoring/low_health_tension_layer.json` | `examples/template_catalog/runtime/low_health_tension_layer.runtime.json` | Tension music layer at low health. |
| Contextual one-shot (enter cave) | `examples/template_catalog/authoring/contextual_oneshot_enter_cave.json` | `examples/template_catalog/runtime/contextual_oneshot_enter_cave.runtime.json` | One-shot contextual cue driven by custom event. |

## Template Details

### 1) Day music (forest)
- Purpose: loop-friendly daytime biome music.
- Conditions used: `biome_is` + `time_between`.
- Expected behavior: eligible only in forest during 06:00-17:00.
- Limitations/assumptions: weather is not constrained in this template.

### 2) Night music (swamp)
- Purpose: nighttime swamp music.
- Conditions used: `biome_is` + `ANY(time_between 18-23, time_between 0-5)`.
- Expected behavior: eligible in swamp during night windows.
- Limitations/assumptions: weather and danger state are not constrained.

### 3) Biome ambient (forest birds)
- Purpose: persistent ambient noise texture in forest.
- Conditions used: `biome_is`.
- Expected behavior: low-priority ambient layer in forest.
- Limitations/assumptions: not weather-sensitive by default.

### 4) Weather ambient (rain)
- Purpose: add ambient rain layer while raining.
- Conditions used: `weather_is`.
- Expected behavior: enabled only when weather is `rain`.
- Limitations/assumptions: biome/time are intentionally unconstrained.

### 5) Underwater layer
- Purpose: add underwater ambiance when submerged.
- Conditions used: `is_underwater`.
- Expected behavior: underwater-only ambient layer.
- Limitations/assumptions:
  - current Python simulator does not evaluate `is_underwater` yet (use as Bedrock bridge/runtime contract template),
  - does not differentiate biome/depth.

### 6) Low-health tension layer
- Purpose: elevate tension when health is critical.
- Conditions used: `player_health_range`.
- Expected behavior: high-priority music layer at health `0..8`.
- Limitations/assumptions: danger/combat state is not required in this minimal template.

### 7) Contextual one-shot (enter cave)
- Purpose: emit one-shot sound on a custom transition event.
- Conditions used: `custom_event` (`evt_enter_cave`).
- Expected behavior: one-shot cue when event is raised.
- Limitations/assumptions:
  - requires event production from runtime bridge/game hooks,
  - current Python simulator does not evaluate `custom_event` yet,
  - runtime evaluation support for custom events depends on bridge/event integration maturity.

## How To Build New Scenarios From Templates
1. Copy the closest template from `examples/template_catalog/authoring/`.
2. Rename `project_id`, asset IDs, condition IDs, and rule IDs.
3. Replace condition predicates first, then tune priority/randomness/cooldown.
4. Export to runtime bundle and compare with matching template runtime example shape.
5. Validate and simulate in GUI/CLI; then integrate into Bedrock bridge pipeline.
