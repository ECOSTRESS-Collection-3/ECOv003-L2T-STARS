import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from ECOv003_L2T_STARS import _stars_rust
from ECOv003_L2T_STARS.process_rust_data_fusion import process_rust_data_fusion

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_BUNDLE = REPO_ROOT / "test_bundle"


def test_estimate_spatial_variance_matches_analytical_first_differences():
    rng = np.random.default_rng(42)
    nx, ny, nt = 3, 3, 12
    stack = rng.normal(0.5, 0.02, size=(nx, ny, nt)).astype(np.float64)

    sp_var = _stars_rust.estimate_spatial_variance(
        np.ascontiguousarray(stack),
        coarse_cell_size=490.0,
        fine_cell_size=70.0,
        min_num_obs=8,
        default_var=1e-4,
    )

    assert sp_var.shape == (nx, ny)
    assert np.all(np.isfinite(sp_var))
    assert np.all(sp_var > 0.0)

    # Fewer than min_num_obs valid observations falls back to default_var
    sparse = np.full((2, 2, 10), np.nan, dtype=np.float64)
    sparse[:, :, :3] = 0.25
    fallback = _stars_rust.estimate_spatial_variance(
        sparse,
        coarse_cell_size=490.0,
        fine_cell_size=70.0,
        min_num_obs=8,
        default_var=1.23e-4,
    )
    assert np.allclose(fallback, 1.23e-4)


def test_fuse_stars_product_synthetic_grid():
    nx_c, ny_c, nt_c = 4, 4, 4
    nx_f, ny_f, nt_f = 28, 28, 1

    coarse = np.full((nx_c, ny_c, nt_c), 0.45, dtype=np.float64)
    fine = np.full((nx_f, ny_f, nt_f), 0.46, dtype=np.float64)

    mean_out, sd_out, bias_out, bias_sd_out = _stars_rust.fuse_stars_product(
        coarse_stack=coarse,
        coarse_time_indices=np.array([1, 2, 3, 4], dtype=np.uintp),
        fine_stack=fine,
        fine_time_indices=np.array([4], dtype=np.uintp),
        coarse_origin=[500245.0, 3899755.0],
        coarse_cell_size=[490.0, -490.0],
        fine_origin=[500035.0, 3899965.0],
        fine_cell_size=[70.0, -70.0],
        prior_mean=np.full((nx_f, ny_f), 0.44, dtype=np.float64),
        prior_var=np.full((nx_f, ny_f), 1e-4, dtype=np.float64),
        prior_bias_mean=np.zeros((nx_c, ny_c), dtype=np.float64),
        prior_bias_var=np.full((nx_c, ny_c), 1e-6, dtype=np.float64),
        cov_scale=np.full((nx_f, ny_f), 0.01, dtype=np.float64),
        coarse_res_scalar=490.0,
        target_time_index=4,
        num_workers=2,
    )

    assert mean_out.shape == (nx_f, ny_f)
    assert sd_out.shape == (nx_f, ny_f)
    assert bias_out.shape == (nx_c, ny_c)
    assert bias_sd_out.shape == (nx_c, ny_c)
    assert np.all(np.isfinite(mean_out))
    assert np.all(sd_out > 0.0)
    assert np.all(bias_sd_out > 0.0)
    assert np.allclose(mean_out, 0.46, atol=0.02)


@pytest.mark.skipif(
    os.environ.get("RUN_RUST_FUSION_TEST") != "1" or not TEST_BUNDLE.exists(),
    reason="set RUN_RUST_FUSION_TEST=1 with test_bundle present to run full tile Rust parity verification",
)
@pytest.mark.parametrize("product_name,coarse_res", [("NDVI", 490), ("albedo", 980)])
def test_rust_data_fusion_matches_reference_outputs(tmp_path: Path, product_name: str, coarse_res: int):
    downsampled_dir = TEST_BUNDLE / "inputs" / "DOWNSAMPLED_products"
    priors_dir = TEST_BUNDLE / "priors"
    ref_dir = TEST_BUNDLE / "reference_outputs"
    suffixes = ["", ".UQ", ".flag", ".bias", ".bias.UQ"]

    posteriors = {
        suffix: tmp_path / f"STARS_{product_name}{suffix}_2026-10-10_11SPS_70m.tif"
        for suffix in suffixes
    }

    process_rust_data_fusion(
        tile="11SPS",
        coarse_cell_size=coarse_res,
        fine_cell_size=70,
        VIIRS_start_date=datetime.strptime("2026-10-03", "%Y-%m-%d").date(),
        VIIRS_end_date=datetime.strptime("2026-10-10", "%Y-%m-%d").date(),
        HLS_start_date=datetime.strptime("2026-10-07", "%Y-%m-%d").date(),
        HLS_end_date=datetime.strptime("2026-10-10", "%Y-%m-%d").date(),
        downsampled_directory=str(downsampled_dir),
        product_name=product_name,
        posterior_filename=str(posteriors[""]),
        posterior_UQ_filename=str(posteriors[".UQ"]),
        posterior_flag_filename=str(posteriors[".flag"]),
        posterior_bias_filename=str(posteriors[".bias"]),
        posterior_bias_UQ_filename=str(posteriors[".bias.UQ"]),
        prior_filename=str(priors_dir / f"STARS_{product_name}_2026-10-06_11SPS_70m.tif"),
        prior_UQ_filename=str(priors_dir / f"STARS_{product_name}.UQ_2026-10-06_11SPS_70m.tif"),
        prior_bias_filename=str(priors_dir / f"STARS_{product_name}.bias_2026-10-06_11SPS_70m.tif"),
        prior_bias_UQ_filename=str(priors_dir / f"STARS_{product_name}.bias.UQ_2026-10-06_11SPS_70m.tif"),
        num_workers=4,
    )

    for suffix, out_path in posteriors.items():
        ref_path = ref_dir / out_path.name
        with rasterio.open(out_path) as src_out, rasterio.open(ref_path) as src_ref:
            arr_out = src_out.read(1).astype(np.float64)
            arr_ref = src_ref.read(1).astype(np.float64)
            nan_out = ~np.isfinite(arr_out)
            nan_ref = ~np.isfinite(arr_ref)
            assert np.array_equal(nan_out, nan_ref), f"NaN mask mismatch in {out_path.name}"
            valid = ~nan_out
            rmse = float(np.sqrt(np.mean((arr_out[valid] - arr_ref[valid]) ** 2)))
            assert rmse < 1e-7, f"RMSE too high for {out_path.name}: {rmse}"
