import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_BUNDLE = REPO_ROOT / "test_bundle"


def test_test_bundle_manifest_and_files_exist():
    manifest_path = TEST_BUNDLE / "manifest.json"
    if not manifest_path.exists():
        pytest.skip("test_bundle/manifest.json not present")

    manifest = json.loads(manifest_path.read_text())
    assert manifest["tile"] == "11SPS"
    assert manifest["target_date"] == "2026-10-10"
    for rel_path in manifest["files"]:
        assert (TEST_BUNDLE / rel_path).exists(), f"Missing bundle file: {rel_path}"


@pytest.mark.skipif(
    os.environ.get("RUN_FULL_PGE_TEST") != "1" or shutil.which("julia") is None or not TEST_BUNDLE.exists(),
    reason="set RUN_FULL_PGE_TEST=1 with julia and test_bundle present to run offline end-to-end PGE test",
)
def test_l2t_stars_offline_bundle_end_to_end(tmp_path: Path):
    from ECOv003_exit_codes import SUCCESS_EXIT_CODE
    from ECOv003_granules import open_granule
    from ECOv003_L2T_STARS import L2T_STARS, generate_L2T_STARS_runconfig
    from ECOv003_L2T_STARS.L2TSTARSConfig import L2TSTARSConfig
    import ECOv003_L2T_STARS.L2T_STARS as l2t_mod

    work_dir = tmp_path / "work"
    sources_dir = work_dir / "L2T_STARS_SOURCES"
    shutil.copytree(
        TEST_BUNDLE / "inputs" / "DOWNSAMPLED_products",
        sources_dir / "VCD43NRT_DOWNSAMPLED_products",
    )

    lste_path = TEST_BUNDLE / "inputs" / "ECOv003_L2T_LSTE_46862_004_11SPS_20261010T142849_01"
    prior_path = TEST_BUNDLE / "inputs" / "ECOv003_L2T_STARS_11SPS_20261006_01"
    expected_path = TEST_BUNDLE / "ECOv003_L2T_STARS_11SPS_20261010_01"

    runconfig_filename = generate_L2T_STARS_runconfig(
        L2T_LSTE_filename=str(lste_path),
        prior_L2T_STARS_filename=str(prior_path),
        working_directory=str(work_dir),
        sources_directory=str(sources_dir),
    )

    with (
        patch.object(l2t_mod, "HLS2Connection") as mock_hls_cls,
        patch.object(l2t_mod, "VCD43NRT"),
    ):
        mock_hls_cls.return_value.listing.return_value = pd.DataFrame(
            columns=["date_UTC", "sentinel", "landsat"]
        )
        exit_code = L2T_STARS(
            runconfig_filename=runconfig_filename,
            threads=1,
            num_workers=4,
            overwrite=True,
        )

    assert exit_code == SUCCESS_EXIT_CODE
    rc = L2TSTARSConfig(runconfig_filename)
    local_granule = open_granule(rc.L2T_STARS_zip_filename)
    expected_granule = open_granule(str(expected_path))

    for layer in ("NDVI", "NDVI-UQ", "NDVI-flag", "NDVI-bias", "NDVI-bias-UQ", "albedo", "albedo-UQ", "albedo-flag", "albedo-bias", "albedo-bias-UQ"):
        a = np.array(local_granule.variable(layer), dtype=np.float64)
        b = np.array(expected_granule.variable(layer), dtype=np.float64)
        valid = np.isfinite(a) & np.isfinite(b)
        rmse = float(np.sqrt(np.mean((a[valid] - b[valid]) ** 2)))
        assert rmse < 1e-4, f"RMSE mismatch for {layer}: {rmse}"
