import importlib
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest


def _ensure_dependencies():
    for real_mod in (
        "ECOv003_exit_codes",
        "VCD43NRT",
        "VCD43NRT.exceptions",
        "harmonized_landsat_sentinel",
    ):
        if isinstance(sys.modules.get(real_mod), Mock):
            del sys.modules[real_mod]

    import ECOv003_exit_codes  # noqa: F401
    import VCD43NRT  # noqa: F401
    import VCD43NRT.exceptions  # noqa: F401
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

from ECOv003_exit_codes import (
    AUXILIARY_LATENCY,
    DOWNLOAD_FAILED,
    AuxiliaryLatency,
    DownloadFailed,
)
from VCD43NRT.exceptions import (
    AuxiliaryDownloadFailed as VCD43NRTAuxiliaryDownloadFailed,
    CMRServerUnreachable as VCD43NRTCMRServerUnreachable,
)

importlib.import_module("ECOv003_L2T_STARS.generate_STARS_inputs")
importlib.import_module("ECOv003_L2T_STARS.L2T_STARS")

gen_mod = importlib.reload(sys.modules["ECOv003_L2T_STARS.generate_STARS_inputs"])
l2t_mod = importlib.reload(sys.modules["ECOv003_L2T_STARS.L2T_STARS"])


class FakeRaster:
    def to_geotiff(self, filename: str, **kwargs):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"II*\x00")


def _run_generate_inputs(tmp_path: Path, start_date: date, end_date: date, tile: str = "07KCA"):
    return gen_mod.generate_STARS_inputs(
        tile=tile,
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
        downsampled_directory=str(tmp_path / "downsampled"),
        HLS_connection=Mock(),
        NDVI_VCD43NRT_connection=Mock(),
        albedo_VCD43NRT_connection=Mock(),
        calibrate_fine=False,
    )


def _mock_l2t_lste_granule(tile: str = "07KCA", dt: datetime = datetime(2026, 8, 26, 18, 0, 0)):
    granule = Mock()
    granule.tile = tile
    granule.time_UTC = dt
    granule.date_UTC = dt.date()
    granule.geometry = Mock()
    granule.metadata_dict = {
        "StandardMetadata": {},
        "ProductMetadata": {"AuxiliaryNWP": "GEOS5FP", "NWPSource": "GEOS5FP"},
    }
    return granule


def _mock_runconfig(tmp_path: Path, tile: str = "07KCA"):
    rc = Mock()
    rc.working_directory = str(tmp_path / "work")
    rc.granule_ID = f"ECOv003_L2T_STARS_00001_001_{tile}_20260826T180000_0700_01"
    rc.L2T_STARS_granule_directory = str(tmp_path / "output" / rc.granule_ID)
    rc.L2T_STARS_zip_filename = f"{rc.L2T_STARS_granule_directory}.zip"
    rc.L2T_STARS_browse_filename = f"{rc.L2T_STARS_granule_directory}.png"
    rc.sources_directory = str(tmp_path / "sources")
    rc.indices_directory = str(tmp_path / "indices")
    rc.model_directory = str(tmp_path / "model")
    rc.output_directory = str(tmp_path / "output")
    rc.tile = tile
    rc.build = "0700"
    rc.product_counter = 1
    lste_path = tmp_path / f"ECOv003_L2T_LSTE_00001_001_{tile}_20260826T180000_0700_01.zip"
    lste_path.touch()
    rc.L2T_LSTE_filename = str(lste_path)
    rc.L2T_STARS_prior_filename = None
    return rc


class TestGEOS5FPIntegration:
    def test_l2t_stars_wires_geos5fp_download_directory(self, tmp_path):
        """Verify L2T_STARS passes GEOS5FP_download under sources_directory to VCD43NRT."""
        rc = _mock_runconfig(tmp_path, tile="07KCA")

        with (
            patch.object(l2t_mod, "L2TSTARSConfig", return_value=rc),
            patch.object(l2t_mod, "L2TLSTE", return_value=_mock_l2t_lste_granule("07KCA")),
            patch.object(l2t_mod, "HLS2Connection"),
            patch.object(l2t_mod.sentinel_tiles, "land", return_value=True),
            patch.object(l2t_mod, "VCD43NRT") as mock_vcd_cls,
        ):
            mock_vcd_cls.side_effect = VCD43NRTCMRServerUnreachable("stop after init")
            l2t_mod.L2T_STARS(runconfig_filename="dummy.xml")

        kwargs = mock_vcd_cls.call_args.kwargs
        assert kwargs["GEOS5FP_download"].endswith("GEOS5FP_download")

    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
    def test_geos5fp_aot_outage_on_historical_window_raises_download_failed_16(
        self, mock_ndvi, mock_albedo, tmp_path
    ):
        """
        Issue #1 + #37-#87: When portal.nccs.nasa.gov fails AOT retrieval across all
        historical dates (> VIIRS_GIVEUP_DAYS), generate_STARS_inputs must fail fast with
        DownloadFailed (exit code 16) before invoking Julia data fusion.
        """
        mock_ndvi.side_effect = VCD43NRTAuxiliaryDownloadFailed(
            "unable to retrieve AOT from GEOS5-FP for VCD43NRT"
        )
        mock_albedo.side_effect = VCD43NRTAuxiliaryDownloadFailed(
            "unable to retrieve AOT from GEOS5-FP for VCD43NRT"
        )

        with pytest.raises(DownloadFailed) as exc_info:
            _run_generate_inputs(tmp_path, date(2026, 8, 19), date(2026, 8, 26))

        assert exc_info.value.exit_code == DOWNLOAD_FAILED

    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
    def test_geos5fp_aot_outage_within_giveup_days_raises_auxiliary_latency_15(
        self, mock_ndvi, mock_albedo, tmp_path
    ):
        """
        When GEOS-5 FP AOT retrieval fails on recent dates (<= VIIRS_GIVEUP_DAYS),
        generate_STARS_inputs must raise AuxiliaryLatency (exit code 15) for retry.
        """
        today = datetime.now(timezone.utc).date()
        mock_ndvi.side_effect = VCD43NRTAuxiliaryDownloadFailed(
            "unable to retrieve AOT from GEOS5-FP for VCD43NRT"
        )
        mock_albedo.side_effect = VCD43NRTAuxiliaryDownloadFailed(
            "unable to retrieve AOT from GEOS5-FP for VCD43NRT"
        )

        with pytest.raises(AuxiliaryLatency) as exc_info:
            _run_generate_inputs(tmp_path, today - timedelta(days=2), today)

        assert exc_info.value.exit_code == AUXILIARY_LATENCY

    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_fine_image", side_effect=RuntimeError("no HLS"))
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_fine_image", side_effect=RuntimeError("no HLS"))
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
    def test_partial_geos5fp_503_outage_succeeds_when_one_date_recovers(
        self, mock_ndvi, mock_albedo, _mock_ndvi_fine, _mock_albedo_fine, tmp_path
    ):
        """
        If portal.nccs.nasa.gov returns HTTP 503 / SSLEOFError on 7 of 8 days (> 4 days ago),
        but succeeds on 1 day, generate_STARS_inputs must succeed without raising.
        """
        target = date(2026, 8, 26)
        start = date(2026, 8, 19)

        mock_ndvi.side_effect = (
            lambda date_UTC, **_: FakeRaster()
            if date_UTC == target
            else (_ for _ in ()).throw(
                VCD43NRTAuxiliaryDownloadFailed("unable to retrieve AOT from GEOS5-FP for VCD43NRT")
            )
        )
        mock_albedo.side_effect = (
            lambda date_UTC, **_: FakeRaster()
            if date_UTC == target
            else (_ for _ in ()).throw(
                VCD43NRTAuxiliaryDownloadFailed("unable to retrieve AOT from GEOS5-FP for VCD43NRT")
            )
        )

        _run_generate_inputs(tmp_path, start, target)

    def test_l2t_stars_exits_with_download_failed_16_on_geos5fp_aot_failure(self, tmp_path):
        """
        End-to-end verification that L2T_STARS returns exit code 16 (DOWNLOAD_FAILED)
        instead of exit code 1 (UNCLASSIFIED_FAILURE) when GEOS5-FP AOT fails completely.
        """
        rc = _mock_runconfig(tmp_path, tile="07KCA")
        mock_hls = Mock()
        mock_hls.listing.return_value = pd.DataFrame(
            {"date_UTC": ["2026-08-26"], "sentinel": [None], "landsat": [None]}
        )

        with (
            patch.object(l2t_mod, "L2TSTARSConfig", return_value=rc),
            patch.object(l2t_mod, "L2TLSTE", return_value=_mock_l2t_lste_granule("07KCA")),
            patch.object(l2t_mod, "HLS2Connection", return_value=mock_hls),
            patch.object(l2t_mod.sentinel_tiles, "land", return_value=True),
            patch.object(l2t_mod, "VCD43NRT"),
            patch.object(
                l2t_mod,
                "process_STARS_product",
                side_effect=DownloadFailed("No coarse NDVI images available for tile 07KCA"),
            ),
        ):
            exit_code = l2t_mod.L2T_STARS(runconfig_filename="dummy.xml")

        assert exit_code == DOWNLOAD_FAILED
