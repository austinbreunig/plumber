# shim wraps bap.bap:cluster_polygons
from bap.bap import cluster_polygons

def run(data, *, key_field, id_field=None):
    output, _summary = cluster_polygons(data, key_field, id_field)
    return output
