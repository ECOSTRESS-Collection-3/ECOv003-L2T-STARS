import importlib
import logging
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch


def _ensure_dependencies():
    for real_mod in ("ECOv003_exit_codes", "harmonized_landsat_sentinel"):
        if isinstance(sys.modules.get(real_mod), Mock):
            del sys.modules[real_mod]

    import ECOv003_exit_codes  # noqa: F401
    import harmonized_landsat_sentinel  # noqa: F401

    for module_name in [
        "ECOv002_CMR",
        "ECOv002_granules",
        "ECOv003_granules",
        "GEOS5FP",
        "modland",
        "sentinel_tiles",
        "earthaccess",
        "colored_logging",
        "untangle",
        "VCD43NRT",
        "VCD43NRT.exceptions",
    ]:
        if module_name not in sys.modules:
            sys.modules[module_name] = Mock()


_ensure_dependencies()

from ECOv003_exit_codes import LAND_FILTER

importlib.import_module("ECOv003_L2T_STARS.L2T_STARS")
l2t_mod = importlib.reload(sys.modules["ECOv003_L2T_STARS.L2T_STARS"])


def test_land_filter_logs_info_without_error_records(tmp_path: Path):
    """Issue #2: Non-land tiles return LAND_FILTER without logging ERROR tracebacks."""
    rc = Mock()
    rc.working_directory = str(tmp_path / "work")
    rc.granule_ID = "ECOv003_L2T_STARS_00001_001_55TFM_20260826T180000_0700_01"
    rc.L2T_STARS_granule_directory = str(tmp_path / "output" / rc.granule_ID)
    rc.L2T_STARS_zip_filename = f"{rc.L2T_STARS_granule_directory}.zip"
    rc.L2T_STARS_browse_filename = f"{rc.L2T_STARS_granule_directory}.png"
    rc.sources_directory = str(tmp_path / "sources")
    rc.indices_directory = str(tmp_path / "indices")
    rc.model_directory = str(tmp_path / "model")
    rc.output_directory = str(tmp_path / "output")
    rc.tile = "55TFM"
    rc.build = "0700"
    rc.product_counter = 1
    lste_path = tmp_path / "ECOv003_L2T_LSTE_00001_001_55TFM_20260826T180000_0700_01.zip"
    lste_path.touch()
    rc.L2T_LSTE_filename = str(lste_path)
    rc.L2T_STARS_prior_filename = None

    granule = Mock()
    granule.tile = "55TFM"
    granule.time_UTC = datetime(2026, 8, 26, 18, 0, 0)
    granule.date_UTC = granule.time_UTC.date()
    granule.geometry = Mock()
    granule.metadata_dict = {"StandardMetadata": {}, "ProductMetadata": {}}

    with (
        patch.object(l2t_mod, "L2TSTARSConfig", return_value=rc),
        patch.object(l2t_mod, "L2TLSTE", return_value=granule),
        patch.object(l2t_mod, "HLS2Connection"),
        patch.object(l2t_mod.sentinel_tiles, "land", return_value=False),
    ):
        exit_code = l2t_mod.L2T_STARS(runconfig_filename="dummy.xml")

    assert exit_code == LAND_FILTER
    log_text = (Path(rc.working_directory) / "log" / f"{rc.granule_ID}.log").read_text()
    assert "ERROR" not in log_text
    assert "WARNING" not in log_text
    assert "INFO] Sentinel tile 55TFM is not on land. Skipping processing." in log_text