import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_BUNDLE = REPO_ROOT / "test_bundle"
JULIA_SCRIPT = REPO_ROOT / "ECOv003_L2T_STARS" / "process_ECOSTRESS_data_fusion_distributed_bias.jl"
JULIA_PROJECT = REPO_ROOT / "ECOv003_L2T_STARS"

PRODUCTS = [
    ("NDVI", 490),
    ("albedo", 980),
]

SUFFIXES = ["", ".UQ", ".flag", ".bias", ".bias.UQ"]


@pytest.mark.skipif(
    os.environ.get("RUN_JULIA_FUSION_TEST") != "1" or shutil.which("julia") is None or not TEST_BUNDLE.exists(),
    reason="set RUN_JULIA_FUSION_TEST=1 with julia and test_bundle present to run full Julia fusion verification",
)
@pytest.mark.parametrize("product_name,coarse_res", PRODUCTS)
def test_julia_data_fusion_matches_reference_outputs(tmp_path: Path, product_name: str, coarse_res: int):
    downsampled_dir = TEST_BUNDLE / "inputs" / "DOWNSAMPLED_products"
    priors_dir = TEST_BUNDLE / "priors"
    ref_dir = TEST_BUNDLE / "reference_outputs"

    posteriors = {
        suffix: tmp_path / f"STARS_{product_name}{suffix}_2026-10-10_11SPS_70m.tif"
        for suffix in SUFFIXES
    }
    priors = [
        priors_dir / f"STARS_{product_name}_2026-10-06_11SPS_70m.tif",
        priors_dir / f"STARS_{product_name}.UQ_2026-10-06_11SPS_70m.tif",
        priors_dir / f"STARS_{product_name}.bias_2026-10-06_11SPS_70m.tif",
        priors_dir / f"STARS_{product_name}.bias.UQ_2026-10-06_11SPS_70m.tif",
    ]

    cmd = [
        "julia",
        f"--project={JULIA_PROJECT}",
        "--threads",
        "1",
        str(JULIA_SCRIPT),
        "4",
        "11SPS",
        str(coarse_res),
        "70",
        "2026-10-03",
        "2026-10-10",
        "2026-10-07",
        "2026-10-10",
        str(downsampled_dir),
        product_name,
        str(posteriors[""]),
        str(posteriors[".UQ"]),
        str(posteriors[".flag"]),
        str(posteriors[".bias"]),
        str(posteriors[".bias.UQ"]),
        *[str(p) for p in priors],
    ]

    clean_env = os.environ.copy()
    for var in ("GDAL_DATA", "GDAL_DRIVER_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        clean_env.pop(var, None)

    result = subprocess.run(cmd, cwd=REPO_ROOT, env=clean_env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"Julia failed:\n{result.stdout}\n{result.stderr}"

    for suffix, out_path in posteriors.items():
        ref_path = ref_dir / out_path.name
        assert out_path.exists(), f"Missing output raster: {out_path}"
        with rasterio.open(out_path) as src_out, rasterio.open(ref_path) as src_ref:
            assert src_out.shape == src_ref.shape
            arr_out = src_out.read(1).astype(np.float64)
            arr_ref = src_ref.read(1).astype(np.float64)
            nan_out = ~np.isfinite(arr_out)
            nan_ref = ~np.isfinite(arr_ref)
            assert np.array_equal(nan_out, nan_ref), f"NaN mask mismatch in {out_path.name}"
            valid = ~nan_out
            rmse = float(np.sqrt(np.mean((arr_out[valid] - arr_ref[valid]) ** 2)))
            assert rmse < 1e-4, f"RMSE too high for {out_path.name}: {rmse}"
