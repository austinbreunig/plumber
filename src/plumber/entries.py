"""Small readers for one config entry (an `input:`, `output:` or phase block)."""


def params_of(entry):
    return entry.get("params") or {}


def name_of(entry):
    return entry.get("name", entry["path"])
