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
