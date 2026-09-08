<!-- wayfinder:map -->
# plumber — Discovery map

## Destination

A signed-off `plan.md` for **plumber**: a pip/pipx-installable geospatial
pipeline framework + `plumber` CLI — module-level `run(gdf, **params) -> gdf`
phase protocol, a builder, pluggable execution strategies, config-file-driven
phase runs, and a `plumber check` validator — plus a thin **optional** AI skill
(under `ab_spatial/.claude/`) that only helps author the config file and gives
protocol/partition rework recommendations by consuming plumber's public API. The
core is fully usable without the skill.

Discovery ends when every decision ticket below is resolved or explicitly
deferred, enough for Tracer to write a spec. We decide the skill's *boundary*
(what it reads, what it emits, how it's invoked) — not its conversation flow.

## Notes

**Domain:** geospatial data engineering. Phases are algorithm modules; execution
strategy (local / multiprocess / dataflow / pyspark) is orthogonal and swappable
without touching phase code. Prototype→production scaling is the core pain point
this separation targets.

**Seed design doc:** the "Geospatial Pipeline Project — Design Doc & Handoff
Spec" from the charting conversation (sections 1–8). Treat its `core/` reasoning
as load-bearing; treat its section 6 "agentic pipeline generation" as
superseded by the constraints below.

**Skills every session should consult:** `/grilling` + `/domain-modeling` for any
decision ticket; `/prototype` for the `check` validator ticket. Wu Wei
(`.claude/skills/wu-wei/`) — plain functions over classes; a class only for
genuine persistent state (the builder may qualify, the protocols do not).

**Constraints established while charting (not re-open without cause):**

- **Skill scope:** config authoring + protocol/partition rework recs only. It
  consumes plumber's protocols + `check` output and drives the public API; it
  never reimplements framework logic and never generates whole phase modules.
  Everything works with the skill removed.
- **Skill home:** `ab_spatial/.claude/` (root), importing plumber as a dep — not
  in-repo.
- **Config:** a config file (YAML or TOML — TBD) drives the phase list + per-phase
  params. CLI flags pick executor + scale and override params.
- **Executors:** design `ExecutionStrategy` to admit all four; implement `local`
  + `localmp` for the tracer. `dataflow` + `pyspark` implementations deferred
  (see Out of scope) — the protocol must not foreclose them.
- **Payload:** `GeoDataFrame` for v1. Leave a seam for other formats (raster,
  plain DataFrame, arrow) without a protocol break.
- **Partitioning is explicit config:** by field(s), by chunk size, or (mp) by
  worker count.
- **Name:** `plumber` (was `geo-plumber`).

## Decisions so far

<!-- one line per resolved ticket: gist + link -->

- [Research: Beam/Spark partition contract](issues/08-research-beam-spark-partition-contract.md)
  — nothing forces an arity change to `execute(...)` or `run(gdf, **params) -> gdf`.
  The portable per-partition callable is a module-level pure fn
  `(partition_gdf, params) -> partition_gdf` (idempotent, order-independent, no
  shared state, picklable) — plumber's phase contract already meets this if
  phases stay pure. Lock two costless decisions so Beam/Spark aren't foreclosed:
  (1) type `execute`'s `data` as a **dataset reference** (path + format + opts),
  not a materialized GeoDataFrame — distributed executors do their own IO;
  (2) type `execute`'s **return as a result/handle**, not necessarily a
  driver-collected GeoDataFrame. Beam core has no vector/GeoParquet IO
  (`geobeam` is 3rd-party); a Spark executor effectively requires Sedona.
  Full findings: `research/beam-spark-partition-contract.md`.
- [Research: pipeline-framework prior art](issues/09-research-pipeline-framework-prior-art.md)
  — Kedro/Dagster/Snakemake/Luigi all *derive* order from a DAG and need their
  own project skeleton (fails "run from any repo"). **Ploomber** is the model:
  explicit ordered step list in YAML, each entry a dotted path resolved directly
  to `<module>.run`, no package layout. Config: Kedro's two layers with CLI-wins
  precedence (`parameters.yml` + `--params`) merged and passed as `**params`;
  optional typed validation via a phase-exported Pydantic model checked by
  `plumber check` — entry point stays `run(gdf, **params)`, never a class.
  Executor swap: one flag/key picks an `ExecutionStrategy`, phase code never
  references it; parallel contract = Kedro ParallelRunner rules (picklable, no
  shared state, no cross-phase side effects). Partitioning: Dagster's
  runtime-key-injection model, but explicit in config — phases stay
  partition-agnostic, one gdf in / one gdf out. Reject: DAG inference, mandatory
  skeletons, class-per-phase, target-file-existence ordering.
  Full findings: `research/pipeline-framework-prior-art.md`.

## Not yet specified

<!-- in-scope fog; graduates to tickets as the frontier advances -->

- **Payload seam for non-GDF formats** — how the GeoDataFrame assumption is
  isolated so raster / DataFrame / arrow can slot in later. Revisit after the
  PhaseModule protocol and ExecutionStrategy tickets resolve.
- **Tracer fixture / first pipeline** — the synthetic fixture + stub phases (or a
  real pipeline) used to exercise the interface end to end. Revisit after the
  config-schema and ExecutionStrategy tickets.
- **Skill conversation flow + spec diffing/versioning** — how the interview runs
  and how a later session diffs an existing config instead of starting over.
  Revisit after the skill-boundary ticket. (Its own effort, likely.)
- **Contract-violation → rework-rec formatting** — how `check` failures are
  phrased back to a human or the skill; any retry semantics. Revisit after the
  `check` validator ticket.

## Out of scope

<!-- ruled beyond the destination; never graduates -->

- **`dataflow` + `pyspark` executor implementations** — the protocol must admit
  them; building/testing them is a later effort.
- **Agent-generated phase modules** — the design doc's section 6a/6c codegen. The
  skill authors config + recs only.
- **The skill's conversation-flow design** — deferred; becomes its own effort
  once the boundary is fixed.
