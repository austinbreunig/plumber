# ExecutionStrategy protocol & partition model

Type: grilling
Status: open
Blocked by: 02

## Question

Design the execution-strategy seam so `local` + `localmp` ship now and
`dataflow` + `pyspark` slot in later without a protocol change.

- The `ExecutionStrategy` Protocol: `execute(phases, data, params)` signature —
  what `data` is, what comes back, how per-phase params are threaded through.
- Partition model: how the config's partition spec (by field(s) / chunk size /
  worker count) is turned into partitions, how the phase chain runs per
  partition, how outputs are reassembled into one `GeoDataFrame`.
- The uniform-partition question: does `local` also pass a single whole-dataset
  partition so phase code never branches on executor? Decide yes/no.
- What `LocalSequential` and `LocalMultiprocess` each need from the protocol;
  confirm nothing in the signature blocks a Beam `Map`-chain or a Spark
  `mapPartitions` implementation later (cross-check with ticket 08 findings).

Output: the `ExecutionStrategy` Protocol, the partition-spec → partitions
mapping, and the reassembly contract.

## Input from research

Ticket 08 (`research/beam-spark-partition-contract.md`) — lock two costless
decisions so Beam/Spark stay open: type `execute`'s `data` as a **dataset
reference** (path + format + opts), not a materialized GeoDataFrame — distributed
executors do their own IO; type the **return as a result/handle**, not
necessarily a driver-collected GeoDataFrame. Beam has no first-class per-partition
transform (carry a partition as one pickled element) and no vector IO in core;
Spark uses `applyInPandas` (by field) / `mapInPandas` (by size) and effectively
requires Sedona. Local + localmp can still collect to a GeoDataFrame behind the
same handle type.
