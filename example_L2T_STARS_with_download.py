import logging
from os.path import join, expanduser
from os import makedirs

import numpy as np

from ECOv003_CMR import download_ECOSTRESS_granule
from ECOv003_granules import open_granule
from ECOv003_L2T_STARS import generate_L2T_STARS_runconfig, L2T_STARS
from ECOv003_L2T_STARS.L2TSTARSConfig import L2TSTARSConfig

# Disable logger output
logging.getLogger().handlers = []

# Set working directory
working_directory = expanduser(join("~", "data", "ECOv003_testing"))
makedirs(working_directory, exist_ok=True)

# Retrieve LST LSTE granule from CMR API for target date
L2T_LSTE_granule = download_ECOSTRESS_granule(
    product="L2T_LSTE",
    tile="11SPS",
    aquisition_date="2026-10-10",
    parent_directory=working_directory
)

# Retrieve L2T STARS granule from CMR API as prior
L2T_STARS_granule = download_ECOSTRESS_granule(
    product="L2T_STARS",
    tile="11SPS",
    aquisition_date="2026-10-06",
    parent_directory=working_directory
)

# Retrieve the published L2T STARS granule for the target date to compare against
L2T_STARS_expected_output = download_ECOSTRESS_granule(
    product="L2T_STARS",
    tile="11SPS",
    aquisition_date="2026-10-10",
    parent_directory=working_directory
)

# Generate XML run-config file for L2T STARS PGE run
runconfig_filename = generate_L2T_STARS_runconfig(
    L2T_LSTE_filename=L2T_LSTE_granule.product_filename,
    prior_L2T_STARS_filename=L2T_STARS_granule.product_filename,
    working_directory=working_directory
)

print("Runconfig generated:", runconfig_filename)

# Run L2T STARS PGE
exit_code = L2T_STARS(
    runconfig_filename=runconfig_filename,
    threads=1,
    num_workers=8,
    remove_input_staging=False,
    remove_prior=False,
    remove_posterior=False,
    overwrite=True
)

print("L2T STARS PGE exit code:", exit_code)

# Compare the locally generated product against the downloaded product
COMPARISON_VARIABLES = [
    f"{layer}{suffix}"
    for layer in ("NDVI", "albedo")
    for suffix in ("", "-UQ", "-flag", "-bias", "-bias-UQ")
]


def compare_variable(local: np.ndarray, downloaded: np.ndarray) -> str:
    if local.shape != downloaded.shape:
        return f"shape mismatch: local {local.shape}, downloaded {downloaded.shape}"

    local = local.astype(np.float64)
    downloaded = downloaded.astype(np.float64)
    local_nan = ~np.isfinite(local)
    downloaded_nan = ~np.isfinite(downloaded)
    valid = ~(local_nan | downloaded_nan)
    nan_disagreement = int(np.count_nonzero(local_nan != downloaded_nan))

    if not valid.any():
        return f"no jointly valid pixels (NaN-mask disagreements: {nan_disagreement})"

    a = local[valid]
    b = downloaded[valid]
    diff = a - b
    identical = 100 * np.mean(a == b)
    corr = np.corrcoef(a, b)[0, 1] if a.std() > 0 and b.std() > 0 else np.nan

    return (
        f"n={a.size}  NaN-mask disagreements={nan_disagreement}  identical={identical:.2f}%\n"
        f"    mean local={a.mean():.6f}  mean downloaded={b.mean():.6f}  bias={diff.mean():.6f}\n"
        f"    MAE={np.abs(diff).mean():.6f}  RMSE={np.sqrt((diff ** 2).mean()):.6f}  "
        f"max|diff|={np.abs(diff).max():.6f}  r={corr:.6f}"
    )


if exit_code == 0:
    runconfig = L2TSTARSConfig(runconfig_filename)
    local_granule = open_granule(runconfig.L2T_STARS_zip_filename)
    downloaded_granule = open_granule(L2T_STARS_expected_output.product_filename)

    print("\nLocal vs downloaded L2T STARS comparison")
    print(f"  local:      {runconfig.L2T_STARS_zip_filename}")
    print(f"  downloaded: {L2T_STARS_expected_output.product_filename}")

    for variable in COMPARISON_VARIABLES:
        print(f"\n{variable}")
        try:
            local_data = np.array(local_granule.variable(variable))
            downloaded_data = np.array(downloaded_granule.variable(variable))
            print("  " + compare_variable(local_data, downloaded_data))
        except Exception as e:
            print(f"  could not compare: {e}")
else:
    print("L2T STARS PGE did not succeed; skipping comparison")
