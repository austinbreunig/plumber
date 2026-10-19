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
- `passthrough`: the other required params. The phase's `params:` in the YAML holds the
  `<param>_source` values and the passthrough values.

Name clash: `python <this folder>/scripts/render_shim.py taken <repo> <name>`. If `taken: true`, say
"pick another name". Never overwrite.

### Build

1. Render each pending shim: `python <this folder>/scripts/render_shim.py render < spec.json`.
   Show every pending shim in full with its expected `params:`. Ask one yes for the whole set.
2. Yes: `python <this folder>/scripts/render_shim.py create <repo> < spec.json` once per shim. It
   writes `.plumber/<name>.py` and refuses to overwrite. The shim is referenced as `<name>:run`.
   Line 1 is `# base: <hash>`, line 2 is `# shim wraps <module:fn>`.
3. Run `check` once. Show the result. Do not retry.
4. Resume: a config pointing at a missing shim resumes at this step.

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
