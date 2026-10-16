import geopandas as gpd

def load_sample(path):
    return gpd.read_parquet(path)

def write_out(data, path):
    data.to_parquet(path)
