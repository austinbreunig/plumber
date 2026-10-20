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
- The config keys are in `<this folder>/templates/plumber.example.yaml`. Read it once. Never read
  plumber's source to learn them.
- After every answer, rewrite the Draft (below) and show the YAML block you just changed.
- Ask for required params only (with the type hint). Params with defaults: list them once, leave
  them out unless the user asks. The scan shows a named constant default (`n=DEFAULT_N`) as its
  value, so list the value.
- Do not ask for phase names. The default is the path. Ask only to resolve a duplicate.

Conversation, in this order:

1. Workflow. Ask one open question: "What does this pipeline do, step by step?" Not stored.
2. Scan. Run `python <this folder>/scripts/scan_signatures.py <repo>`. Show each function as
   `label` (`path:name(params)`). Pre-select likely matches from the workflow answer. The user picks
   and orders the phases. The input function and output function come from the same list. A library
   function counts: suggest `geopandas:read_parquet` (with `params: {path: ...}`) as the input if the
   repo has no reader. Plumber cannot resolve `GeoDataFrame.to_parquet`, so a missing writer means a
   small `write_parquet(gdf, path)`: offer to add it and ask where it should live. If the repo has
   no loader or writer function at all, the read or write may sit inside another function (for
   example `main`). Ask which function holds it, and read that function's body only, for that one
   purpose. If the user
   types a path the scan missed, accept it.
3. Fit. For each function say whether it matches `fn(data, **params) -> data` and give one line of
   why. The user can overrule. A function that does not fit needs a shim (built in step 2), unless
   the mismatch is in the return value and the user wants the extra output (see below). Propose
   the name `<function>_shim`. The user may rename it. A name clash with an existing file means
   "pick another name", never overwrite.
   Write the phase as `path: <name>:run  # shim wraps <module:fn>` (see Draft).
   Return value: if the scan says `returns_tuple: true`, ask one question: "Do you want the extra
   output (for example a summary to log)?" No: shim with `result_index` (the data's position in
   the tuple, usually 0). Yes: a plain function in the repo that calls the original, logs or keeps
   the extra, and returns the data. A shim stays pure, so it cannot do that. Offer to write it and
   ask where it should live, then list it as a normal phase.
4. Repeated function. One shim, reused. Give each use its own `params:` and a distinct phase `name:`.
5. Params. Required ones only. Before the first draft write, ask for every file path you need (the
   input file, the sample). Never guess one. A value the user will fill in later: write `null`, tell
   them `check` will flag it, and list it as an open item before Approve. If the user already has a
   sample file, run `sample.py schema <file>` and suggest its columns for params like `key_field`
   and `id_field` (for example `zone`, `parcel_id`).
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
   discarded. Do not ask these one by one. Offer the default for every remaining item in one
   sentence, for example "no checkpoints, INFO logs, no output function: OK?", and ask only about
   what differs.

### Draft

`plumber.draft.yaml` in the repo root is the only memory. It is a full config, rewritten after every
answer, with a quoted heredoc so shell quoting cannot change the YAML:

```
<venv>/bin/python <this folder>/scripts/write_draft.py <repo> <<'EOF'
<full yaml>
EOF
```

Line 1 is `# base: none` in case A (the helper writes it). The helper keeps the draft's `# base:` line
on every rewrite. Never write that line yourself.

Shim comment: when a phase uses a shim that is not built yet, write its path line as
`path: <name>:run  # shim wraps <module:fn>`. Step 4 reads that comment to offer the build. A block
rewrite replaces the whole block, so always put the comment back on every shim path line you write
(with `write_draft.py` and with `edit_block.py`). Do not drop it.

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

## Step 2: adapter shims

Skip this step if no function needs a shim. Shims are built from the fixed template by
`scripts/render_shim.py`. Never write a shim by hand.

### Shim spec (settled in step 1)

For each function that does not fit `fn(data, **params) -> data`, agree on one spec:
- `name`: unique, proposed `<function>_shim`.
- `wraps`: `module:fn`.
- `data_arg`: the wrapped function's param that receives the data.
- `loaders`: for a param YAML cannot hold (a network, a model). Pick a loader function that builds
  it from one value. The loader must take exactly one required param (check with the scan: one
  param with `required: true`). The shim gets a plain `<param>_source` param. No loader exists:
  offer "skip this shim" or "pick another function". Never invent a shape.
- `result_index`: optional. Picks one item out of a tuple the wrapped function returns, so the shim
  returns only the data. Leave it out when the function returns the data alone.
- `passthrough`: the other required params, plus any optional ones the user wants in YAML. The
  shim makes each passthrough a required keyword with no default, so put every passthrough value
  in the phase's `params:`, including the defaults of the optional ones. YAML `[80, 35]` arrives as
  a list, not a tuple. Tell the user if the function needs a tuple. The phase's `params:` in the YAML holds the
  `<param>_source` values and the passthrough values.

Name clash: `python <this folder>/scripts/render_shim.py taken <repo> <name>`. If `taken: true`, say
"pick another name". Never overwrite.

### Build

1. Write each spec to the scratchpad, never `/tmp`. Render each pending shim:
   `python <this folder>/scripts/render_shim.py render < spec.json`.
   Show every pending shim in full with its expected `params:`. Ask one yes for the whole set.
2. Yes: `python <this folder>/scripts/render_shim.py create <repo> < spec.json` once per shim. It
   writes `.plumber/<name>.py` and refuses to overwrite. The shim is referenced as `<name>:run`.
   Line 1 is `# base: <hash>`, line 2 is `# shim wraps <module:fn>`.
3. Run `check` once. Show the result. Do not retry.
4. Resume: a config pointing at a missing shim resumes at this step.

## Step 3: check sample

Helper: `<venv>/bin/python <this folder>/scripts/sample.py`. It needs the repo's venv (geopandas).

Have one (asked in step 1): run `sample.py schema <file>`. It reads the schema only, never rows. Never
open the file any other way. Show columns, types, geometry, CRS and row count. Cross-check against the
config: tell the user about config columns (partition fields, `_col`/`_column`/`_field` params) that the
sample lacks. Do not change the file.

Make one:
1. Pre-fill columns: `sample.py prefill <repo>` reads the draft, else `plumber.yaml`. Show them. Ask for more as `name: type`
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
   draft from `plumber.yaml` if there is none, and replaces only that block's lines. The new block replaces the old lines whole, so re-include any
   `# shim wraps <module:fn>` comment from the old block on its path line. Comments, blank
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
   merge the two by hand or automatically. Normal rewrites keep the draft's old `# base:` line, so
   drift stays visible. On overwrite only, rewrite the draft with `write_draft.py <repo> --rebase`
   so its `# base:` matches the current `plumber.yaml`.
3. Neither. Say what the draft has so far, then ask: continue or discard?

## Step 4: recommendations

Case C starts here. Cases A and B end here after approve. Run once:
`<venv>/bin/python <this folder>/scripts/recommend.py <repo> [config-file] [--params '<json>']`
It runs `check` once on the draft (else `plumber.yaml`) and prints `{"items": [...]}` already in
order: FAIL, WARN, SKIP (one folded line), PASS (one last line). Say each item's `text` in plain
words. Do not re-sort, re-word the facts, or run `check` again to "see if it got better".

Each item has `kind`:
- `offer`: you may write the fix, only through the existing gates. Ask yes or no for each.
  - `rename_param`, `remove_param`, `add_param`, `set_path`, `set_partitionable`, `fix_block`,
    `fix_execution`, `fix_user_level`, `add_input`, `rename_phase`, `repick_path`, `fix_config`:
    edit the block with `edit_block.py` (Change an existing config, above).
  - `set_partitionable_false`: write `partitionable: false` for that phase only. Say that fixing the
    function is the user's job.
  - `build_shim`: the config has `# shim wraps <module:fn>` on that path. Go to step 2 with
    `name` and `wraps`. Ask only for what the spec still needs (`data_arg`, loaders).
  - `new_sample`: go to step 3.
- `tell`: say it, never fix it. `crash`, `crs_changed`, `dropped_columns` (ask "intended?"),
  `unused_param` (a `--params` key no phase lists), `other`. If a crash has `cause`, say the
  earlier dropped column is the likely root cause. The user decides about their own code and data.
- `note`: read the line as it is.

WARNs on a working pipeline are questions, not errors. Keep them calm.

After the approved fixes, run `check` once (`recommend.py` again, or `plumber check`), show the
result, and stop. No retry loop. A FAIL left over is told, not chased.

## Edit and remove shims

Only on request. Helper: `python <this folder>/scripts/shim_edit.py`. Only shims with the
`# shim wraps` line are skill-made. Never touch any other file in `.plumber/`.

1. Look first: `shim_edit.py status <repo> <name>`.
   - `skill_made: false`: say it is hand-written and stop. Never edit or delete it.
   - `hand_edited: true`: the `# base:` hash no longer matches, so someone edited it. Show `text`
     and ask: overwrite, keep, or stop. Keep and stop change nothing.
2. Edit: re-ask only the part of the shim spec that changes. Pipe the new spec to
   `shim_edit.py diff <repo>` and show `diff` (old vs new). One approval, then pipe the spec to
   `shim_edit.py edit <repo> [overwrite]`. Pass `overwrite` only if the user chose it. `status: kept`
   means nothing was written. Run `check` once and show it.
3. Remove: ask a yes for each file. Then run `shim_edit.py remove <repo> <name> [overwrite]`.
   - `in_use`: say which files (`used_by`) still have a phase on `<name>:run`. Offer to repoint the
     phase first (edit the `phases` block with `edit_block.py`), then remove again.
   - `hand_edited`: ask overwrite, keep or stop as above. Delete only on overwrite.
   - `not_skill_made`: say the file is hand-written and was left alone.
