# tests/test_translation/test_time/test_to_timeslices.py

import pytest
import pandas as pd
from datetime import time

from pyoscomp.constants import ENDOFDAY
from pyoscomp.translation.time.structures import DayType
from pyoscomp.translation.time.translate import to_timeslices, TimesliceResult


class TestToTimeslicesHourlySingleDay:
    """Integration tests for hourly snapshots within a single day."""
    
    def test_hourly_single_day_full_24h(self):
        """Test 24 hourly snapshots for one full day."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert isinstance(result, TimesliceResult)
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before (Jan 1 - Jun 14), Jun 15, after (Jun 16 - Dec 31)
        assert len(result.daytypes) == 3
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 6, 14)
        assert daytypes_list[1] == DayType(6, 15, 6, 15)
        assert daytypes_list[2] == DayType(6, 16, 12, 31)
        
        # Verify timebrackets: 24 hourly brackets
        assert len(result.dailytimebrackets) == 24
        brackets_list = sorted(result.dailytimebrackets)
        for i, bracket in enumerate(brackets_list):
            assert bracket.hour_start == time(i, 0, 0)
            if i < 23:
                assert bracket.hour_end == time(i + 1, 0, 0)
            else:
                assert bracket.hour_end == ENDOFDAY
        
        # Verify total timeslices = daytypes × timebrackets
        assert len(result.timeslices) == 3 * 24
        assert len(result.timeslices) == 72
        
        # Verify mapping
        assert len(result.snapshot_to_timeslice) == 24
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
    
    def test_hourly_single_day_partial_12h(self):
        """Test 12 hourly snapshots for half day (00:00 to 11:00)."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=12, freq='h')
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: 3 (before, Jun 15, after)
        assert len(result.daytypes) == 3
        
        # Verify timebrackets: 12 hourly brackets
        assert len(result.dailytimebrackets) == 12
        brackets_list = sorted(result.dailytimebrackets)
        for i, bracket in enumerate(brackets_list):
            assert bracket.hour_start == time(i, 0, 0)
            if i < 11:
                assert bracket.hour_end == time(i + 1, 0, 0)
            else:
                assert bracket.hour_end == ENDOFDAY
        
        # Verify total timeslices = 3 daytypes × 12 timebrackets
        assert len(result.timeslices) == 3 * 12
        assert len(result.timeslices) == 36
    
    def test_hourly_single_day_with_gaps(self):
        """Test hourly snapshots with gaps (e.g., every 3 hours)."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=8, freq='3h')
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: 3
        assert len(result.daytypes) == 3
        
        # Verify timebrackets: 8 brackets (00:00, 03:00, 06:00, ..., 21:00)
        assert len(result.dailytimebrackets) == 8
        brackets_list = sorted(result.dailytimebrackets)
        expected_hours = [0, 3, 6, 9, 12, 15, 18, 21]
        for i, bracket in enumerate(brackets_list):
            assert bracket.hour_start == time(expected_hours[i], 0, 0)
            if i < 7:
                assert bracket.hour_end == time(expected_hours[i + 1], 0, 0)
            else:
                assert bracket.hour_end == ENDOFDAY
        
        # Verify total timeslices
        assert len(result.timeslices) == 3 * 8
        assert len(result.timeslices) == 24


class TestToTimeslicesHourlyMultipleDays:
    """Integration tests for hourly snapshots spanning multiple days."""
    
    def test_hourly_two_consecutive_days(self):
        """Test 48 hourly snapshots for two consecutive days."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=48, freq='h')
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before (Jan 1 - Jun 14), Jun 15, Jun 16, after (Jun 17 - Dec 31)
        assert len(result.daytypes) == 4
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 6, 14)
        assert daytypes_list[1] == DayType(6, 15, 6, 15)
        assert daytypes_list[2] == DayType(6, 16, 6, 16)
        assert daytypes_list[3] == DayType(6, 17, 12, 31)
        
        # Verify timebrackets: 24 hourly brackets
        assert len(result.dailytimebrackets) == 24
        
        # Verify total timeslices = 4 daytypes × 24 timebrackets
        assert len(result.timeslices) == 4 * 24
        assert len(result.timeslices) == 96
        
        # Verify mapping
        assert len(result.snapshot_to_timeslice) == 48
    
    def test_hourly_full_week(self):
        """Test hourly snapshots for a full week (7 days)."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=168, freq='h')  # 7 * 24
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before (Jan 1 - Jun 14), 7 individual days, after (Jun 22 - Dec 31)
        assert len(result.daytypes) == 9
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 6, 14)
        for i in range(7):
            assert daytypes_list[i + 1] == DayType(6, 15 + i, 6, 15 + i)
        assert daytypes_list[8] == DayType(6, 22, 12, 31)
        
        # Verify timebrackets: 24 hourly brackets
        assert len(result.dailytimebrackets) == 24
        
        # Verify total timeslices = 9 daytypes × 24 timebrackets
        assert len(result.timeslices) == 9 * 24
        assert len(result.timeslices) == 216
    
    def test_hourly_multiple_days_different_hours_each_day(self):
        """Test hourly snapshots that start at different hours on different days."""
        # Day 1: 00:00-23:00, Day 2: 06:00-23:00, Day 3: 12:00-23:00
        day1 = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        day2 = pd.date_range('2020-06-16 06:00', periods=18, freq='h')
        day3 = pd.date_range('2020-06-17 12:00', periods=12, freq='h')
        snapshots = pd.DatetimeIndex(list(day1) + list(day2) + list(day3))
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: 4 (before, Jun 15-17, after)
        assert len(result.daytypes) == 5
        
        # Verify timebrackets: all unique times across all days
        unique_times = sorted(set(ts.time() for ts in snapshots))
        assert len(result.dailytimebrackets) == len(unique_times)


class TestToTimeslicesDailyConsecutive:
    """Integration tests for daily snapshots on consecutive days."""
    
    def test_daily_consecutive_one_week(self):
        """Test 7 consecutive daily snapshots."""
        snapshots = pd.date_range('2020-06-15', periods=7, freq='D')
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before (Jan 1 - Jun 14), 7 individual days, after (Jun 22 - Dec 31)
        assert len(result.daytypes) == 9
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 6, 14)
        for i in range(7):
            assert daytypes_list[i + 1] == DayType(6, 15 + i, 6, 15 + i)
        assert daytypes_list[8] == DayType(6, 22, 12, 31)
        
        # Verify timebrackets: single full-day bracket
        assert len(result.dailytimebrackets) == 1
        bracket = list(result.dailytimebrackets)[0]
        assert bracket.hour_start == time(0, 0, 0)
        assert bracket.hour_end == ENDOFDAY
        
        # Verify total timeslices = 9 daytypes × 1 timebracket
        assert len(result.timeslices) == 9 * 1
        assert len(result.timeslices) == 9
        
        # Verify mapping
        assert len(result.snapshot_to_timeslice) == 7
    
    def test_daily_consecutive_one_month(self):
        """Test 30 consecutive daily snapshots (full month)."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before (Jan 1 - May 31), 30 individual days, after (Jul 1 - Dec 31)
        assert len(result.daytypes) == 32
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 5, 31)
        for i in range(30):
            assert daytypes_list[i + 1] == DayType(6, 1 + i, 6, 1 + i)
        assert daytypes_list[31] == DayType(7, 1, 12, 31)
        
        # Verify timebrackets: single full-day bracket
        assert len(result.dailytimebrackets) == 1
        
        # Verify total timeslices
        assert len(result.timeslices) == 32 * 1
        assert len(result.timeslices) == 32
    
    def test_daily_consecutive_spanning_month_boundary(self):
        """Test daily snapshots spanning month boundary."""
        # June 28 - July 2 (5 days spanning June/July)
        snapshots = pd.date_range('2020-06-28', periods=5, freq='D')
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before, 5 individual days, after
        assert len(result.daytypes) == 7
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 6, 27)
        assert daytypes_list[1] == DayType(6, 28, 6, 28)
        assert daytypes_list[2] == DayType(6, 29, 6, 29)
        assert daytypes_list[3] == DayType(6, 30, 6, 30)
        assert daytypes_list[4] == DayType(7, 1, 7, 1)
        assert daytypes_list[5] == DayType(7, 2, 7, 2)
        assert daytypes_list[6] == DayType(7, 3, 12, 31)
        
        # Verify total timeslices
        assert len(result.timeslices) == 7


class TestToTimeslicesDailyGapped:
    """Integration tests for daily snapshots with gaps."""
    
    def test_daily_gapped_simple(self):
        """Test daily snapshots with simple gap (e.g., Jun 1 and Jun 5)."""
        snapshots = pd.DatetimeIndex(['2020-06-01', '2020-06-05'])
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before (Jan 1 - May 31), Jun 1, gap (Jun 2-4), Jun 5, after (Jun 6 - Dec 31)
        assert len(result.daytypes) == 5
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 5, 31)
        assert daytypes_list[1] == DayType(6, 1, 6, 1)
        assert daytypes_list[2] == DayType(6, 2, 6, 4)  # Gap
        assert daytypes_list[3] == DayType(6, 5, 6, 5)
        assert daytypes_list[4] == DayType(6, 6, 12, 31)
        
        # Verify timebrackets: single full-day bracket
        assert len(result.dailytimebrackets) == 1
        
        # Verify total timeslices
        assert len(result.timeslices) == 5 * 1
        assert len(result.timeslices) == 5
        
        # Verify mapping
        assert len(result.snapshot_to_timeslice) == 2
    
    def test_daily_gapped_multiple_gaps(self):
        """Test daily snapshots with multiple gaps."""
        snapshots = pd.DatetimeIndex([
            '2020-03-01', '2020-03-05',  # 3-day gap
            '2020-06-01', '2020-06-10',  # 8-day gap
            '2020-09-01'                  # Large gap
        ])
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before, Mar 1, gap1, Mar 5, gap2, Jun 1, gap3, Jun 10, gap4, Sep 1, after
        assert len(result.daytypes) == 11
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 2, 29)  # Before Mar 1
        assert daytypes_list[1] == DayType(3, 1, 3, 1)   # Mar 1
        assert daytypes_list[2] == DayType(3, 2, 3, 4)   # Gap: Mar 2-4
        assert daytypes_list[3] == DayType(3, 5, 3, 5)   # Mar 5
        assert daytypes_list[4] == DayType(3, 6, 5, 31)  # Gap: Mar 6 - May 31
        assert daytypes_list[5] == DayType(6, 1, 6, 1)   # Jun 1
        assert daytypes_list[6] == DayType(6, 2, 6, 9)   # Gap: Jun 2-9
        assert daytypes_list[7] == DayType(6, 10, 6, 10) # Jun 10
        assert daytypes_list[8] == DayType(6, 11, 8, 31) # Gap: Jun 11 - Aug 31
        assert daytypes_list[9] == DayType(9, 1, 9, 1)   # Sep 1
        assert daytypes_list[10] == DayType(9, 2, 12, 31) # After Sep 1
        
        # Verify total timeslices
        assert len(result.timeslices) == 11
    
    def test_daily_gapped_large_gap(self):
        """Test daily snapshots with very large gap (multiple months)."""
        snapshots = pd.DatetimeIndex(['2020-01-15', '2020-11-15'])
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before, Jan 15, gap, Nov 15, after
        assert len(result.daytypes) == 5
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 1, 14)
        assert daytypes_list[1] == DayType(1, 15, 1, 15)
        assert daytypes_list[2] == DayType(1, 16, 11, 14)  # Large gap
        assert daytypes_list[3] == DayType(11, 15, 11, 15)
        assert daytypes_list[4] == DayType(11, 16, 12, 31)
        
        # Verify total timeslices
        assert len(result.timeslices) == 5


class TestToTimeslicesAnnualMultiYear:
    """Integration tests for annual snapshots across multiple years."""
    
    def test_annual_two_consecutive_years(self):
        """Test annual snapshots for two consecutive years."""
        snapshots = pd.DatetimeIndex(['2020-01-01', '2021-01-01'])
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020, 2021]
        assert result.validate_coverage()
        
        # Verify daytypes: Jan 1, Jan 2 - Dec 31
        assert len(result.daytypes) == 2
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 1, 1)
        assert daytypes_list[1] == DayType(1, 2, 12, 31)
        
        # Verify timebrackets: single full-day bracket
        assert len(result.dailytimebrackets) == 1
        
        # Verify total timeslices
        assert len(result.timeslices) == 2 * 1
        assert len(result.timeslices) == 2
        
        # Verify mapping
        assert len(result.snapshot_to_timeslice) == 2
    
    def test_annual_five_consecutive_years(self):
        """Test annual snapshots for five consecutive years."""
        snapshots = pd.DatetimeIndex([
            '2020-01-01', '2021-01-01', '2022-01-01', 
            '2023-01-01', '2024-01-01'
        ])
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020, 2021, 2022, 2023, 2024]
        assert result.validate_coverage()
        
        # Verify daytypes: Jan 1, Jan 2 - Dec 31
        assert len(result.daytypes) == 2
        
        # Verify total timeslices
        assert len(result.timeslices) == 2
    
    def test_annual_gapped_years(self):
        """Test annual snapshots with gaps (e.g., 2020, 2022, 2025)."""
        snapshots = pd.DatetimeIndex(['2020-01-01', '2022-01-01', '2025-01-01'])
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        # Note: gaps in years mean intervening years are not in result.years
        assert result.years == [2020, 2022, 2025]
        assert result.validate_coverage()
        
        # Verify daytypes: Jan 1, Jan 2 - Dec 31
        assert len(result.daytypes) == 2
        
        # Verify total timeslices
        assert len(result.timeslices) == 2
    
    def test_annual_mid_year_snapshots(self):
        """Test annual snapshots at mid-year (e.g., June 30)."""
        snapshots = pd.DatetimeIndex([
            '2020-06-30', '2021-06-30', '2022-06-30'
        ])
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020, 2021, 2022]
        assert result.validate_coverage()
        
        # Verify daytypes: before, Jun 30, after
        assert len(result.daytypes) == 3
        daytypes_list = sorted(result.daytypes)
        assert daytypes_list[0] == DayType(1, 1, 6, 29)
        assert daytypes_list[1] == DayType(6, 30, 6, 30)
        assert daytypes_list[2] == DayType(7, 1, 12, 31)
        
        # Verify total timeslices
        assert len(result.timeslices) == 3


class TestToTimeslicesMixedTimes:
    """Integration tests for snapshots at mixed times (00:00, 12:00, etc.)."""
    
    def test_mixed_times_two_times_per_day(self):
        """Test snapshots at 00:00 and 12:00 for multiple days."""
        morning = pd.date_range('2020-06-15 00:00', periods=7, freq='D')
        noon = pd.date_range('2020-06-15 12:00', periods=7, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(noon)))
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before, 7 individual days, after
        assert len(result.daytypes) == 9
        
        # Verify timebrackets: 00:00-12:00, 12:00-24:00
        assert len(result.dailytimebrackets) == 2
        brackets_list = sorted(result.dailytimebrackets)
        assert brackets_list[0].hour_start == time(0, 0, 0)
        assert brackets_list[0].hour_end == time(12, 0, 0)
        assert brackets_list[1].hour_start == time(12, 0, 0)
        assert brackets_list[1].hour_end == ENDOFDAY
        
        # Verify total timeslices = 9 daytypes × 2 timebrackets
        assert len(result.timeslices) == 9 * 2
        assert len(result.timeslices) == 18
    
    def test_mixed_times_three_times_per_day(self):
        """Test snapshots at 00:00, 08:00, and 16:00 for multiple days."""
        time1 = pd.date_range('2020-06-15 00:00', periods=5, freq='D')
        time2 = pd.date_range('2020-06-15 08:00', periods=5, freq='D')
        time3 = pd.date_range('2020-06-15 16:00', periods=5, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(time1) + list(time2) + list(time3)))
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before, 5 individual days, after
        assert len(result.daytypes) == 7
        
        # Verify timebrackets: 00:00-08:00, 08:00-16:00, 16:00-24:00
        assert len(result.dailytimebrackets) == 3
        brackets_list = sorted(result.dailytimebrackets)
        assert brackets_list[0].hour_start == time(0, 0, 0)
        assert brackets_list[0].hour_end == time(8, 0, 0)
        assert brackets_list[1].hour_start == time(8, 0, 0)
        assert brackets_list[1].hour_end == time(16, 0, 0)
        assert brackets_list[2].hour_start == time(16, 0, 0)
        assert brackets_list[2].hour_end == ENDOFDAY
        
        # Verify total timeslices = 7 daytypes × 3 timebrackets
        assert len(result.timeslices) == 7 * 3
        assert len(result.timeslices) == 21
    
    def test_mixed_times_irregular_pattern(self):
        """Test snapshots with irregular time pattern across days."""
        # Day 1: 00:00, 06:00, 12:00
        # Day 2: 00:00, 08:00, 16:00
        # Day 3: 00:00, 12:00, 18:00
        day1 = pd.DatetimeIndex(['2020-06-15 00:00', '2020-06-15 06:00', '2020-06-15 12:00'])
        day2 = pd.DatetimeIndex(['2020-06-16 00:00', '2020-06-16 08:00', '2020-06-16 16:00'])
        day3 = pd.DatetimeIndex(['2020-06-17 00:00', '2020-06-17 12:00', '2020-06-17 18:00'])
        snapshots = pd.DatetimeIndex(sorted(list(day1) + list(day2) + list(day3)))
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before, Jun 15-17, after
        assert len(result.daytypes) == 5
        
        # Verify timebrackets: all unique times create brackets
        # Unique times: 00:00, 06:00, 08:00, 12:00, 16:00, 18:00
        assert len(result.dailytimebrackets) == 6
        
        # Verify total timeslices = 5 daytypes × 6 timebrackets
        assert len(result.timeslices) == 5 * 6
        assert len(result.timeslices) == 30
    
    def test_mixed_times_morning_evening_only(self):
        """Test snapshots only at morning (06:00) and evening (18:00)."""
        morning = pd.date_range('2020-06-01 06:00', periods=30, freq='D')
        evening = pd.date_range('2020-06-01 18:00', periods=30, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(evening)))
        result = to_timeslices(snapshots)
        
        # Validate basic properties
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Verify daytypes: before, 30 individual days, after
        assert len(result.daytypes) == 32
        
        # Verify timebrackets: 00:00-06:00, 06:00-18:00, 18:00-24:00
        assert len(result.dailytimebrackets) == 3
        brackets_list = sorted(result.dailytimebrackets)
        assert brackets_list[0].hour_start == time(0, 0, 0)
        assert brackets_list[0].hour_end == time(6, 0, 0)
        assert brackets_list[1].hour_start == time(6, 0, 0)
        assert brackets_list[1].hour_end == time(18, 0, 0)
        assert brackets_list[2].hour_start == time(18, 0, 0)
        assert brackets_list[2].hour_end == ENDOFDAY
        
        # Verify total timeslices = 32 daytypes × 3 timebrackets
        assert len(result.timeslices) == 32 * 3
        assert len(result.timeslices) == 96


class TestToTimeslicesTimesliceCountValidation:
    """Tests focused on timeslice count validation."""
    
    def test_timeslice_count_single_snapshot(self):
        """Verify timeslice count for single snapshot."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        result = to_timeslices(snapshots)
        
        n_daytypes = len(result.daytypes)
        n_timebrackets = len(result.dailytimebrackets)
        n_timeslices = len(result.timeslices)
        
        # Verify: timeslices = daytypes × timebrackets
        assert n_timeslices == n_daytypes * n_timebrackets
        assert n_daytypes == 3  # before, Jun 15, after
        assert n_timebrackets == 2  # 00:00-12:00, 12:00-24:00
        assert n_timeslices == 6
    
    def test_timeslice_count_hourly_week(self):
        """Verify timeslice count for hourly week."""
        snapshots = pd.date_range('2020-03-01 00:00', periods=168, freq='h')  # 7 days
        result = to_timeslices(snapshots)
        
        n_daytypes = len(result.daytypes)
        n_timebrackets = len(result.dailytimebrackets)
        n_timeslices = len(result.timeslices)
        
        assert n_timeslices == n_daytypes * n_timebrackets
        assert n_daytypes == 9  # before, 7 days, after
        assert n_timebrackets == 24  # 24 hours
        assert n_timeslices == 216
    
    def test_timeslice_count_daily_month(self):
        """Verify timeslice count for daily month."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        result = to_timeslices(snapshots)
        
        n_daytypes = len(result.daytypes)
        n_timebrackets = len(result.dailytimebrackets)
        n_timeslices = len(result.timeslices)
        
        assert n_timeslices == n_daytypes * n_timebrackets
        assert n_daytypes == 32  # before, 30 days, after
        assert n_timebrackets == 1  # full day
        assert n_timeslices == 32
    
    def test_timeslice_count_mixed_two_times(self):
        """Verify timeslice count for mixed times (2 times per day)."""
        morning = pd.date_range('2020-06-15 00:00', periods=10, freq='D')
        evening = pd.date_range('2020-06-15 18:00', periods=10, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(evening)))
        result = to_timeslices(snapshots)
        
        n_daytypes = len(result.daytypes)
        n_timebrackets = len(result.dailytimebrackets)
        n_timeslices = len(result.timeslices)
        
        assert n_timeslices == n_daytypes * n_timebrackets
        assert n_daytypes == 12  # before, 10 days, after
        assert n_timebrackets == 2  # 00:00-18:00, 18:00-24:00
        assert n_timeslices == 24
    
    def test_timeslice_count_multi_year_annual(self):
        """Verify timeslice count for multi-year annual snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-01-01', '2021-01-01', '2022-01-01', 
            '2023-01-01', '2024-01-01'
        ])
        result = to_timeslices(snapshots)
        
        n_daytypes = len(result.daytypes)
        n_timebrackets = len(result.dailytimebrackets)
        n_timeslices = len(result.timeslices)
        
        assert n_timeslices == n_daytypes * n_timebrackets
        assert n_daytypes == 2  # Jan 1, Jan 2 - Dec 31
        assert n_timebrackets == 1  # full day
        assert n_timeslices == 2
    
    def test_timeslice_count_leap_year(self):
        """Verify timeslice count handles leap year correctly."""
        # Feb 29 in leap year
        snapshots = pd.DatetimeIndex(['2020-02-29 00:00'])
        result = to_timeslices(snapshots)
        
        n_daytypes = len(result.daytypes)
        n_timebrackets = len(result.dailytimebrackets)
        n_timeslices = len(result.timeslices)
        
        assert n_timeslices == n_daytypes * n_timebrackets
        assert n_daytypes == 3  # before, Feb 29, after
        assert n_timebrackets == 1  # full day
        assert n_timeslices == 3
        
        # Verify coverage for leap year
        assert result.validate_coverage()
    
    def test_timeslice_count_complex_pattern(self):
        """Verify timeslice count for complex pattern."""
        # Quarterly snapshots with 3 times per day
        dates = pd.date_range('2020-01-01', periods=4, freq='QS')
        times = ['00:00', '08:00', '16:00']
        snapshots = pd.DatetimeIndex([
            f"{d.date()} {t}" for d in dates for t in times
        ])
        result = to_timeslices(snapshots)
        
        n_daytypes = len(result.daytypes)
        n_timebrackets = len(result.dailytimebrackets)
        n_timeslices = len(result.timeslices)
        
        assert n_timeslices == n_daytypes * n_timebrackets
        assert n_timebrackets == 3  # 3 time brackets
        # Daytypes: 4 days, 3 gaps, after = 9 daytypes
        assert n_daytypes == 8


class TestToTimeslicesEdgeCases:
    """Edge case tests for to_timeslices integration."""
    
    def test_empty_snapshots_raises_error(self):
        """Test that empty snapshots raise ValueError."""
        snapshots = pd.DatetimeIndex([])
        with pytest.raises(ValueError, match="snapshots cannot be empty"):
            to_timeslices(snapshots)
    
    def test_single_snapshot_at_midnight_jan_1(self):
        """Test single snapshot at start of year."""
        snapshots = pd.DatetimeIndex(['2020-01-01 00:00'])
        result = to_timeslices(snapshots)
        
        assert result.years == [2020]
        assert result.validate_coverage()
        assert len(result.daytypes) == 2  # Jan 1, Jan 2 - Dec 31
        assert len(result.dailytimebrackets) == 1
        assert len(result.timeslices) == 2
    
    def test_single_snapshot_at_end_of_year(self):
        """Test single snapshot at end of year, outside 1-minute tolerance.
        
        Note: Times within 1 minute of ENDOFDAY (23:59:59.999999) are snapped to ENDOFDAY.
        This test uses 23:58:00 which is >1 minute before ENDOFDAY, so it should create
        distinct timebrackets: [00:00, 23:58:00) and [23:58:00, ENDOFDAY).
        """
        snapshots = pd.DatetimeIndex(['2020-12-31 23:58:00'])
        result = to_timeslices(snapshots)
        
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Daytypes: Jan 1 - Dec 30, Dec 31
        assert len(result.daytypes) == 2
        
        # Timebrackets: [00:00, 23:58:00), [23:58:00, ENDOFDAY)
        assert len(result.dailytimebrackets) == 2
        
        # Total timeslices
        assert len(result.timeslices) == 2 * 2
        assert len(result.timeslices) == 4
    
    def test_unsorted_snapshots(self):
        """Test that unsorted snapshots are handled correctly."""
        snapshots = pd.DatetimeIndex([
            '2020-06-20 12:00',
            '2020-06-15 00:00',
            '2020-06-18 06:00'
        ])
        result = to_timeslices(snapshots)
        
        # Should still work correctly
        assert result.years == [2020]
        assert result.validate_coverage()
        assert len(result.snapshot_to_timeslice) == 3
    
    def test_duplicate_snapshots(self):
        """Test that duplicate snapshots are handled correctly."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 12:00',
            '2020-06-15 12:00',  # Duplicate
            '2020-06-16 12:00'
        ])
        result = to_timeslices(snapshots)
        
        # Duplicates should be removed
        assert result.years == [2020]
        assert result.validate_coverage()
        # Check that mapping only has unique snapshots
        assert len(result.snapshot_to_timeslice) == 2
    
    def test_year_boundary_crossing(self):
        """Test snapshots crossing year boundary."""
        snapshots = pd.DatetimeIndex([
            '2020-12-31 12:00',
            '2021-01-01 12:00'
        ])
        result = to_timeslices(snapshots)
        
        assert result.years == [2020, 2021]
        assert result.validate_coverage()
        # Should handle both years correctly
        assert len(result.snapshot_to_timeslice) == 2
    
    def test_leap_year_and_non_leap_year(self):
        """Test that both leap and non-leap years validate correctly."""
        # Include Feb 29 in leap year
        snapshots = pd.DatetimeIndex([
            '2020-02-29 00:00',  # Leap year
            '2021-02-28 00:00'   # Non-leap year
        ])
        result = to_timeslices(snapshots)
        
        assert result.years == [2020, 2021]
        assert result.validate_coverage()
        
        # Both years should be fully covered
        assert len(result.daytypes) == 4  # Before Feb 28/29, Feb 28, Feb 29, after
    
    def test_microsecond_precision(self):
        """Test snapshots with microsecond precision."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 12:00:00.123456',
            '2020-06-15 18:00:00.654321'
        ])
        result = to_timeslices(snapshots)
        
        assert result.years == [2020]
        assert result.validate_coverage()
        # Should handle microsecond precision correctly
        assert len(result.dailytimebrackets) == 3  # 00:00-12:00:00.123456, 12:00:00.123456-18:00:00.654321, 18:00:00.654321-24:00
    
    def test_snapshot_within_one_minute_of_endofday(self):
        """Test snapshot within 1-second tolerance of ENDOFDAY is snapped to ENDOFDAY.
        
        The implementation treats times within 1 second of ENDOFDAY (23:59:59.999999)
        as equal to ENDOFDAY to avoid tiny time slivers. This means 23:59:30 should
        create a single full-day bracket [00:00, ENDOFDAY).
        """
        # 23:59:59 is within 1-second tolerance of ENDOFDAY
        snapshots = pd.DatetimeIndex(['2020-06-15 23:59:59'])
        result = to_timeslices(snapshots)
        
        assert result.years == [2020]
        assert result.validate_coverage()
        
        # Should create single full-day bracket since 23:59:59 → ENDOFDAY
        assert len(result.dailytimebrackets) == 1
        bracket = list(result.dailytimebrackets)[0]
        assert bracket.hour_start == time(0, 0, 0)
        assert bracket.hour_end == ENDOFDAY
        
        # Daytypes: before, Jun 15, after
        assert len(result.daytypes) == 3
        
        # Total timeslices
        assert len(result.timeslices) == 3 * 1
        assert len(result.timeslices) == 3
