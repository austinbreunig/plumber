"""Turn `check` findings into recommendations (step 4). Plain functions over the check report.

Run with the target repo's venv Python and the repo as the working directory:
  <venv>/bin/python recommend.py <repo> [config] [--params '{"key": 1}']
Runs `check` once on <config> (default: plumber.draft.yaml if present, else plumber.yaml) and
prints {"items": [...]} already in display order. Each item:
  {"label", "status", "kind": "offer"|"tell"|"note", "action", "text", ...extra}
  offer: the skill can write the fix (config edit, shim, sample), through the usual gates.
  tell:  the cause is in the user's code or data (crash, CRS change, dropped columns, unused
         --params key). Never fixed by the skill.
  note:  one summary line (skipped phases, passing rows).
Rules, all plain functions: classify, merge_renames, link_crashes, fold, order, recommend.
"""

import json
import os
import re
import sys
from pathlib import Path

OFFER, TELL, NOTE = "offer", "tell", "note"

# (pattern, kind, action, text). `{0}`, `{1}` are the pattern's groups. WARN texts are questions.
RULES = [
    (r"^config does not load: (.*)", OFFER, "fix_config",
     "plumber.yaml does not load ({0}). Want me to fix it in a draft?"),
    (r"^cannot resolve '(.+?)': (.*)", OFFER, "repick_path",
     "I can't find `{0}` ({1}). Want me to pick the function again from the scan?"),
    (r"^unexpected param '(.+?)' \(signature: (.*)\)", OFFER, "remove_param",
     "`{0}` is not a parameter of this function. It takes: {1}. Remove it from the config?"),
    (r"^missing required param '(.+?)'", OFFER, "add_param",
     "This function needs `{0}` and the config does not give it. What value should it get?"),
    (r"^missing `path`", OFFER, "set_path", "This phase has no function. Which one should it use?"),
    (r"^missing `partitionable`|^`partitionable` must be", OFFER, "set_partitionable",
     "Can this phase run on a slice of the rows alone? I will set `partitionable`."),
    (r"^`checkpoint` must be|^`checkpoints", OFFER, "fix_block",
     "The checkpoint setting is wrong. Want me to fix that block?"),
    (r"^Duplicate phase name|^Phase name '(.+?)' is reserved", OFFER, "rename_phase",
     "Two phases share a name, or a name is reserved. What should the new name be?"),
    (r"^unknown strategy|^key .* is not used by strategy|^strategy .* needs one of|^`by` must|"
     r"^`\w+` must be a whole number|^`partition` must|^`execution` must", OFFER, "fix_execution",
     "The strategy or partition setting is wrong. Want me to fix the `execution` block?"),
    (r"^missing `input:` block", OFFER, "add_input",
     "The config has no input function. Which function loads your data?"),
    (r"^.*user_level", OFFER, "fix_user_level", "`user_level` is wrong. Want me to fix it?"),
    (r"^cannot read '(.+?)'", OFFER, "new_sample",
     "The sample file `{0}` can't be read. Point me to another file, or make a new one?"),
    (r"^different output on identical input", OFFER, "set_partitionable_false",
     "Running this phase twice on the same rows gave different results, so it is not safe to "
     "split into chunks. I can set `partitionable: false`. Fixing the function is up to you."),
    (r"^CRS changed from", TELL, "crs_changed",
     "This phase changed the coordinate system. Did you mean it to?"),
    (r"^columns dropped: (.+)", TELL, "dropped_columns",
     "This phase removed column(s): {0}. Intended?"),
    (r"^'(.+?)': no phase lists this param", TELL, "unused_param",
     "You passed `{0}` with --params but no phase lists it, so it did nothing. Is it a typo?"),
    (r"^upstream phase failed", NOTE, "skipped", ""),
    (r"^[A-Za-z_.]*(?:Error|Exception)\b", TELL, "crash",
     "This phase crashed on the sample: {m}. I don't read your code, so I can't say why."),
]


def classify(label, status, message):
    """One check message -> one item. Unknown messages are told as they are, never dropped."""
    for pattern, kind, action, text in RULES:
        match = re.match(pattern, message)
        if match:
            text = text.replace("{m}", message).format(*match.groups())
            item = {"label": label, "status": status, "kind": kind, "action": action,
                    "text": text, "message": message}
            if action in ("remove_param", "add_param", "unused_param"):
                item["param"] = match.group(1)
            if action in ("repick_path", "new_sample"):
                item["path"] = match.group(1)
            if action == "dropped_columns":
                item["columns"] = [c.strip() for c in match.group(1).split(",")]
            return item
    return {"label": label, "status": status, "kind": TELL, "action": "other",
            "text": f"check says: {message}", "message": message}


def merge_renames(items):
    """In one phase, "unexpected param X" then "missing required param Y" is one rename X -> Y.

    `check` lists unexpected params before missing ones. Pairs go in order; leftovers stay.
    """
    merged = []
    for item in items:
        if item["action"] == "add_param":
            for i, earlier in enumerate(merged):
                if earlier["label"] == item["label"] and earlier["action"] == "remove_param":
                    old, new = earlier["param"], item["param"]
                    merged[i] = {**earlier, "action": "rename_param", "old": old, "new": new,
                                 "text": f"Rename `{old}` to `{new}`?"}
                    break
            else:
                merged.append(item)
        else:
            merged.append(item)
    return merged


def phase_number(label):
    """3 for "P3", None for rows like "input" or "--params"."""
    match = re.fullmatch(r"P(\d+)", label)
    return int(match.group(1)) if match else None


def link_crashes(items):
    """A crash that names a column an earlier phase dropped gets `cause` (that phase's label)."""
    linked = []
    for item in items:
        number = phase_number(item["label"])
        if item["action"] == "crash" and number:
            for earlier in items:
                before = phase_number(earlier["label"])
                if earlier["action"] != "dropped_columns" or not before or before >= number:
                    continue
                column = next((c for c in earlier["columns"] if c in item["message"]), None)
                if column:
                    where = f"`{column}` dropped in {earlier['label']}"
                    text = f"{item['text']} It may come from {where}."
                    item = {**item, "cause": earlier["label"], "text": text}
                    break
        linked.append(item)
    return linked


def shim_wraps(config_text, path):
    """`module:fn` from a `# shim wraps module:fn` comment on the config line with `path`."""
    for line in config_text.splitlines():
        if path in line:
            match = re.search(r"#\s*shim wraps\s+(\S+)", line)
            if match:
                return match.group(1)
    return None


def offer_shims(items, config_text):
    """An unresolved path with a `# shim wraps` comment becomes an offer to build that shim."""
    offered = []
    for item in items:
        wraps = item["action"] == "repick_path" and shim_wraps(config_text, item["path"])
        if wraps:
            name = item["path"].partition(":")[0]
            text = (f"`{item['path']}` is a shim that is not built yet. "
                    f"Build `{name}` to wrap `{wraps}`?")
            item = {**item, "action": "build_shim", "wraps": wraps, "name": name, "text": text}
        offered.append(item)
    return offered


def fold(items, rows):
    """SKIP rows become one note line and PASS rows another. Other items stay as they are."""
    kept = [i for i in items if i["action"] != "skipped"]
    skipped = [i["label"] for i in items if i["action"] == "skipped"]
    passed = [r["label"] for r in rows if r["status"] == "PASS"]
    if skipped:
        text = f"{', '.join(skipped)} were not tested because an earlier phase failed."
        kept.append({"label": ", ".join(skipped), "status": "SKIP", "kind": NOTE,
                     "action": "skipped", "text": text})
    if passed:
        kept.append({"label": ", ".join(passed), "status": "PASS", "kind": NOTE,
                     "action": "passed", "text": f"{', '.join(passed)} look fine."})
    return kept


STATUS_ORDER = ["FAIL", "WARN", "SKIP", "PASS"]


def order(items):
    """FAIL, WARN, SKIP, PASS. Within one status the report's row order stays."""
    return sorted(items, key=lambda item: STATUS_ORDER.index(item["status"]))


def recommend(report, config_text=""):
    """The whole step: report rows -> ordered items."""
    items = [
        classify(row["label"], row["status"], message)
        for row in report["rows"]
        if row["status"] != "PASS"
        for message in row["messages"]
    ]
    items = offer_shims(link_crashes(merge_renames(items)), config_text)
    return {"items": order(fold(items, report["rows"]))}


def default_config(repo):
    """The draft if there is one (it is the work in progress), else plumber.yaml."""
    draft = Path(repo) / "plumber.draft.yaml"
    return draft.name if draft.exists() else "plumber.yaml"


def recommend_repo(repo, config_file=None, overrides=None):
    """Run `check` once on the config and recommend. Never retries."""
    from plumber import check, load_config  # needs plumber, so import only when used

    repo = Path(repo)
    path = repo / (config_file or default_config(repo))
    text = path.read_text(encoding="utf-8")
    try:
        report = check(load_config(path), overrides or {})
    except Exception as error:  # a config that will not load is one FAIL, as in detect_case
        report = {"rows": [{"label": "config", "status": "FAIL",
                            "messages": [f"config does not load: {error}"]}]}
    return recommend(report, text)


def main():
    args = sys.argv[1:]
    overrides = json.loads(args[args.index("--params") + 1]) if "--params" in args else {}
    if "--params" in args:
        del args[args.index("--params"):args.index("--params") + 2]
    repo = args[0] if args else "."
    os.chdir(repo)  # plumber resolves phase paths from the working directory
    print(json.dumps(recommend_repo(".", args[1] if len(args) > 1 else None, overrides)))


if __name__ == "__main__":
    main()
