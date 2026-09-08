# PhaseModule protocol & the phase contract

Type: grilling
Status: open
Blocked by: —

## Question

Pin the phase interface and its written contract.

- Module-level `run(gdf, **params) -> gdf` as the single public entry point, with
  a `typing.Protocol` (`PhaseModule`) capturing it — confirm this over a bare
  convention or a registry dict, and confirm no class-based ABC.
- State the purity / partition contract every executor assumes: `run()` is a pure
  function of its input, sees **one partition** (never assumes it has the whole
  dataset), holds no shared mutable state, does not depend on global phase order.
- CRS / schema expectations: what a phase may assume about its input and must
  guarantee about its output (design doc: "CRS preserved unless explicitly
  reprojected").
- Where the `GeoDataFrame`-only assumption lives so a later payload type does not
  break the Protocol (feeds the "payload seam" fog item).

Output: the `PhaseModule` Protocol definition and a contract statement suitable
to drop into `CONTEXT.md` / an ADR.
