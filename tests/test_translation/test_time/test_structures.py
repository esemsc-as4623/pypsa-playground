# tests/test_translation/test_structures.py

import pytest
import pandas as pd
from datetime import time, date, datetime
import calendar

from pyoscomp.constants import ENDOFDAY
from pyoscomp.translation.time.structures import DayType, DailyTimeBracket, Timeslice


class TestDayType:
    """Tests for DayType dataclass."""
    
    # ========== Valid Constructions ==========
    
    def test_full_year(self):
        """Test full year daytype."""
        dt = DayType(1, 1, 12, 31)
        assert dt.is_full_year()
        assert dt.name == "YEAR"
        assert dt.duration_days(2000) == 366  # Leap year
        assert dt.duration_days(2001) == 365  # Non-leap year
    
    def test_single_day(self):
        """Test single day daytype."""
        dt = DayType(6, 15, 6, 15)
        assert not dt.is_full_year()
        assert dt.duration_days(2020) == 1
        assert dt.contains_date(date(2020, 6, 15))
        assert not dt.contains_date(date(2020, 6, 14))
        assert not dt.contains_date(date(2020, 6, 16))
    
    def test_single_month(self):
        """Test single month daytype for all months."""
        for month in range(1, 13):
            last_day = calendar.monthrange(2000, month)[1]
            dt = DayType(month, 1, month, last_day)
            assert not dt.is_full_year()
            assert dt.duration_days(2000) == last_day
            assert dt.contains_date(date(2000, month, 1))
            assert dt.contains_date(date(2000, month, last_day))
            # Check doesn't bleed into next month
            if month < 12:
                assert not dt.contains_date(date(2000, month + 1, 1))
    
    def test_multi_month_span(self):
        """Test daytype spanning multiple months."""
        dt = DayType(3, 1, 5, 31)  # March 1 to May 31
        assert dt.duration_days(2020) == 92  # 31 + 30 + 31
        assert dt.contains_date(date(2020, 3, 1))
        assert dt.contains_date(date(2020, 4, 15))
        assert dt.contains_date(date(2020, 5, 31))
        assert not dt.contains_date(date(2020, 2, 29))
        assert not dt.contains_date(date(2020, 6, 1))
    
    def test_partial_months(self):
        """Test daytype with partial month boundaries."""
        dt = DayType(3, 15, 4, 20)  # Mid-March to mid-April
        assert dt.duration_days(2020) == 37  # 17 days in March + 20 days in April
        assert dt.contains_date(date(2020, 3, 15))
        assert dt.contains_date(date(2020, 4, 20))
        assert not dt.contains_date(date(2020, 3, 14))
        assert not dt.contains_date(date(2020, 4, 21))

    def test_partial_months_leap(self):
        """Test daytype with partial month boundaries including leap day."""
        dt = DayType(2, 20, 3, 10)  # Feb 20 to Mar 10
        assert dt.duration_days(2020) == 20  # Leap year: 9 days in Feb + 11 days in Mar
        assert dt.duration_days(2021) == 19  # Non-leap year: 8 days in Feb + 11 days in Mar
        assert dt.contains_date(date(2020, 2, 20))
        assert dt.contains_date(date(2020, 2, 29)) # Leap day
        assert dt.contains_date(date(2020, 3, 10))
        assert not dt.contains_date(date(2020, 2, 19))
        assert not dt.contains_date(date(2020, 3, 11))
    
    # ========== Validation Errors ==========
    
    def test_year_wrapping_prevented(self):
        """Test that year-wrapping intervals raise error."""
        with pytest.raises(ValueError, match="Year-wrapping"):
            DayType(12, 1, 2, 28)  # Dec to Feb wraps year
        
        with pytest.raises(ValueError, match="Year-wrapping"):
            DayType(12, 31, 1, 1)  # Dec 31 to Jan 1 wraps
    
    def test_invalid_month_start(self):
        """Test invalid month_start validation."""
        with pytest.raises(ValueError, match="month_start"):
            DayType(0, 1, 12, 31)
        
        with pytest.raises(ValueError, match="month_start"):
            DayType(13, 1, 12, 31)
    
    def test_invalid_month_end(self):
        """Test invalid month_end validation."""
        with pytest.raises(ValueError, match="month_end"):
            DayType(1, 1, 0, 1)
        
        with pytest.raises(ValueError, match="month_end"):
            DayType(1, 1, 13, 1)
    
    def test_invalid_day_start(self):
        """Test invalid day_start validation."""
        with pytest.raises(ValueError, match="day_start"):
            DayType(2, 0, 2, 28)  # Day 0 doesn't exist
        
        with pytest.raises(ValueError, match="day_start"):
            DayType(2, 30, 2, 28)  # Feb doesn't have 30 days
        
        with pytest.raises(ValueError, match="day_start"):
            DayType(4, 31, 4, 30)  # April doesn't have 31 days
    
    def test_invalid_day_end(self):
        """Test invalid day_end validation."""
        with pytest.raises(ValueError, match="day_end"):
            DayType(6, 1, 6, 31)  # June only has 30 days
    
    # ========== Boundary Cases ==========
    
    def test_january_first(self):
        """Test January 1st boundary."""
        dt = DayType(1, 1, 1, 1)
        assert dt.contains_date(date(2020, 1, 1))
        assert not dt.contains_date(date(2019, 12, 31))
        assert not dt.contains_date(date(2020, 1, 2))
    
    def test_december_31st(self):
        """Test December 31st boundary."""
        dt = DayType(12, 31, 12, 31)
        assert dt.contains_date(date(2020, 12, 31))
        assert not dt.contains_date(date(2020, 12, 30))
        assert not dt.contains_date(date(2021, 1, 1))
    
    def test_february_29_leap_year(self):
        """Test Feb 29 in leap year."""
        dt = DayType(2, 29, 2, 29)
        
        # Leap year: Feb 29 exists
        assert dt.contains_date(date(2000, 2, 29))
        assert dt.contains_date(date(2020, 2, 29))
        assert dt.duration_days(2000) == 1
        assert dt.duration_days(2020) == 1
    
    def test_february_29_non_leap_year(self):
        """Test Feb 29 handling in non-leap year."""
        dt = DayType(2, 29, 2, 29)
        
        # Non-leap year: Falls back to Feb 28
        start, end = dt.to_dates(2001)
        assert end == date(2001, 2, 28)
        assert dt.duration_days(2001) == 0  # Falls on Feb 28, but daytype is for 29
        
        # Feb 29 doesn't exist in 2001, so contains_date should be False
        assert not dt.contains_date(date(2001, 2, 28))
        assert not dt.contains_date(date(2001, 3, 1))
    
    def test_february_span_with_29(self):
        """Test February span including day 29."""
        dt = DayType(2, 1, 2, 29)
        
        # Leap year
        assert dt.duration_days(2000) == 29
        start, end = dt.to_dates(2000)
        assert end == date(2000, 2, 29)
        
        # Non-leap year: truncates to Feb 28
        assert dt.duration_days(2001) == 28
        start, end = dt.to_dates(2001)
        assert end == date(2001, 2, 28)
    
    # ========== to_dates() Method ==========
    
    def test_to_dates_leap_year(self):
        """Test to_dates() for leap year."""
        dt = DayType(2, 1, 2, 29)
        start, end = dt.to_dates(2000)
        assert start == date(2000, 2, 1)
        assert end == date(2000, 2, 29)
    
    def test_to_dates_non_leap_year(self):
        """Test to_dates() for non-leap year."""
        dt = DayType(2, 1, 2, 29)
        start, end = dt.to_dates(2001)
        assert start == date(2001, 2, 1)
        assert end == date(2001, 2, 28)  # Falls back
    
    def test_to_dates_different_years(self):
        """Test to_dates() produces correct dates for different years."""
        dt = DayType(6, 15, 6, 20)
        
        for year in [2000, 2001, 2020, 2025]:
            start, end = dt.to_dates(year)
            assert start == date(year, 6, 15)
            assert end == date(year, 6, 20)
    
    # ========== contains_date() Accuracy ==========
    
    def test_contains_date_closed_interval(self):
        """Test that contains_date uses closed interval [start, end]."""
        dt = DayType(3, 15, 4, 20)
        
        # Boundaries (closed interval)
        assert dt.contains_date(date(2020, 3, 15))  # Start included
        assert dt.contains_date(date(2020, 4, 20))  # End included
        
        # Just outside boundaries
        assert not dt.contains_date(date(2020, 3, 14))
        assert not dt.contains_date(date(2020, 4, 21))
        
        # Well inside
        assert dt.contains_date(date(2020, 3, 20))
        assert dt.contains_date(date(2020, 4, 1))
        assert dt.contains_date(date(2020, 4, 15))
    
    def test_contains_date_different_year(self):
        """Test contains_date with dates from different years."""
        dt = DayType(6, 1, 6, 30)
        
        # Same daytype, different years - all should match
        assert dt.contains_date(date(2000, 6, 15))
        assert dt.contains_date(date(2020, 6, 15))
        assert dt.contains_date(date(2025, 6, 15))
    
    # ========== duration_days() Correctness ==========
    
    def test_duration_days_single_day(self):
        """Test duration for single day."""
        dt = DayType(5, 10, 5, 10)
        assert dt.duration_days(2020) == 1
        assert dt.duration_days(2021) == 1
    
    def test_duration_days_full_months(self):
        """Test duration for full months."""
        # January (31 days)
        dt = DayType(1, 1, 1, 31)
        assert dt.duration_days(2020) == 31
        
        # April (30 days)
        dt = DayType(4, 1, 4, 30)
        assert dt.duration_days(2020) == 30
        
        # February in leap year (29 days)
        dt = DayType(2, 1, 2, 29)
        assert dt.duration_days(2020) == 29
        
        # February in non-leap year (28 days)
        assert dt.duration_days(2021) == 28
    
    def test_duration_days_multi_month(self):
        """Test duration spanning multiple months."""
        # Q1: Jan + Feb + Mar
        dt = DayType(1, 1, 3, 31)
        assert dt.duration_days(2020) == 91  # Leap year: 31+29+31
        assert dt.duration_days(2021) == 90  # Non-leap: 31+28+31
    
    def test_duration_days_full_year(self):
        """Test duration for full year."""
        dt = DayType(1, 1, 12, 31)
        assert dt.duration_days(2020) == 366  # Leap year
        assert dt.duration_days(2021) == 365  # Non-leap year
        assert dt.duration_days(2000) == 366  # Leap year
        assert dt.duration_days(1900) == 365  # Not a leap year (divisible by 100 but not 400)
    
    # ========== Sorting and Hashing ==========
    
    def test_sorting(self):
        """Test DayType sorting by start date."""
        dt1 = DayType(1, 1, 1, 31)
        dt2 = DayType(3, 15, 4, 20)
        dt3 = DayType(6, 1, 6, 30)
        dt4 = DayType(12, 1, 12, 31)
        
        unsorted = [dt3, dt1, dt4, dt2]
        sorted_dts = sorted(unsorted)
        
        assert sorted_dts == [dt1, dt2, dt3, dt4]
    
    def test_hashing(self):
        """Test DayType hashing for set operations."""
        dt1 = DayType(1, 1, 1, 31)
        dt2 = DayType(1, 1, 1, 31)  # Same as dt1
        dt3 = DayType(2, 1, 2, 28)
        
        # Same daytypes should hash to same value
        assert hash(dt1) == hash(dt2)
        
        # Can be used in sets
        dt_set = {dt1, dt2, dt3}
        assert len(dt_set) == 2  # dt1 and dt2 are duplicates
    
    def test_equality(self):
        """Test DayType equality."""
        dt1 = DayType(3, 15, 4, 20)
        dt2 = DayType(3, 15, 4, 20)
        dt3 = DayType(3, 15, 4, 21)
        
        assert dt1 == dt2
        assert dt1 != dt3
        assert not (dt1 == "not a daytype")


class TestDailyTimeBracket:
    """Tests for DailyTimeBracket dataclass."""
    
    # ========== Valid Constructions ==========
    
    def test_full_day(self):
        """Test full day bracket."""
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        assert dtb.is_full_day()
        assert dtb.name == "DAY"
        assert dtb.duration_hours() == 24.0
        assert dtb.contains_time(time(0, 0, 0))
        assert dtb.contains_time(time(23, 59, 59))
    
    def test_morning_bracket(self):
        """Test morning time bracket."""
        dtb = DailyTimeBracket(time(6, 0, 0), time(12, 0, 0))
        assert not dtb.is_full_day()
        assert dtb.name == "T0600_1200"
        assert dtb.duration_hours() == 6.0
    
    def test_afternoon_bracket(self):
        """Test afternoon time bracket."""
        dtb = DailyTimeBracket(time(12, 0, 0), time(18, 0, 0))
        assert dtb.duration_hours() == 6.0
        assert dtb.contains_time(time(15, 0, 0))
    
    def test_hourly_brackets(self):
        """Test 1-hour brackets."""
        for hour in range(24):
            start = time(hour, 0, 0)
            end = time(hour + 1, 0, 0) if hour < 23 else ENDOFDAY
            dtb = DailyTimeBracket(start, end)
            assert dtb.duration_hours() == 1.0
    
    def test_sub_hourly_bracket(self):
        """Test sub-hourly precision."""
        dtb = DailyTimeBracket(time(10, 30, 0), time(11, 15, 0))
        assert dtb.duration_hours() == 0.75  # 45 minutes
    
    def test_midnight_to_noon(self):
        """Test bracket from midnight to noon."""
        dtb = DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
        assert dtb.duration_hours() == 12.0
        assert dtb.contains_time(time(0, 0, 0))
        assert not dtb.contains_time(time(12, 0, 0))  # Half-open
    
    # ========== ENDOFDAY Handling ==========
    
    def test_evening_to_endofday(self):
        """Test bracket extending to end of day."""
        dtb = DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
        assert dtb.name == "T1800_24:00"
        assert dtb.duration_hours() == 6.0
        assert dtb.contains_time(time(18, 0, 0))
        assert dtb.contains_time(time(23, 59, 59))
    
    def test_endofday_inclusive(self):
        """Test that ENDOFDAY means inclusive end."""
        dtb = DailyTimeBracket(time(23, 0, 0), ENDOFDAY)
        # Should contain all times from 23:00 onwards
        assert dtb.contains_time(time(23, 0, 0))
        assert dtb.contains_time(time(23, 30, 0))
        assert dtb.contains_time(time(23, 59, 59))
    
    def test_endofday_duration(self):
        """Test duration calculation with ENDOFDAY."""
        # Last hour of day
        dtb = DailyTimeBracket(time(23, 0, 0), ENDOFDAY)
        assert dtb.duration_hours() == 1.0
        
        # Last 6 hours
        dtb = DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
        assert dtb.duration_hours() == 6.0
    
    # ========== contains_time() with Boundaries ==========
    
    def test_contains_time_half_open_interval(self):
        """Test that contains_time uses half-open interval [start, end)."""
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        
        # Start included
        assert dtb.contains_time(time(9, 0, 0))
        
        # End excluded (unless ENDOFDAY)
        assert not dtb.contains_time(time(17, 0, 0))
        
        # Inside
        assert dtb.contains_time(time(12, 30, 0))
        
        # Outside
        assert not dtb.contains_time(time(8, 59, 59))
        assert not dtb.contains_time(time(17, 0, 1))
    
    def test_contains_time_edge_cases(self):
        """Test edge cases for time containment."""
        dtb = DailyTimeBracket(time(0, 0, 0), time(0, 0, 1))  # 1 second
        assert dtb.contains_time(time(0, 0, 0))
        assert not dtb.contains_time(time(0, 0, 1))
    
    # ========== duration_hours() Calculations ==========
    
    def test_duration_hours_precision(self):
        """Test duration calculation with various precisions."""
        # 1 hour
        dtb = DailyTimeBracket(time(10, 0, 0), time(11, 0, 0))
        assert dtb.duration_hours() == 1.0
        
        # 30 minutes
        dtb = DailyTimeBracket(time(10, 0, 0), time(10, 30, 0))
        assert dtb.duration_hours() == 0.5
        
        # 15 minutes
        dtb = DailyTimeBracket(time(10, 0, 0), time(10, 15, 0))
        assert dtb.duration_hours() == 0.25
        
        # 1 second
        dtb = DailyTimeBracket(time(10, 0, 0), time(10, 0, 1))
        assert abs(dtb.duration_hours() - 1/3600) < 1e-10
    
    def test_duration_hours_full_day(self):
        """Test duration for full day."""
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        assert dtb.duration_hours() == 24.0
    
    # ========== is_full_day() Detection ==========
    
    def test_is_full_day_true(self):
        """Test is_full_day() returns True for full day."""
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        assert dtb.is_full_day()
    
    def test_is_full_day_false(self):
        """Test is_full_day() returns False for partial days."""
        dtb = DailyTimeBracket(time(0, 0, 0), time(23, 59, 59))
        assert not dtb.is_full_day()
        
        dtb = DailyTimeBracket(time(0, 0, 1), ENDOFDAY)
        assert not dtb.is_full_day()
        
        dtb = DailyTimeBracket(time(6, 0, 0), time(18, 0, 0))
        assert not dtb.is_full_day()
    
    # ========== Validation Errors ==========
    
    def test_invalid_ordering(self):
        """Test that start must be before end."""
        with pytest.raises(ValueError, match="must be before"):
            DailyTimeBracket(time(12, 0, 0), time(6, 0, 0))
        
        with pytest.raises(ValueError, match="must be before"):
            DailyTimeBracket(time(10, 0, 0), time(10, 0, 0))  # Equal not allowed
    
    def test_endofday_no_validation_error(self):
        """Test that ENDOFDAY doesn't trigger validation error."""
        # Should not raise
        dtb = DailyTimeBracket(time(23, 59, 59), ENDOFDAY)
        assert dtb.duration_hours() > 0
    
    # ========== Sorting and Hashing ==========
    
    def test_sorting(self):
        """Test DailyTimeBracket sorting by start time."""
        dtb1 = DailyTimeBracket(time(0, 0, 0), time(6, 0, 0))
        dtb2 = DailyTimeBracket(time(6, 0, 0), time(12, 0, 0))
        dtb3 = DailyTimeBracket(time(12, 0, 0), time(18, 0, 0))
        dtb4 = DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
        
        unsorted = [dtb3, dtb1, dtb4, dtb2]
        sorted_dtbs = sorted(unsorted)
        
        assert sorted_dtbs == [dtb1, dtb2, dtb3, dtb4]
    
    def test_hashing(self):
        """Test DailyTimeBracket hashing."""
        dtb1 = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        dtb2 = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        dtb3 = DailyTimeBracket(time(9, 0, 0), time(18, 0, 0))
        
        assert hash(dtb1) == hash(dtb2)
        
        dtb_set = {dtb1, dtb2, dtb3}
        assert len(dtb_set) == 2
    
    def test_equality(self):
        """Test DailyTimeBracket equality."""
        dtb1 = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        dtb2 = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        dtb3 = DailyTimeBracket(time(9, 0, 0), time(18, 0, 0))
        
        assert dtb1 == dtb2
        assert dtb1 != dtb3


class TestTimeslice:
    """Tests for Timeslice dataclass."""
    
    # ========== Name Generation ==========
    
    def test_name_generation_full_year_full_day(self):
        """Test name for full year, full day timeslice."""
        dt = DayType(1, 1, 12, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        assert ts.name == "X_YEAR_DAY"
    
    def test_name_generation_specific_dates_times(self):
        """Test name generation for specific dates and times."""
        dt = DayType(6, 15, 6, 15)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        assert "06-15" in ts.name
        assert "0900" in ts.name
        assert "1700" in ts.name
    
    def test_name_generation_endofday(self):
        """Test name generation with ENDOFDAY."""
        dt = DayType(12, 31, 12, 31)
        dtb = DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        assert "24:00" in ts.name
    
    # ========== contains_timestamp() ==========
    
    def test_contains_timestamp_basic(self):
        """Test basic timestamp containment."""
        dt = DayType(6, 1, 6, 30)  # Month of June
        dtb = DailyTimeBracket(time(8, 0, 0), time(18, 0, 0))  # 8AM to 6PM
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        # Should contain
        assert ts.contains_timestamp(datetime(2020, 6, 15, 12, 0, 0))
        assert ts.contains_timestamp(datetime(2020, 6, 1, 8, 0, 0))
        assert ts.contains_timestamp(datetime(2020, 6, 30, 17, 59, 59))
        
        # Wrong month
        assert not ts.contains_timestamp(datetime(2020, 5, 15, 12, 0, 0))
        assert not ts.contains_timestamp(datetime(2020, 7, 15, 12, 0, 0))
        
        # Wrong time
        assert not ts.contains_timestamp(datetime(2020, 6, 15, 7, 59, 59))
        assert not ts.contains_timestamp(datetime(2020, 6, 15, 18, 0, 0))
        assert not ts.contains_timestamp(datetime(2020, 6, 15, 20, 0, 0))
    
    def test_contains_timestamp_different_years(self):
        """Test that timeslice pattern applies to any year."""
        dt = DayType(1, 1, 1, 1)  # January 1st
        dtb = DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))  # Morning
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        # Should work for any year
        assert ts.contains_timestamp(datetime(2000, 1, 1, 6, 0, 0))
        assert ts.contains_timestamp(datetime(2020, 1, 1, 6, 0, 0))
        assert ts.contains_timestamp(datetime(2025, 1, 1, 6, 0, 0))
    
    def test_contains_timestamp_pandas(self):
        """Test contains_timestamp with pandas Timestamp."""
        dt = DayType(3, 15, 3, 15)
        dtb = DailyTimeBracket(time(10, 0, 0), time(11, 0, 0))
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        pd_ts = pd.Timestamp('2020-03-15 10:30:00')
        assert ts.contains_timestamp(pd_ts)
        
        pd_ts_wrong = pd.Timestamp('2020-03-15 11:30:00')
        assert not ts.contains_timestamp(pd_ts_wrong)
    
    # ========== duration_hours() and year_fraction() ==========
    
    def test_duration_hours_full_year(self):
        """Test duration for full year timeslice."""
        dt = DayType(1, 1, 12, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == 366 * 24  # Leap year
        assert ts.duration_hours(2021) == 365 * 24  # Non-leap year
    
    def test_duration_hours_single_day(self):
        """Test duration for single day timeslice."""
        dt = DayType(6, 15, 6, 15)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == 24
    
    def test_duration_hours_partial_day(self):
        """Test duration for partial day."""
        dt = DayType(6, 15, 6, 15)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == 8  # 8 hours per day * 1 day
    
    def test_duration_hours_multi_day(self):
        """Test duration for multiple days."""
        dt = DayType(6, 1, 6, 7)  # 7 days
        dtb = DailyTimeBracket(time(8, 0, 0), time(20, 0, 0))  # 12 hours per day
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == 7 * 12  # 84 hours
    
    def test_duration_hours_month(self):
        """Test duration for full month."""
        for month in range(1, 13):
            last_day = calendar.monthrange(2020, month)[1]
            dt = DayType(month, 1, month, last_day)
            dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
            
            assert ts.duration_hours(2020) == last_day * 24
    
    def test_year_fraction_full_year(self):
        """Test year fraction for full year."""
        dt = DayType(1, 1, 12, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        assert abs(ts.year_fraction(2020) - 1.0) < 1e-10
        assert abs(ts.year_fraction(2021) - 1.0) < 1e-10
    
    def test_year_fraction_single_hour(self):
        """Test year fraction for single hour."""
        dt = DayType(1, 1, 1, 1)
        dtb = DailyTimeBracket(time(0, 0, 0), time(1, 0, 0))
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        # 1 hour out of 8784 hours (leap year)
        expected = 1.0 / (366 * 24)
        assert abs(ts.year_fraction(2020) - expected) < 1e-10
    
    def test_year_fraction_consistency(self):
        """Test that year fractions sum to reasonable value."""
        # Create 4 quarters, each 3 months
        dt1 = DayType(1, 1, 3, 31)
        dt2 = DayType(4, 1, 6, 30)
        dt3 = DayType(7, 1, 9, 30)
        dt4 = DayType(10, 1, 12, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        
        total = sum([
            Timeslice(season="X", daytype=dt, dailytimebracket=dtb).year_fraction(2020)
            for dt in [dt1, dt2, dt3, dt4]
        ])
        
        assert abs(total - 1.0) < 1e-10
    
    # ========== Leap Year Handling ==========
    
    def test_leap_year_february(self):
        """Test leap year handling for February timeslices."""
        dt = DayType(2, 1, 2, 29)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        # Leap year: 29 days
        assert ts.duration_hours(2020) == 29 * 24
        
        # Non-leap year: 28 days
        assert ts.duration_hours(2021) == 28 * 24
    
    def test_leap_year_february_29(self):
        """Test specific Feb 29 timeslice."""
        dt = DayType(2, 29, 2, 29)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        # Leap year: exists
        assert ts.contains_timestamp(datetime(2020, 2, 29, 12, 0, 0))
        assert ts.duration_hours(2020) == 24
        
        # Non-leap year: doesn't exist (falls back to Feb 28)
        assert ts.duration_hours(2021) == 0  # Day 29 doesn't exist
    
    def test_leap_year_consistency(self):
        """Test that leap year handling is consistent."""
        dt_full = DayType(1, 1, 12, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season="X", daytype=dt_full, dailytimebracket=dtb)
        
        # Leap years: 2000, 2020, 2024
        for year in [2000, 2020, 2024]:
            assert ts.duration_hours(year) == 366 * 24
        
        # Non-leap years: 2001, 2021, 2100 (not divisible by 400)
        for year in [2001, 2021, 2100]:
            assert ts.duration_hours(year) == 365 * 24
    
    # ========== Hashing and Equality ==========
    
    def test_hashing(self):
        """Test Timeslice hashing."""
        dt = DayType(6, 15, 6, 15)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        ts1 = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        ts2 = Timeslice(season="X", daytype=dt, dailytimebracket=dtb)
        
        assert hash(ts1) == hash(ts2)
        
        ts_set = {ts1, ts2}
        assert len(ts_set) == 1
    
    def test_equality(self):
        """Test Timeslice equality."""
        dt1 = DayType(6, 15, 6, 15)
        dt2 = DayType(6, 15, 6, 15)
        dt3 = DayType(6, 16, 6, 16)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        
        ts1 = Timeslice(season="X", daytype=dt1, dailytimebracket=dtb)
        ts2 = Timeslice(season="X", daytype=dt2, dailytimebracket=dtb)
        ts3 = Timeslice(season="X", daytype=dt3, dailytimebracket=dtb)
        
        assert ts1 == ts2
        assert ts1 != ts3
