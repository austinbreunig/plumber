"""Not partitionable: keep only the highest-`value` row in each zone.

Needs the whole dataset. On a single partition every row would win.
"""


def run(gdf, **params):
    leader_index = gdf.groupby("zone")["value"].idxmax()
    return gdf.loc[sorted(leader_index)].copy()
