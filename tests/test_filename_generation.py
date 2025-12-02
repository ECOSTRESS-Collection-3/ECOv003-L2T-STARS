import os
import sys
import pytest
from unittest.mock import Mock
from datetime import date, datetime

# Mock missing dependencies
missing_modules = [
    'harmonized_landsat_sentinel',
    'ECOv003_exit_codes',
    'ECOv002_CMR',
    'ECOv002_granules',
    'ECOv003_granules',
    'GEOS5FP',
    'modland',
    'sentinel_tiles',
    'earthaccess',
    'colored_logging',
    'untangle',
]

for module in missing_modules:
    if module not in sys.modules:
        sys.modules[module] = Mock()

from ECOv003_L2T_STARS.generate_filename import generate_filename
from ECOv003_L2T_STARS.generate_model_state_tile_date_directory import generate_model_state_tile_date_directory
from ECOv003_L2T_STARS.generate_output_directory import generate_output_directory


class TestFilenameGeneration:
    """Tests for filename generation functions."""
    
    def test_generate_filename_basic(self, tmp_path):
        """Test basic filename generation."""
        filename = generate_filename(
            directory=str(tmp_path / "output"),
            variable="NDVI",
            date_UTC=date(2024, 10, 30),
            tile="11SPS",
            cell_size=70
        )
        
        assert "11SPS" in filename
        assert "2024-10-30" in filename
        assert "NDVI" in filename
        assert filename.endswith(".tif")
    
    def test_generate_filename_with_string_date(self, tmp_path):
        """Test filename generation with date as string."""
        result = generate_filename(
            directory=str(tmp_path / "output"),
            variable="albedo",
            date_UTC="2023-06-15",
            tile="T12ABC",
            cell_size=980
        )
        
        assert "STARS_albedo" in result
        assert "2023-06-15" in result
    
    def test_generate_model_state_directory(self):
        """Test model state directory generation."""
        directory = generate_model_state_tile_date_directory(
            model_directory="/tmp/model",
            tile="11SPS",
            date_UTC=date(2024, 10, 30)
        )
        
        assert "/tmp/model" in directory
        assert "11SPS" in directory
    
    def test_generate_output_directory(self):
        """Test output directory generation."""
        directory = generate_output_directory(
            working_directory="/tmp/output",
            date_UTC=date(2024, 10, 30),
            tile="11SPS"
        )
        
        assert "/tmp/output" in directory
        assert "11SPS" in directory


class TestDownsampledDirectory:
    """Tests for downsampled directory generation."""
    
    def test_downsampled_directory_structure(self):
        """Test that downsampled directory follows expected structure."""
        from ECOv003_L2T_STARS.generate_downsampled_filename import generate_downsampled_filename
        
        filename = generate_downsampled_filename(
            directory="/tmp/downsampled",
            variable="NDVI",
            date_UTC=date(2024, 10, 30),
            tile="11SPS",
            cell_size=490
        )
        
        assert "/tmp/downsampled" in filename
        assert "11SPS" in filename
        assert "NDVI" in filename
        assert "490m" in filename
