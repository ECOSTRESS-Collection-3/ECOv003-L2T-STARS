import sys
import types
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


def _ensure_stub_modules():
    try:
        import ECOv003_exit_codes  # noqa: F401
    except ImportError:
        exit_codes = types.ModuleType("ECOv003_exit_codes")

        class ECOSTRESSExitCodeException(Exception):
            exit_code = 1

        class BlankOutput(ECOSTRESSExitCodeException):
            exit_code = 17

        exit_codes.ECOSTRESSExitCodeException = ECOSTRESSExitCodeException
        exit_codes.BlankOutput = BlankOutput
        sys.modules["ECOv003_exit_codes"] = exit_codes

    for module_name in [
        "harmonized_landsat_sentinel",
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
    ]:
        if module_name not in sys.modules:
            sys.modules[module_name] = Mock()


_ensure_stub_modules()

from ECOv003_exit_codes import BlankOutput
from ECOv003_L2T_STARS.prior import Prior
from ECOv003_L2T_STARS.process_STARS_product import process_STARS_product


def _invoke_process(tmp_path):
    return process_STARS_product(
        tile="07KCA",
        date_UTC=date(2026, 8, 26),
        time_UTC=datetime(2026, 8, 26, 18, 0, 0),
        build="0700",
        product_counter=1,
        HLS_start_date=date(2026, 8, 19),
        HLS_end_date=date(2026, 8, 26),
        VIIRS_start_date=date(2026, 8, 19),
        VIIRS_end_date=date(2026, 8, 26),
        NDVI_resolution=490,
        albedo_resolution=980,
        target_resolution=70,
        downsampled_directory=str(tmp_path / "downsampled"),
        model_directory=str(tmp_path / "model"),
        input_staging_directory=str(tmp_path / "staging"),
        L2T_STARS_granule_directory=str(tmp_path / "granule"),
        L2T_STARS_zip_filename=str(tmp_path / "granule.zip"),
        L2T_STARS_browse_filename=str(tmp_path / "granule.png"),
        metadata={"StandardMetadata": {}},
        prior=Prior(using_prior=False),
        HLS_connection=Mock(),
        NDVI_VCD43NRT_connection=Mock(),
        albedo_VCD43NRT_connection=Mock(),
        using_prior=False,
    )


@patch("ECOv003_L2T_STARS.process_STARS_product.Raster.open")
@patch("ECOv003_L2T_STARS.process_STARS_product.process_julia_data_fusion")
@patch("ECOv003_L2T_STARS.process_STARS_product.generate_STARS_inputs")
def test_raises_blank_output_when_ndvi_posterior_missing(_mock_inputs, _mock_fusion, mock_raster_open, tmp_path):
    with pytest.raises(BlankOutput, match="Posterior NDVI raster file not found") as exc_info:
        _invoke_process(tmp_path)

    assert exc_info.value.exit_code == 17
    mock_raster_open.assert_not_called()


@patch("ECOv003_L2T_STARS.process_STARS_product.Raster.open")
@patch("ECOv003_L2T_STARS.process_STARS_product.process_julia_data_fusion")
@patch("ECOv003_L2T_STARS.process_STARS_product.generate_STARS_inputs")
def test_raises_blank_output_when_albedo_posterior_missing(_mock_inputs, mock_fusion, mock_raster_open, tmp_path):
    def create_only_ndvi_posteriors(**kwargs):
        if kwargs["product_name"] == "NDVI":
            for key in (
                "posterior_filename",
                "posterior_UQ_filename",
                "posterior_flag_filename",
                "posterior_bias_filename",
                "posterior_bias_UQ_filename",
            ):
                p = Path(kwargs[key])
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()

    mock_fusion.side_effect = create_only_ndvi_posteriors
    mock_raster_open.return_value = Mock()

    with pytest.raises(BlankOutput, match="Posterior albedo raster file not found") as exc_info:
        _invoke_process(tmp_path)

    assert exc_info.value.exit_code == 17
    # Raster.open should only have been called for the 5 NDVI files, never for albedo
    assert mock_raster_open.call_count == 5
