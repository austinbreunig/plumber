# Phase discovery & ordering

Type: grilling
Status: open
Blocked by: —

## Question

How does the `plumber` CLI, run from an arbitrary repo, find that repo's phase
modules and determine their execution order?

Decide between (and/or combine): a conventioned `phases/` directory ordered by
filename prefix; an explicit ordered list in the config file; a
registry/decorator the modules opt into. Resolve the design-doc section 7 open
thread — string names in the pipeline list vs. module-object introspection for
keying per-phase params. Output: the discovery mechanism, the ordering source of
truth, and how a phase's identity string is formed and matched to its config
params.

## Input from research

Ticket 09 (`research/pipeline-framework-prior-art.md`) recommends the **Ploomber**
model: an explicit ordered step list in the config file, each entry a dotted path
resolved directly to `<module>.run`, no project skeleton or package layout
required (Kedro/Dagster/Prefect all fail "run from any repo" by requiring one).
No DAG inference, no named IO ports — the chain is linear, one gdf passed through.
Per-phase params keyed by the config entry, not by module introspection.
