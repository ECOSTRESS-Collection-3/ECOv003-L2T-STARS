import os
import subprocess
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

from ECOv003_L2T_STARS.VNP43NRT.VNP43NRT import _julia_environment, process_julia_BRDF
from ECOv003_L2T_STARS.julia_environment import find_compatible_julia


@patch('sys.platform', 'darwin')
@patch.dict(os.environ, {
    'DYLD_LIBRARY_PATH': '/opt/homebrew/opt/llvm/lib',
    'GDAL_DATA': '/some/gdal/path',
    'GDAL_DRIVER_PATH': '/some/driver/path',
    'TEST_VAR': 'test_value',
}, clear=True)
def test_julia_environment_isolates_macos_loader_and_gdal():
    env = _julia_environment()

    assert 'DYLD_LIBRARY_PATH' not in env
    assert 'GDAL_DATA' not in env
    assert 'GDAL_DRIVER_PATH' not in env
    assert env['TEST_VAR'] == 'test_value'
    assert os.environ['DYLD_LIBRARY_PATH'] == '/opt/homebrew/opt/llvm/lib'
    assert os.environ['GDAL_DATA'] == '/some/gdal/path'


@patch('sys.platform', 'linux')
@patch.dict(os.environ, {'DYLD_LIBRARY_PATH': '/custom/lib'}, clear=True)
def test_julia_environment_preserves_macos_loader_setting_on_other_platforms():
    assert _julia_environment()['DYLD_LIBRARY_PATH'] == '/custom/lib'


@patch('ECOv003_L2T_STARS.julia_environment._manifest_julia_version', return_value='1.11')
@patch('ECOv003_L2T_STARS.julia_environment.shutil.which')
@patch('ECOv003_L2T_STARS.julia_environment.subprocess.run')
def test_find_compatible_julia_skips_incompatible_versions(run, which, manifest):
    which.side_effect = ['/first/julia', '/second/julia']
    run.side_effect = [
        subprocess.CompletedProcess([], 0, stdout='julia version 1.12.3\n', stderr=''),
        subprocess.CompletedProcess([], 0, stdout='julia version 1.11.5\n', stderr=''),
    ]
    env = {'PATH': os.pathsep.join(['/first', '/second'])}

    assert find_compatible_julia('/project', env) == '/second/julia'
    assert run.call_args_list[1].kwargs['env'] is env


@patch('ECOv003_L2T_STARS.julia_environment._manifest_julia_version', return_value='1.11')
@patch('ECOv003_L2T_STARS.julia_environment.shutil.which', return_value='/first/julia')
@patch('ECOv003_L2T_STARS.julia_environment.subprocess.run')
def test_find_compatible_julia_reports_missing_version(run, which, manifest):
    run.return_value = subprocess.CompletedProcess(
        [], 0, stdout='julia version 1.12.3\n', stderr=''
    )
    with pytest.raises(FileNotFoundError, match=r'Julia 1\.11\.x'):
        find_compatible_julia('/project', {'PATH': '/first'})


class TestProcessJuliaBRDF:
    """Tests for the process_julia_BRDF function."""

    @pytest.fixture(autouse=True)
    def mock_julia_executable(self):
        with patch(
            'ECOv003_L2T_STARS.VNP43NRT.VNP43NRT.find_compatible_julia',
            return_value='julia',
        ):
            yield
    
    @patch('subprocess.run')
    @patch('sys.platform', 'darwin')
    @patch.dict('os.environ', {
        'GDAL_DATA': '/some/gdal/path',
        'GDAL_DRIVER_PATH': '/some/driver/path',
        'DYLD_LIBRARY_PATH': '/opt/homebrew/opt/llvm/lib',
        'TEST_VAR': 'test_value'
    }, clear=True)
    def test_gdal_data_removed_when_present(self, mock_subprocess):
        """Test that GDAL_DATA and GDAL_DRIVER_PATH are removed when present."""
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
        
        # Verify GDAL vars were removed from the subprocess environment
        assert 'GDAL_DATA' not in call_env
        assert 'GDAL_DRIVER_PATH' not in call_env
        assert 'DYLD_LIBRARY_PATH' not in call_env
        assert os.environ['DYLD_LIBRARY_PATH'] == '/opt/homebrew/opt/llvm/lib'
        
        # Verify other vars remain in subprocess environment
        assert call_env['TEST_VAR'] == 'test_value'
    
    @patch('subprocess.run')
    @patch.dict('os.environ', {'SOME_VAR': 'value'}, clear=True)
    def test_no_error_when_gdal_vars_absent(self, mock_subprocess):
        """Test that no KeyError is raised when GDAL vars don't exist."""
        # Should not raise KeyError even if GDAL vars are absent from mocked environment
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
    
    @patch('subprocess.run')
    @patch.dict('os.environ', {}, clear=True)
    def test_subprocess_called_with_check_true(self, mock_subprocess):
        """A Julia failure must be reported before reading its output."""
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
        
        assert mock_subprocess.called
        assert mock_subprocess.call_args[1].get('check') is True

    @patch('subprocess.run')
    def test_subprocess_failure_propagates(self, mock_subprocess):
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, ["julia"])

        with pytest.raises(subprocess.CalledProcessError):
            process_julia_BRDF(
                band="I1",
                h=8,
                v=5,
                tile_width_cells=2400,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                reflectance_directory="/tmp/reflectance",
                solar_zenith_directory="/tmp/solar",
                sensor_zenith_directory="/tmp/sensor",
                relative_azimuth_directory="/tmp/ra",
                SZA_filename="/tmp/sza.tif",
                output_directory="/tmp/output",
                initialize_julia=False,
            )
    
    @patch('subprocess.run')
    @patch.dict('os.environ', {}, clear=True)
    def test_command_contains_required_paths(self, mock_subprocess):
        """Test that the Julia command contains all required directory paths."""
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
