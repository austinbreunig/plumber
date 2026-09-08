# Research: Beam & Spark partition/step contract for geospatial data

Type: research
Status: open
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
