import importlib
import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
from shapely.geometry import box


def _ensure_dependencies():
    for real_mod in ("ECOv003_exit_codes", "modland"):
        if isinstance(sys.modules.get(real_mod), Mock):
            del sys.modules[real_mod]

    import ECOv003_exit_codes  # noqa: F401

    try:
        import modland  # noqa: F401
    except ImportError:
        pass

    for module_name in [
        "harmonized_landsat_sentinel",
        "ECOv002_CMR",
        "ECOv002_granules",
        "ECOv003_granules",
        "GEOS5FP",
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

importlib.import_module("ECOv003_L2T_STARS.generate_STARS_inputs")
gen_mod = importlib.reload(sys.modules["ECOv003_L2T_STARS.generate_STARS_inputs"])


class FakeRaster:
    def to_geotiff(self, filename: str, **kwargs):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"II*\x00")


class TestModlandAntimeridianFix:
    def test_sinusoidal_matrices_no_affine_tuple_typeerror(self):
        """
        Issue #6: MODISLandTile.sinusoidal_matrices() previously executed
        `np.meshgrid(np.arange(self.columns), np.arange(self.rows)) * affine`,
        raising `TypeError: can't multiply sequence by non-int of type 'Affine'`.
        """
        modland_tile = pytest.importorskip("modland.MODIS_land_tile")
        tile = modland_tile.MODISLandTile(35, 10, 100, 100)

        x_matrix, y_matrix, lon, lat = tile.sinusoidal_matrices()

        assert isinstance(x_matrix, np.ndarray)
        assert isinstance(y_matrix, np.ndarray)
        assert x_matrix.shape == (100, 100)
        assert y_matrix.shape == (100, 100)
        assert np.isfinite(lon).any()
        assert np.isfinite(lat).any()

    @pytest.mark.parametrize(
        "h,v",
        [
            (35, 10),  # East antimeridian tile overlapping MGRS 56UNA (Fiji / Taveuni)
            (0, 10),   # West antimeridian tile
        ],
    )
    def test_outline_latlon_on_antimeridian_tiles(self, h: int, v: int):
        """Verify outline_latlon computes valid geometries for antimeridian MODLAND tiles."""
        outlines = pytest.importorskip("modland.outlines")
        polygon = outlines.outline_latlon(h, v)

        assert polygon is not None
        assert not polygon.is_empty

    def test_find_modland_tiles_for_tile_56una_footprint(self):
        """
        Verify find_modland_tiles resolves MODLAND tiles intersecting MGRS tile 56UNA
        (~179.4E to 180.0E, -17.2S to -16.2S) without raising TypeError.
        """
        find_modland = pytest.importorskip("modland.find_modland_tiles")
        footprint_56una = box(179.4, -17.2, 180.0, -16.2)

        tiles = sorted(find_modland.find_modland_tiles(footprint_56una))

        assert len(tiles) >= 1
        assert "h35v10" in tiles

    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_fine_image", side_effect=RuntimeError("no HLS"))
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_fine_image", side_effect=RuntimeError("no HLS"))
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_albedo_coarse_image", return_value=FakeRaster())
    @patch("ECOv003_L2T_STARS.generate_STARS_inputs.generate_NDVI_coarse_image", return_value=FakeRaster())
    def test_generate_stars_inputs_succeeds_for_tile_56una(
        self, _mock_ndvi, _mock_albedo, _mock_ndvi_fine, _mock_albedo_fine, tmp_path
    ):
        """Verify generate_STARS_inputs writes coarse NDVI and albedo GeoTIFFs for tile 56UNA."""
        target = date(2026, 8, 26)
        gen_mod.generate_STARS_inputs(
            tile="56UNA",
            date_UTC=target,
            HLS_start_date=target,
            HLS_end_date=target,
            VIIRS_start_date=target,
            VIIRS_end_date=target,
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

        ndvi_file = tmp_path / "downsampled" / "2026" / "2026-08-26" / "56UNA" / "STARS_NDVI_56UNA_490m.tif"
        albedo_file = tmp_path / "downsampled" / "2026" / "2026-08-26" / "56UNA" / "STARS_albedo_56UNA_980m.tif"
        assert ndvi_file.exists()
        assert albedo_file.exists()
