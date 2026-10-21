# Adapter shim

An **adapter shim** is a thin wrapper that gives your existing function the shape of a phase.

## When you need one

A phase must look like `run(gdf, **params) -> gdf`. You need a shim when your function:

- takes the data in a different position or under a different name,
- needs extra objects (a network, a model) that cannot go in YAML, or
- returns a tuple, and you only want the GeoDataFrame in it.

If your function already looks like `run(gdf, **params) -> gdf`, list it directly. No shim.

## Before and after

```python
# your existing function: wrong shape for a phase
def snap_to_network(roads, network, tolerance): ...

# adapter shim: phase-shaped, pure, nothing else
def run(gdf, *, network_path, tolerance):
    network = read_network(network_path)
    return snap_to_network(gdf, network, tolerance)
```

```yaml
phases:
  - path: snap:run
    partitionable: true
    params: {network_path: data/network.parquet, tolerance: 2.0}
```

The working example is `src/plumber/examples/snap_shim.py`. The test suite runs it through
`plumber run` and `plumber check` (`tests/test_snap_shim.py`), so it cannot drift.

## How to write one by hand

1. Copy `snap_shim.py` into your project's `.plumber/` folder (for example
   `.plumber/snap.py`). Plumber finds modules there, so pipeline glue stays apart from
   your project code. Input and output functions can live there too. Modules in the project
   folder still work. If a name is in both, `.plumber/` wins.
2. Keep the name `run`. First argument is the data. Everything else is a keyword param.
3. Turn things YAML cannot hold into plain values. Pass a file path, not a loaded network.
   Load it inside `run`.
4. Call your existing function and return its result as a GeoDataFrame. If it returns a tuple like
   `(gdf, summary)`, return the item you want: `return cluster_polygons(gdf, ...)[0]`. The skill does
   this with `result_index`. To keep the extra output (log the summary, say), write a plain
   function in your repo instead. A shim must stay pure, so it cannot log or save.
5. List it in `plumber.yaml` and run `plumber check`.

## The phase contract

The shim must keep these rules:

- **Pure.** Same input and params give the same output. No writing files, no printing results.
- **No shared state.** No module-level caches or globals that change between calls. Each call
  stands alone, so plumber can run it on any slice of the data.
- **Picklable.** `run` is a top-level function in an importable module. No lambdas, no closures,
  no params that cannot be pickled. This lets plumber send it to other processes later.

## The AI skill

The AI skill only copies this pattern. It never invents a new one. If a function does not fit
the pattern, the skill stops and asks you instead of making up a new shape.
