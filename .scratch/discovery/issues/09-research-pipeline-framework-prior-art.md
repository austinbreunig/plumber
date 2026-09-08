# Research: pipeline-framework prior art

Type: research
Status: open
Blocked by: —

## Question

Survey how established Python pipeline frameworks handle the three seams plumber
is designing, so tickets 01/03/04 borrow proven patterns instead of reinventing.

- Kedro: node/pipeline discovery, the data catalog + parameters YAML, pluggable
  runners (SequentialRunner / ParallelRunner / ThreadRunner), how it keeps
  node functions ignorant of the runner.
- Dagster: op/asset definition, config schema (`Config` / run config), executors
  (in-process / multiprocess / k8s), partitions API.
- Prefect: task/flow discovery, task runners (Concurrent / Dask / Ray),
  parametrization.
- Optional: Luigi, Snakemake, Ploomber for contrast.

For each: how phases are discovered/ordered, how config/params are supplied, how
the execution backend is swapped, and what the phase function is allowed to
assume. Call out which patterns fit plumber's "functions over classes" +
"run from any repo" stance and which don't.

Capture findings as `.scratch/discovery/research/pipeline-framework-prior-art.md`
and link it here.
