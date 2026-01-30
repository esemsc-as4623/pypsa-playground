# tests/test_translation/test_helpers.py

import pytest
from datetime import time, date, timedelta

from pyoscomp.translation.time.constants import ENDOFDAY
from pyoscomp.translation.time.structures import DayType, DailyTimeBracket
from pyoscomp.translation.time.translate import create_daytypes_from_dates, create_timebrackets_from_times


class TestCreateDaytypesFromDates:
    """Tests for create_daytypes_from_dates helper function."""
    
    # ========== Single Date ==========
    
    def test_single_date_mid_year(self):
        """Test single date in middle of year."""
        dates = [date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 3 daytypes: Jan 1 to Jun 14, Jun 15, Jun 16 to Dec 31
        assert len(daytypes) == 3
        
        # Verify coverage
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 6, 14)  # Before
        assert daytype_list[1] == DayType(6, 15, 6, 15)  # Target date
        assert daytype_list[2] == DayType(6, 16, 12, 31)  # After
    
    def test_single_date_jan_1(self):
        """Test single date on Jan 1."""
        dates = [date(2020, 1, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 2 daytypes: Jan 1, Jan 2 to Dec 31
        assert len(daytypes) == 2
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 1, 1)  # Jan 1
        assert daytype_list[1] == DayType(1, 2, 12, 31)  # Rest of year
    
    def test_single_date_dec_31(self):
        """Test single date on Dec 31."""
        dates = [date(2020, 12, 31)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 2 daytypes: Jan 1 to Dec 30, Dec 31
        assert len(daytypes) == 2
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 12, 30)  # Most of year
        assert daytype_list[1] == DayType(12, 31, 12, 31)  # Dec 31
    
    # ========== Consecutive Dates ==========
    
    def test_consecutive_dates(self):
        """Test consecutive dates create individual daytypes."""
        dates = [date(2020, 6, 15), date(2020, 6, 16), date(2020, 6, 17)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 5 daytypes: before, 3 individual days, after
        assert len(daytypes) == 5
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 6, 14)  # Before
        assert daytype_list[1] == DayType(6, 15, 6, 15)  # Day 1
        assert daytype_list[2] == DayType(6, 16, 6, 16)  # Day 2
        assert daytype_list[3] == DayType(6, 17, 6, 17)  # Day 3
        assert daytype_list[4] == DayType(6, 18, 12, 31)  # After
    
    def test_consecutive_dates_full_week(self):
        """Test full week of consecutive dates."""
        dates = [date(2020, 3, i) for i in range(1, 8)]  # March 1-7
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, 7 individual days, after
        assert len(daytypes) == 9
        
        # Check individual days exist
        daytype_list = sorted(daytypes)
        for i, d in enumerate(range(1, 8)):
            assert daytype_list[i+1] == DayType(3, d, 3, d)
    
    # ========== Gapped Dates ==========
    
    def test_gapped_dates_simple(self):
        """Test gapped dates create gap-fill daytypes."""
        dates = [date(2020, 6, 1), date(2020, 6, 5)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Jun 1, Jun 2-4 (gap), Jun 5, after
        assert len(daytypes) == 5
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 5, 31)  # Before Jun 1
        assert daytype_list[1] == DayType(6, 1, 6, 1)  # Jun 1
        assert daytype_list[2] == DayType(6, 2, 6, 4)  # Gap: Jun 2-4
        assert daytype_list[3] == DayType(6, 5, 6, 5)  # Jun 5
        assert daytype_list[4] == DayType(6, 6, 12, 31)  # After Jun 5
    
    def test_gapped_dates_large_gap(self):
        """Test large gap between dates."""
        dates = [date(2020, 1, 15), date(2020, 12, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Jan 15, Jan 16 to Dec 14 (gap), Dec 15, after
        assert len(daytypes) == 5
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 1, 14)  # Before Jan 15
        assert daytype_list[1] == DayType(1, 15, 1, 15)  # Jan 15
        assert daytype_list[2] == DayType(1, 16, 12, 14)  # Large gap
        assert daytype_list[3] == DayType(12, 15, 12, 15)  # Dec 15
        assert daytype_list[4] == DayType(12, 16, 12, 31)  # After Dec 15
    
    def test_gapped_dates_multiple_gaps(self):
        """Test multiple gaps create multiple gap-fill daytypes."""
        dates = [date(2020, 3, 1), date(2020, 3, 5), date(2020, 3, 10)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Mar 1, gap1, Mar 5, gap2, Mar 10, after
        assert len(daytypes) == 7
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 2, 29)  # Before Mar 1
        assert daytype_list[1] == DayType(3, 1, 3, 1)  # Mar 1
        assert daytype_list[2] == DayType(3, 2, 3, 4)  # Gap 1: Mar 2-4
        assert daytype_list[3] == DayType(3, 5, 3, 5)  # Mar 5
        assert daytype_list[4] == DayType(3, 6, 3, 9)  # Gap 2: Mar 6-9
        assert daytype_list[5] == DayType(3, 10, 3, 10)  # Mar 10
        assert daytype_list[6] == DayType(3, 11, 12, 31)  # After Mar 10
    
    # ========== Start of Year Boundary ==========
    
    def test_start_of_year_jan_1(self):
        """Test that Jan 1 start doesn't create empty before-daytype."""
        dates = [date(2020, 1, 1), date(2020, 1, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: Jan 1, Jan 2-14 (gap), Jan 15, after
        assert len(daytypes) == 4
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 1, 1)  # Jan 1
        assert daytype_list[1] == DayType(1, 2, 1, 14)  # Gap
        assert daytype_list[2] == DayType(1, 15, 1, 15)  # Jan 15
        assert daytype_list[3] == DayType(1, 16, 12, 31)  # After
    
    def test_start_of_year_jan_15(self):
        """Test that Jan 15 start creates before-daytype from Jan 1."""
        dates = [date(2020, 1, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: Jan 1-14 (before), Jan 15, after
        assert len(daytypes) == 3
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 1, 14)  # Before
        assert daytype_list[1] == DayType(1, 15, 1, 15)  # Jan 15
        assert daytype_list[2] == DayType(1, 16, 12, 31)  # After
    
    def test_start_of_year_mid_year(self):
        """Test mid-year start creates full before-daytype."""
        dates = [date(2020, 6, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: Jan 1 to May 31, Jun 1, Jun 2 to Dec 31
        assert len(daytypes) == 3
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 5, 31)  # Full before
        assert daytype_list[1] == DayType(6, 1, 6, 1)  # Jun 1
        assert daytype_list[2] == DayType(6, 2, 12, 31)  # After
    
    # ========== End of Year Boundary ==========
    
    def test_end_of_year_dec_31(self):
        """Test that Dec 31 end doesn't create empty after-daytype."""
        dates = [date(2020, 12, 15), date(2020, 12, 31)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Dec 15, Dec 16-30 (gap), Dec 31
        assert len(daytypes) == 4
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 12, 14)  # Before
        assert daytype_list[1] == DayType(12, 15, 12, 15)  # Dec 15
        assert daytype_list[2] == DayType(12, 16, 12, 30)  # Gap
        assert daytype_list[3] == DayType(12, 31, 12, 31)  # Dec 31
    
    def test_end_of_year_dec_20(self):
        """Test that Dec 20 end creates after-daytype to Dec 31."""
        dates = [date(2020, 12, 20)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Dec 20, Dec 21-31 (after)
        assert len(daytypes) == 3
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 12, 19)  # Before
        assert daytype_list[1] == DayType(12, 20, 12, 20)  # Dec 20
        assert daytype_list[2] == DayType(12, 21, 12, 31)  # After
    
    def test_end_of_year_mid_year(self):
        """Test mid-year end creates full after-daytype."""
        dates = [date(2020, 6, 30)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Jun 30, Jul 1 to Dec 31
        assert len(daytypes) == 3
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 6, 29)  # Before
        assert daytype_list[1] == DayType(6, 30, 6, 30)  # Jun 30
        assert daytype_list[2] == DayType(7, 1, 12, 31)  # Full after
    
    # ========== Year-Wrapping Prevention ==========
    
    def test_year_wrapping_dec_to_jan(self):
        """Test that Dec 31 doesn't wrap to Jan 1."""
        dates = [date(2020, 12, 31), date(2021, 1, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Function normalizes to year 2000, so both become separate single days
        # Should create: before (Jan 1 to Dec 30), Dec 31, Jan 1 (already at start)
        # Since both dates normalize to same year (2000), Jan 1 and Dec 31 become consecutive
        daytype_list = sorted(daytypes)
        
        # After normalization: Jan 1 and Dec 31 in year 2000
        # Creates: Jan 1, Jan 2 to Dec 30 (gap), Dec 31
        assert len(daytypes) == 3
        assert DayType(1, 1, 1, 1) in daytypes  # Jan 1
        assert DayType(12, 31, 12, 31) in daytypes  # Dec 31
    
    def test_year_wrapping_validation(self):
        """Test that daytypes don't attempt year wrapping."""
        # Any dates that would cause year-wrapping should be prevented
        # by the function's normalization to a single year
        dates = [date(2020, 12, 25), date(2021, 1, 5)]
        daytypes = create_daytypes_from_dates(dates)
        
        # After normalization, becomes Dec 25 and Jan 5 in year 2000
        # Should not create a daytype spanning Dec 25 to Jan 5
        for dt in daytypes:
            # Verify no daytype wraps year
            start_ordinal = date(2000, dt.month_start, dt.day_start).toordinal()
            end_ordinal = date(2000, dt.month_end, dt.day_end).toordinal()
            assert start_ordinal <= end_ordinal, f"Daytype {dt} wraps year"
    
    # ========== Leap Year Dates ==========
    
    def test_leap_year_feb_29(self):
        """Test Feb 29 handling in leap year context."""
        dates = [date(2020, 2, 29)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Feb 29, after
        assert len(daytypes) == 3
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 2, 28)  # Before Feb 29
        assert daytype_list[1] == DayType(2, 29, 2, 29)  # Feb 29
        assert daytype_list[2] == DayType(3, 1, 12, 31)  # After Feb 29
    
    def test_leap_year_feb_28_29(self):
        """Test consecutive dates around Feb 29."""
        dates = [date(2020, 2, 28), date(2020, 2, 29)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: before, Feb 28, Feb 29, after
        assert len(daytypes) == 4
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1, 2, 27)  # Before
        assert daytype_list[1] == DayType(2, 28, 2, 28)  # Feb 28
        assert daytype_list[2] == DayType(2, 29, 2, 29)  # Feb 29
        assert daytype_list[3] == DayType(3, 1, 12, 31)  # After
    
    def test_leap_year_normalization(self):
        """Test that function uses leap year (2000) for normalization."""
        # Input dates from non-leap year, but Feb 29 should still be valid
        dates = [date(2021, 2, 28), date(2021, 3, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Function normalizes to year 2000 (leap year), so Feb 29 should be possible in gaps
        daytype_list = sorted(daytypes)
        
        # Should create: before, Feb 28, Feb 29 (gap), Mar 1, after
        assert len(daytypes) == 5
        assert DayType(2, 28, 2, 28) in daytypes
        assert DayType(2, 29, 2, 29) in daytypes  # Gap fill includes Feb 29
        assert DayType(3, 1, 3, 1) in daytypes
    
    # ========== Edge Cases ==========
    
    def test_duplicate_dates_ignored(self):
        """Test that duplicate dates are handled correctly."""
        dates = [date(2020, 6, 15), date(2020, 6, 15), date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should be same as single date
        assert len(daytypes) == 3
        assert DayType(6, 15, 6, 15) in daytypes
    
    def test_unsorted_dates(self):
        """Test that unsorted dates are handled correctly."""
        dates = [date(2020, 6, 20), date(2020, 6, 10), date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should produce same result as sorted dates
        daytype_list = sorted(daytypes)
        assert DayType(6, 10, 6, 10) in daytypes
        assert DayType(6, 15, 6, 15) in daytypes
        assert DayType(6, 20, 6, 20) in daytypes
    
    def test_different_input_years_normalized(self):
        """Test that dates from different years are normalized."""
        dates = [date(2020, 6, 15), date(2021, 9, 20), date(2025, 3, 10)]
        daytypes = create_daytypes_from_dates(dates)
        
        # All should be normalized to year 2000
        # Creates: before (Jan 1 to Mar 9), Mar 10, gap, Jun 15, gap, Sep 20, after
        assert DayType(3, 10, 3, 10) in daytypes
        assert DayType(6, 15, 6, 15) in daytypes
        assert DayType(9, 20, 9, 20) in daytypes
    
    # ========== Coverage Validation ==========
    
    def test_coverage_full_year_single_date(self):
        """Test that single date produces full year coverage."""
        dates = [date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Sum durations should equal full leap year
        total_days = sum(dt.duration_days(2000) for dt in daytypes)
        assert total_days == 366  # Leap year
    
    def test_coverage_full_year_multiple_dates(self):
        """Test that multiple dates produce full year coverage."""
        dates = [date(2020, 3, 10), date(2020, 6, 15), date(2020, 9, 20)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Sum durations should equal full leap year
        total_days = sum(dt.duration_days(2000) for dt in daytypes)
        assert total_days == 366
    
    def test_coverage_no_overlaps(self):
        """Test that daytypes don't overlap."""
        dates = [date(2020, 3, 10), date(2020, 6, 15), date(2020, 9, 20)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Check each date in year 2000 is covered by exactly one daytype
        coverage = {}
        for d in range(1, 367):  # All days in leap year
            test_date = date(2000, 1, 1) + timedelta(days=d-1)
            covering_daytypes = [dt for dt in daytypes if dt.contains_date(test_date)]
            coverage[test_date] = len(covering_daytypes)
            assert len(covering_daytypes) == 1, f"Date {test_date} covered by {len(covering_daytypes)} daytypes"


class TestCreateTimebracketsFromTimes:
    """Tests for create_timebrackets_from_times helper function."""
    
    # ========== Single Time ==========
    
    def test_single_time_midnight(self):
        """Test single time at midnight creates full day."""
        times = [time(0, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create one bracket: 00:00 to ENDOFDAY
        assert len(brackets) == 1
        bracket = list(brackets)[0]
        assert bracket.hour_start == time(0, 0, 0)
        assert bracket.hour_end == ENDOFDAY
        assert bracket.is_full_day()
        assert bracket.duration_hours() == 24.0
    
    def test_single_time_not_midnight(self):
        """Test single time not at midnight adds midnight bracket."""
        times = [time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create two brackets: 00:00-12:00, 12:00-ENDOFDAY
        assert len(brackets) == 2
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].hour_end == time(12, 0, 0)
        assert bracket_list[1].hour_start == time(12, 0, 0)
        assert bracket_list[1].hour_end == ENDOFDAY
    
    def test_single_time_morning(self):
        """Test single time in morning."""
        times = [time(6, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-06:00, 06:00-ENDOFDAY
        assert len(brackets) == 2
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].duration_hours() == 6.0
        assert bracket_list[1].duration_hours() == 18.0
    
    # ========== Multiple Times ==========
    
    def test_multiple_times_hourly(self):
        """Test hourly time brackets."""
        times = [time(h, 0, 0) for h in range(24)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create 24 one-hour brackets
        assert len(brackets) == 24
        
        bracket_list = sorted(brackets)
        for i, bracket in enumerate(bracket_list):
            assert bracket.hour_start == time(i, 0, 0)
            if i < 23:
                assert bracket.hour_end == time(i + 1, 0, 0)
            else:
                assert bracket.hour_end == ENDOFDAY
            assert bracket.duration_hours() == 1.0
    
    def test_multiple_times_irregular(self):
        """Test irregular time intervals."""
        times = [time(6, 0, 0), time(9, 30, 0), time(17, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-06:00, 06:00-09:30, 09:30-17:00, 17:00-ENDOFDAY
        assert len(brackets) == 4
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].hour_end == time(6, 0, 0)
        assert bracket_list[1].hour_start == time(6, 0, 0)
        assert bracket_list[1].hour_end == time(9, 30, 0)
        assert bracket_list[2].hour_start == time(9, 30, 0)
        assert bracket_list[2].hour_end == time(17, 0, 0)
        assert bracket_list[3].hour_start == time(17, 0, 0)
        assert bracket_list[3].hour_end == ENDOFDAY
    
    def test_multiple_times_quarter_day(self):
        """Test quarter-day time brackets."""
        times = [time(0, 0, 0), time(6, 0, 0), time(12, 0, 0), time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create 4 six-hour brackets
        assert len(brackets) == 4
        
        for bracket in brackets:
            assert bracket.duration_hours() == 6.0
    
    # ========== Midnight Not Included ==========
    
    def test_midnight_not_included_morning_start(self):
        """Test that midnight is auto-added when not in list."""
        times = [time(8, 0, 0), time(16, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-08:00, 08:00-16:00, 16:00-ENDOFDAY
        assert len(brackets) == 3
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].hour_end == time(8, 0, 0)
    
    def test_midnight_not_included_afternoon_start(self):
        """Test midnight auto-add with afternoon start."""
        times = [time(14, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-14:00, 14:00-ENDOFDAY
        assert len(brackets) == 2
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].duration_hours() == 14.0
        assert bracket_list[1].duration_hours() == 10.0
    
    def test_midnight_already_included(self):
        """Test that explicit midnight doesn't create duplicate."""
        times = [time(0, 0, 0), time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-12:00, 12:00-ENDOFDAY (no duplicate midnight)
        assert len(brackets) == 2
    
    # ========== ENDOFDAY for Last Bracket ==========
    
    def test_endofday_single_time(self):
        """Test ENDOFDAY used for last bracket with single time."""
        times = [time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        assert last_bracket.hour_start == time(18, 0, 0)
        assert last_bracket.hour_end == ENDOFDAY
        assert last_bracket.duration_hours() == 6.0
    
    def test_endofday_multiple_times(self):
        """Test ENDOFDAY used for last bracket with multiple times."""
        times = [time(6, 0, 0), time(12, 0, 0), time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        assert last_bracket.hour_start == time(18, 0, 0)
        assert last_bracket.hour_end == ENDOFDAY
    
    def test_endofday_late_evening_start(self):
        """Test ENDOFDAY with late evening start time."""
        times = [time(23, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        assert last_bracket.hour_start == time(23, 0, 0)
        assert last_bracket.hour_end == ENDOFDAY
        assert last_bracket.duration_hours() == 1.0
    
    def test_endofday_inclusive(self):
        """Test that ENDOFDAY makes bracket inclusive to last moment of day."""
        times = [time(22, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        # Should contain time 23:59:59
        assert last_bracket.contains_time(time(23, 59, 59))
    
    # ========== Edge Cases ==========
    
    def test_duplicate_times_ignored(self):
        """Test that duplicate times are handled correctly."""
        times = [time(6, 0, 0), time(6, 0, 0), time(12, 0, 0), time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should be same as without duplicates
        assert len(brackets) == 3
    
    def test_unsorted_times(self):
        """Test that unsorted times are handled correctly."""
        times = [time(18, 0, 0), time(6, 0, 0), time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should produce correct sorted brackets
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[1].hour_start == time(6, 0, 0)
        assert bracket_list[2].hour_start == time(12, 0, 0)
        assert bracket_list[3].hour_start == time(18, 0, 0)
    
    def test_sub_hourly_precision(self):
        """Test sub-hourly time precision."""
        times = [time(9, 15, 0), time(9, 30, 0), time(9, 45, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create fine-grained brackets
        bracket_list = sorted(brackets)
        
        # Find the 15-minute brackets
        for i in range(len(bracket_list) - 1):
            if bracket_list[i].hour_start == time(9, 15, 0):
                assert bracket_list[i].hour_end == time(9, 30, 0)
                assert bracket_list[i].duration_hours() == 0.25
    
    def test_seconds_precision(self):
        """Test second-level time precision."""
        times = [time(10, 0, 0), time(10, 0, 30)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        
        # Find the 30-second bracket
        for bracket in bracket_list:
            if bracket.hour_start == time(10, 0, 0) and bracket.hour_end == time(10, 0, 30):
                assert abs(bracket.duration_hours() - 30/3600) < 1e-10
    
    # ========== Coverage Validation ==========
    
    def test_coverage_full_day_single_time(self):
        """Test that single time produces full 24-hour coverage."""
        times = [time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        total_hours = sum(b.duration_hours() for b in brackets)
        assert abs(total_hours - 24.0) < 1e-10
    
    def test_coverage_full_day_multiple_times(self):
        """Test that multiple times produce full 24-hour coverage."""
        times = [time(3, 0, 0), time(9, 0, 0), time(15, 0, 0), time(21, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        total_hours = sum(b.duration_hours() for b in brackets)
        assert abs(total_hours - 24.0) < 1e-10
    
    def test_coverage_no_overlaps(self):
        """Test that brackets don't overlap."""
        times = [time(6, 0, 0), time(12, 0, 0), time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        
        # Each bracket's end should equal next bracket's start
        for i in range(len(bracket_list) - 1):
            assert bracket_list[i].hour_end == bracket_list[i + 1].hour_start
    
    def test_coverage_no_gaps(self):
        """Test that brackets cover all times in day."""
        times = [time(4, 0, 0), time(8, 0, 0), time(16, 0, 0), time(20, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Check a sample of times throughout the day
        test_times = [
            time(0, 0, 0), time(5, 0, 0), time(10, 0, 0), 
            time(15, 0, 0), time(18, 0, 0), time(22, 0, 0), time(23, 59, 59)
        ]
        
        for t in test_times:
            covering = [b for b in brackets if b.contains_time(t)]
            assert len(covering) == 1, f"Time {t} covered by {len(covering)} brackets"
    
    def test_coverage_contiguous_half_open(self):
        """Test that brackets form contiguous half-open intervals."""
        times = [time(8, 0, 0), time(12, 0, 0), time(16, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        
        # Test boundary times
        assert bracket_list[0].contains_time(time(0, 0, 0))
        assert not bracket_list[0].contains_time(time(8, 0, 0))  # Boundary belongs to next
        assert bracket_list[1].contains_time(time(8, 0, 0))
        assert not bracket_list[1].contains_time(time(12, 0, 0))
        assert bracket_list[2].contains_time(time(12, 0, 0))
        assert not bracket_list[2].contains_time(time(16, 0, 0))
        assert bracket_list[3].contains_time(time(16, 0, 0))
        assert bracket_list[3].contains_time(time(23, 59, 59))  # ENDOFDAY is inclusive
