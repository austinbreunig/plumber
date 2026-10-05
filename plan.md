# plumber — Plan

Written from the resolved [wayfinder map](https://github.com/austinbreunig/plumber/issues/1) (Discovery). Ticket numbers below are `austinbreunig/plumber` issues — each holds the full decision detail; this file only gists it.

## Problem statement

Geospatial pipelines are usually written once for a laptop-scale prototype, then rewritten by hand to run at production scale (multiprocess, Beam, Spark). There's no framework that keeps the algorithm code untouched while swapping the execution strategy underneath it.

## Goals

- Ship plumber as an installable framework + CLI that any repo can run without scaffolding.
- Let prototype pipeline code scale up (multiprocess, later Beam/Spark) without touching phase code.
- Catch broken phases before a real run, not during one.
- Make config authoring easy without requiring the AI skill.

## Success criteria

- `plumber run` executes a multi-phase pipeline against a config file, locally and via multiprocess, from a fresh `pip install`/`pipx install`, with no project scaffolding beyond the config and phase modules.
- `plumber check` catches a shared-state phase and a signature/param mismatch before `run` is attempted.
- Switching `local` → `localmp` (or back) requires a one-line config/flag change, zero phase-code changes.
- The AI skill can author a working config from a plain-language description of an existing set of phase functions, and plumber runs correctly with the skill absent.

## Stakeholders

- Austin Breunig — author, sole user for v1.
- Future plumber users — anyone writing geospatial (or later raster/tabular) pipelines who wants prototype code to scale without a rewrite.

The `ab_spatial/.claude/` AI skill consumes plumber's public API; its boundary is fixed in Scope→In, see #7.

## Scope

### In

- `PhaseModule` protocol, generic over `Payload` (v1: `GeoDataFrame`) (#3, #12).
- `ExecutionStrategy` protocol; `LocalSequential` and `LocalMultiprocess` implementations (#5).
- Config schema (YAML): phase list, `input`/`output` (both user-written, dotted-path resolved, symmetric — #4, #14), partitioning, CLI-override precedence.
- `plumber check` — structural → static → runtime-probe validation (#6).
- Packaging: `ab-plumber` on PyPI, `pipx`/`pip` install, `plumber run`/`plumber check` subcommands, fixed `./plumber.yaml` discovery (#8).
- Checkpoints + partial runs: opt-in `checkpoint: true` per phase, written by plumber as GeoParquet to `checkpoints.dir`; `plumber run --from/--to <name>` runs a contiguous slice, starting from the previous phase's checkpoint (#15).
- AI skill boundary: config authoring + rework recs + hand-proven adapter-shim generation, pure `import plumber`, draft-only writes (#7, #11).

### Out

- `dataflow` and `pyspark` executor *implementations* — the protocol must admit them (#9, #12), building them is a later effort.
- Agent-generated pipeline wiring/scaling/execution logic — only mechanical, hand-proven-first adapter shims are in scope (#11).
- The AI skill's conversation-flow / UX design, spec diffing, rework-rec phrasing (#7) — boundary is fixed, the interview itself is a separate later effort.
- `new-phase` CLI subcommand (#8, deferred).

## Assumptions

- Input CRS is set on incoming data; phases don't change it unless explicitly reprojecting (#3).
- A phase is pure, module-level, one-partition-at-a-time, idempotent, order-independent, picklable — enforced by `check`'s double-call diff, not by static analysis (#3, #6).
- `format` on `DatasetRef` is a real discriminator today (dispatches the payload's shape) but implies no plumber-side IO work — the user's own `input`/`output` function always does the read/write of source/destination data, no engine-native override hook (#4, #12, #14). The one exception is plumber's own checkpoint files (#15).

## Risks

- Beam has no first-party vector IO (`geobeam` is third-party); a real Spark executor effectively requires Sedona (#9) — deferred, but means "admit the protocol" is easier than "actually run well" when that phase arrives.
- `check`'s idempotency gate (call twice, diff output) doesn't catch every shared-state bug — only ones that manifest as a diff between two calls on identical input (#6).
- Checkpoints have no staleness check (#15): after changing an upstream phase's params or code, `--from` will happily load an out-of-date checkpoint. The warning shows its timestamp; judging it is on the user.
- `dtypes` comparison in `check` was deferred because the prototype fixture isn't a real GeoDataFrame (#6) — may need revisiting once `check` runs against real data.
