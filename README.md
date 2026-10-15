# plumber

A geospatial data-engineering pipeline framework. A stable function-shaped phase
interface (`run(gdf, **params) -> gdf`) separates three concerns that are usually
tangled: *what an algorithm does*, *how phases are sequenced and scaled*, and
*how a pipeline is specified*. That separation is meant to make both
prototyping→production scaling and safe agentic pipeline generation tractable —
new logic drops into a fixed slot instead of modifying a monolith.

## Status

Phase 5 (Refinement), v0.1.2. `run`, `check`, `localmp`, checkpoints and partial runs work. See
[issue #1](https://github.com/austinbreunig/plumber/issues/1) for the wayfinder map and
`plan.md` for the design.

## Install

Plumber must be installed in the **same Python environment** as the code your pipeline
imports. Your shims import your project, so a global `pipx install` will not work.

Plumber is **not** a dependency of your project. Do not add it to your project's
`pyproject.toml`. Install it into the environment after the fact.

### Use plumber (from PyPI)

Activate the environment your project already runs in, then install plumber into it.
Pick the tool you like:

```bash
# pip
pip install ab-plumber

# uv (pass the venv, so uv does not pick another Python)
uv pip install --python .venv/bin/python ab-plumber

# conda
conda install pip && pip install ab-plumber
```

Check it: `plumber --help`.

### Develop plumber (editable install)

Editable means the environment points at the source, so your edits show up with no reinstall.
Activate your project's environment first, then pick one.

**pip can install straight from GitHub.** No manual clone. pip clones the repo for you into
`<venv>/src/ab-plumber`, and that folder is a normal git clone you can edit and commit from:

```bash
pip install -e "git+https://github.com/austinbreunig/plumber@develop#egg=ab-plumber"
```

**uv cannot.** `uv pip install -e` only takes a local folder, so clone first:

```bash
git clone https://github.com/austinbreunig/plumber
uv pip install --python .venv/bin/python -e ./plumber
```

(With pip you can also clone first and run `pip install -e ./plumber`.)

To work on plumber itself (tests, lint), pick one:

```bash
# uv
uv run --extra dev pytest -q
uv run --extra dev ruff check .

# pip
pip install -e ".[dev]" && pytest -q && ruff check .

# Nix (adds Python, uv and system libraries for you)
nix develop --command uv run --extra dev pytest -q
nix develop --command uv run --extra dev ruff check .
```

### Notes

- Nix is optional. Use it only if your project has a `flake.nix`. On Nix, run the commands
  above inside `nix develop`, and always pass `--python <venv>/bin/python` to `uv pip`.
- `uv sync` removes packages that are not in your lockfile, including plumber. Keep plumber in
  its own venv (for example `.venv-plumber`), or run `uv sync --inexact`.

## Quickstart

First [install plumber](#install). Then, in any repo, write your input function, one or more phases, and an output function.
A phase is `run(gdf, **params) -> gdf`. Put pipeline glue (input, output, shims) in a `.plumber/`
folder, or in the project folder. Then add a `plumber.yaml`:

```yaml
input:
  path: myio:load_roads
  params: {path: data/roads.parquet}
phases:
  - path: phases.buffer:run
    partitionable: true
    params: {distance: 10}
output:
  path: myio:write_parquet
  params: {path: out/roads.parquet}
```

Check it, then run it:

```bash
plumber check                  # PASS/WARN/FAIL per phase, also writes report.json
plumber run                    # one process (local)
plumber run --strategy localmp --worker-count 4   # worker processes, same output
```

Optional: `checkpoint: true` on a slow phase saves its output, and
`plumber run --from <phase> --to <phase>` runs a slice.

## Execution strategy

Default is `local` (one process). Switch to `localmp` (worker processes) with no phase
changes:

```yaml
execution:
  strategy: localmp
  partition:            # pick exactly one
    by: [zone_id]       # one piece per unique value combination
    # chunk_size: 10000 # fixed-size row slices, in order
    # worker_count: 8   # N roughly equal slices
```

CLI flags override the config: `--strategy localmp`, `--by zone_id`, `--chunk-size 10000`,
`--worker-count 8`. Any partition flag replaces the config's whole `partition:` block.
A phase with `partitionable: false` gets the joined data once. The output keeps the input's
row order, and the output function runs once on the joined data.

## Wrapping your own function

See [`docs/adapter-shim.md`](docs/adapter-shim.md).

## Development workflow

Follows the `ab_spatial` playbook: Discovery → POC → Tracer → MVP → Refinement.
See `../../playbook/phases.md`.

## Issue tracker

GitHub Issues in [`austinbreunig/plumber`](https://github.com/austinbreunig/plumber/issues),
via the `gh` CLI. See `docs/agents/issue-tracker.md`.
