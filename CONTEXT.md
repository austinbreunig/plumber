# plumber

A geospatial pipeline framework: an ordered list of phase functions, run over a dataset by a swappable execution strategy.

## Language

**Checkpoint**:
A phase's output saved to disk because that phase's config entry opts in. Never saved automatically.
_Avoid_: Cache, snapshot, intermediate

**Partial run**:
A run that executes only a slice of the configured phases, chosen on the CLI rather than in the config.
_Avoid_: Resume, rerun, skip
