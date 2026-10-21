"""Turn a "pkg.mod:attr" string into the callable it names."""

import importlib
import os
import sys
from typing import Callable


def resolve(path: str) -> Callable:
    """Import `pkg.mod` and return its `attr`. The `:attr` part is required."""
    module_name, sep, attr = path.partition(":")
    if not (module_name and sep and attr):
        raise ValueError(f"Bad path {path!r}: expected 'module:attr' (':attr' is required)")
    cwd = os.getcwd()
    plumber_dir = os.path.join(cwd, ".plumber")
    # .plumber/ goes first so pipeline glue wins over same-named project modules.
    for folder in (cwd, plumber_dir):
        if os.path.isdir(folder) and folder not in sys.path:
            sys.path.insert(0, folder)
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attr)
    except AttributeError:
        raise ValueError(f"Module {module_name!r} has no attribute {attr!r}") from None
