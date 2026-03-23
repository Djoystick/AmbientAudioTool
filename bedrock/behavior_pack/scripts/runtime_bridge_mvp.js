/*
  Bedrock Runtime Bridge MVP (controlled pass)
  --------------------------------------------
  Purpose:
  - Consume exported runtime data shape:
    runtime_rules.json, runtime_conditions.json, runtime_assets.json
  - Evaluate one context step with channel-aware selection.
  - Maintain runtime state for cooldown and preemption behavior.

  Notes:
  - This is still a bridge MVP, not final Bedrock production runtime.
  - Bedrock API usage is defensive/optional to avoid engine-version hard coupling.
*/

const AAT_DEFAULT_CONTEXT = Object.freeze({
  biome: "minecraft:plains",
  time: 12,
  weather: "clear",
  player_health: 20,
  is_underwater: false,
});

function createRuntimeState() {
  return {
    current_time_ms: 0,
    rule_last_played_at: {},
    asset_last_played_at: {},
    recent_asset_history: [],
    rule_asset_history: {},
    active_channel_selections: {},
  };
}

function createRuntimeBridge(options = {}) {
  const log = typeof options.log === "function" ? options.log : console.log;
  const random = typeof options.random === "function" ? options.random : Math.random;
  const state = options.initialState || createRuntimeState();

  let runtimeBundle = null;
  let indexes = null;

  function setRuntimeBundle(bundle) {
    runtimeBundle = normalizeBundle(bundle);
    indexes = buildIndexes(runtimeBundle);
    log("[AAT] Runtime bundle loaded.");
    return indexes;
  }

  function hasBundle() {
    return indexes !== null;
  }

  function evaluateStep(context, nowMs) {
    if (!indexes) {
      return {
        timestamp_ms: nowMs,
        selections: [],
        state: cloneJson(state),
        reason: "runtime_bundle_not_loaded",
      };
    }

    const safeContext = normalizeContext(context);
    const selectionsByChannel = evaluateSelectionsByChannel(
      indexes,
      safeContext,
      state,
      nowMs,
      random,
    );

    state.current_time_ms = nowMs;
    state.active_channel_selections = selectionsByChannel.active_channel_selections;
    recordStartedSelections(state, nowMs, selectionsByChannel.started_selections);

    return {
      timestamp_ms: nowMs,
      selections: selectionsByChannel.selections,
      state: cloneJson(state),
      reason: "ok",
    };
  }

  function evaluateAndDispatch(context, nowMs, dispatchApi, playerRef = null) {
    const previous = cloneJson(state.active_channel_selections);
    const result = evaluateStep(context, nowMs);
    const actions = buildDispatchActions(previous, state.active_channel_selections);
    applyDispatchActions(actions, dispatchApi, playerRef);
    return { result, actions };
  }

  return {
    setRuntimeBundle,
    hasBundle,
    evaluateStep,
    evaluateAndDispatch,
    getState: () => cloneJson(state),
  };
}

function normalizeBundle(bundle) {
  if (!bundle || typeof bundle !== "object") {
    return { runtime_rules: [], runtime_conditions: [], runtime_assets: [] };
  }
  const rules = Array.isArray(bundle.runtime_rules) ? bundle.runtime_rules : [];
  const conditions = Array.isArray(bundle.runtime_conditions)
    ? bundle.runtime_conditions
    : [];
  const assets = Array.isArray(bundle.runtime_assets) ? bundle.runtime_assets : [];
  return {
    runtime_rules: rules,
    runtime_conditions: conditions,
    runtime_assets: assets,
  };
}

function buildIndexes(bundle) {
  const conditionsById = {};
  for (const entry of bundle.runtime_conditions) {
    if (entry && typeof entry.id === "string") {
      conditionsById[entry.id] = entry;
    }
  }

  const assetsById = {};
  for (const entry of bundle.runtime_assets) {
    if (entry && typeof entry.id === "string") {
      assetsById[entry.id] = entry;
    }
  }

  const rules = [...bundle.runtime_rules].sort((a, b) => {
    const orderA = asInt(a?.export_order, 0);
    const orderB = asInt(b?.export_order, 0);
    if (orderA !== orderB) {
      return orderA - orderB;
    }
    return asString(a?.id).localeCompare(asString(b?.id));
  });

  return { rules, conditionsById, assetsById };
}

function normalizeContext(context) {
  const source = context && typeof context === "object" ? context : {};
  return {
    biome: asString(source.biome || AAT_DEFAULT_CONTEXT.biome),
    time: clamp(asInt(source.time, AAT_DEFAULT_CONTEXT.time), 0, 23),
    weather: asString(source.weather || AAT_DEFAULT_CONTEXT.weather),
    player_health: asInt(
      source.player_health,
      AAT_DEFAULT_CONTEXT.player_health,
    ),
    is_underwater: Boolean(source.is_underwater),
  };
}

function evaluateSelectionsByChannel(indexes, context, state, nowMs, randomFn) {
  const conditionCache = {};
  const candidatesByChannel = {};

  for (const rule of indexes.rules) {
    if (!rule || rule.enabled === false) {
      continue;
    }
    const ruleId = asString(rule.id);
    const channel = asString(rule.channel);
    const conditionRef = asString(rule.condition_ref);
    if (!ruleId || !channel || !conditionRef) {
      continue;
    }
    if (
      !evaluateConditionRef(
        conditionRef,
        indexes.conditionsById,
        context,
        conditionCache,
        new Set(),
      )
    ) {
      continue;
    }

    const randomness = asObject(rule.randomness);
    const cooldown = asObject(rule.cooldown);
    const conflict = asObject(rule.conflict);
    const priority = asObject(rule.priority);

    const probability = asNumber(randomness.probability, 1);
    if (probability <= 0) {
      continue;
    }
    if (probability < 1 && randomFn() > probability) {
      continue;
    }

    const ruleCooldownMs = Math.max(0, asInt(cooldown.rule_cooldown_ms, 0));
    if (isInCooldown(nowMs, state.rule_last_played_at[ruleId], ruleCooldownMs)) {
      continue;
    }

    const assetIds = Array.isArray(rule.asset_ids)
      ? rule.asset_ids.filter((item) => typeof item === "string")
      : [];
    if (!assetIds.length) {
      continue;
    }

    const assetCooldownMs = Math.max(0, asInt(cooldown.asset_cooldown_ms, 0));
    const cooldownEligible = assetIds.filter(
      (assetId) =>
        !isInCooldown(nowMs, state.asset_last_played_at[assetId], assetCooldownMs),
    );
    if (!cooldownEligible.length) {
      continue;
    }

    const noRepeatWindow = Math.max(0, asInt(randomness.no_repeat_window, 0));
    let eligibleAssets = cooldownEligible;
    let reason = "selected";
    if (cooldownEligible.length !== assetIds.length) {
      reason = "selected_after_cooldown_filter";
    }
    if (noRepeatWindow > 0 && cooldownEligible.length > 1) {
      const ruleHistory = Array.isArray(state.rule_asset_history[ruleId])
        ? state.rule_asset_history[ruleId]
        : [];
      const preferred = cooldownEligible.filter(
        (assetId) => !wasPlayedRecently(ruleHistory, assetId, noRepeatWindow),
      );
      if (preferred.length) {
        eligibleAssets = preferred;
        if (preferred.length !== cooldownEligible.length) {
          reason = "selected_after_no_repeat_filter";
        }
      }
    }

    const candidate = {
      channel,
      rule_id: ruleId,
      base_priority: asInt(priority.base_priority, 50),
      weight: Math.max(1, asInt(randomness.weight, 1)),
      max_concurrent: Math.max(1, asInt(conflict.max_concurrent, 1)),
      tie_breaker: asString(conflict.tie_breaker) || "priority_then_weight",
      can_preempt_lower_priority: Boolean(conflict.can_preempt_lower_priority),
      eligible_assets: eligibleAssets,
      last_played_at: state.rule_last_played_at[ruleId],
      reason,
    };
    if (!candidatesByChannel[channel]) {
      candidatesByChannel[channel] = [];
    }
    candidatesByChannel[channel].push(candidate);
  }

  const allChannels = new Set([
    ...Object.keys(candidatesByChannel),
    ...Object.keys(state.active_channel_selections || {}),
  ]);
  const selections = [];
  const startedSelections = [];
  const nextActiveSelections = {};

  for (const channel of [...allChannels].sort()) {
    const candidates = candidatesByChannel[channel] || [];
    const existing = normalizeExistingSelections(
      state.active_channel_selections[channel] || [],
      channel,
    );
    const proposed = selectProposedForChannel(candidates, randomFn);
    const [finalSelections, started] = applyChannelPreemption(existing, proposed);

    if (finalSelections.length) {
      nextActiveSelections[channel] = finalSelections.map(toStateSelection);
      for (const item of finalSelections) {
        selections.push(stripInternal(item));
      }
    }
    if (started.length) {
      for (const item of started) {
        startedSelections.push(stripInternal(item));
      }
    }
  }

  return {
    selections,
    started_selections: startedSelections,
    active_channel_selections: nextActiveSelections,
  };
}

function evaluateConditionRef(conditionId, conditionsById, context, cache, stack) {
  if (cache.hasOwnProperty(conditionId)) {
    return cache[conditionId];
  }
  if (stack.has(conditionId)) {
    return false;
  }
  const entry = conditionsById[conditionId];
  if (!entry || typeof entry !== "object") {
    cache[conditionId] = false;
    return false;
  }
  stack.add(conditionId);
  const result = evaluateConditionNode(entry.root, conditionsById, context, cache, stack);
  stack.delete(conditionId);
  cache[conditionId] = result;
  return result;
}

function evaluateConditionNode(node, conditionsById, context, cache, stack) {
  if (!node || typeof node !== "object") {
    return false;
  }
  const op = asString(node.op);
  if (op === "ALL") {
    const nodes = Array.isArray(node.nodes) ? node.nodes : [];
    return nodes.every((item) =>
      evaluateConditionNode(item, conditionsById, context, cache, stack),
    );
  }
  if (op === "ANY") {
    const nodes = Array.isArray(node.nodes) ? node.nodes : [];
    return nodes.some((item) =>
      evaluateConditionNode(item, conditionsById, context, cache, stack),
    );
  }
  if (op === "NOT") {
    return !evaluateConditionNode(node.node, conditionsById, context, cache, stack);
  }
  if (op === "REF") {
    return evaluateConditionRef(
      asString(node.ref_id),
      conditionsById,
      context,
      cache,
      stack,
    );
  }
  if (op === "PRED") {
    return evaluatePredicate(asObject(node.predicate), context);
  }
  return false;
}

function evaluatePredicate(predicate, context) {
  const type = asString(predicate.type);
  if (type === "biome_is") {
    return asString(predicate.biome) === context.biome;
  }
  if (type === "time_between") {
    const start = clamp(asInt(predicate.start_hour, -1), 0, 23);
    const end = clamp(asInt(predicate.end_hour, -1), 0, 23);
    if (start <= end) {
      return context.time >= start && context.time <= end;
    }
    return context.time >= start || context.time <= end;
  }
  if (type === "weather_is") {
    return asString(predicate.weather) === context.weather;
  }
  if (type === "player_health_range") {
    const min = asNumber(predicate.min_health, Number.NEGATIVE_INFINITY);
    const max = asNumber(predicate.max_health, Number.POSITIVE_INFINITY);
    return context.player_health >= min && context.player_health <= max;
  }
  if (type === "is_underwater") {
    const expected = predicate.hasOwnProperty("value")
      ? Boolean(predicate.value)
      : true;
    return context.is_underwater === expected;
  }
  return false;
}

function selectProposedForChannel(candidates, randomFn) {
  if (!candidates.length) {
    return [];
  }
  const policySorted = [...candidates].sort((a, b) => {
    if (a.base_priority !== b.base_priority) {
      return b.base_priority - a.base_priority;
    }
    return a.rule_id.localeCompare(b.rule_id);
  });
  const policy = policySorted[0];
  const tieBreaker =
    policy.tie_breaker === "priority_then_oldest"
      ? "priority_then_oldest"
      : "priority_then_weight";
  const maxConcurrent = Math.max(1, asInt(policy.max_concurrent, 1));

  const ranked = [...candidates].sort((a, b) =>
    compareCandidates(a, b, tieBreaker),
  );
  const top = ranked.slice(0, maxConcurrent);

  return top.map((candidate) => {
    const assetId = chooseAsset(candidate.eligible_assets, randomFn);
    return {
      channel: candidate.channel,
      selected_rule_id: candidate.rule_id,
      selected_asset_id: assetId,
      reason: candidate.reason,
      _base_priority: candidate.base_priority,
      _can_preempt_lower_priority: candidate.can_preempt_lower_priority,
      _max_concurrent: maxConcurrent,
    };
  });
}

function compareCandidates(a, b, tieBreaker) {
  if (a.base_priority !== b.base_priority) {
    return b.base_priority - a.base_priority;
  }
  if (tieBreaker === "priority_then_oldest") {
    const oldA = oldestSortKey(a.last_played_at);
    const oldB = oldestSortKey(b.last_played_at);
    if (oldA !== oldB) {
      return oldA - oldB;
    }
    if (a.weight !== b.weight) {
      return b.weight - a.weight;
    }
    return a.rule_id.localeCompare(b.rule_id);
  }
  if (a.weight !== b.weight) {
    return b.weight - a.weight;
  }
  const oldA = oldestSortKey(a.last_played_at);
  const oldB = oldestSortKey(b.last_played_at);
  if (oldA !== oldB) {
    return oldA - oldB;
  }
  return a.rule_id.localeCompare(b.rule_id);
}

function applyChannelPreemption(existing, proposed) {
  if (!existing.length) {
    return [proposed, proposed];
  }
  if (!proposed.length) {
    return [
      existing.map((item) => ({ ...item, reason: "kept_previous_no_candidates" })),
      [],
    ];
  }

  const maxConcurrent = Math.max(1, asInt(proposed[0]._max_concurrent, 1));
  const limitedExisting = existing.slice(0, maxConcurrent);
  const limitedProposed = proposed.slice(0, maxConcurrent);

  const existingRuleIds = limitedExisting.map((item) => item.selected_rule_id);
  const proposedRuleIds = limitedProposed.map((item) => item.selected_rule_id);
  if (sameRuleList(existingRuleIds, proposedRuleIds)) {
    return [limitedProposed, limitedProposed];
  }

  const existingPriority = Math.max(
    ...limitedExisting.map((item) => asInt(item._base_priority, 0)),
  );
  const proposedPriority = Math.max(
    ...limitedProposed.map((item) => asInt(item._base_priority, 0)),
  );
  const canPreempt = limitedProposed.some(
    (item) =>
      asInt(item._base_priority, 0) === proposedPriority &&
      Boolean(item._can_preempt_lower_priority),
  );

  if (proposedPriority > existingPriority && canPreempt) {
    const replaced = limitedProposed.map((item) => ({
      ...item,
      reason: "preempted_by_higher_priority",
    }));
    return [replaced, replaced];
  }

  const kept = limitedExisting.map((item) => ({
    ...item,
    reason: "kept_previous_no_preemption",
  }));
  return [kept, []];
}

function normalizeExistingSelections(items, channel) {
  if (!Array.isArray(items)) {
    return [];
  }
  return items.map((item) => ({
    channel: asString(item.channel) || channel,
    selected_rule_id: asString(item.selected_rule_id),
    selected_asset_id: asString(item.selected_asset_id),
    reason: "kept_previous",
    _base_priority: asInt(item.base_priority, 0),
    _can_preempt_lower_priority: Boolean(item.can_preempt_lower_priority),
    _max_concurrent: Math.max(1, asInt(item.max_concurrent, 1)),
  }));
}

function toStateSelection(item) {
  return {
    channel: item.channel,
    selected_rule_id: item.selected_rule_id,
    selected_asset_id: item.selected_asset_id,
    base_priority: asInt(item._base_priority, 0),
    can_preempt_lower_priority: Boolean(item._can_preempt_lower_priority),
    max_concurrent: Math.max(1, asInt(item._max_concurrent, 1)),
  };
}

function stripInternal(item) {
  return {
    channel: item.channel,
    selected_rule_id: item.selected_rule_id,
    selected_asset_id: item.selected_asset_id,
    reason: item.reason,
  };
}

function buildDispatchActions(previousActive, nextActive) {
  const actions = [];
  const channels = new Set([
    ...Object.keys(previousActive || {}),
    ...Object.keys(nextActive || {}),
  ]);

  for (const channel of [...channels].sort()) {
    const prev = Array.isArray(previousActive[channel]) ? previousActive[channel] : [];
    const next = Array.isArray(nextActive[channel]) ? nextActive[channel] : [];

    for (const item of prev) {
      if (!containsSelection(next, item)) {
        actions.push({
          action: "stop",
          channel,
          selected_rule_id: asString(item.selected_rule_id),
          selected_asset_id: asString(item.selected_asset_id),
        });
      }
    }
    for (const item of next) {
      if (!containsSelection(prev, item)) {
        actions.push({
          action: "play",
          channel,
          selected_rule_id: asString(item.selected_rule_id),
          selected_asset_id: asString(item.selected_asset_id),
        });
      }
    }
  }
  return actions;
}

function applyDispatchActions(actions, dispatchApi, playerRef) {
  if (!dispatchApi || typeof dispatchApi !== "object") {
    return;
  }
  for (const action of actions) {
    if (action.action === "play" && typeof dispatchApi.play === "function") {
      dispatchApi.play(action, playerRef);
      continue;
    }
    if (action.action === "stop" && typeof dispatchApi.stop === "function") {
      dispatchApi.stop(action, playerRef);
    }
  }
}

function recordStartedSelections(state, nowMs, startedSelections) {
  if (!Array.isArray(startedSelections)) {
    return;
  }
  for (const item of startedSelections) {
    const ruleId = asString(item.selected_rule_id);
    const assetId = asString(item.selected_asset_id);
    if (ruleId) {
      state.rule_last_played_at[ruleId] = nowMs;
    }
    if (assetId) {
      state.asset_last_played_at[assetId] = nowMs;
      state.recent_asset_history.push(assetId);
      if (ruleId) {
        if (!state.rule_asset_history[ruleId]) {
          state.rule_asset_history[ruleId] = [];
        }
        state.rule_asset_history[ruleId].push(assetId);
      }
    }
  }
}

function containsSelection(list, item) {
  return list.some(
    (candidate) =>
      asString(candidate.channel) === asString(item.channel) &&
      asString(candidate.selected_rule_id) === asString(item.selected_rule_id) &&
      asString(candidate.selected_asset_id) === asString(item.selected_asset_id),
  );
}

function chooseAsset(assetIds, randomFn) {
  if (!Array.isArray(assetIds) || !assetIds.length) {
    return "";
  }
  const index = Math.floor(randomFn() * assetIds.length);
  return asString(assetIds[index]);
}

function isInCooldown(nowMs, lastPlayedMs, cooldownMs) {
  if (cooldownMs <= 0) {
    return false;
  }
  if (typeof lastPlayedMs !== "number") {
    return false;
  }
  return nowMs - lastPlayedMs < cooldownMs;
}

function wasPlayedRecently(history, assetId, windowSize) {
  if (!Array.isArray(history) || windowSize <= 0) {
    return false;
  }
  const start = Math.max(history.length - windowSize, 0);
  const window = history.slice(start);
  return window.includes(assetId);
}

function sameRuleList(left, right) {
  if (left.length !== right.length) {
    return false;
  }
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) {
      return false;
    }
  }
  return true;
}

function oldestSortKey(value) {
  if (typeof value !== "number") {
    return -1;
  }
  return value;
}

function asObject(value) {
  return value && typeof value === "object" ? value : {};
}

function asString(value) {
  return typeof value === "string" ? value : "";
}

function asInt(value, fallback) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function asNumber(value, fallback) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function safeCall(fn, fallbackValue = null) {
  try {
    return fn();
  } catch (_err) {
    return fallbackValue;
  }
}

function createBedrockContextCollector(options = {}) {
  const customCollector =
    typeof options.collectContext === "function" ? options.collectContext : null;

  return function collectContext(playerRef, worldRef) {
    if (customCollector) {
      const custom = safeCall(() => customCollector(playerRef, worldRef), null);
      if (custom && typeof custom === "object") {
        return normalizeContext(custom);
      }
    }

    const fallback = { ...AAT_DEFAULT_CONTEXT };

    const timeOfDay = safeCall(() =>
      typeof worldRef?.getTimeOfDay === "function" ? worldRef.getTimeOfDay() : null,
    );
    if (typeof timeOfDay === "number" && Number.isFinite(timeOfDay)) {
      fallback.time = clamp(Math.trunc(timeOfDay % 24), 0, 23);
    }

    const healthValue = safeCall(() => {
      if (!playerRef || typeof playerRef.getComponent !== "function") {
        return null;
      }
      const component = playerRef.getComponent("minecraft:health");
      if (!component || typeof component !== "object") {
        return null;
      }
      if (typeof component.currentValue === "number") {
        return component.currentValue;
      }
      if (typeof component.value === "number") {
        return component.value;
      }
      return null;
    });
    if (typeof healthValue === "number" && Number.isFinite(healthValue)) {
      fallback.player_health = Math.max(0, Math.trunc(healthValue));
    }

    const underwaterState = safeCall(() => {
      if (!playerRef || typeof playerRef !== "object") {
        return null;
      }
      if (typeof playerRef.isUnderwater === "boolean") {
        return playerRef.isUnderwater;
      }
      if (typeof playerRef.isSwimming === "boolean") {
        return playerRef.isSwimming;
      }
      if (typeof playerRef.isInWater === "boolean") {
        return playerRef.isInWater;
      }
      return null;
    });
    if (typeof underwaterState === "boolean") {
      fallback.is_underwater = underwaterState;
    }

    // Biome/weather APIs vary by Bedrock version; keep conservative defaults unless overridden.
    return normalizeContext(fallback);
  };
}

function createBedrockDispatchApi(options = {}) {
  const customPlay = typeof options.dispatchPlay === "function" ? options.dispatchPlay : null;
  const customStop = typeof options.dispatchStop === "function" ? options.dispatchStop : null;
  const log = typeof options.log === "function" ? options.log : console.log;

  return {
    play(action, playerRef) {
      if (customPlay) {
        safeCall(() => customPlay(action, playerRef), null);
        return;
      }
      if (playerRef && typeof playerRef.playSound === "function") {
        safeCall(() => playerRef.playSound(action.selected_asset_id), null);
        return;
      }
      log(
        `[AAT] play dispatch fallback: channel=${action.channel}, asset=${action.selected_asset_id}`,
      );
    },
    stop(action, playerRef) {
      if (customStop) {
        safeCall(() => customStop(action, playerRef), null);
        return;
      }
      if (playerRef && typeof playerRef.stopSound === "function") {
        safeCall(() => playerRef.stopSound(action.selected_asset_id), null);
        return;
      }
      log(
        `[AAT] stop dispatch fallback: channel=${action.channel}, asset=${action.selected_asset_id}`,
      );
    },
  };
}

function createBedrockHooks(options = {}) {
  const systemRef = options.system_ref || globalThis.system || null;
  const worldRef = options.world_ref || globalThis.world || null;
  const log = typeof options.log === "function" ? options.log : console.log;

  const getPlayers =
    typeof options.getPlayers === "function"
      ? options.getPlayers
      : () => {
          const players = safeCall(() =>
            typeof worldRef?.getAllPlayers === "function" ? worldRef.getAllPlayers() : [],
          );
          return Array.isArray(players) ? players : [];
        };

  const getNowMs =
    typeof options.getNowMs === "function"
      ? options.getNowMs
      : () => {
          const tick = safeCall(() =>
            typeof systemRef?.currentTick === "number" ? systemRef.currentTick : null,
          );
          if (typeof tick === "number" && Number.isFinite(tick)) {
            return Math.trunc(tick * 50);
          }
          return Date.now();
        };

  return {
    system: systemRef,
    world: worldRef,
    log,
    getPlayers,
    getNowMs,
    getContext: createBedrockContextCollector(options),
    dispatchApi: createBedrockDispatchApi(options),
  };
}

function bindBedrockRuntimeLoop(runtimeBridge, hooks, options = {}) {
  if (!runtimeBridge || typeof runtimeBridge.evaluateAndDispatch !== "function") {
    return { bound: false, reason: "runtime_bridge_unavailable" };
  }
  if (!hooks || typeof hooks !== "object") {
    return { bound: false, reason: "hooks_unavailable" };
  }
  const systemRef = hooks.system;
  if (!systemRef || typeof systemRef.runInterval !== "function") {
    return { bound: false, reason: "system_runInterval_unavailable" };
  }

  const tickInterval = Math.max(1, asInt(options.tick_interval_ticks, 20));
  const singlePlayerOnly = Boolean(options.single_player_only);
  const log = typeof hooks.log === "function" ? hooks.log : console.log;

  const intervalHandle = systemRef.runInterval(() => {
    const players = hooks.getPlayers();
    if (!Array.isArray(players) || players.length === 0) {
      return;
    }
    const targetPlayers = singlePlayerOnly ? [players[0]] : players;
    for (const playerRef of targetPlayers) {
      const nowMs = asInt(hooks.getNowMs(systemRef), Date.now());
      const context = hooks.getContext(playerRef, hooks.world);
      const payload = safeCall(
        () =>
          runtimeBridge.evaluateAndDispatch(
            context,
            nowMs,
            hooks.dispatchApi,
            playerRef,
          ),
        null,
      );
      if (payload === null) {
        log("[AAT] evaluateAndDispatch failed for one player tick.");
      }
    }
  }, tickInterval);

  return {
    bound: true,
    tick_interval_ticks: tickInterval,
    single_player_only: singlePlayerOnly,
    interval_handle: intervalHandle,
  };
}

function tryAutoBindBedrockRuntime(runtimeBridge, options = {}) {
  const autoBind = options.auto_bind !== false;
  if (!autoBind) {
    return { bound: false, reason: "auto_bind_disabled" };
  }

  const hooks = createBedrockHooks(options);
  if (!hooks.system || !hooks.world) {
    return {
      bound: false,
      reason: "bedrock_api_unavailable",
      has_system: Boolean(hooks.system),
      has_world: Boolean(hooks.world),
    };
  }

  return bindBedrockRuntimeLoop(runtimeBridge, hooks, options);
}

/*
  Bootstrap strategy:
  - Keep bundle injection contract:
    globalThis.AAT_RUNTIME_BUNDLE = { runtime_rules, runtime_conditions, runtime_assets }.
  - Expose bridge and binding helpers on globalThis.
  - Attempt conservative Bedrock auto-binding only if system/world are available.
*/
const runtimeBridge = createRuntimeBridge();

if (globalThis && globalThis.AAT_RUNTIME_BUNDLE) {
  runtimeBridge.setRuntimeBundle(globalThis.AAT_RUNTIME_BUNDLE);
}

globalThis.AAT_RUNTIME_BRIDGE = runtimeBridge;
globalThis.AAT_CREATE_BEDROCK_HOOKS = createBedrockHooks;
globalThis.AAT_BIND_BEDROCK_RUNTIME_LOOP = (options = {}) =>
  bindBedrockRuntimeLoop(runtimeBridge, createBedrockHooks(options), options);

const bindingOptions =
  globalThis && globalThis.AAT_BEDROCK_BINDING_OPTIONS
    ? asObject(globalThis.AAT_BEDROCK_BINDING_OPTIONS)
    : {};
globalThis.AAT_BEDROCK_BINDING = tryAutoBindBedrockRuntime(
  runtimeBridge,
  bindingOptions,
);
