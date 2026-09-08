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
