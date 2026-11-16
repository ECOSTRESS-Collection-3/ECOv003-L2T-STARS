import sys
import types
from datetime import date, datetime, timedelta, timezone
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

        class AuxiliaryLatency(ECOSTRESSExitCodeException):
            exit_code = 15

        class DownloadFailed(ECOSTRESSExitCodeException):
            exit_code = 16

        exit_codes.ECOSTRESSExitCodeException = ECOSTRESSExitCodeException
        exit_codes.AuxiliaryLatency = AuxiliaryLatency
        exit_codes.DownloadFailed = DownloadFailed
        sys.modules["ECOv003_exit_codes"] = exit_codes

    try:
        import VCD43NRT.exceptions  # noqa: F401
    except ImportError:
        vcd_pkg = sys.modules.setdefault("VCD43NRT", types.ModuleType("VCD43NRT"))
        vcd_pkg.VCD43NRT = Mock()
        vcd_exc = types.ModuleType("VCD43NRT.exceptions")

        class CMRServerUnreachable(Exception):
            pass

        vcd_exc.CMRServerUnreachable = CMRServerUnreachable
        vcd_pkg.exceptions = vcd_exc
        sys.modules["VCD43NRT.exceptions"] = vcd_exc

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
    ]:
        if module_name not in sys.modules:
            sys.modules[module_name] = Mock()


_ensure_stub_modules()

from ECOv003_exit_codes import AuxiliaryLatency, DownloadFailed
from VCD43NRT.exceptions import CMRServerUnreachable as VCD43NRTCMRServerUnreachable
from ECOv003_L2T_STARS.generate_STARS_inputs import generate_STARS_inputs


class FakeRaster:
    def to_geotiff(self, filename: str):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).touch()


def _run_generate(tmp_path, start_date: date, end_date: date):
    return generate_STARS_inputs(
        tile="07KCA",
        date_UTC=end_date,
        HLS_start_date=end_date,
        HLS_end_date=end_date,
        VIIRS_start_date=start_date,
        VIIRS_end_date=end_date,
        NDVI_resolution=490,
        albedo_resolution=980,
        target_resolution=70,
        NDVI_coarse_geometry=Mock(),
        albedo_coarse_geometry=Mock(),
        downsampled_directory=str(tmp_path),
        HLS_connection=Mock(),
        NDVI_VCD43NRT_connection=Mock(),
        albedo_VCD43NRT_connection=Mock(),
        calibrate_fine=False,
    )


@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
def test_cmr_server_unreachable_propagates_immediately(mock_ndvi, mock_albedo, tmp_path):
    mock_ndvi.side_effect = VCD43NRTCMRServerUnreachable("CMR offline")

    with pytest.raises(VCD43NRTCMRServerUnreachable):
        _run_generate(tmp_path, date(2026, 8, 19), date(2026, 8, 26))

    assert mock_ndvi.call_count == 1
    assert mock_albedo.call_count == 0


@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
def test_raises_auxiliary_latency_within_giveup_days(mock_ndvi, mock_albedo, tmp_path):
    today = datetime.now(timezone.utc).date()
    mock_ndvi.side_effect = RuntimeError("not published yet")
    mock_albedo.side_effect = RuntimeError("not published yet")

    with pytest.raises(AuxiliaryLatency) as exc_info:
        _run_generate(tmp_path, today - timedelta(days=2), today)

    assert exc_info.value.exit_code == 15


@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
def test_raises_download_failed_when_zero_coarse_inputs_outside_giveup_days(mock_ndvi, mock_albedo, tmp_path):
    mock_ndvi.side_effect = RuntimeError("VCD43NRT failed")
    mock_albedo.side_effect = RuntimeError("VCD43NRT failed")

    with pytest.raises(DownloadFailed) as exc_info:
        _run_generate(tmp_path, date(2026, 8, 19), date(2026, 8, 26))

    assert exc_info.value.exit_code == 16


@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_fine_image", side_effect=RuntimeError("no HLS"))
@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_fine_image", side_effect=RuntimeError("no HLS"))
@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
@patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
def test_succeeds_when_at_least_one_coarse_ndvi_and_albedo_exist(
    mock_ndvi, mock_albedo, _mock_ndvi_fine, _mock_albedo_fine, tmp_path
):
    target_date = date(2026, 8, 26)
    mock_ndvi.side_effect = lambda date_UTC, **_: FakeRaster() if date_UTC == target_date else (_ for _ in ()).throw(RuntimeError("cloudy"))
    mock_albedo.side_effect = lambda date_UTC, **_: FakeRaster() if date_UTC == target_date else (_ for _ in ()).throw(RuntimeError("cloudy"))

    _run_generate(tmp_path, date(2026, 8, 24), target_date)
