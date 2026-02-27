# tests/test_translation/test_structures.py

import pytest
import pandas as pd
from datetime import time, date, datetime
import calendar

from pyoscomp.constants import ENDOFDAY
from pyoscomp.translation.time.structures import Season, DayType, DailyTimeBracket, Timeslice


class TestSeason:
    """Tests for Season dataclass."""
    
    # ========== Valid Constructions ==========
    
    def test_full_year(self):
        """Test full year season."""
        s = Season(1, 12)
        assert s.is_full_year()
        assert s.name == "YEAR"
        assert s.duration_months() == 12
    
    def test_single_month(self):
        """Test single month season."""
        s = Season(6, 6)
        assert not s.is_full_year()
        assert s.is_one_month()
        assert s.duration_months() == 1
        assert s.contains_date(date(2020, 6, 15))
        assert not s.contains_date(date(2020, 5, 31))
        assert not s.contains_date(date(2020, 7, 1))
    
    def test_multi_month_span(self):
        """Test season spanning multiple months."""
        s = Season(3, 5)  # Mar to May
        assert not s.is_full_year()
        assert not s.is_one_month()
        assert s.duration_months() == 3  # 3 months
        assert s.contains_date(date(2020, 3, 1))
        assert s.contains_date(date(2020, 4, 15))
        assert s.contains_date(date(2020, 5, 31))
        assert not s.contains_date(date(2020, 2, 29))
        assert not s.contains_date(date(2020, 6, 1))

    def test_multi_month_leap(self):
        """Test season spanning multiple months including leap day."""
        s = Season(2, 3)  # Feb to Mar
        assert s.duration_months() == 2
        assert s.contains_date(date(2020, 2, 29)) # Leap day
        assert s.contains_date(date(2020, 2, 28))
        assert s.contains_date(date(2021, 2, 28))
        assert s.contains_date(date(2020, 3, 1))
        assert s.contains_date(date(2021, 3, 1))

    # ========== Validation Errors ==========
    
    def test_year_wrapping_prevented(self):
        """Test that year-wrapping intervals raise error."""
        with pytest.raises(ValueError, match="Year-wrapping"):
            Season(12, 2)  # Dec to Feb wraps year
        
        with pytest.raises(ValueError, match="Year-wrapping"):
            Season(12, 1)  # Dec 31 to Jan 1 wraps
    
    def test_invalid_month_start(self):
        """Test invalid month_start validation."""
        with pytest.raises(ValueError, match="month_start"):
            Season(0, 1)
        
        with pytest.raises(ValueError, match="month_start"):
            Season(13, 1)
    
    def test_invalid_month_end(self):
        """Test invalid month_end validation."""
        with pytest.raises(ValueError, match="month_end"):
            Season(1, 0)
        
        with pytest.raises(ValueError, match="month_end"):
            Season(1, 13)
    
    # ========== Boundary Cases ==========
    
    def test_january_first(self):
        """Test January 1st boundary."""
        s = Season(1, 1)
        assert s.contains_date(date(2020, 1, 1))
        assert not s.contains_date(date(2019, 12, 31))
        assert s.contains_date(date(2020, 1, 2))
    
    def test_december_31st(self):
        """Test December 31st boundary."""
        s = Season(12, 12)
        assert s.contains_date(date(2020, 12, 31))
        assert s.contains_date(date(2020, 12, 30))
        assert not s.contains_date(date(2021, 1, 1))
    
    def test_february_29_leap_year(self):
        """Test Feb 29 in leap year."""
        s = Season(2, 2)
        
        # Leap year: Feb 29 exists
        assert s.contains_date(date(2000, 2, 29))
        assert s.contains_date(date(2020, 2, 29))
    
#     # ========== contains_date() Accuracy ==========
    
    def test_contains_date_closed_interval(self):
        """Test that contains_date uses closed interval [start, end]."""
        s = Season(3, 4)
        
        # Boundaries (closed interval)
        assert s.contains_date(date(2020, 3, 1))  # Start included
        assert s.contains_date(date(2020, 4, 30))  # End included
        
        # Just outside boundaries
        assert not s.contains_date(date(2020, 2, 29))  # Before start
        assert not s.contains_date(date(2020, 5, 1))   # After end
        
        # Well inside
        assert s.contains_date(date(2020, 3, 20))
        assert s.contains_date(date(2020, 4, 1))
        assert s.contains_date(date(2020, 4, 15))
    
    def test_contains_date_different_year(self):
        """Test contains_date with dates from different years."""
        s = Season(6, 6)
        
        # Same daytype, different years - all should match
        assert s.contains_date(date(2000, 6, 15))
        assert s.contains_date(date(2020, 6, 15))
        assert s.contains_date(date(2025, 6, 15))
    
#     # ========== duration_months() Correctness ==========
    
    def test_duration_days_full_months(self):
        """Test duration for full months."""
        # January (31 days)
        s = Season(1, 1)
        assert s.duration_months() == 1
        
        # April (30 days)
        s = Season(4, 4)
        assert s.duration_months() == 1
        
        # February in leap year (29 days)
        s = Season(2, 2)
        assert s.duration_months() == 1
    
    def test_duration_months_multi_month(self):
        """Test duration spanning multiple months."""
        # Q1: Jan + Feb + Mar
        s = Season(1, 3)
        assert s.duration_months() == 3

    def test_duration_months_full_year(self):
        """Test duration for full year."""
        s = Season(1, 12)
        assert s.duration_months() == 12

    # ========== Sorting and Hashing ==========
    
    def test_sorting(self):
        """Test Season sorting by start month."""
        s1 = Season(1, 1)
        s2 = Season(3, 4)
        s3 = Season(6, 6)
        s4 = Season(12, 12)
        
        unsorted = [s3, s1, s4, s2]
        sorted_seasons = sorted(unsorted)
        
        assert sorted_seasons == [s1, s2, s3, s4]
    
    def test_hashing(self):
        """Test Season hashing for set operations."""
        s1 = Season(1, 1)
        s2 = Season(1, 1)  # Same as s1
        s3 = Season(2, 2)
        
        # Same seasons should hash to same value
        assert hash(s1) == hash(s2)
        
        # Can be used in sets
        s_set = {s1, s2, s3}
        assert len(s_set) == 2  # s1 and s2 are duplicates
    
    def test_equality(self):
        """Test Season equality."""
        s1 = Season(3, 4)
        s2 = Season(3, 4)
        s3 = Season(3, 5)
        
        assert s1 == s2
        assert s1 != s3
        assert not (s1 == "not a season")


class TestDayType:
    """Tests for DayType dataclass."""
    
    # ========== Valid Constructions ==========
    
    def test_single_day(self):
        """Test single day daytype."""
        dt = DayType(15, 15)
        assert dt.is_one_day()
        assert dt.duration_days(2020, 6) == 1
        assert dt.contains_date(date(2020, 6, 15))
        assert not dt.contains_date(date(2020, 6, 14))
        assert not dt.contains_date(date(2020, 6, 16))
    
    def test_multi_day_span(self):
        """Test daytype spanning multiple days."""
        dt = DayType(1, 7)
        assert dt.duration_days(2020, 6) == 7
        assert dt.contains_date(date(2020, 3, 1))
        assert dt.contains_date(date(2020, 4, 4))
        assert dt.contains_date(date(2020, 5, 7))
        assert not dt.contains_date(date(2020, 2, 29))
        assert not dt.contains_date(date(2020, 6, 8))
    
    def test_multi_day_leap(self):
        """Test daytype spanning multiple days including leap day."""
        dt = DayType(28, 31)
        assert dt.duration_days(2019, 2) == 1
        assert dt.duration_days(2020, 2) == 2  # Leap year: 28 and 29
        assert dt.duration_days(2020, 3) == 4
        assert dt.duration_days(2020, 4) == 3
        assert dt.contains_date(date(2020, 2, 28))
        assert dt.contains_date(date(2020, 2, 29)) # Leap day
        assert dt.contains_date(date(2020, 3, 31))
        assert dt.contains_date(date(2020, 4, 30))
        assert not dt.contains_date(date(2020, 2, 27))
        assert not dt.contains_date(date(2020, 3, 1))
    
    # ========== Validation Errors ==========
    
    def test_month_wrapping_prevented(self):
        """Test that month-wrapping intervals raise error."""
        with pytest.raises(ValueError, match="Month-wrapping"):
            DayType(28, 1)
        
        with pytest.raises(ValueError, match="Month-wrapping"):
            DayType(31, 1)
    
    def test_invalid_day_start(self):
        """Test invalid day_start validation."""
        with pytest.raises(ValueError, match="day_start"):
            DayType(0, 1)
        
        with pytest.raises(ValueError, match="day_start"):
            DayType(32, 1)
        
    def test_invalid_day_end(self):
        """Test invalid day_end validation."""
        with pytest.raises(ValueError, match="day_end"):
            DayType(28, 0)

        with pytest.raises(ValueError, match="day_end"):
            DayType(28, 32)
    
    # ========== Boundary Cases ==========
    
    def test_january_first(self):
        """Test January 1st boundary."""
        dt = DayType(1, 1)
        assert dt.contains_date(date(2020, 1, 1))
        assert not dt.contains_date(date(2019, 12, 31))
        assert not dt.contains_date(date(2020, 1, 2))
    
    def test_december_31st(self):
        """Test December 31st boundary."""
        dt = DayType(31, 31)
        assert dt.contains_date(date(2020, 12, 31))
        assert not dt.contains_date(date(2020, 12, 30))
        assert not dt.contains_date(date(2021, 1, 1))
    
    def test_february_29_leap_year(self):
        """Test Feb 29 in leap year."""
        dt = DayType(29, 29)
        
        # Leap year: Feb 29 exists
        assert dt.contains_date(date(2000, 2, 29))
        assert dt.contains_date(date(2020, 2, 29))
        assert dt.duration_days(2000, 2) == 1
        assert dt.duration_days(2001, 2) == 0
    
    def test_shorter_months(self):
        """Test daytypes that exceed shorter month lengths."""
        dt = DayType(30, 31)
        assert dt.duration_days(2020, 4) == 1
        start, end = dt.to_dates(2020, 4)
        assert start == date(2020, 4, 30)
        assert end == date(2020, 4, 30)

        dt = DayType(31, 31)
        assert dt.duration_days(2020, 4) == 0  # April only has 30 days
        start, end = dt.to_dates(2020, 4)
        assert start is None
        assert end is None
    
    # ========== to_dates() Method ==========
    
    def test_to_dates_leap_year(self):
        """Test to_dates() for leap year."""
        dt = DayType(29, 29)
        start, end = dt.to_dates(2000, 2)
        assert start == date(2000, 2, 29)
        assert end == date(2000, 2, 29)
    
    def test_to_dates_non_leap_year(self):
        """Test to_dates() for non-leap year."""
        dt = DayType(29, 29)
        start, end = dt.to_dates(2001, 2)
        assert start is None
        assert end is None
    
    def test_to_dates_different_years(self):
        """Test to_dates() produces correct dates for different years."""
        dt = DayType(15, 20)
        
        for year in [2000, 2001, 2020, 2025]:
            for month in range(1, 13):
                start, end = dt.to_dates(year, month)
                assert start == date(year, month, 15)
                assert end == date(year, month, 20)
    
    # ========== contains_date() Accuracy ==========
    
    def test_contains_date_closed_interval(self):
        """Test that contains_date uses closed interval [start, end]."""
        dt = DayType(15, 20)
        
        # Boundaries (closed interval)
        assert dt.contains_date(date(2020, 3, 15))  # Start included
        assert dt.contains_date(date(2020, 4, 20))  # End included
        
        # Just outside boundaries
        assert not dt.contains_date(date(2020, 3, 14))
        assert not dt.contains_date(date(2020, 4, 21))
        
        # Well inside
        assert dt.contains_date(date(2020, 3, 17))
    
    def test_contains_date_different_year(self):
        """Test contains_date with dates from different years."""
        dt = DayType(1, 7)
        
        # Same daytype, different years - all should match
        assert dt.contains_date(date(2000, 6, 7))
        assert dt.contains_date(date(2020, 6, 7))
        assert dt.contains_date(date(2025, 6, 7))
    
    # ========== duration_days() Correctness ==========
    
    def test_duration_days_single_day(self):
        """Test duration for single day."""
        dt = DayType(10, 10)
        assert dt.duration_days(2020, 5) == 1
        assert dt.duration_days(2021, 5) == 1

    def test_duration_days_max_week(self):
        """Test duration for maximum 7-day span."""
        dt = DayType(25, 31)
        assert dt.duration_days(2020, 5) == 7
        assert dt.duration_days(2021, 5) == 7

        with pytest.raises(ValueError, match="cannot exceed"):
            DayType(24, 31)
    
    def test_duration_multi_day_end_of_month(self):
        """Test duration for ends of months."""
        # January (31 days)
        dt = DayType(28, 31)
        assert dt.duration_days(2020, 1) == 4
        
        # April (30 days)
        dt = DayType(28, 31)
        assert dt.duration_days(2020, 4) == 3
        dt = DayType(28, 30)
        assert dt.duration_days(2020, 4) == 3
        
        # February in leap year (29 days)
        dt = DayType(28, 31)
        assert dt.duration_days(2020, 2) == 2
        dt = DayType(28, 29)
        assert dt.duration_days(2020, 2) == 2
        
        # February in non-leap year (28 days)
        dt = DayType(28, 31)
        assert dt.duration_days(2021, 2) == 1
        dt = DayType(28, 28)
        assert dt.duration_days(2021, 2) == 1
    
    # ========== Sorting and Hashing ==========
    
    def test_sorting(self):
        """Test DayType sorting by start date."""
        dt1 = DayType(1, 7)
        dt2 = DayType(8, 14)
        dt3 = DayType(15, 21)
        dt4 = DayType(22, 28)
        dt5 = DayType(29, 31)
        
        unsorted = [dt3, dt1, dt4, dt2, dt5]
        sorted_dts = sorted(unsorted)
        
        assert sorted_dts == [dt1, dt2, dt3, dt4, dt5]
    
    def test_hashing(self):
        """Test DayType hashing for set operations."""
        dt1 = DayType(15, 21)
        dt2 = DayType(15, 21)  # Same as dt1
        dt3 = DayType(14, 20)
        
        # Same daytypes should hash to same value
        assert hash(dt1) == hash(dt2)
        
        # Can be used in sets
        dt_set = {dt1, dt2, dt3}
        assert len(dt_set) == 2  # dt1 and dt2 are duplicates
    
    def test_equality(self):
        """Test DayType equality."""
        dt1 = DayType(15, 20)
        dt2 = DayType(15, 20)
        dt3 = DayType(15, 21)
        
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
        assert dtb.name == "T0600_to_1200"
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
        assert dtb.name == "T1800_to_2400"
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
    
    def test_name_generation_full_year_season(self):
        """Test name for full year season."""
        s = Season(1, 12)
        dt = DayType(1, 7)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        assert "YEAR" in ts.name
        assert "DAY" in ts.name
    
    def test_name_generation_specific_dates_times(self):
        """Test name generation for specific dates and times."""
        s = Season(1, 3)
        dt = DayType(8, 14)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        assert "01_to_03" in ts.name
        assert "08_to_14" in ts.name
        assert "0900" in ts.name
        assert "1700" in ts.name
    
    def test_name_generation_endofday(self):
        """Test name generation with ENDOFDAY."""
        s = Season(12, 12)
        dt = DayType(31, 31)
        dtb = DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        assert "2400" in ts.name
    
    # ========== contains_timestamp() ==========
    
    def test_contains_timestamp_basic(self):
        """Test basic timestamp containment."""
        s = Season(6, 6) # June
        dt = DayType(28, 31)
        dtb = DailyTimeBracket(time(8, 0, 0), time(18, 0, 0))  # 8AM to 6PM
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        # Should contain
        assert ts.contains_timestamp(datetime(2020, 6, 28, 8, 0, 0))
        assert ts.contains_timestamp(datetime(2020, 6, 28, 12, 0, 0))
        assert ts.contains_timestamp(datetime(2020, 6, 30, 8, 0, 0))
        assert ts.contains_timestamp(datetime(2020, 6, 30, 17, 59, 59))
        
        # Wrong month
        assert not ts.contains_timestamp(datetime(2020, 5, 28, 12, 0, 0))
        assert not ts.contains_timestamp(datetime(2020, 7, 30, 12, 0, 0))
        
        # Wrong time
        assert not ts.contains_timestamp(datetime(2020, 6, 28, 7, 59, 59))
        assert not ts.contains_timestamp(datetime(2020, 6, 28, 18, 0, 0))
        assert not ts.contains_timestamp(datetime(2020, 6, 28, 20, 0, 0))
    
    def test_contains_timestamp_different_years(self):
        """Test that timeslice pattern applies to any year."""
        s = Season(1, 1)  # January
        dt = DayType(1, 1)  # 1st
        dtb = DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))  # Morning
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        # Should work for any year
        assert ts.contains_timestamp(datetime(2000, 1, 1, 6, 0, 0))
        assert ts.contains_timestamp(datetime(2020, 1, 1, 6, 0, 0))
        assert ts.contains_timestamp(datetime(2025, 1, 1, 6, 0, 0))
    
    def test_contains_timestamp_pandas(self):
        """Test contains_timestamp with pandas Timestamp."""
        s = Season(3, 3)  # March
        dt = DayType(15, 15) # 15th
        dtb = DailyTimeBracket(time(10, 0, 0), time(11, 0, 0))
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        pd_ts = pd.Timestamp('2020-03-15 10:30:00')
        assert ts.contains_timestamp(pd_ts)
        
        pd_ts_wrong = pd.Timestamp('2020-03-15 11:30:00')
        assert not ts.contains_timestamp(pd_ts_wrong)
    
    # ========== duration_hours() and year_fraction() ==========
    
    def test_duration_hours_all_months_end_of_month(self):
        """Test duration for full year timeslice."""
        s = Season(1, 12)
        dt = DayType(25, 31)  # Last week of month
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == (7*7 + 6*4 + 5*1) * 24  # Leap year
        assert ts.duration_hours(2021) == (7*7 + 6*4 + 4*1) * 24   # Non-leap year
    
    def test_duration_hours_single_day(self):
        """Test duration for single day timeslice."""
        s = Season(6, 6)  # June
        dt = DayType(15, 15) # 15th
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == 24
    
    def test_duration_hours_partial_day(self):
        """Test duration for partial day."""
        s = Season(6, 6)  # June
        dt = DayType(15, 15)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == 8  # 8 hours per day * 1 day
    
    def test_duration_hours_multi_day(self):
        """Test duration for multiple days."""
        s = Season(6, 6)  # June
        dt = DayType(1, 7)  # 7 days
        dtb = DailyTimeBracket(time(8, 0, 0), time(20, 0, 0))  # 12 hours per day
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        assert ts.duration_hours(2020) == 7 * 12  # 84 hours
    
    def test_duration_hours_month(self):
        """Test duration for full month."""
        for month in range(1, 13):
            last_day = calendar.monthrange(2020, month)[1]
            s = Season(month, month)
            dt = DayType(last_day-6, last_day)  # Last week of month
            dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
            
            assert ts.duration_hours(2020) == 7 * 24  # 7 days * 24 hours/day
    
    def test_year_fraction_one_week_per_month(self):
        """Test year fraction for full year."""
        s = Season(1, 12)
        dt = DayType(1, 7)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        assert abs(ts.year_fraction(2020) - 7*12/366) < 1e-10
        assert abs(ts.year_fraction(2021) - 7*12/365) < 1e-10
    
    def test_year_fraction_one_hour_per_month(self):
        """Test year fraction for single hour."""
        s = Season(1, 12)
        dt = DayType(1, 1)
        dtb = DailyTimeBracket(time(0, 0, 0), time(1, 0, 0))
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        assert abs(ts.year_fraction(2020) - (12*1*1)/(366*24)) < 1e-10
        assert abs(ts.year_fraction(2021) - (12*1*1)/(365*24)) < 1e-10
    
    def test_year_fraction_consistency(self):
        """Test that year fractions sum to reasonable value."""
        s1 = Season(1, 3)
        s2 = Season(4, 6)
        s3 = Season(7, 9)
        s4 = Season(10, 12)
        dt1 = DayType(1, 7)
        dt2 = DayType(8, 14)
        dt3 = DayType(15, 21)
        dt4 = DayType(22, 28)
        dt5 = DayType(29, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        
        total_nonleap = 0
        total_leap = 0
        for s in [s1, s2, s3, s4]:
            for dt in [dt1, dt2, dt3, dt4, dt5]:
                ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
                total_nonleap += ts.year_fraction(2021)
                total_leap += ts.year_fraction(2020)
        
        assert abs(total_nonleap - 1.0) < 1e-10
        assert abs(total_leap - 1.0) < 1e-10
    
    # ========== Leap Year Handling ==========
    
    def test_leap_year_february(self):
        """Test leap year handling for February timeslices."""
        s = Season(2, 2)  # February
        dt = DayType(29, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        # Leap year
        assert ts.duration_hours(2020) == 24
        
        # Non-leap year
        assert ts.duration_hours(2021) == 0
    
    def test_leap_year_february_29(self):
        """Test specific Feb 29 timeslice."""
        s = Season(2, 2)  # February
        dt = DayType(29, 31)
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        ts = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        # Leap year: exists
        assert ts.contains_timestamp(datetime(2020, 2, 29, 12, 0, 0))
        assert ts.duration_hours(2020) == 24
        
        # Non-leap year: doesn't exist (falls back to Feb 28)
        assert ts.duration_hours(2021) == 0  # Day 29 doesn't exist
    
    # ========== Hashing and Equality ==========
    
    def test_hashing(self):
        """Test Timeslice hashing."""
        s = Season(6, 6)  # June
        dt = DayType(15, 15)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        ts1 = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        ts2 = Timeslice(season=s, daytype=dt, dailytimebracket=dtb)
        
        assert hash(ts1) == hash(ts2)
        
        ts_set = {ts1, ts2}
        assert len(ts_set) == 1
    
    def test_equality(self):
        """Test Timeslice equality."""
        s1 = Season(6, 6)  # June
        s2 = Season(6, 6)  # Same as s1
        dt1 = DayType(15, 15)
        dt2 = DayType(15, 15)
        dt3 = DayType(16, 16)
        dtb = DailyTimeBracket(time(9, 0, 0), time(17, 0, 0))
        
        ts1 = Timeslice(season=s1, daytype=dt1, dailytimebracket=dtb)
        ts2 = Timeslice(season=s2, daytype=dt2, dailytimebracket=dtb)
        ts3 = Timeslice(season=s1, daytype=dt3, dailytimebracket=dtb)
        
        assert ts1 == ts2
        assert ts1 != ts3
