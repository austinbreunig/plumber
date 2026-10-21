"""Small readers for one config entry, plus the `Finding` shape that check and probe share."""

from typing import NamedTuple

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"


class Finding(NamedTuple):
    """One problem. `label` is the report row it belongs to ("input", "P1", "partition", ...)."""

    label: str
    status: str
    message: str


def phase_label(number):
    return f"P{number}"


def params_of(entry):
    return entry.get("params") or {}


def name_of(entry):
    return entry.get("name", entry["path"])


def merge_params(entry, overrides):
    """The entry's params with CLI overrides replacing them key by key (shallow merge).

    An override only applies to a key the entry already lists.
    """
    return {key: overrides.get(key, value) for key, value in params_of(entry).items()}
