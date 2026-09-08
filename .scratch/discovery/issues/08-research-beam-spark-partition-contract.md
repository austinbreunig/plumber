# Research: Beam & Spark partition/step contract for geospatial data

Type: research
Status: resolved
Blocked by: —

## Question

Surface the facts ticket 04 needs so the `ExecutionStrategy` protocol is designed
without foreclosing `dataflow` (Apache Beam) or `pyspark`, even though neither is
implemented now.

- Apache Beam: how a per-element / per-partition transform is expressed
  (`beam.Map`, `beam.ParDo`), how bundling/partitioning works, what a step
  function may and may not assume, side-input mechanics, and the state of
  geospatial IO connectors (GeoParquet / vector formats) in Beam's Python SDK.
- PySpark: `mapPartitions` / pandas-UDF / `applyInPandas` contract for running a
  function over a partition as a (Geo)DataFrame; how partitioning by column vs.
  by size is expressed; Sedona's role for geospatial types.
- The common shape: what a "run this phase chain over one partition" callable
  must look like to be portable across LocalMultiprocess, Beam, and Spark.
- Anything that would force a signature change to `execute(phases, data, params)`
  or to `run(gdf, **params) -> gdf`.

Capture findings as `.scratch/discovery/research/beam-spark-partition-contract.md`
and link it here. Primary sources: Beam and Spark official docs, Sedona docs.

## Answer

Findings: [`.scratch/discovery/research/beam-spark-partition-contract.md`](../research/beam-spark-partition-contract.md)

Nothing forces an arity change to `execute(phases, data, params)` or to
`run(gdf, **params) -> gdf`. Beam's unit of user code is the element (`beam.Map` /
`ParDo`; no first-class per-partition transform — you carry a partition as one
pickled element or rebuild it after `GroupByKey`/`GroupIntoBatches`); bundles are
opaque, unordered, and retried. Spark's per-partition contract is
`applyInPandas` (partition-by-field) or `mapInPandas` (by size), each needing a
declared output schema, with geometry kept typed via Sedona (+ native GeoParquet);
`repartition`/`repartitionByRange` cover column vs range, target-size is manual
arithmetic. The portable callable is a module-level (not closure) pure function
`(partition_gdf, params) -> partition_gdf` that is order-independent, idempotent,
holds no shared mutable state, and captures no unpicklable resources — the exact
intersection of `Pool` + Beam `ParDo` + Spark `applyInPandas`. Two decisions to
make now so Beam/Spark stay open, both costless on the current signature: type
`data` as a dataset reference (not a materialized GeoDataFrame — distributed
executors do their own IO) and type `execute`'s return as a result/handle (not
necessarily a collected GeoDataFrame). Also name in ticket 02 that a phase must be
a partition-local map, with a "non-partitionable phase runs on the driver" escape
hatch. Beam core has no GeoParquet/vector IO (plain Parquet only; `geobeam` is the
third-party option); a Spark executor effectively requires Sedona.
