# plumber

Geospatial pipeline framework. See `README.md` for the one-paragraph pitch and
GitHub issue #1 for the wayfinder map.

Discovery decisions are on the wayfinder map. The Tracer and MVP slices are built
(`run`, `check`, `localmp`, checkpoints, partial runs, PyPI release). The project is in
Refinement. The design doc that seeded this project is captured on the wayfinder map's Notes.

## Dev commands

```bash
nix develop --command uv run --extra dev pytest -q
nix develop --command uv run --extra dev ruff check .
```

## Agent skills

### Issue tracker

GitHub Issues in `austinbreunig/plumber`, via the `gh` CLI. See
`docs/agents/issue-tracker.md`. The Discovery wayfinder map and its tickets live
as GitHub issues (label `wayfinder:map` for the map, issue #1).

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at the repo root, created
lazily by `/domain-modeling`. See `docs/agents/domain.md`.
