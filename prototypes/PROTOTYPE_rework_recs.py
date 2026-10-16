"""PROTOTYPE, throwaway. Question (#43): how does /plumber-setup turn `check` findings into
plain-language recommendations, and which can it only recommend vs offer to write?

Runs real `check` on fixture + temp-BAP configs with deliberate mistakes, then prints the raw
finding next to a draft recommendation.
Run from projects/bap (needs its nix env): PROTO_SCRATCH=<dir holding bap_tmp> PLUMBER_FIXTURE=<tests/fixture>
PYTHONPATH=<this worktree>/src:<bap>/src direnv exec . .venv-plumber/bin/python prototypes/PROTOTYPE_rework_recs.py
"""
import copy
import os
import re
import sys
from pathlib import Path

import yaml

from plumber.check import check

SCRATCH = Path(os.environ["PROTO_SCRATCH"])
FIXTURE = Path(os.environ["PLUMBER_FIXTURE"])

# kind: OFFER = skill can write it (config edit via draft + approval, or shim step)
#       TELL  = recommend only (the cause is in the user's code or data)
RULES = [
    (r"^cannot resolve '(.+)': (.*)", "OFFER",
     "I can't find `{0}` ({1}). Check the module and function names. Want me to pick it again from the function list?"),
    (r"^unexpected param '(.+)' \(signature: (.*)\)", "OFFER",
     "`{0}` isn't a parameter of this function. It takes: {1}. Want me to remove or rename it in the config?"),
    (r"^missing required param '(.+)'", "OFFER",
     "This function needs `{0}` and the config doesn't give it. What value should it get? I'll add it."),
    (r"^missing `partitionable`", "OFFER",
     "Each phase needs `partitionable: true` or `false`. Can this step run on separate chunks of rows? I'll set it."),
    (r"^Duplicate phase name '(.+)'", "OFFER",
     "Two steps are both called `{0}`. What should the second one be called? I'll add a `name:`."),
    (r"^key '(.+)' is not used by strategy '(.+)'", "OFFER",
     "`{0}` doesn't work with the `{1}` strategy. Remove it, or switch strategy?"),
    (r"^unknown strategy", "OFFER", "That strategy name isn't one plumber knows. Pick one from the list shown and I'll fix it."),
    (r"^missing `input:` block", "OFFER", "The config has no input function. Which function loads your data? I'll add the block."),
    (r"^'(.+)': no phase lists this param", "TELL",
     "You passed `{0}` on the command line but no step uses it, so it did nothing. Check the spelling."),
    (r"^cannot read '(.+)'", "OFFER",
     "The sample file `{0}` can't be read. Point me to another file, or I can make a new one (step 3)."),
    (r"^different output on identical input", "OFFER",
     "Running this step twice on the same rows gave different results, so it keeps hidden state and can't be split into chunks. "
     "I can set `partitionable: false`. Fixing the function itself is up to you; I don't read function code."),
    (r"^CRS changed from", "TELL",
     "This step changed the coordinate system. If that's on purpose, ignore this. If not, the function is the place to look."),
    (r"^columns dropped: (.+)", "TELL",
     "This step removed column(s): {0}. If a later step needs them, that step will fail. Intended?"),
    (r"^upstream phase failed", "FOLD", ""),
    (r"^(\w+Error): (.*)", "TELL",
     "This step crashed on the sample with {0}: {1}. I don't read your code, so I can't say why. The sample or the params may be wrong."),
]


def recommend(status, message):
    if status == "PASS":
        return None
    for pattern, kind, text in RULES:
        m = re.match(pattern, message)
        if m:
            return kind, text.format(*m.groups())
    return "TELL", f"(no rule) {message}"


def load_fixture_config():
    return yaml.safe_load((FIXTURE / "plumber.yaml").read_text())


def load_bap_config():
    return {
        "input": {"path": "bap_io:load_sample", "params": {"path": str(SCRATCH / "bap_tmp/sample.parquet")}},
        "phases": [
            {"path": "validate_shim:run", "partitionable": True, "params": {}},
            {"path": "cluster_shim:run", "partitionable": False,
             "params": {"key_field": "zone", "id_field": "parcel_id"}},
        ],
        "output": {"path": "bap_io:write_out", "params": {"path": "out.parquet"}},
        "check": {"sample": str(SCRATCH / "bap_tmp/sample.parquet")},
    }


def with_fixture_sample(c):
    c["check"] = {"sample": "sample.parquet"}
    return c


# (base, title, mutate(config))
def swap(i, path, **kw):
    def f(c):
        c["phases"][i]["path"] = path
        c["phases"][i]["params"] = kw
        return c
    return f


def edit(fn):
    return fn


SCENARIOS = [
    ("bap", "BAP: good config", lambda c: c),
    ("bap", "BAP: shim not built yet", lambda c: c["phases"].__setitem__(1, {**c["phases"][1], "path": "cluster_polygons_shim:run"}) or c),
    ("bap", "BAP: required param left out", lambda c: c["phases"][1]["params"].pop("key_field") and c),
    ("bap", "BAP: param typo", lambda c: c["phases"][1]["params"].update(key_feild="zone") or c["phases"][1]["params"].pop("key_field") and c),
    ("bap", "BAP: wrong column name (crash on sample)", lambda c: c["phases"][1]["params"].update(key_field="zoneX") or c),
    ("bap", "BAP: missing partitionable", lambda c: c["phases"][0].pop("partitionable") and c),
    ("bap", "BAP: bad partition key for strategy", lambda c: c.update(execution={"strategy": "local", "partition": {"by": ["zone"]}}) or c),
    ("bap", "BAP: sample file missing", lambda c: c["check"].update(sample="nope.parquet") or c),
    ("fix", "FIXTURE: CRS change + dropped column", lambda c: c["phases"].__setitem__(slice(0, 0), [
        {"path": "phases.reproject:run", "partitionable": True, "params": {}},
        {"path": "phases.drop_value:run", "partitionable": True, "params": {}}]) or c),
    ("fix", "FIXTURE: phase crashes, rest skipped", lambda c: c["phases"].insert(1, {"path": "phases.crash:run", "partitionable": True, "params": {}}) or c),
    ("fix", "FIXTURE: hidden state (not chunk-safe)", lambda c: c["phases"].insert(0, {"path": "phases.counter_state:run", "partitionable": True, "params": {}}) or c),
    ("fix", "FIXTURE: duplicate names", lambda c: c["phases"].append(copy.deepcopy(c["phases"][0])) or c),
]


def run_scenario(base, title, mutate):
    if base == "bap":
        os.chdir(SCRATCH / "bap_tmp")
        sys.path[:0] = [str(SCRATCH / "bap_tmp"), str(SCRATCH / "bap_tmp/.plumber")]
        config = mutate(load_bap_config())
    else:
        os.chdir(FIXTURE)
        sys.path[:0] = [str(FIXTURE)]
        FIXTURE_SAMPLE = FIXTURE / "sample.parquet"
        from myio import load_fixture
        load_fixture().to_parquet(FIXTURE_SAMPLE)
        config = mutate(with_fixture_sample(load_fixture_config()))
    report = check(config)
    print(f"\n=== {title}   ok={report['ok']}   probe: {report['runtime_probe']}")
    skipped = []
    for row in report["rows"]:
        if row["status"] == "PASS":
            continue
        for msg in row["messages"] or ["(no message)"]:
            rec = recommend(row["status"], msg)
            if rec and rec[0] == "FOLD":
                skipped.append(row["label"])
                continue
            kind, text = rec
            print(f"  {row['label']:<10}{row['status']:<5} RAW: {msg[:110]}")
            print(f"  {'':<15}[{kind}] {text}")
    if skipped:
        print(f"  (folded: {', '.join(skipped)} not tested because an earlier step failed)")
    passed = [r["label"] for r in report["rows"] if r["status"] == "PASS"]
    if passed:
        print(f"  PASS: {', '.join(passed)} (no comment)")


if __name__ == "__main__":
    only = sys.argv[1:] 
    for base, title, mutate in SCENARIOS:
        if only and not any(o in title for o in only):
            continue
        run_scenario(base, title, mutate)
        # fresh cwd/path state is cheap enough to leave; modules may be cached
