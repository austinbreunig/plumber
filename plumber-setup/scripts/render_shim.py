"""Render an adapter shim from `templates/shim.py.template`.

Run with any Python; the spec comes on stdin as JSON:
  python render_shim.py render < spec.json   -> {"text": "<shim text>"}
  python render_shim.py create <repo> < spec.json -> {"path": "<repo>/.plumber/<name>.py"}
  python render_shim.py taken <repo> <name>  -> {"taken": true|false}
Spec: {"name": "x_shim", "wraps": "module:fn", "data_arg": "data",
       "loaders": [{"param": "model", "loader": "mod:load", "source": "model_source"}],
       "passthrough": ["threshold"]}
`loaders` and `passthrough` are optional. Line 1 of the shim is `# base: <hash>`, line 2 is
`# shim wraps <module:fn>`. `create` never overwrites (raises FileExistsError).
"""

import json
import sys
from pathlib import Path
from string import Template

sys.path.insert(0, str(Path(__file__).parent))

from base_hash import hash_text  # noqa: E402

TEMPLATE = Path(__file__).parents[1] / "templates" / "shim.py.template"
SHIM_DIR = ".plumber"


def loader_ok(params):
    """A loader must take exactly one required param. `params` come from scan_signatures."""
    return sum(1 for p in params if p["required"]) == 1


def name_taken(repo, name):
    return (Path(repo) / SHIM_DIR / f"{name}.py").exists()


def split_path(path):
    module, _, function = path.partition(":")
    if not (module and function) or not all(
        part.isidentifier() for part in [*module.split("."), function]
    ):
        raise ValueError(f"expected <module:fn>, got {path!r}")
    return module, function


def check_identifier(value):
    if not value.isidentifier():
        raise ValueError(f"not a valid Python name: {value!r}")
    return value


def render_shim(spec):
    """Full shim text, with the `# base:` line first."""
    check_identifier(spec["name"])
    module, function = split_path(spec["wraps"])
    loaders = spec.get("loaders", [])
    passthrough = [check_identifier(p) for p in spec.get("passthrough", [])]
    args = [f"{check_identifier(spec['data_arg'])}=data"]
    sources = []
    imports = []
    for i, item in enumerate(loaders):
        loader_module, loader_fn = split_path(item["loader"])
        imports.append(f"from {loader_module} import {loader_fn} as _load_{i}")
        sources.append(check_identifier(item["source"]))
        args.append(f"{check_identifier(item['param'])}=_load_{i}({item['source']})")
    args += [f"{p}={p}" for p in passthrough]
    body = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        wraps=spec["wraps"],
        module=module,
        function=function,
        loader_imports="\n".join(imports),
        params="".join(f", {p}" for p in sources + passthrough).replace(", ", ", *, ", 1),
        call=", ".join(args),
    )
    return f"# base: {hash_text(body)}\n{body}"


def create_shim(repo, spec):
    """Write `.plumber/<name>.py`. Raises FileExistsError rather than overwrite."""
    text = render_shim(spec)
    path = Path(repo) / SHIM_DIR / f"{spec['name']}.py"
    path.parent.mkdir(exist_ok=True)
    with open(path, "x", encoding="utf-8") as f:  # "x" fails if the file exists
        f.write(text)
    return path


def main():
    command = sys.argv[1]
    if command == "taken":
        print(json.dumps({"taken": name_taken(sys.argv[2], sys.argv[3])}))
        return
    spec = json.load(sys.stdin)
    if command == "render":
        print(json.dumps({"text": render_shim(spec)}))
    else:
        print(json.dumps({"path": str(create_shim(sys.argv[2], spec))}))


if __name__ == "__main__":
    main()
