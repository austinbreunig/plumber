# Run guide

For someone running plumber for the first time. Do the steps in order. Run every command from
your repo folder (the one with `plumber.yaml`).

## 1. Turn on your virtual environment

Plumber is installed in your repo's venv. Turn it on first, or the `plumber` command is not found.

```
source .venv/bin/activate
```

Your prompt now starts with `(.venv)`. If your venv has another name, use that folder instead.

## 2. Check the config

Run this before every run. It is fast and it can save you a long wait.

```
plumber check
```

It prints one line per part of your config, each ending in `PASS`, `WARN` or `FAIL`. At the end it
prints `runtime probe:`. That line says whether your phases ran on the check sample.

- `PASS`: good.
- `WARN`: a question, not an error. Read it. The run still works.
- `FAIL`: fix it first. `plumber run` will refuse to start.

Using another file? `plumber check --config my_pipeline.yaml`. Without `--config`, plumber reads
`./plumber.yaml`.

## 3. Run the pipeline

```
plumber run
```

This reads your input, runs each phase in order, and writes the result with your output function.
Same option as before: `plumber run --config my_pipeline.yaml`.

Try a different value without editing the file:

```
plumber run --params factor=3
```

`--params` changes that param in every phase that has it.

## 4. Where the result lands

Open `plumber.yaml` and look at the `output:` block. Example:

```yaml
output:
  path: myio:write_parquet
  params: {path: out/result.parquet}
```

The result is the file in `params`: here, `out/result.parquet`. No `output:` block? The result is
thrown away, and plumber warns you at the start.

## 5. Read the run log

Plumber marks each part of the run with a line between `===`:

```
=== run start: 2 phases ===
=== scale ===
checkpoint saved: .plumber/checkpoints/scale.parquet
=== drop_value ===
=== run end ===
```

- `=== run start ===` and `=== run end ===`: the run began and finished. Seeing `run end` means it
  worked.
- `=== <name> ===`: a phase starts. Your own log lines appear under it.
- `checkpoint saved: <path>`: that phase's output was saved to disk.
- `=== run failed ===`: something broke. The error is printed right after it. Read that.

Warnings print too. A common one: `No output: in config: result discarded`.

## 6. Common failures

- **A missing column.** The error names a column your data does not have. Check the spelling in
  `params` (for example `key_field`). Open your data and compare the names.
- **A function or shim is not found.** `check` says `cannot resolve 'module:name'`. Check the
  `path:` for typos. Is the file in the repo? Is it the same venv?
- **A `null` left in the config.** A param set to `null` is a value you meant to fill in later.
  Put the real value in `plumber.yaml`, then run `plumber check` again.

## 7. Use your real data

Your `input:` may point at a small sample file. A run on it gives a sample result, not the real
one. Change the input path in `plumber.yaml`:

```yaml
input:
  path: geopandas:read_parquet
  params: {path: data/parcels_full.parquet}
```

Also check the `output:` path, so you do not overwrite an earlier result. Then run `plumber check`
and `plumber run` again.

## 8. Run only some phases

Use `--from` and `--to` with phase names. A phase name is its `name:` in the config. Without one, it
is the `path:`.

```
plumber run --to scale
plumber run --from drop_value
plumber run --from scale --to scale
```

- `--to scale`: stop after the `scale` phase. The result is thrown away unless that phase has
  `checkpoint: true`.
- `--from drop_value`: start at `drop_value`. It reads the saved checkpoint of the phase before it,
  so that earlier phase needs `checkpoint: true` and must have been run once.
