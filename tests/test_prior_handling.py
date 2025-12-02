import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date

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

from ECOv003_L2T_STARS.prior import Prior


class TestPriorHandling:
    """Tests for prior data handling."""
    
    def test_prior_initialization_with_none(self):
        """Test Prior initialization with None values."""
        prior = Prior(
            using_prior=False,
            prior_date_UTC=None,
            L2T_STARS_prior_filename=None,
            prior_NDVI_filename=None,
            prior_NDVI_UQ_filename=None,
            prior_NDVI_flag_filename=None,
            prior_NDVI_bias_filename=None,
            prior_NDVI_bias_UQ_filename=None,
            prior_albedo_filename=None,
            prior_albedo_UQ_filename=None,
            prior_albedo_flag_filename=None,
            prior_albedo_bias_filename=None,
            prior_albedo_bias_UQ_filename=None
        )
        
        assert prior.using_prior is False
        assert prior.prior_NDVI_filename is None
        assert prior.prior_albedo_filename is None
    
    def test_prior_initialization_with_filenames(self):
        """Test Prior initialization with actual filenames."""
        prior = Prior(
            using_prior=True,
            prior_date_UTC=date(2024, 10, 30),
            L2T_STARS_prior_filename="/tmp/prior.zip",
            prior_NDVI_filename="/tmp/prior_ndvi.tif",
            prior_NDVI_UQ_filename="/tmp/prior_ndvi_uq.tif",
            prior_NDVI_flag_filename="/tmp/prior_ndvi_flag.tif",
            prior_NDVI_bias_filename="/tmp/prior_ndvi_bias.tif",
            prior_NDVI_bias_UQ_filename="/tmp/prior_ndvi_bias_uq.tif",
            prior_albedo_filename="/tmp/prior_albedo.tif",
            prior_albedo_UQ_filename="/tmp/prior_albedo_uq.tif",
            prior_albedo_flag_filename="/tmp/prior_albedo_flag.tif",
            prior_albedo_bias_filename="/tmp/prior_albedo_bias.tif",
            prior_albedo_bias_UQ_filename="/tmp/prior_albedo_bias_uq.tif"
        )
        
        assert prior.using_prior is True
        assert prior.prior_NDVI_filename == "/tmp/prior_ndvi.tif"
        assert prior.prior_albedo_filename == "/tmp/prior_albedo.tif"
    
    @patch('ECOv003_L2T_STARS.load_prior.exists')
    @patch('ECOv003_L2T_STARS.load_prior.L2TSTARS')
    def test_load_prior_when_files_exist(self, mock_l2tstars, mock_exists):
        """Test loading prior when all files exist."""
        from ECOv003_L2T_STARS.load_prior import load_prior
        
        # Mock all files exist
        mock_exists.return_value = True
        
        prior = load_prior(
            tile="11SPS",
            target_resolution=70,
            model_directory="/tmp/model",
            L2T_STARS_prior_filename="/tmp/prior.zip"
        )
        
        # Should return a Prior object
        assert isinstance(prior, Prior)
    
    @patch('ECOv003_L2T_STARS.load_prior.exists')
    def test_load_prior_when_files_missing(self, mock_exists):
        """Test loading prior when files don't exist."""
        from ECOv003_L2T_STARS.load_prior import load_prior
        
        # Mock files don't exist
        mock_exists.return_value = False
        
        prior = load_prior(
            tile="11SPS",
            target_resolution=70,
            model_directory="/tmp/model",
            L2T_STARS_prior_filename=None
        )
        
        # Should return Prior with using_prior=False
        assert prior.using_prior is False


class TestPriorBiasLayers:
    """Tests for prior bias layer handling."""
    
    def test_prior_has_bias_attributes(self):
        """Test that Prior objects have bias layer attributes."""
        prior = Prior(
            using_prior=True,
            prior_date_UTC=date(2024, 10, 30),
            L2T_STARS_prior_filename="/tmp/prior.zip",
            prior_NDVI_filename="/tmp/prior_ndvi.tif",
            prior_NDVI_UQ_filename="/tmp/prior_ndvi_uq.tif",
            prior_NDVI_flag_filename="/tmp/prior_ndvi_flag.tif",
            prior_NDVI_bias_filename="/tmp/prior_ndvi_bias.tif",
            prior_NDVI_bias_UQ_filename="/tmp/prior_ndvi_bias_uq.tif",
            prior_albedo_filename="/tmp/prior_albedo.tif",
            prior_albedo_UQ_filename="/tmp/prior_albedo_uq.tif",
            prior_albedo_flag_filename="/tmp/prior_albedo_flag.tif",
            prior_albedo_bias_filename="/tmp/prior_albedo_bias.tif",
            prior_albedo_bias_UQ_filename="/tmp/prior_albedo_bias_uq.tif"
        )
        
        # Check that bias attributes exist
        assert hasattr(prior, 'prior_NDVI_bias_filename')
        assert hasattr(prior, 'prior_NDVI_bias_UQ_filename')
        assert hasattr(prior, 'prior_albedo_bias_filename')
        assert hasattr(prior, 'prior_albedo_bias_UQ_filename')
