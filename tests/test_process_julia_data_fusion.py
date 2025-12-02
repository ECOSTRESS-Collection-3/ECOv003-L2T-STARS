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

from ECOv003_L2T_STARS.process_julia_data_fusion import process_julia_data_fusion


class TestProcessJuliaDataFusion:
    """Tests for the process_julia_data_fusion function."""
    
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.subprocess.run')
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.exists')
    def test_gdal_data_removed_when_present(self, mock_exists, mock_subprocess):
        """Test that GDAL_DATA and GDAL_DRIVER_PATH are removed when present."""
        # Set up environment with GDAL vars
        original_env = os.environ.copy()
        os.environ['GDAL_DATA'] = '/some/gdal/path'
        os.environ['GDAL_DRIVER_PATH'] = '/some/driver/path'
        os.environ['TEST_VAR'] = 'test_value'
        
        mock_exists.return_value = False  # No prior files exist
        
        try:
            process_julia_data_fusion(
                tile="T11SPA",
                coarse_cell_size=1000,
                fine_cell_size=30,
                VIIRS_start_date=date(2024, 1, 1),
                VIIRS_end_date=date(2024, 1, 10),
                HLS_start_date=date(2024, 1, 1),
                HLS_end_date=date(2024, 1, 10),
                downsampled_directory="/tmp/test",
                product_name="NDVI",
                posterior_filename="/tmp/posterior.tif",
                posterior_UQ_filename="/tmp/posterior_uq.tif",
                posterior_flag_filename="/tmp/posterior_flag.tif",
                posterior_bias_filename="/tmp/posterior_bias.tif",
                posterior_bias_UQ_filename="/tmp/posterior_bias_uq.tif"
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
    
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.subprocess.run')
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.exists')
    def test_no_error_when_gdal_vars_absent(self, mock_exists, mock_subprocess):
        """Test that no KeyError is raised when GDAL vars don't exist."""
        # Save original environment
        original_env = os.environ.copy()
        
        # Ensure GDAL vars are not in environment
        os.environ.pop('GDAL_DATA', None)
        os.environ.pop('GDAL_DRIVER_PATH', None)
        
        mock_exists.return_value = False  # No prior files exist
        
        try:
            # Should not raise KeyError
            process_julia_data_fusion(
                tile="T11SPA",
                coarse_cell_size=1000,
                fine_cell_size=30,
                VIIRS_start_date=date(2024, 1, 1),
                VIIRS_end_date=date(2024, 1, 10),
                HLS_start_date=date(2024, 1, 1),
                HLS_end_date=date(2024, 1, 10),
                downsampled_directory="/tmp/test",
                product_name="NDVI",
                posterior_filename="/tmp/posterior.tif",
                posterior_UQ_filename="/tmp/posterior_uq.tif",
                posterior_flag_filename="/tmp/posterior_flag.tif",
                posterior_bias_filename="/tmp/posterior_bias.tif",
                posterior_bias_UQ_filename="/tmp/posterior_bias_uq.tif"
            )
            
            # Verify subprocess was called successfully
            assert mock_subprocess.called
            
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)
    
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.subprocess.run')
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.exists')
    def test_julia_num_threads_set(self, mock_exists, mock_subprocess):
        """Test that JULIA_NUM_THREADS is set correctly."""
        original_env = os.environ.copy()
        mock_exists.return_value = False
        
        try:
            process_julia_data_fusion(
                tile="T11SPA",
                coarse_cell_size=1000,
                fine_cell_size=30,
                VIIRS_start_date=date(2024, 1, 1),
                VIIRS_end_date=date(2024, 1, 10),
                HLS_start_date=date(2024, 1, 1),
                HLS_end_date=date(2024, 1, 10),
                downsampled_directory="/tmp/test",
                product_name="NDVI",
                posterior_filename="/tmp/posterior.tif",
                posterior_UQ_filename="/tmp/posterior_uq.tif",
                posterior_flag_filename="/tmp/posterior_flag.tif",
                posterior_bias_filename="/tmp/posterior_bias.tif",
                posterior_bias_UQ_filename="/tmp/posterior_bias_uq.tif",
                threads=8
            )
            
            # Get the environment passed to subprocess
            call_env = mock_subprocess.call_args[1]['env']
            
            # Verify JULIA_NUM_THREADS is set
            assert call_env['JULIA_NUM_THREADS'] == '8'
            
        finally:
            os.environ.clear()
            os.environ.update(original_env)
    
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.subprocess.run')
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.exists')
    def test_prior_files_passed_when_all_exist(self, mock_exists, mock_subprocess):
        """Test that prior filenames are included in command when all exist."""
        original_env = os.environ.copy()
        
        # Mock that all prior files exist
        mock_exists.return_value = True
        
        try:
            process_julia_data_fusion(
                tile="T11SPA",
                coarse_cell_size=1000,
                fine_cell_size=30,
                VIIRS_start_date=date(2024, 1, 1),
                VIIRS_end_date=date(2024, 1, 10),
                HLS_start_date=date(2024, 1, 1),
                HLS_end_date=date(2024, 1, 10),
                downsampled_directory="/tmp/test",
                product_name="NDVI",
                posterior_filename="/tmp/posterior.tif",
                posterior_UQ_filename="/tmp/posterior_uq.tif",
                posterior_flag_filename="/tmp/posterior_flag.tif",
                posterior_bias_filename="/tmp/posterior_bias.tif",
                posterior_bias_UQ_filename="/tmp/posterior_bias_uq.tif",
                prior_filename="/tmp/prior.tif",
                prior_UQ_filename="/tmp/prior_uq.tif",
                prior_bias_filename="/tmp/prior_bias.tif",
                prior_bias_UQ_filename="/tmp/prior_bias_uq.tif"
            )
            
            # Get the command that was passed to subprocess
            command = mock_subprocess.call_args[0][0]
            
            # Verify prior files are in the command
            assert "/tmp/prior.tif" in command
            assert "/tmp/prior_uq.tif" in command
            assert "/tmp/prior_bias.tif" in command
            assert "/tmp/prior_bias_uq.tif" in command
            
        finally:
            os.environ.clear()
            os.environ.update(original_env)
    
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.subprocess.run')
    @patch('ECOv003_L2T_STARS.process_julia_data_fusion.exists')
    def test_prior_files_not_passed_when_missing(self, mock_exists, mock_subprocess):
        """Test that prior filenames are not included when any don't exist."""
        original_env = os.environ.copy()
        
        # Mock that prior files don't exist
        mock_exists.return_value = False
        
        try:
            process_julia_data_fusion(
                tile="T11SPA",
                coarse_cell_size=1000,
                fine_cell_size=30,
                VIIRS_start_date=date(2024, 1, 1),
                VIIRS_end_date=date(2024, 1, 10),
                HLS_start_date=date(2024, 1, 1),
                HLS_end_date=date(2024, 1, 10),
                downsampled_directory="/tmp/test",
                product_name="NDVI",
                posterior_filename="/tmp/posterior.tif",
                posterior_UQ_filename="/tmp/posterior_uq.tif",
                posterior_flag_filename="/tmp/posterior_flag.tif",
                posterior_bias_filename="/tmp/posterior_bias.tif",
                posterior_bias_UQ_filename="/tmp/posterior_bias_uq.tif",
                prior_filename="/tmp/prior.tif",
                prior_UQ_filename="/tmp/prior_uq.tif",
                prior_bias_filename="/tmp/prior_bias.tif",
                prior_bias_UQ_filename="/tmp/prior_bias_uq.tif"
            )
            
            # Get the command that was passed to subprocess
            command = mock_subprocess.call_args[0][0]
            
            # Verify prior files are NOT in the command
            assert "/tmp/prior.tif" not in command
            assert "/tmp/prior_uq.tif" not in command
            
        finally:
            os.environ.clear()
            os.environ.update(original_env)
