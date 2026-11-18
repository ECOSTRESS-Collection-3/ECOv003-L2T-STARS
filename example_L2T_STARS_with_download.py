from glob import glob
import logging
from os import makedirs, remove
from os.path import abspath, dirname, expanduser, join

import colored_logging as cl
import numpy as np
import rasterio

from ECOv003_CMR import download_ECOSTRESS_granule
from ECOv003_granules import open_granule
from ECOv003_L2T_STARS import generate_L2T_STARS_runconfig, L2T_STARS
from ECOv003_L2T_STARS.L2TSTARSConfig import L2TSTARSConfig

cl.configure()

REPO_ROOT = abspath(dirname(__file__))
REF_DIR = join(REPO_ROOT, "test_bundle", "reference_outputs")

# Set working directory
working_directory = expanduser(join("~", "data", "ECOv003_testing"))
makedirs(working_directory, exist_ok=True)

# Retrieve LST LSTE granule from CMR API for target date
L2T_LSTE_granule = download_ECOSTRESS_granule(
    product="L2T_LSTE",
    tile="11SPS",
    aquisition_date="2026-10-10",
    parent_directory=working_directory,
)

# Retrieve L2T STARS granule from CMR API as prior
L2T_STARS_granule = download_ECOSTRESS_granule(
    product="L2T_STARS",
    tile="11SPS",
    aquisition_date="2026-10-06",
    parent_directory=working_directory,
)

# Remove any stale runconfigs for tile 11SPS so a fresh run-config is generated
for stale_rc in glob(join(working_directory, "runconfig", "ECOv003_L2T_STARS_11SPS_*.xml")):
    remove(stale_rc)

# Generate XML run-config file for L2T STARS PGE run
runconfig_filename = generate_L2T_STARS_runconfig(
    L2T_LSTE_filename=L2T_LSTE_granule.product_filename,
    prior_L2T_STARS_filename=L2T_STARS_granule.product_filename,
    working_directory=working_directory,
)

print("Runconfig generated:", runconfig_filename)

# Run the full L2T STARS PGE pipeline (default Rust backend)
exit_code = L2T_STARS(
    runconfig_filename=runconfig_filename,
    backend="rust",
    threads=1,
    num_workers=8,
    remove_input_staging=False,
    remove_prior=False,
    remove_posterior=False,
    overwrite=True,
)

print("L2T STARS PGE exit code:", exit_code)

# Compare the locally generated product against test_bundle/reference_outputs/
LAYER_TO_REF_FILE = {
    "NDVI": "STARS_NDVI_2026-10-10_11SPS_70m.tif",
    "NDVI-UQ": "STARS_NDVI.UQ_2026-10-10_11SPS_70m.tif",
    "NDVI-flag": "STARS_NDVI.flag_2026-10-10_11SPS_70m.tif",
    "NDVI-bias": "STARS_NDVI.bias_2026-10-10_11SPS_70m.tif",
    "NDVI-bias-UQ": "STARS_NDVI.bias.UQ_2026-10-10_11SPS_70m.tif",
    "albedo": "STARS_albedo_2026-10-10_11SPS_70m.tif",
    "albedo-UQ": "STARS_albedo.UQ_2026-10-10_11SPS_70m.tif",
    "albedo-flag": "STARS_albedo.flag_2026-10-10_11SPS_70m.tif",
    "albedo-bias": "STARS_albedo.bias_2026-10-10_11SPS_70m.tif",
    "albedo-bias-UQ": "STARS_albedo.bias.UQ_2026-10-10_11SPS_70m.tif",
}


def compare_variable(local: np.ndarray, expected: np.ndarray) -> str:
    if local.shape != expected.shape:
        return f"shape mismatch: local {local.shape}, expected {expected.shape}"

    local = local.astype(np.float64)
    expected = expected.astype(np.float64)
    local_nan = ~np.isfinite(local)
    expected_nan = ~np.isfinite(expected)
    valid = ~(local_nan | expected_nan)
    nan_disagreement = int(np.count_nonzero(local_nan != expected_nan))

    if not valid.any():
        return f"no jointly valid pixels (NaN-mask disagreements: {nan_disagreement})"

    a = local[valid]
    b = expected[valid]
    diff = a - b
    identical = 100 * np.mean(a == b)
    corr = np.corrcoef(a, b)[0, 1] if a.std() > 0 and b.std() > 0 else np.nan

    return (
        f"n={a.size}  NaN-mask disagreements={nan_disagreement}  identical={identical:.2f}%\n"
        f"    mean local={a.mean():.6f}  mean reference={b.mean():.6f}  bias={diff.mean():.6e}\n"
        f"    MAE={np.abs(diff).mean():.6e}  RMSE={np.sqrt((diff ** 2).mean()):.6e}  "
        f"max|diff|={np.abs(diff).max():.6e}  r={corr:.6f}"
    )


if exit_code == 0:
    runconfig = L2TSTARSConfig(runconfig_filename)
    local_granule = open_granule(runconfig.L2T_STARS_zip_filename)

    print("\nLocal (Rust) vs embedded reference_outputs L2T STARS comparison")
    print(f"  local:     {runconfig.L2T_STARS_zip_filename}")
    print(f"  reference: {REF_DIR}")

    for variable, ref_filename in LAYER_TO_REF_FILE.items():
        print(f"\n{variable}")
        try:
            local_data = np.array(local_granule.variable(variable))
            with rasterio.open(join(REF_DIR, ref_filename)) as src:
                expected_data = src.read(1)
            print("  " + compare_variable(local_data, expected_data))
        except Exception as e:
            print(f"  could not compare: {e}")
else:
    print("L2T STARS PGE did not succeed; skipping comparison")