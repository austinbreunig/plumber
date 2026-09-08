# Research: Beam & Spark partition/step contract for geospatial data

Feeds ticket `04-executionstrategy-protocol-and-partitioning.md`. Goal: know
enough about Apache Beam and PySpark/Sedona that the `ExecutionStrategy` protocol
(`execute(phases, data, params)`) and the phase contract (`run(gdf, **params) ->
gdf`) can be fixed now without foreclosing a `dataflow` (Beam) or `pyspark`
executor later.

Status of those backends: **not implemented now**. This is design-constraint
reconnaissance only.

---

## 1. Apache Beam (Python SDK)

### 1a. Per-element vs per-partition/bundle transforms

- **`beam.Map(fn)`** — one input element → exactly one output element. Sugar over
  `ParDo`. **`beam.FlatMap(fn)`** — one element → an iterable of 0..N elements.
  **`beam.ParDo(DoFn)`** — the general form; a `DoFn.process` call takes one
  element and yields 0..N. "ParDo considers each element in the input
  PCollection, performs some processing function (your user code) on that
  element, and emits zero, one, or multiple elements to an output PCollection."
  (<https://beam.apache.org/documentation/programming-guide/#pardo>)
- **There is no first-class "map over a partition" transform in Beam.** The unit
  of user code is the element. The closest equivalents:
  - **`DoFn.start_bundle` / `finish_bundle`** — lifecycle hooks around an
    arbitrary group of elements ("bundle"). The DoFn lifecycle is
    `Setup → StartBundle → (ProcessElement)* → FinishBundle → Teardown`.
  - **`GroupByKey`** then process each `(key, Iterable[value])` — an explicit
    shuffle, "analogous to the Shuffle phase of a Map/Shuffle/Reduce-style
    algorithm." For unbounded input it requires non-global windowing or a
    trigger.
    (<https://beam.apache.org/documentation/programming-guide/#groupbykey>)
  - **`GroupIntoBatches(batch_size)`** — keyed input `(key, value)` → `(key,
    [value, ...])` in fixed-size batches per key. "Requires keyed input data
    (key-value pairs)." For unkeyed input with dynamic sizing, `BatchElements`
    is the analogue.
    (<https://beam.apache.org/documentation/transforms/python/aggregation/groupintobatches/>,
    <https://beam.apache.org/documentation/transforms/python/aggregation/batchelements/>)

  So "run this phase chain over one partition-as-a-GeoDataFrame" in Beam is:
  key each row/chunk with a partition id, `GroupByKey` (or `GroupIntoBatches`),
  and in a `DoFn.process` rebuild a GeoDataFrame from the grouped rows, run the
  phase chain, yield rows back. Alternatively carry a whole partition as a
  **single element** (one element == one serialized GeoDataFrame / Arrow table /
  parquet blob) and use plain `beam.Map(run_chain)` — no shuffle, no keying.
  The single-element-per-partition model maps most directly onto plumber's
  existing `run(gdf) -> gdf`.

### 1b. Bundling / partitioning — what it guarantees

- Bundles are **runner-chosen and opaque**. "A given DoFn instance generally gets
  invoked one or more times to process some arbitrary bundle of elements.
  However, Beam doesn't guarantee an exact number of invocations; it may be
  invoked multiple times on a given worker node to account for failures and
  retries." You cannot choose bundle size, count, or boundaries from user code.
- **No element-ordering guarantee** within or across bundles.
- **Retries / re-execution:** `process` may run more than once for the same
  element (failures, speculative execution, work rebalancing). User code must be
  **idempotent** and free of side effects that don't tolerate replay.
- **Immutability:** "You should not in any way modify an element returned by the
  @Element annotation or ProcessContext.sideInput() ... Once you output a value
  using OutputReceiver.output() you should not modify that value in any way."
- Input is split into bundles for parallelism; **dynamic work rebalancing** can
  re-split in flight. There is no user-visible "partition" object like Spark's —
  `beam.Partition` merely routes elements into N sub-PCollections by a function,
  it does not give you a per-partition callable.
  (<https://beam.apache.org/documentation/programming-guide/#pardo>,
  <https://beam.apache.org/documentation/runtime/model/>)

### 1c. Side-input mechanics

- Extra read-only data passed to a `ParDo` beyond the main element:
  `beam.pvalue.AsSingleton`, `AsIter`, `AsList`, `AsDict`, `AsMultiMap` wrap a
  side PCollection; it arrives as a normal argument to `process`.
  (<https://beam.apache.org/documentation/programming-guide/#side-inputs>)
- **Materialized per worker and must fit in memory** on each worker processing
  the transform. Computed once then cached/reused across element calls.
- **Read-only** — do not mutate a side input value.
- **Windowing must be compatible** between main input and side input; there is a
  dedicated "Side inputs and windowing" caveat.
- Fit for plumber: broadcast params, small lookup tables, a shared reference
  layer. **Not** for a second large dataset (spatial join against another big
  layer) — that wants a `CoGroupByKey` / keyed join, i.e. a shuffle, which is a
  different shape than `run(gdf, **params) -> gdf`.

### 1d. Serialization / pickling

- "The pipeline contents such as DoFn user code, is serialized into bytecode.
  Therefore, DoFns should not reference objects that are not serializable, such
  as locks." (file handles, DB connections, thread locks, open sessions → all
  forbidden as captured state).
- Historically dill did **not** capture the `__main__` module globals →
  `--save_main_session` needed, or `NameError` on the worker. **Beam ≥ 2.65.0
  defaults to `cloudpickle`**, which removes that footgun (earlier versions:
  `--pickle_library=cloudpickle`).
  (<https://beam.apache.org/documentation/sdks/python-pipeline-dependencies/>)
- Practical consequence for plumber: phases and the per-partition callable must
  be **importable module-level objects** (which plumber phases already are —
  `run` in a named module), not closures over unpicklable state.

### 1e. Geospatial / GeoParquet / vector IO in the Python SDK

- **No geospatial IO in Beam core.** Built-in file IO covers text, Avro,
  **Parquet (`apache_beam.io.parquetio`, plain Arrow/Parquet only)**, TFRecord,
  and connector IO for BigQuery, GCS, JDBC, Kafka, etc. GeoParquet's `geo`
  metadata and geometry encoding are **not** interpreted — you'd read columns as
  WKB bytes and call `shapely`/`geopandas` yourself inside a DoFn.
  (<https://beam.apache.org/documentation/io/connectors/>,
  <https://beam.apache.org/documentation/io/built-in/parquet/>)
- **`geobeam`** (GoogleCloudPlatform/dataflow-geobeam) is the de-facto option: a
  third-party set of `FileBasedSource` classes — `ShapefileSource`,
  `GeodatabaseSource`, `GeoJSONSource`, `ESRIServerSource`, `RasterBlockSource`,
  `RasterPolygonSource` — bundling GDAL/rasterio/fiona/shapely. It emits
  `(props, geom_wkb)` tuples, not GeoDataFrames. Not an Apache project, GCP/
  Dataflow-oriented.
  (<https://github.com/GoogleCloudPlatform/dataflow-geobeam>,
  <https://pypi.org/project/geobeam/>)
- Takeaway: a Beam executor for plumber must own its **IO shim** (read source →
  emit partition payloads; collect payloads → write sink). This is true of every
  backend and is not a protocol problem, but it means "the executor reads and
  writes", not "plumber hands the executor an in-memory GeoDataFrame".

---

## 2. PySpark + Sedona

### 2a. Running a function over a partition as a DataFrame

Three contracts, increasing structure:

- **`RDD.mapPartitions(f, preservesPartitioning=False)`** — `f: Iterator[T] ->
  Iterator[U]`. Whole partition as a lazy iterator; you build/return an iterator.
  Order within the partition is preserved as iterated. `preservesPartitioning`
  tells Spark the key layout is unchanged so downstream joins can skip a
  shuffle. Row type is opaque Python objects — no schema, no columnar transfer.
  (<https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.RDD.mapPartitions.html>)
- **`DataFrame.mapInPandas(fn, schema)`** — `fn: Iterator[pd.DataFrame] ->
  Iterator[pd.DataFrame]`. Partition delivered as one or more Arrow batches
  (pandas frames). Output row count is independent of input; a partition can be
  filtered or exploded. Arrow-based transfer.
- **`GroupedData.applyInPandas(fn, schema)`** — `fn: pd.DataFrame ->
  pd.DataFrame`, called **once per group** from `df.groupBy(cols)`. "Each group's
  data is loaded entirely into memory as a pandas DataFrame" — groups larger
  than worker memory break it. Output must match the declared `schema`
  (StructType or DDL string); group-key columns are carried through.
  (<https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.GroupedData.applyInPandas.html>)
- **`pandas_udf`** — vectorized column UDFs: Series→Series, Iterator[Series]→
  Iterator[Series], Series→Scalar (aggregation). Scalar variants **must return
  the same number of rows as the input**. The old "grouped map" `pandas_udf` is
  **deprecated in favour of `applyInPandas`**. Function must be picklable; must
  not depend on partition/row ordering across partitions.
  (<https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.pandas_udf.html>,
  <https://spark.apache.org/docs/latest/api/python/user_guide/sql/arrow_pandas.html>)

Best fit for plumber's `run(gdf, **params) -> gdf`: **`applyInPandas`** (explicit
partition-by-field) or **`mapInPandas`** (partition-by-size / opaque chunks),
converting the pandas frame ↔ GeoDataFrame at the boundary. Both require a
**declared output schema** — the one genuinely new obligation vs. local/mp.

### 2b. Partitioning: by column vs by target size

- **`df.repartition(numPartitions)`** — round-robin into exactly N partitions.
- **`df.repartition([numPartitions,] *cols)`** — **hash** partitioning; equal
  key values land together. Column-only form uses
  `spark.sql.shuffle.partitions` (default 200).
- **`df.repartitionByRange([numPartitions,] *cols)`** — **range** partitioning by
  sorted value ranges (samples the data); good for spatially/temporally ordered
  keys.
- **`df.coalesce(n)`** — reduce partition count without a full shuffle.
- **`DataFrameWriter.partitionBy(*cols)`** — **on-disk directory layout only**
  (Hive-style `col=val/` folders) at write time; unrelated to in-memory compute
  partitions.
  (<https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.repartition.html>,
  `.../pyspark.sql.DataFrame.repartitionByRange.html`,
  `.../pyspark.sql.DataFrameWriter.partitionBy.html`)
- **There is no built-in "repartition to ~128 MB per partition".** Target-size
  partitioning = you compute `numPartitions = ceil(total_bytes / target)` and
  call `repartition(numPartitions)`, or lean on input-split sizing
  (`spark.sql.files.maxPartitionBytes`) at read. plumber's "by chunk size"
  partition spec becomes an arithmetic step in the Spark executor, not a native
  call.

### 2c. Sedona's role

- Sedona adds a **`GeometryType`** to Spark SQL plus `ST_*` functions and spatial
  joins, so geometry survives as a real column through shuffles/UDFs instead of
  being WKB bytes. Reads/writes **GeoParquet** natively via
  `format("geoparquet")` (since 1.3.0; geometry inferred from `geo` metadata),
  round-trips with GeoPandas; also `shapefile`, `geojson`, `geopackage`.
  (<https://sedona.apache.org/latest/tutorial/sql/>,
  <https://wherobots.com/blog/spatial-data-geoparquet-and-apache-sedona/>)
- **Spatial partitioning** (co-locating nearby geometries so a spatial join is
  local): grid types **KDB-tree, Quad-tree, R-tree**, via the SpatialRDD API
  `rdd.spatialPartitioning(GridType.KDBTREE)` then
  `other.spatialPartitioning(rdd.getPartitioner())`. This is a **spatial-join
  optimization**, not something plumber's per-phase `run` needs unless a phase
  itself does a cross-layer spatial join.
  (<https://sedona.apache.org/latest/tutorial/rdd/>,
  <https://sedona.apache.org/latest/api/javadoc/spark/org/apache/sedona/core/spatialPartitioning/KDB.html>)
- **Sedona 1.8.0+ ships a distributed "GeoPandas API on Sedona"** — GeoPandas
  syntax executing on Spark, plus explicit GeoPandas↔Spark-DataFrame conversion
  helpers that preserve GeoParquet/CRS metadata. Relevant as the pandas↔GeoDF
  boundary shim inside an `applyInPandas` phase call.
  (<https://sedona.apache.org/latest/tutorial/geopandas-api/>,
  <https://sedona.apache.org/latest-snapshot/api/pydocs/sedona.spark.geopandas.html>)
- A Spark executor for plumber effectively **requires Sedona** (or manual WKB
  columns) to keep geometry typed across the cluster.

---

## 3. The common callable shape

A "run this phase chain over one partition" function that is portable across
`multiprocessing.Pool`, a Beam `ParDo`/`Map`, and Spark
`mapPartitions`/`applyInPandas` must be:

- **A module-level function (or importable callable), not a closure.** Beam
  serializes DoFn code; Spark pickles the task; `multiprocessing` (spawn, the
  default on macOS and Windows and Python ≥ 3.14 on Linux) pickles the target.
  Lambdas and locally-defined closures fail on at least one backend.
- **Pure w.r.t. captured state.** No open file handles, DB connections, locks,
  sockets, or thread pools captured in scope — all three backends forbid
  unpicklable captured objects (Beam says so explicitly; Spark and spawn
  multiprocessing enforce it via pickle). Acquire such resources *inside* the
  call (or in `DoFn.setup` / a module-level lazy singleton).
- **`(partition_payload, params) -> partition_payload`**, where `params` is a
  plain picklable dict and `partition_payload` is a self-contained chunk:
  serializable, no reference to the parent process. A GeoDataFrame qualifies
  (pickles fine); so does an Arrow table or a parquet byte blob.
- **Order-independent and deterministic.** No reliance on partition order, global
  row order, or previous-partition results. Beam may reorder and retry; Spark
  may recompute a partition on executor loss or speculation; both can run
  partitions concurrently in any order.
- **No shared mutable state between partitions.** No module global being written,
  no accumulator the phase reads back. Cross-partition aggregation must be an
  explicit separate step (a reduce / groupby), not a side effect of the map.
- **Idempotent.** Safe to run twice on the same input (retries, speculative
  execution).
- **Self-contained imports.** Import heavy libs (geopandas, shapely, pyproj)
  inside the function or at module top level of an importable module — not relying
  on `__main__` globals (the classic Beam `--save_main_session` trap; mitigated
  but not eliminated by cloudpickle).
- **Returns, never mutates in place.** Beam requires outputs not be mutated after
  emission; treat the input payload as read-only and return a new frame.

plumber's existing `run(gdf, **params) -> gdf` **already satisfies all of this**
if phases are kept pure (no global state, no captured handles) — which the
wu-wei "plain functions" rule already pushes toward. The per-partition callable
is just `reduce(lambda g, ph: ph.run(g, **params[ph]), phases, partition_gdf)`.

### Backend-by-backend "forbidden" list

| Constraint | multiprocessing.Pool | Beam ParDo | Spark mapPartitions / applyInPandas |
|---|---|---|---|
| Unpicklable captured state (locks, handles) | forbidden (spawn) | forbidden (explicit) | forbidden |
| Closures / lambdas as the task | fragile | forbidden | forbidden (needs pickle) |
| Relying on element/partition order | ok-ish | **no guarantee** | **no guarantee** |
| Shared mutable global across workers | no (separate processes) | **no** | **no** (separate JVM/py workers) |
| Non-idempotent side effects | mostly ok | **retried/replayed** | **recomputed on loss/speculation** |
| Declared output schema required | no | no | **yes** (applyInPandas/mapInPandas) |
| In-memory whole dataset handed to executor | ok (localish) | **no** (executor does IO) | **no** (executor does IO) |

---

## 4. Anything that forces a signature change

Nothing forces a change to **`run(gdf, **params) -> gdf`**. It is already the
right shape for a Beam single-element `Map` and a Spark `applyInPandas` body.
Watch items, none blocking:

1. **Output schema (Spark).** `applyInPandas` / `mapInPandas` need the result
   schema up front. plumber can derive it (run phase chain on an empty/sample
   frame, or require phases to declare output columns) — this is an *executor*
   concern, not a phase-signature concern, **provided** `execute(phases, data,
   params)` gives the Spark executor enough to obtain a sample. `data` being a
   GeoDataFrame (or a lazy handle that can yield `.head(0)`) covers it.

2. **`data` should be a handle/spec, not necessarily a materialized
   GeoDataFrame.** Beam and Spark executors **do their own IO** and never want a
   fully-materialized in-memory GeoDataFrame. If `execute`'s `data` param is
   typed/documented as "an in-memory GeoDataFrame", that forecloses them. Make
   `data` an opaque **dataset reference** (path + format + read options, or an
   already-loaded GeoDataFrame for local) that each strategy resolves its own
   way. This is a *documentation/typing* decision on the existing signature, not
   a new parameter — but it must be made now.

3. **Return of `execute`.** For local/mp the natural return is one reassembled
   GeoDataFrame. For Beam/Spark the natural result is "written to the sink; maybe
   returns a summary/handle". Keep `execute`'s return type a **union / result
   object** (`GeoDataFrame | DatasetRef`) or "returns the output dataset
   reference, which local resolves to an in-memory GeoDataFrame" so a distributed
   executor isn't forced to collect to the driver. Decide now; costless if the
   signature stays `execute(phases, data, params) -> Result`.

4. **`params` must stay a plain picklable mapping** (phase-name → param dict).
   No callables, no live objects, no CRS objects that don't pickle cleanly
   (pyproj CRS pickles; arbitrary user objects may not). Document "params values
   must be JSON-serializable" and all three backends are safe.

5. **Cross-partition operations are out of scope for a phase.** Any phase that
   needs a global view (dataset-wide dissolve, global spatial index, join to
   another big layer) cannot be expressed as `run(partition_gdf) ->
   partition_gdf` on any distributed backend. Either such phases are declared
   "non-partitionable" (executor runs them on a single partition / driver) or
   plumber gains a separate reduce/co-group step type **later**. Not a v1
   signature change, but the phase contract (ticket 02) should name the
   restriction: **a phase must be a partition-local map**.

6. **No uniform-partition blocker.** Having `local` pass a single
   whole-dataset partition (so phase code never branches on executor) is
   compatible with every backend — Beam single-element `Map`, Spark one
   partition, `Pool` of one. Recommend **yes, uniform**.

---

## Implications for plumber's `ExecutionStrategy` protocol

- **Keep** `execute(phases, data, params)` and `run(gdf, **params) -> gdf`. No
  arity change is required for Beam or Spark.
- **Type `data` as a dataset reference**, not "an in-memory GeoDataFrame":
  `path + format + read_opts`, which the `local` strategy may also accept as an
  already-loaded GeoDataFrame. Distributed executors own their read; local
  materializes. Decide this now — it is the one thing that would otherwise
  foreclose Beam/Spark.
- **Type `execute`'s return as a result/handle**, not necessarily a
  GeoDataFrame: `local`/`localmp` resolve it to a reassembled GeoDataFrame; a
  distributed executor may return the output dataset reference after writing the
  sink, without collecting to the driver.
- **`params` = plain nested dict, JSON-serializable values only.** Documented
  constraint; keeps pickling safe on `spawn` multiprocessing, cloudpickle (Beam),
  and Spark task serialization.
- **Phase contract (ticket 02) must state: a phase is a pure, partition-local,
  order-independent, idempotent map with no shared mutable state and no captured
  unpicklable resources.** That single sentence is exactly the intersection of
  what `Pool`, Beam `ParDo`, and Spark `applyInPandas` each demand. If phases
  honour it, the same per-partition callable
  (`functools.reduce` over the phase chain) drops into all four backends
  unchanged.
- **The per-partition payload abstraction "one GeoDataFrame per partition" is
  sound** for all four. Beam carries it as a single pickled element (or rebuilds
  it from a `GroupByKey`); Spark carries it as an Arrow batch via
  `applyInPandas`/`mapInPandas` with a GeoDataFrame↔pandas shim (Sedona or WKB
  columns). Leave a seam for Arrow/parquet-blob payloads (raster, plain
  DataFrame) as already planned — no protocol break needed.
- **Executor-owned IO shim is expected and fine.** Each strategy has its own
  source→partitions and partitions→sink code; that is not the protocol's job.
  Beam core has no GeoParquet/vector IO (only plain Parquet); a Beam executor
  would depend on `geobeam` or hand-rolled WKB. A Spark executor would depend on
  **Sedona** for typed geometry + GeoParquet.
- **Partition spec translation is per-executor arithmetic**, not a protocol
  concern: "by field(s)" → `groupBy`/`applyInPandas` (Spark), key + `GroupByKey`
  (Beam), `groupby` (pandas, local); "by chunk size" → compute `numPartitions`
  then `repartition` (Spark), chunked iterable (local/Beam); "by worker count" →
  `repartition(n)` / `Pool(n)`. The protocol only needs to pass the spec through
  in `params` (or a dedicated `partitioning` arg if ticket 04 prefers it
  explicit).
- **Add a "non-partitionable phase" escape hatch in the design vocabulary now**
  (even if unused in v1): a phase that needs a global view runs on a single
  partition / the driver. Cheaper to name than to retrofit.

### Source list

- Beam programming guide — ParDo/Map/FlatMap, GroupByKey, side inputs, DoFn
  lifecycle & immutability: <https://beam.apache.org/documentation/programming-guide/>
- Beam execution model (bundles, retries, dynamic rebalancing):
  <https://beam.apache.org/documentation/runtime/model/>
- Beam GroupIntoBatches / BatchElements:
  <https://beam.apache.org/documentation/transforms/python/aggregation/groupintobatches/>
- Beam I/O connectors list & Parquet IO:
  <https://beam.apache.org/documentation/io/connectors/>,
  <https://beam.apache.org/documentation/io/built-in/parquet/>
- Beam Python pipeline dependencies / pickling (cloudpickle default ≥ 2.65,
  `--save_main_session`):
  <https://beam.apache.org/documentation/sdks/python-pipeline-dependencies/>
- geobeam (third-party geospatial sources for Beam/Dataflow):
  <https://github.com/GoogleCloudPlatform/dataflow-geobeam>,
  <https://pypi.org/project/geobeam/>
- PySpark `RDD.mapPartitions`:
  <https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.RDD.mapPartitions.html>
- PySpark `GroupedData.applyInPandas`:
  <https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.GroupedData.applyInPandas.html>
- PySpark `pandas_udf` + Arrow/pandas guide:
  <https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.pandas_udf.html>,
  <https://spark.apache.org/docs/latest/api/python/user_guide/sql/arrow_pandas.html>
- PySpark `repartition` / `repartitionByRange` / writer `partitionBy`:
  <https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.repartition.html>
- Sedona SQL (GeometryType, ST_ functions, GeoParquet):
  <https://sedona.apache.org/latest/tutorial/sql/>
- Sedona spatial partitioning (KDB/Quad/R-tree, SpatialRDD):
  <https://sedona.apache.org/latest/tutorial/rdd/>
- Sedona GeoPandas API + GeoPandas↔Spark interop:
  <https://sedona.apache.org/latest/tutorial/geopandas-api/>,
  <https://sedona.apache.org/latest-snapshot/api/pydocs/sedona.spark.geopandas.html>
- Sedona + GeoParquet background:
  <https://wherobots.com/blog/spatial-data-geoparquet-and-apache-sedona/>
