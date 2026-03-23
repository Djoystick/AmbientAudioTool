/*
  Runtime bundle injection example (non-final helper artifact)
  ------------------------------------------------------------
  Purpose:
  - Show expected shape for feeding exported runtime JSON data into
    runtime_bridge_mvp.js without changing exporter file format.

  Workflow:
  1) Export project with Python runtime exporter.
  2) Copy arrays from runtime_rules.json / runtime_conditions.json / runtime_assets.json.
  3) Paste into AAT_RUNTIME_BUNDLE below (or generate this file externally).
*/

globalThis.AAT_RUNTIME_BUNDLE = {
  runtime_rules: [
    // Paste runtime_rules.json array entries here.
  ],
  runtime_conditions: [
    // Paste runtime_conditions.json array entries here.
  ],
  runtime_assets: [
    // Paste runtime_assets.json array entries here.
  ],
};

