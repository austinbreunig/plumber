# Phase discovery & ordering

Type: grilling
Status: open
Blocked by: —

## Question

How does the `plumber` CLI, run from an arbitrary repo, find that repo's phase
modules and determine their execution order?

Decide between (and/or combine): a conventioned `phases/` directory ordered by
filename prefix; an explicit ordered list in the config file; a
registry/decorator the modules opt into. Resolve the design-doc section 7 open
thread — string names in the pipeline list vs. module-object introspection for
keying per-phase params. Output: the discovery mechanism, the ordering source of
truth, and how a phase's identity string is formed and matched to its config
params.
