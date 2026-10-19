"""List the functions in a repo's .py files, using `ast` only.

Run with any Python: `python scan_signatures.py [repo]`. Prints a JSON list:
  [{"path": "pkg.mod:fn", "name": "fn", "label": "pkg.mod:fn(data, n=3)",
    "params": [{"name", "hint", "default", "required"}], "doc": "first docstring line"}]

Never imports user code. Never reads function bodies (only names, params, defaults,
type hints and the first docstring line). Skips venvs, hidden folders, tests, `.plumber/`.
"""

import ast
import json
import os
import sys
from pathlib import Path

SKIP_DIRS = {"tests", "__pycache__", "node_modules"}


def source_files(repo):
    """Every .py file under `repo`, skipping venvs, hidden folders, tests and `.plumber/`."""
    for folder, subdirs, files in os.walk(repo):
        if "pyvenv.cfg" in files:
            subdirs[:] = []
            continue
        subdirs[:] = sorted(d for d in subdirs if not d.startswith(".") and d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(".py"):
                yield Path(folder) / name


def module_name(repo, file):
    parts = list(file.relative_to(repo).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def read_params(args):
    """Named params of a function, in order, each as a dict. Skips *args and **kwargs."""
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    pairs = list(zip(positional, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults))
    return [
        {
            "name": arg.arg,
            "hint": ast.unparse(arg.annotation) if arg.annotation else None,
            "default": ast.unparse(default) if default is not None else None,
            "required": default is None,
        }
        for arg, default in pairs
    ]


def format_label(path, params, args):
    parts = []
    for p in params:
        text = p["name"]
        if p["hint"]:
            text += f": {p['hint']}"
        if p["default"] is not None:
            text += f" = {p['default']}" if p["hint"] else f"={p['default']}"
        parts.append(text)
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    return f"{path}({', '.join(parts)})"


def scan_file(repo, file):
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return []
    module = module_name(repo, file)
    found = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = read_params(node.args)
        path = f"{module}:{node.name}"
        doc = (ast.get_docstring(node) or "").strip().split("\n")[0]
        found.append(
            {
                "path": path,
                "name": node.name,
                "label": format_label(path, params, node.args),
                "params": params,
                "doc": doc,
            }
        )
    return found


def scan_signatures(repo="."):
    repo = Path(repo)
    return [f for file in source_files(repo) for f in scan_file(repo, file)]


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(scan_signatures(repo)))


if __name__ == "__main__":
    main()
