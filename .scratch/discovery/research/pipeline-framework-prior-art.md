# Pipeline-framework prior art

Research for plumber Discovery ticket `09-research-pipeline-framework-prior-art`.
Surveys how established Python pipeline frameworks handle the three seams plumber
is designing:

1. **phase discovery & ordering** — how the tool finds a repo's steps and their order
2. **config / params supply** — file-driven phase list + per-phase params, CLI overrides
3. **pluggable execution backend** — local sequential / multiprocess now, Beam + Spark later,
   kept orthogonal to phase logic

For each framework: how phases are discovered/ordered, how config/params are supplied,
how the execution backend is swapped, and what a phase function may assume about its
runtime. Comparison and recommendations at the end.

All claims cite official docs inline. Consulted 2026-09-08.

---

## 1. Kedro

### Phase discovery & ordering

- A **node** is `Node(func, inputs, outputs, name=...)` — a plain Python function plus
  the *names* of its inputs and outputs. Node functions are ordinary functions;
  `*args`, `**kwargs` and generator signatures are all supported.
  <https://docs.kedro.org/en/stable/nodes_and_pipelines/nodes.html>
- **Ordering is inferred, not declared.** When one node's input name matches another
  node's output name, that edge is added to the DAG and Kedro topologically sorts it.
  There is no explicit ordered list — order falls out of the input/output name graph.
  <https://docs.kedro.org/en/stable/nodes_and_pipelines/nodes.html>
- **Discovery** is via a project-level registry. `src/<pkg>/pipeline_registry.py` must
  define a top-level `register_pipelines()` returning `{name: Pipeline}`, including a
  `"__default__"` entry. `find_pipelines()` auto-discovers by scanning
  `src/<pkg>/pipelines/`, importing each `<pkg>.pipelines.<name>` module, calling its
  `create_pipeline()` and validating the result is a `Pipeline`. Failures warn and skip
  unless `find_pipelines(raise_errors=True)`.
  <https://docs.kedro.org/en/stable/nodes_and_pipelines/pipeline_registry.html>
- Requires a Kedro project layout (`pyproject.toml [tool.kedro]`, `settings.py`,
  `conf/`, `pipeline_registry.py`). `kedro run` is not runnable from an arbitrary repo
  without that scaffold.

### Config / params supply

- **Parameters**: `conf/base/parameters.yml` is a flat dict of key/value pairs. A node
  consumes them by naming inputs with a `params:` prefix (`params:model_options.lr`) or
  the whole set as `parameters`. CLI `kedro run --params=key1=v1,key2=2.0` overrides, and
  "values provided in the CLI take precedence and overwrite parameters specified in
  configuration files." Optional Pydantic/dataclass type hints on node args validate
  params before the run.
  <https://docs.kedro.org/en/stable/configuration/parameters.html>
- **Data Catalog**: `conf/base/catalog.yml` names datasets and their IO (file type,
  path, load/save args). Nodes reference datasets by name only; the catalog resolves the
  name to a concrete reader/writer. Un-catalogued intermediate names become in-memory
  `MemoryDataset`s.
  <https://docs.kedro.org/en/stable/configuration/parameters.html> (catalog cross-ref)

### Execution backend swap

- Three built-in runners: **SequentialRunner** (default), **ParallelRunner**
  (multiprocessing), **ThreadRunner** (multithreading). Selected with the CLI
  `--runner=` flag (`kedro run --runner=ParallelRunner`) or by instantiating the class
  in the Python API. The runner is chosen *outside* the node.
  <https://docs.kedro.org/en/stable/nodes_and_pipelines/run_a_pipeline.html>
- Node functions "remain agnostic of the runner type … the runner handles execution
  strategy transparently." The Data Catalog is the seam: nodes receive/return plain
  Python objects, the runner + catalog decide how they are materialised and passed.
- **ParallelRunner constraints** (the thing a node implicitly must satisfy): all
  objects must be picklable, it needs a `SharedMemoryDataCatalog`, it cannot use
  `SparkDataset`, and it does **not** run node/dataset hooks — "if your project relies
  on these hooks, use SequentialRunner or ThreadRunner instead." ThreadRunner disables
  async load/save.
  <https://docs.kedro.org/en/stable/nodes_and_pipelines/run_a_pipeline.html>

### What a phase function may assume

Only its declared inputs (plain Python objects supplied by the catalog). Not: the
runner, the process/thread it runs in, shared mutable state, or hook side effects
(under ParallelRunner). Must be picklable to survive the parallel runners.

---

## 2. Dagster

### Phase discovery & ordering

- **Ops**: `@dg.op` decorates a plain function (the `compute_fn`). Ops are wired into a
  DAG with `@job` / `@graph`; "an op only starts to execute once all of its inputs have
  been resolved." Ordering is by passing one op's output into another
  (`b(a())`) inside the graph body — explicit composition, still data-dependency driven.
  <https://docs.dagster.io/guides/build/ops/>
- **Assets**: `@dg.asset` decorates a function that computes one persisted object.
  Dependencies are inferred when a **function parameter name matches an upstream asset
  key**, or declared with `deps=[other_asset]`. Ordering is the asset-key graph.
  <https://docs.dagster.io/guides/build/assets/defining-assets>
- **Discovery** is registration-based: ops/assets are collected into a `Definitions`
  object (project convention: helpers that load assets from modules / autoload a
  package). Dagster tooling reads `Definitions` from a code location; there is no
  filesystem-order convention — the graph is authoritative.

### Config / params supply

- **Pythonic config**: subclass `dg.Config` (a `pydantic.BaseModel` subclass) and add a
  `config:` parameter to the op/asset; the body reads `config.person_name`. Dagster
  validates run config against the model and raises `DagsterInvalidConfigError` on
  mismatch. `PermissiveConfig` allows arbitrary extra fields.
  <https://docs.dagster.io/api/dagster/config>,
  <https://docs.dagster.io/guides/operate/configuration/run-configuration>
- **Supplying it**: a `RunConfig` object to `execute_in_process()` / `materialize()` in
  Python; YAML in the UI Launchpad; `--config <file.yaml>` on the CLI. The YAML has
  top-level keys `ops:`, `resources:`, `execution:`, values nested beneath.
  <https://docs.dagster.io/guides/operate/configuration/run-configuration>

### Execution backend swap

- Executors: `in_process_executor` (serial, in the run worker), `multiprocess_executor`
  (one process per step), plus `dask_executor`, `celery_executor`, `k8s_job_executor`,
  `docker_executor`, `ecs_executor`, etc.
  <https://docs.dagster.io/guides/operate/run-executors>
- Selection hierarchy: a job may pass an `ExecutorDefinition` to `executor_def=`;
  otherwise the code location's `Definitions` default is used. "If a job explicitly
  specifies an executor, that executor will be used. Otherwise … the default provided to
  the code location." The `execution:` key in run config configures the chosen executor.
  Executing a bare `JobDefinition` forces `in_process_executor`.
  <https://docs.dagster.io/guides/operate/run-executors>
- Op/asset code has no awareness of which executor runs it.

### Partitions API

- A `PartitionsDefinition` attached to an asset/op: `StaticPartitionsDefinition([...])`,
  `DailyPartitionsDefinition(start_date=...)` / `TimeWindowPartitionsDefinition`,
  `MultiPartitionsDefinition` (two axes), `DynamicPartitionsDefinition` (runtime-decided).
  <https://docs.dagster.io/guides/build/partitions-and-backfills/partitioning-assets>
- The compute function reads its slice at runtime via `context.partition_key` (or
  `context.partition_key.keys_by_dimension` for multi). The **compute logic is the same
  regardless of partition** — only the key differs. Downstream partitions map to the
  matching upstream partitions automatically.
  <https://docs.dagster.io/guides/build/partitions-and-backfills/partitioning-assets>

### What a phase function may assume

Its declared inputs, plus a typed `config` object (validated) and, if partitioned, a
partition key from `context`. Not: the executor, the process, or cross-op state except
through declared IO / IO managers.

---

## 3. Prefect

### Phase discovery & ordering

- `@task` decorates a plain function; `@flow` decorates the function that calls tasks.
  There is **no static discovery and no declared DAG** — the flow body is ordinary
  imperative Python. "Discovery appears to be purely imperative at runtime."
  <https://docs.prefect.io/v3/develop/write-tasks>
- Ordering is implicit through data flow: calling `task_b(task_a())` (or
  `task_b.submit(task_a.submit())` with futures) sequences them; an explicit
  `wait_for=[...]` argument adds an ordering edge without a data dependency.
  <https://docs.prefect.io/v3/develop/write-tasks>
- For scheduled execution Prefect uses **deployments**: an entrypoint
  (`path/to/file.py:flow_function`), `flow.from_source(...)`, `prefect deploy`, and
  `prefect.yaml`. The pipeline is still the imperative flow; the deployment only points
  at it.

### Config / params supply

- Flow/task **parameters are the function arguments**. Parameters passed to a flow are
  validated and coerced by Pydantic (`validate_parameters`, default `True`).
  Deployments carry default parameter values; a run can override them.
  <https://docs.prefect.io/v3/develop/write-flows>

### Execution backend swap

- Task runners (Prefect 3): **ThreadPoolTaskRunner** (default; was `ConcurrentTaskRunner`
  in Prefect 2), **ProcessPoolTaskRunner**, **DaskTaskRunner** (`prefect[dask]`),
  **RayTaskRunner** (`prefect[ray]`).
  <https://docs.prefect.io/v3/develop/task-runners>
- Selected with one kwarg on the flow: `@flow(task_runner=ThreadPoolTaskRunner(max_workers=3))`.
  Task runners "operate transparently at the flow level" — task functions do not know
  which runner executes them. Parallelism is opt-in per call site via `.submit()` /
  `.map()`, which return `PrefectFuture`s.
  <https://docs.prefect.io/v3/develop/task-runners>

### What a phase function may assume

Its arguments (Pydantic-validated). Not the runner, not the thread/process. If it uses
`.submit()`/`.map()` it deals in futures; otherwise it gets resolved values.

---

## 4. Brief contrast

### Luigi

- **Discovery/order**: `luigi.Task` subclasses; each implements `requires()` (returns
  upstream Task objects), `output()` (returns `Target`s), `run()`. The DAG is the
  `requires()` graph; a task is "done" when its `output()` targets exist, so ordering is
  target-existence + dependency graph, with an optional numeric `priority`.
- **Config/params**: parameters are class attributes (`luigi.Parameter()`,
  `DateParameter()`, …), supplied on the CLI or in `luigi.cfg`.
- **Execution**: a worker runs the graph; `--workers N` gives local process parallelism;
  a central scheduler coordinates multi-machine runs and dedups work. Backend is not a
  swappable object — it's "local worker" vs "central scheduler".
- <https://luigi.readthedocs.io/en/stable/tasks.html>
- Fit for plumber: **poor** — class-per-task, params-as-attributes, IO defined by target
  files, all against "functions over classes" and in-memory gdf passing.

### Snakemake

- **Discovery/order**: rules in a `Snakefile` declare `input:` and `output:` file
  patterns with wildcards. The DAG is derived purely from **filename matching** — "if
  the rule's output matches a requested file, the wildcards are propagated to the
  input". `ruleorder:` breaks ambiguity.
- **Config/params**: `config.yaml` / `--config` populate a global `config` dict; the
  `params:` directive holds per-rule values (static or a function of wildcards).
- **Execution**: `--cores N` local; `--jobs N` + `--executor slurm|kubernetes` for
  clusters/cloud; `resources:` / `--resources` cap global usage. Backend is a CLI flag.
- <https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html>
- Fit for plumber: **config/execution split is clean and CLI-driven (good model)**, but
  the file-pattern DAG doesn't fit passing one GeoDataFrame through a linear chain
  in memory.

### Ploomber

- **Discovery/order**: `pipeline.yaml` lists tasks explicitly, each with `source`
  (a `.py`/`.sql`/notebook/dotted-path callable), `product` (output path/relation), and
  optional `upstream` (list of task names). Ordering is the `upstream` graph; upstream
  can also be extracted from the task source (an `upstream` variable in the script).
- **Config/params**: each task takes an optional `params:` dict of arbitrary values
  passed to the task at runtime; `env.yaml` holds `{{placeholders}}` interpolated into
  `pipeline.yaml`. A `PythonCallable` is invoked as `fn(product, upstream=..., **params)`.
- **Execution**: `executor: serial` (one task at a time; function tasks in a subprocess
  by default) or `executor: parallel` (independent tasks concurrently, all in
  subprocesses). Customisable via `executor: {dotted_path: ploomber.executors.Parallel,
  processes: 2}` or `ploomber.executors.Serial, build_in_subprocess: false`.
  `ploomber build` runs it.
- <https://docs.ploomber.io/en/stable/api/spec.html>,
  <https://docs.ploomber.io/en/latest/api/_modules/executors/ploomber.executors.Parallel.html>,
  <https://docs.ploomber.io/en/latest/user-guide/parametrized.html>
- Fit for plumber: **closest prior art.** YAML explicitly lists steps, task bodies are
  plain callables receiving `**params`, the executor is one YAML key (or CLI-swappable
  dotted path), and there's no required project package layout.

---

## Comparison — what fits plumber's stance

plumber's stance: plain Python functions over classes; a module-level
`run(gdf, **params) -> gdf` per phase; a config file (YAML/TOML) drives an **explicit
ordered phase list** + per-phase params; CLI flags pick the executor and override
params; the `plumber` CLI runs from any repo without scaffolding.

| Concern | Fits plumber | Doesn't fit | Why |
|---|---|---|---|
| **Ordering** | Ploomber explicit `upstream` list; Snakemake/Luigi/Kedro/Dagster all *derive* order | Kedro & Dagster data-dependency graph (input/output *name* matching, asset keys) | plumber's phases are a linear chain passing one gdf; there are no named IO ports to match on, and an explicit ordered list in the config is simpler and is the config's job anyway. Deriving a DAG buys nothing here. |
| **Discovery** | Ploomber (`source:` resolves a dotted path / file — no package layout); Kedro `find_pipelines()` *module scan* as an idea for `plumber check` | Kedro's mandatory `pipeline_registry.py` + `conf/` + `settings.py`; Dagster's `Definitions` code location; Prefect deployments | plumber must run "from any repo". Frameworks that require their own project skeleton fail that test. Resolve each config entry to `<module>.run` directly. |
| **Params** | Kedro two-layer (`parameters.yml` + `--params` override, CLI wins); Ploomber per-task `params:` dict passed as `**params`; Dagster typed `Config` for *validation* | Luigi params-as-class-attributes; Prefect params-as-flow-args (no file) | plumber wants a file for the phase list + params and CLI overrides on top — exactly Kedro's precedence rule. Pass the merged dict as `**params` (Ploomber). Optionally let a phase declare a Pydantic params model and have `plumber check` validate it (Dagster's idea, without making the phase a class). |
| **Executor swap** | Prefect `task_runner=` (one kwarg, tasks unaware); Dagster `executor_def` / `execution:` config key; Ploomber `executor:` YAML key / dotted path; Kedro `--runner=` | — (every surveyed framework keeps this orthogonal; the pattern is well-proven) | Adopt directly: a single CLI flag / config key selects an `ExecutionStrategy`; the phase `run` never imports or names it. |
| **Partitioning** | Dagster: same compute logic for every partition, key injected at runtime; strategy handles fan-out/gather | Dagster's `PartitionsDefinition` *object graph* and partition-to-partition mapping machinery | plumber's partitioning is explicit config (by field(s) / chunk size / worker count), not a first-class typed object with backfill semantics. Keep the phase partition-agnostic: it gets one gdf, returns one gdf; the strategy splits and reassembles. |
| **Runtime contract** | Kedro's "pure node" + ParallelRunner rules (picklable, no shared state, no reliance on hooks); Dagster's executor-agnostic op | Any assumption of same-process state, execution order, working directory, or access to other phases' outputs | Under localmp (and later Beam/Spark) a phase runs in another process/worker. The one thing a phase may *not* assume is in-process continuity. |

### Patterns to borrow

1. **Explicit ordered phase list in the config file** (Ploomber `pipeline.yaml` tasks) —
   not a derived DAG.
2. **Dotted-path / module resolution for each phase** (Ploomber `source:`) — no required
   project layout, so `plumber` runs from any repo.
3. **Two-layer params with CLI-wins precedence** (Kedro `parameters.yml` + `--params`),
   merged dict handed to the phase as `**params` (Ploomber `PythonCallable(**params)`).
4. **Executor as an out-of-band selection** — one CLI flag / config key picks an
   `ExecutionStrategy`; phase code never references it (Prefect `task_runner`, Dagster
   `executor_def`, Ploomber `executor:`).
5. **Optional typed params validation** without classes-as-phases — a phase may expose a
   Pydantic model that `plumber check` validates against config (Dagster `Config`, Kedro
   type-hinted node args), but the phase entry point stays `run(gdf, **params)`.
6. **Document the parallel contract explicitly** (Kedro ParallelRunner): params + gdf
   must be picklable; no shared mutable state; no reliance on side effects between
   phases.
7. **Partition-agnostic phase body** (Dagster partitions): the strategy owns split /
   distribute / gather; the phase always sees "a GeoDataFrame in, a GeoDataFrame out".

### Patterns to reject

- **Data-dependency DAG inference** (Kedro input/output names, Dagster asset keys,
  Snakemake filename patterns, Luigi `requires()`): plumber's chain is explicitly
  ordered in config and passes a single payload; inference adds a naming ceremony with
  no payoff.
- **Mandatory framework project skeleton** (Kedro `pipeline_registry.py` + `conf/` +
  `settings.py`, Dagster code locations, Prefect deployments): breaks "run from any
  repo".
- **Class-per-phase / params-as-attributes** (Luigi `Task` subclass, and to a lesser
  extent Dagster/Kedro decorator objects): against "plain functions over classes".
- **Target-existence / file-materialisation as the ordering primitive** (Luigi
  `output()`, Snakemake, Ploomber `product`): plumber v1 passes an in-memory
  GeoDataFrame; persistence is a separate concern, not the scheduler's ordering signal.
- **Purely imperative, no config** (Prefect flow body): plumber's whole point is that a
  config file — not Python — drives which phases run in which order.

---

## Recommendations for plumber

1. **Phase discovery & ordering** — the config file (YAML/TOML) carries an ordered
   `phases:` list. Each entry is a dotted path (or `module: path` + optional
   `name:`) that plumber imports and resolves to a module-level `run`. Order = list
   order, full stop. No DAG inference, no `pipeline_registry.py`. This is Ploomber's
   model minus `product`/`upstream` (plumber's chain is linear).

2. **Config / params supply** — two layers, Kedro precedence:
   - config file: the `phases:` list + a per-phase `params:` mapping (+ a top-level
     `partition:` spec and optional `executor:` default).
   - CLI: `--executor/--scale` selects the backend; `-p phase.key=value` (or
     `--set`) overrides individual params, and **CLI wins over the file**.
   - plumber merges file + CLI params per phase and calls `run(gdf, **merged_params)`.
   - Optional: a phase may export a `Params` Pydantic model; `plumber check` validates
     the config's params block against it before any run. The entry point stays
     `run(gdf, **params)` — no class.

3. **Pluggable execution backend** — one `ExecutionStrategy` abstraction, selected by
   `--executor` / config key, never referenced by phase code (Prefect/Dagster/Ploomber
   pattern). Minimal interface: given the ordered `[(run_callable, params), ...]`, an
   input gdf, and the partition spec, return the final gdf. Ship `local` (sequential)
   and `localmp` (multiprocess) for Tracer; `dataflow` (Beam) and `pyspark` behind the
   same interface later. The multiprocess/Beam strategies own partition fan-out and
   result concatenation so phases never see partitioning.

4. **What a phase may assume about its runtime** — codify this as plumber's phase
   contract (borrowed from Kedro's pure-node + ParallelRunner rules and Dagster's
   executor-agnostic op):
   - **May assume**: it receives one `GeoDataFrame` and must return one `GeoDataFrame`;
     it receives its params as keyword arguments; anything it reads from the filesystem
     it opens itself.
   - **May NOT assume**: the process/thread/host it runs on, that it runs in the same
     process as any other phase or as the CLI, execution relative to other phases beyond
     "all earlier phases already ran", access to earlier phases' outputs except via the
     gdf it is handed, or that global/module state set by one phase survives into
     another. Under `localmp`/`dataflow` the gdf and every param value must be
     picklable/serialisable.

5. **Validator (`plumber check`)** — reuse Kedro's `find_pipelines()` *technique* (import
   the module, confirm the expected callable exists, confirm its shape) as a
   config-time check: every `phases:` entry resolves to an importable module exposing a
   callable `run`; each declared param matches the phase's `Params` model if it has one;
   the partition spec names real gdf columns. This is discovery-as-validation, not
   discovery-as-magic.
