import sys
import pytest
from unittest.mock import Mock
from datetime import date, timedelta

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


class TestDateHandling:
    """Tests for date range and date utility functions."""
    
    def test_get_date_from_string(self):
        """Test date parsing from string."""
        from ECOv003_L2T_STARS.daterange import get_date
        
        # Test various date formats
        test_date = get_date("2024-10-30")
        assert isinstance(test_date, date)
        assert test_date.year == 2024
        assert test_date.month == 10
        assert test_date.day == 30
    
    def test_get_date_from_date_object(self):
        """Test that date objects pass through unchanged."""
        from ECOv003_L2T_STARS.daterange import get_date
        
        input_date = date(2024, 10, 30)
        result = get_date(input_date)
        assert result == input_date
    
    def test_date_range_calculation(self):
        """Test date range calculations for spinup."""
        start_date = date(2024, 10, 30)
        spinup_days = 16
        
        # Calculate VIIRS start date (spinup period before target)
        viirs_start = start_date - timedelta(days=spinup_days)
        
        assert viirs_start == date(2024, 10, 14)
        assert (start_date - viirs_start).days == spinup_days
    
    def test_date_range_inclusive(self):
        """Test that date ranges are inclusive of endpoints."""
        from dateutil.rrule import rrule, DAILY
        
        start = date(2024, 10, 28)
        end = date(2024, 10, 30)
        
        dates = list(rrule(DAILY, dtstart=start, until=end))
        
        # Should include 3 days: 28th, 29th, 30th
        assert len(dates) == 3


class TestTimeHandling:
    """Tests for time and datetime utilities."""
    
    def test_utc_time_handling(self):
        """Test UTC time parsing and handling."""
        from datetime import datetime
        from dateutil import parser
        
        # Test parsing ISO format
        time_string = "2024-10-30T12:00:00Z"
        parsed_time = parser.parse(time_string)
        
        assert parsed_time.year == 2024
        assert parsed_time.month == 10
        assert parsed_time.day == 30
        assert parsed_time.hour == 12
    
    def test_date_from_datetime(self):
        """Test extracting date from datetime."""
        from datetime import datetime
        
        dt = datetime(2024, 10, 30, 12, 0, 0)
        d = dt.date()
        
        assert d == date(2024, 10, 30)
        assert isinstance(d, date)


class TestSpinupCalculations:
    """Tests for spinup period calculations."""
    
    def test_spinup_days_constant(self):
        """Test that SPINUP_DAYS constant is defined."""
        from ECOv003_L2T_STARS.constants import SPINUP_DAYS
        
        assert SPINUP_DAYS == 7  # Standard spin-up period
    
    def test_spinup_date_range(self):
        """Test spinup date range calculation."""
        target_date = date(2024, 10, 30)
        spinup_days = 16
        
        viirs_start = target_date - timedelta(days=spinup_days)
        viirs_end = target_date
        
        # Verify range
        assert viirs_start == date(2024, 10, 14)
        assert viirs_end == date(2024, 10, 30)
        
        # Verify span
        span = (viirs_end - viirs_start).days
        assert span == spinup_days
