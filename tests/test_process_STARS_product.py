import importlib
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


def _ensure_dependencies():
    if isinstance(sys.modules.get("ECOv003_exit_codes"), Mock):
        del sys.modules["ECOv003_exit_codes"]
    import ECOv003_exit_codes  # noqa: F401

    if isinstance(sys.modules.get("VCD43NRT"), Mock):
        del sys.modules["VCD43NRT"]
        sys.modules.pop("VCD43NRT.exceptions", None)
    import VCD43NRT  # noqa: F401

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


_ensure_dependencies()

from ECOv003_exit_codes import BlankOutput
from ECOv003_L2T_STARS.prior import Prior
import ECOv003_L2T_STARS.process_STARS_product as proc_mod

importlib.reload(proc_mod)
process_STARS_product = proc_mod.process_STARS_product


def _invoke_process(
    tmp_path,
    backend: str = "rust",
    granule_id: str = "ECOv003_L2T_STARS_00001_001_07KCA_20260826T180000_0700_01",
    remove_posterior: bool = True,
):
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
        L2T_STARS_granule_directory=str(tmp_path / granule_id),
        L2T_STARS_zip_filename=str(tmp_path / f"{granule_id}.zip"),
        L2T_STARS_browse_filename=str(tmp_path / f"{granule_id}.png"),
        metadata={"StandardMetadata": {}},
        prior=Prior(using_prior=False),
        HLS_connection=Mock(),
        NDVI_VCD43NRT_connection=Mock(),
        albedo_VCD43NRT_connection=Mock(),
        using_prior=False,
        remove_posterior=remove_posterior,
        backend=backend,
    )


def test_rejects_unsupported_backend(tmp_path):
    with pytest.raises(ValueError, match="Unsupported STARS fusion backend"):
        _invoke_process(tmp_path, backend="invalid")


@patch("ECOv003_L2T_STARS.process_STARS_product.Raster.open")
@patch("ECOv003_L2T_STARS.process_STARS_product.process_rust_data_fusion")
@patch("ECOv003_L2T_STARS.process_STARS_product.generate_STARS_inputs")
def test_defaults_to_rust_backend_and_raises_blank_output_when_missing(
    _mock_inputs, mock_rust_fusion, mock_raster_open, tmp_path
):
    with pytest.raises(BlankOutput, match="Posterior NDVI raster file not found") as exc_info:
        _invoke_process(tmp_path)

    assert exc_info.value.exit_code == 17
    mock_rust_fusion.assert_called_once()
    mock_raster_open.assert_not_called()


@patch("ECOv003_L2T_STARS.process_STARS_product.Raster.open")
@patch("ECOv003_L2T_STARS.process_julia_data_fusion.process_julia_data_fusion")
@patch("ECOv003_L2T_STARS.process_STARS_product.generate_STARS_inputs")
def test_raises_blank_output_when_ndvi_posterior_missing(_mock_inputs, _mock_fusion, mock_raster_open, tmp_path):
    with pytest.raises(BlankOutput, match="Posterior NDVI raster file not found") as exc_info:
        _invoke_process(tmp_path, backend="julia")

    assert exc_info.value.exit_code == 17
    mock_raster_open.assert_not_called()


@patch("ECOv003_L2T_STARS.process_STARS_product.Raster.open")
@patch("ECOv003_L2T_STARS.process_julia_data_fusion.process_julia_data_fusion")
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
        _invoke_process(tmp_path, backend="julia")

    assert exc_info.value.exit_code == 17
    assert mock_raster_open.call_count == 5


@patch("ECOv003_L2T_STARS.process_STARS_product.L2TSTARS")
@patch("ECOv003_L2T_STARS.process_STARS_product.Raster.open")
@patch("ECOv003_L2T_STARS.process_STARS_product.process_rust_data_fusion")
@patch("ECOv003_L2T_STARS.process_STARS_product.generate_STARS_inputs")
def test_posterior_directory_isolated_per_granule_for_concurrent_scenes(
    _mock_inputs, mock_rust_fusion, mock_raster_open, mock_l2t_stars_cls, tmp_path
):
    """Issue #94: Concurrent runs on the same (tile, date_UTC) must isolate posterior paths by granule_ID."""
    granule_a = "ECOv003_L2T_STARS_00001_001_07KCA_20260826T180000_0700_01"
    granule_b = "ECOv003_L2T_STARS_00002_004_07KCA_20260826T193000_0700_01"
    seen_dirs = []

    def create_posteriors(**kwargs):
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
        seen_dirs.append(Path(kwargs["posterior_filename"]).parent)

    mock_rust_fusion.side_effect = create_posteriors
    mock_raster_open.return_value = Mock()

    def make_granule(**kwargs):
        Path(kwargs["product_location"]).mkdir(parents=True, exist_ok=True)
        g = Mock()
        def write_browse(PNG_filename):
            Path(PNG_filename).touch()
        g.write_browse_image.side_effect = write_browse
        return g

    mock_l2t_stars_cls.side_effect = make_granule

    _invoke_process(tmp_path, granule_id=granule_a, remove_posterior=True)
    _invoke_process(tmp_path, granule_id=granule_b, remove_posterior=True)

    assert len(seen_dirs) == 4
    assert seen_dirs[0].name == granule_a
    assert seen_dirs[2].name == granule_b
    assert seen_dirs[0] != seen_dirs[2]
