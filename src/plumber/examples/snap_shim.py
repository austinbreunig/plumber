"""The canonical adapter shim. Copy this pattern; see docs/adapter-shim.md.

`snap_to_network` stands in for "your existing function": it does not have the phase shape.
`run` is the shim: phase-shaped, pure, and nothing else.
"""

import geopandas as gpd
from shapely.ops import nearest_points


def snap_to_network(points, network, tolerance):
    """Existing function (wrong shape for a phase): move points onto the network line."""
    line = network.geometry.union_all()
    snapped = []
    for point in points.geometry:
        on_line = nearest_points(line, point)[0]
        snapped.append(on_line if point.distance(on_line) <= tolerance else point)
    return points.set_geometry(snapped)


def read_network(path):
    return gpd.read_parquet(path)


def run(gdf, *, network_path, tolerance):
    """The shim. Reads its own side input from a path, keeps no state, returns a new gdf."""
    network = read_network(network_path)
    return snap_to_network(gdf, network, tolerance)
