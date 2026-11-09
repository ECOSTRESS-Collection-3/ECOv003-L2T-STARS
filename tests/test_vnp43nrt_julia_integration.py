"""Optional integration test for Julia BRDF processing and GeoTIFF output."""

import os
import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin


@pytest.mark.skipif(
    not os.environ.get("VNP43NRT_TEST_JULIA"),
    reason="set VNP43NRT_TEST_JULIA to a Julia 1.11 executable to run this test",
)
def test_julia_brdf_writes_all_geotiffs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    project = root / "ECOv003_L2T_STARS"
    script = project / "VNP43NRT" / "process_VNP43NRT.jl"
    directories = {name: tmp_path / name for name in ("reflectance", "solar", "sensor", "azimuth")}
    for directory in directories.values():
        directory.mkdir()

    def write_raster(path, value):
        with rasterio.open(
            path, "w", driver="GTiff", width=4, height=4, count=1,
            dtype="float32", transform=from_origin(0, 4, 1, 1),
        ) as dataset:
            dataset.write(np.full((4, 4), value, dtype="float32"), 1)

    start = date(2024, 10, 14)
    end = date(2024, 10, 30)
    for i in range(17):
        day = start + timedelta(days=i)
        values = (0.1 + i * 0.002, 30 + i * 0.5, 5 + i, 30 + i * 3)
        for (name, directory), value in zip(directories.items(), values):
            write_raster(directory / f"{day}_{name}.tif", value)

    noon = tmp_path / "noon.tif"
    write_raster(noon, 35)
    output = tmp_path / "output"
    env = os.environ.copy()
    env.pop("DYLD_LIBRARY_PATH", None)
    env.pop("GDAL_DATA", None)
    env.pop("GDAL_DRIVER_PATH", None)
    env["JULIA_NUM_THREADS"] = "1"
    subprocess.run(
        [
            os.environ["VNP43NRT_TEST_JULIA"], f"--project={project}", str(script),
            "I1", "8", "5", "4", str(start), str(end),
            *(str(directory) for directory in directories.values()), str(noon), str(output),
        ],
        env=env,
        check=True,
    )

    for layer in ("WSA", "BSA", "NBAR", "WSA_SE", "BSA_SE", "NBAR_SE", "BRDF_SE", "BRDF_R2", "count"):
        with rasterio.open(output / f"{end}_{layer}.tif") as dataset:
            assert dataset.driver == "GTiff"
            assert (dataset.width, dataset.height) == (4, 4)
