# plumber

A geospatial data-engineering pipeline framework. A stable function-shaped phase
interface (`run(gdf, **params) -> gdf`) separates three concerns that are usually
tangled: *what an algorithm does*, *how phases are sequenced and scaled*, and
*how a pipeline is specified*. That separation is meant to make both
prototyping→production scaling and safe agentic pipeline generation tractable —
new logic drops into a fixed slot instead of modifying a monolith.

## Status

Phase 3 (Tracer). `run`, `check`, `localmp`, checkpoints and partial runs work. See
[issue #1](https://github.com/austinbreunig/plumber/issues/1) for the wayfinder map and
`plan.md` for the design.

## Quickstart

```bash
pipx install ab-plumber
```

In any repo, write your input function, one or more phases, and an output function.
A phase is `run(gdf, **params) -> gdf`. Then add a `plumber.yaml`:

```yaml
input:
  path: myio:load_roads
  params: {path: data/roads.parquet}
phases:
  - path: phases.buffer:run
    partitionable: true
    params: {distance: 10}
output:
  path: myio:write_parquet
  params: {path: out/roads.parquet}
```

Check it, then run it:

```bash
plumber check                  # PASS/WARN/FAIL per phase, also writes report.json
plumber run                    # one process (local)
plumber run --strategy localmp --worker-count 4   # worker processes, same output
```

Optional: `checkpoint: true` on a slow phase saves its output, and
`plumber run --from <phase> --to <phase>` runs a slice.

## Execution strategy

Default is `local` (one process). Switch to `localmp` (worker processes) with no phase
changes:

```yaml
execution:
  strategy: localmp
  partition:            # pick exactly one
    by: [zone_id]       # one piece per unique value combination
    # chunk_size: 10000 # fixed-size row slices, in order
    # worker_count: 8   # N roughly equal slices
```

CLI flags override the config: `--strategy localmp`, `--by zone_id`, `--chunk-size 10000`,
`--worker-count 8`. Any partition flag replaces the config's whole `partition:` block.
A phase with `partitionable: false` gets the joined data once. The output keeps the input's
row order, and the output function runs once on the joined data.

## Setup

Install with `pipx install ab-plumber`, then follow the [Quickstart](#quickstart).

## Wrapping your own function

See [`docs/adapter-shim.md`](docs/adapter-shim.md).

## Development workflow

Follows the `ab_spatial` playbook: Discovery → POC → Tracer → MVP → Refinement.
See `../../playbook/phases.md`.

## Issue tracker

GitHub Issues in [`austinbreunig/plumber`](https://github.com/austinbreunig/plumber/issues),
via the `gh` CLI. See `docs/agents/issue-tracker.md`.
