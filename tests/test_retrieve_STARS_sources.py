import importlib
import sys
from datetime import date
from unittest.mock import Mock

import pytest


def _ensure_dependencies():
    if isinstance(sys.modules.get("ECOv003_exit_codes"), Mock):
        del sys.modules["ECOv003_exit_codes"]
    import ECOv003_exit_codes  # noqa: F401

    if isinstance(sys.modules.get("VCD43NRT"), Mock):
        del sys.modules["VCD43NRT"]
        sys.modules.pop("VCD43NRT.exceptions", None)
    import VCD43NRT.exceptions  # noqa: F401

    if isinstance(sys.modules.get("harmonized_landsat_sentinel"), Mock):
        del sys.modules["harmonized_landsat_sentinel"]
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
    ]:
        if module_name not in sys.modules:
            sys.modules[module_name] = Mock()


_ensure_dependencies()

from ECOv003_exit_codes import DownloadFailed
from harmonized_landsat_sentinel import HLSDownloadFailed
from VCD43NRT.exceptions import (
    CMRServerUnreachable as VCD43NRTCMRServerUnreachable,
    DownloadFailed as VCD43NRTDownloadFailed,
    VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError,
)
import ECOv003_L2T_STARS.retrieve_STARS_sources as retrieve_mod

importlib.reload(retrieve_mod)
retrieve_STARS_sources = retrieve_mod.retrieve_STARS_sources


def test_viirs_unavailable_during_prefetch_is_deferred():
    vcd = Mock()
    vcd.prefetch_VNP09GA.side_effect = VCD43NRTVIIRSUnavailableError("no VIIRS granules")

    retrieve_STARS_sources(
        tile="07KCA",
        geometry=Mock(),
        HLS_start_date=date(2026, 8, 26),
        HLS_end_date=date(2026, 8, 26),
        VIIRS_start_date=date(2026, 8, 3),
        VIIRS_end_date=date(2026, 8, 26),
        HLS_connection=Mock(),
        VCD43NRT_connection=vcd,
    )

    vcd.prefetch_VNP09GA.assert_called_once()


@pytest.mark.parametrize(
    "exc",
    [
        VCD43NRTCMRServerUnreachable("CMR offline"),
        VCD43NRTDownloadFailed("transfer failed"),
    ],
)
def test_critical_prefetch_errors_propagate(exc):
    vcd = Mock()
    vcd.prefetch_VNP09GA.side_effect = exc

    with pytest.raises(type(exc)):
        retrieve_STARS_sources(
            tile="07KCA",
            geometry=Mock(),
            HLS_start_date=date(2026, 8, 26),
            HLS_end_date=date(2026, 8, 26),
            VIIRS_start_date=date(2026, 8, 3),
            VIIRS_end_date=date(2026, 8, 26),
            HLS_connection=Mock(),
            VCD43NRT_connection=vcd,
        )


def test_hls_download_failed_raises_download_failed():
    hls = Mock()
    hls.sentinel.side_effect = HLSDownloadFailed("HLS transfer failed")
    vcd = Mock()

    with pytest.raises(DownloadFailed) as exc_info:
        retrieve_STARS_sources(
            tile="07KCA",
            geometry=Mock(),
            HLS_start_date=date(2026, 8, 26),
            HLS_end_date=date(2026, 8, 26),
            VIIRS_start_date=date(2026, 8, 3),
            VIIRS_end_date=date(2026, 8, 26),
            HLS_connection=hls,
            VCD43NRT_connection=vcd,
        )

    assert exc_info.value.exit_code == 16
    vcd.prefetch_VNP09GA.assert_not_called()