# shim wraps bap.validate:validate_geometries
from bap.validate import validate_geometries

def run(data):
    return validate_geometries(data)
