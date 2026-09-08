# `plumber check` validator design

Type: prototype
Status: open
Blocked by: 02

## Question

Decide how `plumber check` inspects a repo's phase modules for contract
adherence — this is also the capability the AI skill consumes for its rework
recommendations.

- Inspection method: static (AST) / import-and-introspect signatures / runtime
  probe with a small synthetic `GeoDataFrame` fixture — or a layered combination.
- What it checks: `run()` present and signature-compatible with `PhaseModule`;
  no obvious shared-state / global-order violations; declared vs. actual dtypes;
  CRS-preservation constraint; params in config match `run()`'s accepted kwargs.
- Output shape: machine-readable (for the skill) + human-readable; per-phase
  pass/fail with actionable messages.
- Where it runs: standalone `plumber check`, and/or an automatic preflight before
  `plumber run`.

Build a rough prototype against 2–3 stub phase modules (one clean, one with a
bad signature, one with a dtype/CRS violation) to pressure-test the approach.
Link the prototype from this ticket.
