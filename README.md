# plumber

A geospatial data-engineering pipeline framework. A stable function-shaped phase
interface (`run(gdf, **params) -> gdf`) separates three concerns that are usually
tangled: *what an algorithm does*, *how phases are sequenced and scaled*, and
*how a pipeline is specified*. That separation is meant to make both
prototyping→production scaling and safe agentic pipeline generation tractable —
new logic drops into a fixed slot instead of modifying a monolith.

## Status

Phase 0 (Discovery). No implementation yet. See `.scratch/discovery/map.md` for
the wayfinder map of open decisions, and `plan.md` once Discovery completes.

## Setup

_TBD — established during Discovery/POC._

## Development workflow

Follows the `ab_spatial` playbook: Discovery → POC → Tracer → MVP → Refinement.
See `../../playbook/phases.md`.

## Issue tracker

GitHub Issues in [`austinbreunig/plumber`](https://github.com/austinbreunig/plumber/issues),
via the `gh` CLI. See `docs/agents/issue-tracker.md`.
