import importlib
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from rasterio.errors import RasterioIOError


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
    AUXILIARY_SERVER_UNREACHABLE,
    DOWNLOAD_FAILED,
    AuxiliaryLatency,
    DownloadFailed,
)
from VCD43NRT.exceptions import (
    BRDFRetrievalFailed as VCD43NRTBRDFRetrievalFailed,
    CMRServerUnreachable as VCD43NRTCMRServerUnreachable,
    DownloadFailed as VCD43NRTDownloadFailed,
    VIIRSUnavailableError as VCD43NRTVIIRSUnavailableError,
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


class TestVCD43NRTConfiguration:
    def test_l2t_stars_initializes_vcd43nrt_with_staging_and_fallback(self, tmp_path):
        """
        Verify L2T_STARS passes VCD43NRT_staging_directory and fallback_mode=True
        to prevent multi-worker collisions on shared VCD43NRT_products/ (Issues #3-#27).
        """
        rc = _mock_runconfig(tmp_path, tile="07KCA")

        with (
            patch.object(l2t_mod, "L2TSTARSConfig", return_value=rc),
            patch.object(l2t_mod, "L2TLSTE", return_value=_mock_l2t_lste_granule("07KCA")),
            patch.object(l2t_mod, "HLS2Connection"),
            patch.object(l2t_mod.sentinel_tiles, "land", return_value=True),
            patch.object(l2t_mod, "VCD43NRT") as mock_vcd_cls,
        ):
            mock_vcd_cls.side_effect = VCD43NRTCMRServerUnreachable("stop after init")
            exit_code = l2t_mod.L2T_STARS(runconfig_filename="dummy.xml")

        assert exit_code == AUXILIARY_SERVER_UNREACHABLE
        kwargs = mock_vcd_cls.call_args.kwargs
        assert kwargs["VCD43NRT_staging_directory"].endswith("VCD43NRT_staging")
        assert kwargs["fallback_mode"] is True
        assert kwargs["mission_priority"] == ("SNPP", "JPSS1", "JPSS2")


class TestVCD43NRTResilienceAndExceptions:
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_fine_image", side_effect=RuntimeError("no HLS"))
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_fine_image", side_effect=RuntimeError("no HLS"))
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
    def test_tolerates_partial_granule_or_temp_cog_errors_when_other_dates_succeed(
        self, mock_ndvi, mock_albedo, _mock_ndvi_fine, _mock_albedo_fine, tmp_path
    ):
        """
        Verify transient RasterioIOError / FileNotFoundError (*.temp.tif) / OSError
        on individual days do not abort the window if at least one valid day succeeds.
        """
        day1 = date(2026, 8, 24)
        day2 = date(2026, 8, 25)
        day3 = date(2026, 8, 26)

        def ndvi_side_effect(date_UTC, **_):
            if date_UTC == day1:
                raise RasterioIOError("not recognized as being in a supported file format")
            if date_UTC == day2:
                raise FileNotFoundError("No such file or directory: '...NBAR_I1.temp.tif'")
            return FakeRaster()

        def albedo_side_effect(date_UTC, **_):
            if date_UTC == day1:
                raise OSError("raster file not found: '...NBAR_I1.tif'")
            return FakeRaster()

        mock_ndvi.side_effect = ndvi_side_effect
        mock_albedo.side_effect = albedo_side_effect

        _run_generate_inputs(tmp_path, day1, day3)

    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
    def test_brdf_and_viirs_unavailable_across_all_historical_dates_raises_download_failed(
        self, mock_ndvi, mock_albedo, tmp_path
    ):
        mock_ndvi.side_effect = VCD43NRTVIIRSUnavailableError("No VIIRS granules")
        mock_albedo.side_effect = VCD43NRTBRDFRetrievalFailed("Insufficient clear observations")

        with pytest.raises(DownloadFailed) as exc_info:
            _run_generate_inputs(tmp_path, date(2026, 8, 19), date(2026, 8, 26))

        assert exc_info.value.exit_code == DOWNLOAD_FAILED

    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image")
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image")
    def test_viirs_unavailable_within_giveup_days_raises_auxiliary_latency(
        self, mock_ndvi, mock_albedo, tmp_path
    ):
        today = datetime.now(timezone.utc).date()
        mock_ndvi.side_effect = VCD43NRTVIIRSUnavailableError("NRT latency")
        mock_albedo.side_effect = VCD43NRTVIIRSUnavailableError("NRT latency")

        with pytest.raises(AuxiliaryLatency) as exc_info:
            _run_generate_inputs(tmp_path, today - timedelta(days=1), today)

        assert exc_info.value.exit_code == AUXILIARY_LATENCY

    @pytest.mark.parametrize(
        "vcd_exc,expected_exit_code",
        [
            (VCD43NRTCMRServerUnreachable("CMR 500 Internal Server Error"), AUXILIARY_SERVER_UNREACHABLE),
            (VCD43NRTVIIRSUnavailableError("VIIRS granule not yet published"), AUXILIARY_LATENCY),
            (VCD43NRTDownloadFailed("VIIRS granule transfer failed"), DOWNLOAD_FAILED),
        ],
    )
    def test_l2t_stars_maps_vcd43nrt_exceptions_to_locked_exit_codes(
        self, tmp_path, vcd_exc, expected_exit_code
    ):
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
            patch.object(l2t_mod, "process_STARS_product", side_effect=vcd_exc),
        ):
            exit_code = l2t_mod.L2T_STARS(runconfig_filename="dummy.xml")

        assert exit_code == expected_exit_code
