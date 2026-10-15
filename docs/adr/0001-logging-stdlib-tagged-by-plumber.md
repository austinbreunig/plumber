# Logging: stdlib logging, tagged and ordered by plumber

Users log with plain Python `logging`; plumber does not hand phases a logger, because that would break the `fn(data, **params)` shape and tie user code to plumber. Instead plumber wraps each phase call, tags every record `[phase|process]`, and prints a **Phase heading** (with a closing line) before each phase, so the **Run log** reads as the user's code inside a pipeline. Every strategy must use the shared heading helper and wrapper, and must deliver all lines of phase N before the heading of phase N+1; how lines travel back is the strategy's own job (`localmp`: a queue from workers to the main process).

## Considered Options

- **A plumber logger passed into phases.** Rejected: changes the phase signature and couples user code to plumber.
- **Workers write to stderr/file directly.** Rejected: lines interleave across phases and depend on fork vs spawn.

## Consequences

- Plumber lines (all levels) always show. Only the **User log** is filtered, by `user_level` (`off` allowed). Any logger not named `plumber` counts as User log, library loggers included.
- The line format is fixed in v1.
- The `ExecutionStrategy` protocol signature does not change; the logging rules are part of the strategy contract.
