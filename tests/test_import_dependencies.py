import pytest

# List of dependencies
dependencies = [
    "colored_logging",
    "ECOv002_CMR",
    "ECOv002_granules",
    "GEOS5FP",
    "h5py",
    "harmonized_landsat_sentinel",
    "matplotlib",
    "modland",
    "numpy",
    "pandas",
    "rasters",
    "skimage",
    "scipy",
    "sentinel_tiles",
    "shapely",
    "untangle",
    "VCD43NRT",
    "xmltodict"
]

# Generate individual test functions for each dependency
@pytest.mark.parametrize("dependency", dependencies)
def test_dependency_import(dependency):
    __import__(dependency)
