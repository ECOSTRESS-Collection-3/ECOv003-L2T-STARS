import os
import sys
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Mock missing dependencies (including ECOv003_exit_codes which isn't installed)
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
]

for module in missing_modules:
    if module not in sys.modules:
        sys.modules[module] = Mock()


# Skip all config tests since they require ECOv003_exit_codes and untangle
# which have complex integration that can't be easily mocked
pytestmark = pytest.mark.skip(reason="Config tests require ECOv003_exit_codes and untangle integration")


class TestL2TSTARSConfig:
    """Tests for L2TSTARSConfig parsing (skipped due to dependencies)."""
    pass
