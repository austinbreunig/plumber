# Research: pipeline-framework prior art

Type: research
Status: resolved
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

## Answer

Full findings: `.scratch/discovery/research/pipeline-framework-prior-art.md`
(primary-source citations inline).

- **Discovery/ordering**: Kedro, Dagster, Snakemake, Luigi all *derive* order from a
  data-dependency / filename DAG; only **Ploomber** lists steps explicitly in a YAML
  (`pipeline.yaml` tasks with `source`/`upstream`). plumber's chain is linear and passes
  one gdf, so the explicit ordered `phases:` list in the config is the right model — no
  DAG inference, no named IO ports.
- **Discovery mechanism**: Kedro (`pipeline_registry.py` + `conf/` + `settings.py`),
  Dagster (`Definitions` code location) and Prefect (deployments) all need their own
  project skeleton — fails plumber's "run from any repo". Ploomber resolves a dotted
  path / file directly with no package layout; do that: each config entry -> `<module>.run`.
- **Config/params**: adopt Kedro's two layers with CLI-wins precedence (`parameters.yml`
  + `--params`); hand the merged dict to the phase as `**params` (Ploomber
  `PythonCallable(**params)`). Optional typed validation via a phase-exported Pydantic
  model checked by `plumber check` (Dagster `Config` idea) — entry point stays
  `run(gdf, **params)`, never a class.
- **Executor swap**: every framework keeps this orthogonal (Prefect `task_runner=`,
  Dagster `executor_def` / `execution:`, Ploomber `executor:`, Kedro `--runner`). One
  CLI flag / config key picks an `ExecutionStrategy`; phase code never references it.
  Mirror Kedro's ParallelRunner rules as plumber's parallel contract: gdf + params must
  be picklable, no shared mutable state, no cross-phase side effects.
- **Partitioning**: Dagster's model (same compute logic per partition, key injected at
  runtime, strategy owns fan-out/gather) fits; its `PartitionsDefinition` object graph
  does not — plumber's partitioning is explicit config. Keep phases partition-agnostic:
  one gdf in, one gdf out.
- **Reject**: DAG inference, mandatory framework skeletons, class-per-phase
  (Luigi), target-file-existence as the ordering primitive, and Prefect's
  config-less imperative flow.
