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

The steps after launch (config, shim, sample, recommendations) are added by later tickets.
