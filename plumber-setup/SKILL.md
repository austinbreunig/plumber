---
name: plumber-setup
description: Set up a plumber.yaml for a repo. Run only when the user types /plumber-setup [path].
disable-model-invocation: true
---

# plumber-setup

Helpers live in `scripts/` next to this file. Run them by full path with the target
repo's venv Python, with the target repo as the working directory. Helpers print JSON.
Never install anything. Never run this skill unless the user invoked it.

## Launch

The argument is the target repo path. Default: the current directory.

1. Find the venv: `python <this folder>/scripts/find_venv.py <repo>` (any Python works).
   - `status: ok`: use `venv`.
   - `status: ask`: show `candidates` and ask the user to pick. Never guess.
   - `status: stop`: print `reason` and the exact `fix` command. Stop. Do not run it.
2. Detect the case: `<venv>/bin/python <this folder>/scripts/detect_case.py <repo>`.

| case     | meaning                                                          |
|----------|------------------------------------------------------------------|
| `resume` | `plumber.draft.yaml` exists. Ask: continue or discard? If `draft_error` is set, show it in plain words and ask: fix or discard. |
| `A`      | No `plumber.yaml`. Fresh start, not an error.                    |
| `C`      | `plumber.yaml` has check FAIL/WARN, or does not load. Fix it. `findings` lists why. |
| `B`      | `plumber.yaml` is clean. Change it.                              |

3. Say which case you found and why, in one or two plain sentences. Wait for the user's yes.
   If they say it is a different case ("change it, not fix it"), use theirs.

After launch, the steps run in order: 1 config, 2 shim, 3 sample, 4 recommendations. The user can
skip any step. If a skipped step is needed later, say so in one line. Do not block. Between steps ask
"next, skip, or stop here?". Steps 2 to 4 are added by later tickets. Only case A step 1 is below.

## Step 1, case A: fresh config

Rules for the whole step:
- Read signatures only, with `scripts/scan_signatures.py`. Never read function bodies. Never import
  or call the user's code, and never call the input function.
- After every answer, rewrite the Draft (below) and show the YAML block you just changed.
- Ask for required params only (with the type hint). Params with defaults: list them once, leave
  them out unless the user asks.
- Do not ask for phase names. The default is the path. Ask only to resolve a duplicate.

Conversation, in this order:

1. Workflow. Ask one open question: "What does this pipeline do, step by step?" Not stored.
2. Scan. Run `python <this folder>/scripts/scan_signatures.py <repo>`. Show each function as
   `label` (`path:name(params)`). Pre-select likely matches from the workflow answer. The user picks
   and orders the phases. The input function and output function come from the same list. If the user
   types a path the scan missed, accept it.
3. Fit. For each function say whether it matches `fn(data, **params) -> data` and give one line of
   why. The user can overrule. A function that does not fit needs a shim (built in step 2). Propose
   the name `<function>_shim`. The user may rename it. A name clash with an existing file means
   "pick another name", never overwrite.
4. Repeated function. One shim, reused. Give each use its own `params:` and a distinct phase `name:`.
5. Params. Required ones only.
6. `partitionable`, for every phase, never defaulted. Ask in plain words with an example, for
   example: "Can this phase run on a slice of the rows alone? Yes for a per-row scale. No for a
   dedupe across all rows."
7. Strategy: "one process or several?" If several, `localmp` with exactly one of `by`,
   `chunk_size`, `worker_count`. Say in one line what each means. If no phase is partitionable,
   warn that `localmp` will not help.
8. Sample offer: "have one, make one, or skip?" Put `check.sample` in the Draft. Default path for a
   new one: `.plumber/check_sample.parquet`. Another path: offer to hide it too (see Exclude). The
   sample itself is built in step 3.
9. Tail: slow phases for `checkpoint: true`, `checkpoints.dir`, `user_level`, and the output
   function. If the user skips the output function, repeat plumber's warning: the result is
   discarded.

### Draft

`plumber.draft.yaml` in the repo root is the only memory. It is a full config, rewritten after every
answer: `echo "<full yaml>" | <venv>/bin/python <this folder>/scripts/write_draft.py <repo>`.
Line 1 is `# base: none` in case A (the helper writes it).

The first time you create the draft, ask once (default yes): "Hide plumber.yaml, the draft and
`.plumber/` from git?" Run
`python <this folder>/scripts/exclude_append.py <repo> plumber.yaml plumber.draft.yaml .plumber/`
with only the lines the user picked. It appends to `.git/info/exclude`, never `.gitignore`, and skips
lines already there. If it returns `status: skipped` (not a git repo), say nothing more.

### Approve

1. Run `detect_case.py`'s `check_findings` or `plumber check` on the draft once. Show the full draft
   file (case A has no old file to diff) next to the `check` output. A FAIL does not block approval.
   Label rows that fail only because a shim is not built yet: "expected: shim built in step 2".
2. Ask once: save this as `plumber.yaml`?
   - Yes: copy the draft over `plumber.yaml` without the `# base:` line, then delete the draft.
     End state: a valid `plumber.yaml` and no draft file.
   - No: leave `plumber.yaml` alone and keep the draft. Tell the user they can run `/plumber-setup`
     again to continue.

## Step 3: check sample

Helper: `<venv>/bin/python <this folder>/scripts/sample.py`. It needs the repo's venv (geopandas).

Have one (asked in step 1): run `sample.py schema <file>`. It reads the schema only, never rows. Never
open the file any other way. Show columns, types, geometry, CRS and row count. Cross-check against the
config: tell the user about config columns (partition fields, `_col`/`_column`/`_field` params) that the
sample lacks. Do not change the file.

Make one:
1. Pre-fill columns: `sample.py prefill <repo>` reads the draft. Show them. Ask for more as `name: type`
   (`int`, `float`, `str`, `bool`, `datetime`). On resume the file is missing and nothing was saved, so
   ask the columns again.
2. Ask geometry: points, lines or polygons (default points). Ask CRS (default the config's CRS, else
   EPSG:4326). Rows: 20 unless the user says otherwise. Seed: 0.
3. Build the JSON spec `{"path", "columns", "geometry", "crs", "rows", "seed", "partition"}`. `partition`
   is the `by` columns, so they get 3 distinct values. Pipe it to `sample.py preview`. Show path, row
   count, columns, types and the 5 preview rows.
4. Ask once: write it? On yes pipe the same spec to `sample.py write`. If it returns `status: exists`,
   never overwrite. Ask for a new name, update `check.sample` in the draft, and write again.
5. Run `check` once. Show the result. Do not retry.

## Step 1 tail: strategy, partition, checkpoints, output (ticket #57)

Continues the case A conversation (items 6 to 9 above) and ends before Approve.

- Duplicate function: give each use a distinct `name:` (the default name is the path, so two uses
  of one path clash). Show both phase blocks and ask for the new name.
- Strategy: if `localmp`, write `execution: {strategy: localmp, partition: {<one key>}}`. Exactly one
  of `by` (list of columns, one piece per value), `chunk_size` (rows per piece), `worker_count`
  (N slices).
- Tail order: `checkpoint: true` on slow phases, `checkpoints: {dir: ...}`, `user_level`, then the
  output function (same pick list as the input).
- Before Approve, run `python <this folder>/scripts/lint_draft.py <repo>/plumber.draft.yaml`.
  - Any `problems`: fix them with the user, rewrite the draft, lint again. Do not go to Approve
    until `problems` is empty.
  - Each `warnings` line: say it in plain words once (for example "localmp will not help: no phase
    is partitionable", "no output function, the result is discarded"). Warnings do not block.

## Change an existing config (case B and C)

Case B starts here. Case C is the same path, fed by `findings` from `detect_case.py` (and later by
step 4 recommendations). Work on a copy: the draft. `plumber.yaml` stays untouched until Approve.

1. Case B: ask one question, "What do you want to change?" Case C: say which `findings` you will
   fix, in plain words, and skip the question.
2. Map the answer to top-level blocks: `input`, `phases`, `output`, `strategy`, `check`,
   `checkpoints`, `user_level`. Re-run only the matching parts of the Step 1 interview for those
   blocks. If the user says "walk me through all of it", run the full Step 1 order on the copy.
3. Write each changed block as YAML (the whole block, starting with `<key>:`) with
   `<venv>/bin/python <this folder>/scripts/edit_block.py <repo> <key> < block.yaml`. It starts the
   draft from `plumber.yaml` if there is none, and replaces only that block's lines. Comments, blank
   lines and key order everywhere else stay byte-for-byte. Never rewrite the whole file here.
4. The helper prints `error`. If it is not null, show it in plain words, fix the block, and write
   it again. Show the block you just changed after every edit.
5. Approve as in case A, but show a diff of `plumber.yaml` against the draft (without the `# base:`
   line) next to the `check` output. The diff must show only real changes.

## Resume and drift (ticket 58)

Case `resume` means a session was killed or stopped. The draft is the memory. Read the draft and
continue from the first thing it does not answer yet. Never re-ask what the draft already holds.
If the user deleted the draft by hand, `detect_case` just finds A, B or C again. Say nothing special.

Before continuing, check the result of `detect_case.py`, in this order:

1. `draft_error` is set. Say: "your draft doesn't load: <error>" (in plain words). Ask: fix it or
   discard it? Fix: edit the draft with the user, then rewrite it with `write_draft.py`. Discard:
   delete `plumber.draft.yaml` and re-run `detect_case.py`.
2. `drift` is true. Say: "plumber.yaml changed since this draft started." Ask: discard the draft,
   overwrite (keep the draft and replace the new `plumber.yaml` when approved), or stop. Never
   merge the two by hand or automatically. On overwrite, rewrite the draft with `write_draft.py`
   so its `# base:` matches the current `plumber.yaml`.
3. Neither. Say what the draft has so far, then ask: continue or discard?
