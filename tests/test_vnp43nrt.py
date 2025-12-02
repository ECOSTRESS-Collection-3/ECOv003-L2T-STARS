import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call, Mock
from datetime import date

# Mock all the missing dependencies before importing
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
    sys.modules[module] = Mock()

from ECOv003_L2T_STARS.VNP43NRT.VNP43NRT import process_julia_BRDF


class TestProcessJuliaBRDF:
    """Tests for the process_julia_BRDF function."""
    
    @patch('ECOv003_L2T_STARS.VNP43NRT.VNP43NRT.subprocess.run')
    def test_gdal_data_removed_when_present(self, mock_subprocess):
        """Test that GDAL_DATA and GDAL_DRIVER_PATH are removed when present."""
        # Set up environment with GDAL vars
        original_env = os.environ.copy()
        os.environ['GDAL_DATA'] = '/some/gdal/path'
        os.environ['GDAL_DRIVER_PATH'] = '/some/driver/path'
        os.environ['TEST_VAR'] = 'test_value'
        
        try:
            process_julia_BRDF(
                band="red",
                h=8,
                v=5,
                tile_width_cells=1200,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                reflectance_directory="/tmp/reflectance",
                solar_zenith_directory="/tmp/solar",
                sensor_zenith_directory="/tmp/sensor",
                relative_azimuth_directory="/tmp/ra",
                SZA_filename="/tmp/sza.tif",
                output_directory="/tmp/output",
                initialize_julia=False
            )
            
            # Check subprocess was called
            assert mock_subprocess.called
            
            # Get the environment passed to subprocess
            call_env = mock_subprocess.call_args[1]['env']
            
            # Verify GDAL vars were removed
            assert 'GDAL_DATA' not in call_env
            assert 'GDAL_DRIVER_PATH' not in call_env
            
            # Verify other vars remain
            assert call_env['TEST_VAR'] == 'test_value'
            
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)
    
    @patch('ECOv003_L2T_STARS.VNP43NRT.VNP43NRT.subprocess.run')
    def test_no_error_when_gdal_vars_absent(self, mock_subprocess):
        """Test that no KeyError is raised when GDAL vars don't exist."""
        # Save original environment
        original_env = os.environ.copy()
        
        # Ensure GDAL vars are not in environment
        os.environ.pop('GDAL_DATA', None)
        os.environ.pop('GDAL_DRIVER_PATH', None)
        
        try:
            # Should not raise KeyError
            process_julia_BRDF(
                band="red",
                h=8,
                v=5,
                tile_width_cells=1200,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                reflectance_directory="/tmp/reflectance",
                solar_zenith_directory="/tmp/solar",
                sensor_zenith_directory="/tmp/sensor",
                relative_azimuth_directory="/tmp/ra",
                SZA_filename="/tmp/sza.tif",
                output_directory="/tmp/output",
                initialize_julia=False
            )
            
            # Verify subprocess was called successfully
            assert mock_subprocess.called
            
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)
    
    @patch('ECOv003_L2T_STARS.VNP43NRT.VNP43NRT.subprocess.run')
    def test_subprocess_called_with_check_false(self, mock_subprocess):
        """Test that subprocess.run is called with check=False."""
        original_env = os.environ.copy()
        
        try:
            process_julia_BRDF(
                band="red",
                h=8,
                v=5,
                tile_width_cells=1200,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                reflectance_directory="/tmp/reflectance",
                solar_zenith_directory="/tmp/solar",
                sensor_zenith_directory="/tmp/sensor",
                relative_azimuth_directory="/tmp/ra",
                SZA_filename="/tmp/sza.tif",
                output_directory="/tmp/output",
                initialize_julia=False
            )
            
            # Verify subprocess was called with check=False
            assert mock_subprocess.called
            assert mock_subprocess.call_args[1].get('check') == False
            
        finally:
            os.environ.clear()
            os.environ.update(original_env)
    
    @patch('ECOv003_L2T_STARS.VNP43NRT.VNP43NRT.subprocess.run')
    def test_command_contains_required_paths(self, mock_subprocess):
        """Test that the Julia command contains all required directory paths."""
        original_env = os.environ.copy()
        
        try:
            process_julia_BRDF(
                band="nir",
                h=10,
                v=6,
                tile_width_cells=1200,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 15),
                reflectance_directory="/tmp/reflectance",
                solar_zenith_directory="/tmp/solar",
                sensor_zenith_directory="/tmp/sensor",
                relative_azimuth_directory="/tmp/ra",
                SZA_filename="/tmp/sza.tif",
                output_directory="/tmp/output",
                initialize_julia=False
            )
            
            # Get the command that was passed to subprocess
            command = mock_subprocess.call_args[0][0]
            
            # Verify key paths and values are in the command
            command_str = " ".join(command)
            assert "nir" in command or "nir" in command_str
            assert "/tmp/reflectance" in command or "/tmp/reflectance" in command_str
            assert "/tmp/output" in command or "/tmp/output" in command_str
            
        finally:
            os.environ.clear()
            os.environ.update(original_env)
