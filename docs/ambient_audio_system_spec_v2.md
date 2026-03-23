# Ambient Audio System Spec v2

## 1. Executive Summary
This system provides a desktop authoring workflow for Minecraft Bedrock add-on audio that compiles into a runtime package consumed by Bedrock scripts. Authors import audio assets, define rules for when sounds should play, and export a deterministic runtime bundle.

The v2 design solves key issues in the current concept:
- Separates authoring concerns from runtime concerns.
- Replaces ad-hoc filters with a typed, validated condition model.
- Adds explicit policies for priority, conflict resolution, randomness, and anti-repeat behavior.
- Defines a normalized export format optimized for runtime evaluation and performance.

## 2. Analysis of the Current Config Concept
### Strengths
| Area | Strength |
|---|---|
| Structure | Existing `ambient_sound_definitions` and global/biome scope concepts are useful primitives. |
| Grouping | Event groups (`music`, `noise`, `sounds`) map naturally to playback categories. |
| Filtering | `all_of` / `any_of` shows an intent for composable condition logic. |
| Audio Metadata | `event_name`, `length_seconds`, and delay ranges are good scheduling inputs. |
| Selection | Weighted events and priorities enable non-deterministic variety and conflict handling. |

### Weaknesses
| Area | Weakness |
|---|---|
| Semantics | Condition leaves are often implicit/untyped, making validation and tooling difficult. |
| Reuse | No first-class reusable condition sets or biome groups with centralized ownership. |
| Runtime Fit | Authoring format appears close to runtime behavior, risking script complexity and drift. |
| Conflict Policy | Priority and suppression rules are under-specified for ties, transitions, and fallback. |
| Anti-Repeat | Cooldown/no-repeat logic is not modeled as a first-class policy object. |

### Scaling Risks
- Rule explosion as dimensions increase (biome + weather + time + player state + events).
- Inconsistent behavior if multiple authors define similar filters differently.
- Runtime performance degradation if scripts must evaluate deep raw trees every tick.
- Package instability if asset mappings are not canonicalized at export.

### Missing Concepts
- Explicit condition typing and schema-level validation.
- Transition-aware triggers (entering/leaving biome, rising danger state).
- Channel-level concurrency policy.
- Deterministic tie-breaking and fallback sequence.
- Export manifest with stable IDs, hashes, and diagnostics.

## 3. Proposed High-Level Architecture
### Components
| Layer | Responsibility | Output |
|---|---|---|
| Desktop Authoring App | Import audio, edit rules/policies, validate, preview, version project | Authoring project file |
| Data Model / Schema | Typed entities and constraints, reusable references, defaults | In-memory model + schema validation errors |
| Export/Generation Pipeline | Normalize conditions, compile lookup indexes, emit runtime bundle | Runtime JSON + asset package + manifest |
| Bedrock Runtime Script Layer | Load bundle, evaluate context, pick candidates, apply policies, trigger sounds | In-game playback behavior |
| Audio Asset/Package Structure | Canonical file layout and sound mapping | Stable folder tree and mapping files |

### Separation Contract
- Authoring format: expressive, user-friendly, supports references and comments/labels.
- Runtime format: normalized, denormalized indexes, minimal branching, no editor-only metadata.

## 4. Proposed Data Model v2
| Entity | Responsibility | Key Fields |
|---|---|---|
| AudioAsset | Source file and technical metadata | `id`, `path`, `durationMs`, `loudnessLUFS?`, `tags[]` |
| Rule | Top-level playable rule binding conditions + playback | `id`, `channel`, `conditionExprId`, `playbackPolicyId`, `enabled` |
| ConditionGroup | Reusable boolean logic subtree | `id`, `name`, `expr` |
| PlaybackPolicy | How and when an item starts/stops | `mode(loop|oneshot)`, `fadeInMs`, `fadeOutMs`, `minGapMs` |
| PriorityPolicy | Relative importance and boosts | `basePriority`, `boosts[]`, `suppressionThreshold` |
| RandomnessPolicy | Controlled variation | `weight`, `probability`, `rotationPool`, `jitterMs` |
| CooldownPolicy | Anti-repeat controls | `cooldownMs`, `noRepeatWindow`, `perAssetWindow` |
| ConflictPolicy | Candidate arbitration in same tick/window | `scope(channel|global)`, `maxConcurrent`, `tieBreaker` |
| BiomeGroup | Reusable named biome sets | `id`, `biomes[]`, `includeTags[]` |
| ContextTrigger | Edge/transition trigger definition | `id`, `type`, `windowMs`, `debounceMs` |
| StateSnapshot | Runtime context frame | biome/time/weather/player/combat/location fields |
| ExportManifest | Package metadata and checksums | `specVersion`, `generatedAt`, `contentHash`, `files[]`, `diagnostics[]` |

### Minimal Authoring Shape (example)
```json
{
  "rule": {
    "id": "rule_forest_dawn_music",
    "channel": "music",
    "conditionExprId": "expr_forest_dawn_safe",
    "playbackPolicyId": "pb_music_default",
    "priorityPolicyId": "prio_music_base",
    "randomnessPolicyId": "rnd_music_forest",
    "cooldownPolicyId": "cd_music_long"
  }
}
```

## 5. Condition System Design
### Model: Typed Condition Expression Graph
Use a typed expression AST/DAG with explicit operators and leaf predicates.

Operators:
- `ALL` (AND)
- `ANY` (OR)
- `NOT`
- `REF` (reference another named expression)

Leaf predicates (typed):
- `biomeIs`, `biomeInGroup`
- `timeBetween`
- `weatherIs`
- `playerHealthRange`, `playerHungerRange`, `playerArmorRange`
- `isUnderwater`, `isUnderground`, `isInCave`, `isOnSurface`
- `heightRange`, `distanceFromSpawnRange`
- `dangerStateIs` (`combat`, `danger`, `peaceful`)
- `transitionEvent` (`enter_biome`, `leave_biome`, etc.)
- `customEvent` (user-defined runtime event IDs)

### Why stronger than plain `all_of` / `any_of`
- Typed leaves with field-level validation.
- Reusable `REF` nodes to avoid duplication.
- Supports NOT cleanly without ad-hoc inversion hacks.
- Export-time normalization and simplification (constant folding, dead branch removal).
- Future extension by adding leaf predicate types without changing operator semantics.

### Nesting and Validation Rules
| Rule | Validation |
|---|---|
| `NOT` | Must have exactly one child |
| `ALL` / `ANY` | Must have at least two children |
| `REF` | Must resolve to existing expression and be cycle-free |
| Predicates | Typed payload required; unknown fields rejected |
| Transition predicates | Require `windowMs` and edge source (`prevState` vs `currentState`) |

### Extensibility
- New predicate types registered via `predicateCatalog` with schema + runtime evaluator binding.
- Versioned condition spec (`conditionSpecVersion`) to support migrations.

## 6. Playback Model
### Channels
| Channel | Purpose | Default Behavior |
|---|---|---|
| `music` | Long-form background tracks | Low concurrency (usually 1) with fades |
| `ambient_noise` | Looping environmental texture | Can layer with music; capped concurrency |
| `context_oneshot` | Short contextual cues | Burst-limited, short cooldown |
| `event_alert` | High-priority alerts | Preempt lower channels if configured |
| `layer_optional` | Optional decorative layers | Disabled by default unless explicitly enabled |

### Concurrency Rules
- Global cap: max simultaneous instances across all channels.
- Per-channel cap: configurable hard limit.
- `event_alert` can preempt `ambient_noise` and optionally duck `music`.
- `music` tracks are mutually exclusive by default.
- `context_oneshot` can overlap with `music` but must respect anti-spam limits.

## 7. Priority and Conflict Resolution
### Arbitration Algorithm (per evaluation cycle)
1. Build eligible candidate list from condition matches.
2. Compute `effectivePriority = basePriority + contextualBoosts - suppressionPenalties`.
3. Remove candidates blocked by cooldown/no-repeat/global spam gate.
4. Partition by channel and apply per-channel conflict policy.
5. Apply suppression rules against stronger active/queued events.
6. Tie-break using deterministic order:
   1. Higher `effectivePriority`
   2. Higher `recencyPenaltyAdjustedWeight`
   3. Lower `lastPlayedAt` recency score (older wins)
   4. Stable `ruleId` lexical order for determinism
7. Apply fallback candidate if no candidate survives.

### Fallback Behavior
- Channel fallback chain: `event_alert -> context_oneshot -> ambient_noise -> music` (configurable).
- If no fallback exists, emit no action and log debug metric.

### Anti-Spam
- Per-rule trigger debounce.
- Per-channel minimum trigger gap.
- Global burst limiter (e.g., max N oneshots within T seconds).

## 8. Randomness and Repetition Control
| Mechanism | Purpose | Notes |
|---|---|---|
| Probability Gate | Skip some eligible plays | Evaluated before weighted pick |
| Weighted Selection | Prefer certain assets | Weight can be static or context-adjusted |
| No-Repeat Window | Prevent recently used items | Sliding window by rule or asset |
| Cooldown | Block retrigger for fixed time | Per rule and optionally per asset |
| Min/Max Delay | Natural timing for loops | Delay sampled after each completion |
| Jitter | Avoid synchronized starts | Small random offset around scheduled time |
| Rotation Pool | Enforce variety cycle | Do not repeat until pool exhausted/reset |

### Practical Example
- Forest daytime ambient pool has 6 clips.
- Probability gate = 0.65 each cycle.
- Weighted pick favors rare bird calls only near dawn.
- Rotation pool prevents same clip twice until 4 unique clips played.
- Cooldown of 25s per clip and 8s per rule prevents rapid retriggers.

## 9. Export Design
### Authoring Format vs Runtime Export
| Format | Purpose | Characteristics |
|---|---|---|
| Authoring Project | Editable source of truth | Rich metadata, labels, comments, reusable references |
| Runtime Bundle | Script-consumable payload | Normalized IDs, flattened indexes, no editor-only fields |

### Recommended Generated Outputs
```text
/export
  /assets
    /audio
      music/*.ogg
      ambient/*.ogg
      oneshot/*.ogg
      alerts/*.ogg
  /runtime
    ambient_rules.runtime.json
    condition_index.runtime.json
    playback_policies.runtime.json
    cooldown_tables.runtime.json
  /bedrock
    sounds.json
    sound_definitions.generated.json
  export_manifest.json
```

### Runtime Normalized Snippet (example)
```json
{
  "ruleId": "rule_forest_dawn_music",
  "channel": "music",
  "expr": {"op":"ALL","nodes":["pred_biome_forest","pred_time_dawn","pred_peaceful"]},
  "assetPool": ["asset_music_forest_01","asset_music_forest_02"],
  "priority": {"base": 50, "boostRefs": ["boost_dawn"]},
  "cooldown": {"ruleMs": 90000, "assetMs": 120000}
}
```

## 10. Minecraft Bedrock Runtime Responsibilities
### Runtime Script Must
- Load generated runtime JSON tables on world/script init.
- Maintain `StateSnapshot` each tick or coarse interval.
- Detect transitions by comparing previous/current snapshots.
- Evaluate eligible rules with indexed predicate evaluation.
- Apply conflict/priority/randomness/cooldown pipeline.
- Start, stop, fade, or duck sounds per channel policy.
- Track active instances, recent history, and cooldown timers.
- Emit diagnostic counters (debug mode) for dropped/suppressed rules.

### Performance Considerations
- Evaluate at fixed interval (e.g., 250-1000ms) instead of every tick where possible.
- Use predicate indexes (biome/time/weather first) to reduce candidate set.
- Cache expression results for unchanged snapshot segments.
- Keep runtime payload compact; avoid editor metadata in exported files.

## 11. GUI Planning Inputs
Future UI must support:
- Importing audio files and auto-reading duration/format.
- Assigning categories/channels and asset tags.
- Building condition expressions with reusable groups and NOT logic.
- Defining custom events and transition triggers.
- Configuring priorities, boosts, randomness, cooldown, and conflict policies.
- Preview/simulation mode using synthetic state timeline.
- Validation panel with actionable warnings/errors.
- Export action with manifest + diagnostics summary.

## 12. Recommended Implementation Roadmap
| Phase | Goals | Risks | Definition of Done |
|---|---|---|---|
| 1. Schema/Spec | Finalize v2 entities, condition grammar, versioning | Over-modeling before runtime validation | JSON Schema + spec doc + sample projects |
| 2. Validation Layer | Semantic checks (cycles, unreachable rules, conflicts) | False positives hurting UX | CLI/engine validator with deterministic diagnostics |
| 3. Exporter | Compile authoring project to runtime bundle | Mismatch with Bedrock expectations | Reproducible export + manifest + snapshot tests |
| 4. Runtime Prototype | Implement script evaluator and playback arbiter | Bedrock API limitations/perf | In-game prototype proving core channels/policies |
| 5. GUI | Editor workflows for rules and assets | Complexity creep in first UI version | Usable MVP for import/edit/validate/export |
| 6. EXE Packaging | Desktop distribution and update strategy | Native packaging and signing issues | Installable signed Windows build with smoke tests |

## 13. Risks and Assumptions
### Assumptions Requiring Bedrock Verification
- Assumption A1: Runtime scripts can reliably access all needed context signals (biome, weather, player state, transitions). If unavailable, these must be approximated.
- Assumption A2: Sound playback API supports enough control for channel-level stop/fade/duck behavior. If fade/duck is limited, emulate with stop/start and priority simplification.
- Assumption A3: Event hooks for custom gameplay events are available or can be proxied through script-owned triggers.

### Likely Bottlenecks
- Large rule sets with deep condition graphs evaluated too frequently.
- Transition detection churn if snapshot resolution is too high.
- Excessive one-shot candidate generation causing arbitration overhead.

### Approximation Zones
- `underground/cave/surface` may need heuristic definitions.
- `danger/combat/peaceful` may require synthesized state from nearby entities/events.
- Distance-from-spawn in multiplayer may need per-player local context strategy.

## 14. Final Recommendation
Recommended next step: implement **Phase 1 (Schema/Spec freeze)** as a small, testable package containing:
- v2 JSON schemas for authoring and runtime formats,
- condition predicate catalog with validator contracts,
- 3-5 canonical example projects,
- and a rule evaluation pseudocode appendix.

This de-risks all later work by locking data contracts before building exporter/runtime/GUI.
