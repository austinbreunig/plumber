# Skill dry run (manual)

Checks the `/plumber-setup` skill by hand. This file is outside `plumber-setup/` so it does
not ship. Spec: #54.

## Setup

1. Install the skill: copy `plumber-setup/` into `.claude/skills/` of your test harness.
2. Copy the fixture to a scratch folder for each run (do not edit it in place):
   `cp -r tests/skill/fixtures/repo /tmp/dryrun-X && cd /tmp/dryrun-X && git init`
3. Make a venv there with plumber installed and `geopandas`. Activate it.
4. Open the agent in that folder and run `/plumber-setup`.

The fixture has `myio.py` (`load_fixture`, `write_parquet`), `phases/scale_value.py`
(`run(gdf, factor=1, **params)`) and `phases/drop_value.py` (drops the `value` column).
Its `plumber.yaml` is clean.

## Case A: fresh repo

Start: delete `plumber.yaml`.

1. Skill says "fresh start" and waits for yes.
2. Say the pipeline loads data, scales `value`, writes parquet.
3. Pick `myio:load_fixture`, `phases/scale_value:run`, `myio:write_parquet` from the scan.
4. Answer `factor`, say `partitionable: true`, choose `localmp` with `by: zone`.
5. Choose "make a sample". Accept the default path `.plumber/check_sample.parquet`.
6. Approve the full file. Then step 3: pick points, EPSG:4326, accept the preview.
7. Step 4: read the recommendations.

Expect: `plumber.yaml` exists, `check` has no FAIL, draft gone, one exclude offer (accept it).

## Case B: change a clean config

Start: restore the fixture as is (clean `plumber.yaml`).

1. Skill says "change" and waits for yes.
2. Answer "What do you want to change?" with "add the drop_value phase after scale".
3. Only the phases block should change in the diff. Comments and key order stay.
4. Approve.

Expect: `plumber.yaml` has the new phase, no FAIL, draft gone.

## Case C: fix a check problem

Start: fixture, then in `plumber.yaml` change `factor` to `fctor`.

1. Skill says "fix" and waits for yes. It starts at step 4.
2. Expect one merged offer: "rename `fctor` to `factor`?" (not two findings).
3. Approve the rename.
4. `check` runs once and the skill stops.

Expect: no FAIL, no silent overwrite, the skill did not touch `phases/*.py`.
Also try putting `drop_value` before `scale_value`: the skill should tell the dropped column
("intended?") and link the later crash to it. It must not edit your code.

## Kill and resume

Start: case A setup again.

1. Answer until the phases and `partitionable` are done, then kill the session
   (close the terminal) before approval.
2. Check that `plumber.draft.yaml` exists, line 1 is `# base: none`, and `plumber.yaml` does not.
3. Open a new session and run `/plumber-setup`.
4. Expect "draft found: continue or discard". Choose continue.
5. Expect nothing already answered is asked again. Finish and approve.

Also try: hand-edit `plumber.yaml` after a draft starts. Resume must offer discard,
overwrite or stop. It must not merge.

## Pass checklist (every run)

- [ ] Ends with a `plumber.yaml`
- [ ] `check` shows no FAIL (WARN is fine)
- [ ] No file was overwritten without a yes
- [ ] No `plumber.draft.yaml` left after approval
- [ ] The agent never read function bodies or called `load_fixture`
- [ ] The agent never ran an install command
