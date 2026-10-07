# plumber

Geospatial pipeline framework. See `README.md` for the one-paragraph pitch and
`.scratch/discovery/map.md` for the wayfinder map of open Discovery decisions.

Discovery decisions are on the wayfinder map. The Tracer slice (#20 skeleton,
#21 config + CLI overrides) is implemented. The design doc that seeded this
project is captured on the wayfinder map's Notes.

## Dev commands

```bash
nix develop --command uv run --extra dev pytest -q
nix develop --command uv run --extra dev ruff check .
```

## Agent skills

### Issue tracker

GitHub Issues in `austinbreunig/plumber`, via the `gh` CLI. See
`docs/agents/issue-tracker.md`. The Discovery wayfinder map and its tickets live
as GitHub issues (label `wayfinder:map` for the map). The original
`.scratch/discovery/` markdown is kept as the charting-session record only —
GitHub is now the source of truth.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root, created
lazily by `/domain-modeling`. See `docs/agents/domain.md`.
