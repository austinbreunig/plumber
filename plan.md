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
- `plumber check` catches a signature/param mismatch with no sample, and a shared-state phase when a `check.sample` is configured, before `run` is attempted.
- Switching `local` → `localmp` (or back) requires a one-line config/flag change, zero phase-code changes.
- The AI skill can author a working config from a plain-language description of an existing set of phase functions, and plumber runs correctly with the skill absent.

## Stakeholders

- Austin Breunig — author, sole user for v1.
- Future plumber users — anyone writing geospatial (or later raster/tabular) pipelines who wants prototype code to scale without a rewrite.

The `ab_spatial/.claude/` AI skill consumes plumber's public API; its boundary is fixed in Scope→In, see #7.

## Scope

### In

- `PhaseModule` protocol, generic over `Payload` (v1: `GeoDataFrame`) (#3, #12).
- `ExecutionStrategy` protocol: `execute(input, steps, output, run_params) -> Result[Payload]`, where `input`/`output` are pre-bound (fn, params) pairs (`output` may be `None`) and each step is a frozen `Step(name, fn, params, partitionable, checkpoint)`. `Result` exposes only `.collect()`. No `DatasetRef`. `run()` owns partial runs by swapping the input pair for plumber's checkpoint reader (#5, #17).
- `LocalSequential` and `LocalMultiprocess` implementations; under `localmp` the output function runs once, on the joined, re-ordered data (#5, #17).
- Config schema (YAML): phase list (each entry a `module:attr` path — `:attr` always required, no default to `run` — #2, #16), `input`/`output` (both user-written, dotted-path resolved, symmetric — #4, #14), partitioning, CLI-override precedence.
- `plumber check` — structural → static → runtime-probe validation (#6). The runtime probe runs only when the optional `check.sample` (GeoParquet, path relative to cwd) is set, chains the sample through the phases in order, and reports PASS/WARN/FAIL/SKIP (SKIP = an upstream phase failed). With no sample it prints one info line and does not run. `plumber run`'s preflight runs only the structural + static layers (#18).
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
- Plumber does no IO on the user's source/destination data. The strategy calls the user's **input function** (`fn(**params) -> GeoDataFrame`) and optional **output function** (`fn(gdf, **params) -> None`), never a substitute — no engine-native override hook (#4, #14, #17). The one exception is plumber's own checkpoint files (#15).

## Constraints

- Python 3.9–3.12. CI runs `ruff check .` + `pytest -q` on 3.9 and 3.12 (#8).
- Dev setup mirrors maply: Nix flake + `uv` + `direnv`, `hatchling` build backend, hand-bumped semver, MIT license (#8).
- Distribution name `ab-plumber` (plain `plumber` is taken on PyPI); import name and console script stay `plumber` (#8).
- Wu Wei: phases are plain functions, never classes. A class only where state must persist or data needs named fields (e.g. `Result`, the frozen `Step` dataclass — #17).
- Plumber-core never depends on the AI skill. The dependency only goes skill → plumber (#7).

## Risks

- Beam has no first-party vector IO (`geobeam` is third-party); a real Spark executor effectively requires Sedona (#9) — deferred, but means "admit the protocol" is easier than "actually run well" when that phase arrives.
- `check`'s idempotency gate (call twice, diff output) doesn't catch every shared-state bug — only ones that manifest as a diff between two calls on identical input (#6).
- Checkpoints have no staleness check (#15): after changing an upstream phase's params or code, `--from` will happily load an out-of-date checkpoint. The warning shows its timestamp; judging it is on the user.
- `dtypes` comparison in `check` was deferred because the prototype fixture isn't a real GeoDataFrame (#6). The runtime probe now uses the user's real-shaped `check.sample` (#18), so this can be revisited.
- A `check.sample` can go out of date as the input changes; `check` can't tell (#18).
- Shared-state bugs are only caught when the user runs `plumber check` with a sample — `run`'s preflight skips the runtime probe (#18).

## Deferred

- How `check` results get phrased as rework recommendations for people and the skill. `check`'s output *shape* is locked (#6); the phrasing belongs to the skill's conversation-flow effort (Out).

## Next phase

The usual next step is POC. But the two prototypes on the map already answered the core "does it work" questions:

- `check` can catch shared state by calling a phase twice and diffing the output (#6).
- `LocalSequential` and a real `ProcessPoolExecutor` runner agree on the same config, so phases pickle across processes (#13).

Proposal: count these as the POC and go straight to **Tracer** (`/to-spec` → `/to-tickets`). Needs sign-off.
