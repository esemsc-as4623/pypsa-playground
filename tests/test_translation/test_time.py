# tests/test_translation/test_time.py

import pytest
import pandas as pd
from datetime import time, date, datetime
import calendar

from pyoscomp.translation.time.constants import ENDOFDAY
from pyoscomp.translation.time.structures import DayType, DailyTimeBracket, Timeslice
from pyoscomp.translation.time.translate import to_timeslices


class TestDayType:
    """Tests for DayType dataclass."""
    
    def test_full_year(self):
        """Test full year daytype."""
        dt = DayType(1, 1, 12, 31)
        assert dt.is_full_year()
        assert dt.name == "YEAR"
        assert dt.duration_days(2000) == 366  # Leap year
        assert dt.duration_days(2001) == 365  # Non-leap year
    
    def test_single_month(self):
        """Test single month daytype."""
        for month in range(1, 13):
            last_day = calendar.monthrange(2000, month)[1]
            dt = DayType(month, 1, month, last_day)
            assert not dt.is_full_year()
            assert dt.duration_days(2000) == last_day
            assert dt.contains_date(date(2000, month, last_day // 2))
            assert not dt.contains_date(date(2000, month+1 if month < 12 else 1, 1))
    
    def test_leap_year_handling(self):
        """Test Feb 29 handling in leap vs non-leap years."""
        dt = DayType(2, 1, 2, 29)
        
        # Leap year: Feb has 29 days
        assert dt.duration_days(2000) == 29
        start, end = dt.to_dates(2000)
        assert end == date(2000, 2, 29)
        
        # Non-leap year: Falls back to Feb 28
        assert dt.duration_days(2001) == 28
        start, end = dt.to_dates(2001)
        assert end == date(2001, 2, 28)
    
    def test_year_wrapping_prevented(self):
        """Test that year-wrapping intervals raise error."""
        with pytest.raises(ValueError, match="Year-wrapping"):
            DayType(12, 1, 2, 28)  # Dec to Feb wraps year
    
    def test_invalid_month(self):
        """Test invalid month validation."""
        with pytest.raises(ValueError, match="month_start"):
            DayType(13, 1, 12, 31)
    
    def test_invalid_day(self):
        """Test invalid day validation."""
        with pytest.raises(ValueError, match="day_start"):
            DayType(2, 30, 2, 28)  # Feb doesn't have 30 days
    
    def test_contains_date_boundary(self):
        """Test boundary conditions for contains_date."""
        dt = DayType(3, 15, 4, 20)
        
        # Boundaries (closed interval)
        assert dt.contains_date(date(2020, 3, 15))  # Start included
        assert dt.contains_date(date(2020, 4, 20))  # End included
        
        # Outside boundaries
        assert not dt.contains_date(date(2020, 3, 14))
        assert not dt.contains_date(date(2020, 4, 21))


class TestDailyTimeBracket:
    """Tests for DailyTimeBracket dataclass."""
    
    def test_full_day(self):
        """Test full day bracket."""
        dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
        assert dtb.is_full_day()
        assert dtb.name == "DAY"
        assert dtb.duration_hours() == 24.0
    
    def test_morning_bracket(self):
        """Test partial day bracket."""
        dtb = DailyTimeBracket(time(6, 0, 0), time(12, 0, 0))
        assert not dtb.is_full_day()
        assert dtb.duration_hours() == 6.0
        assert dtb.contains_time(time(9, 0, 0))
        assert not dtb.contains_time(time(12, 0, 0))  # Half-open, end excluded
    
    def test_evening_to_endofday(self):
        """Test bracket extending to end of day."""
        dtb = DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
        assert dtb.duration_hours() == 6.0
        assert dtb.contains_time(time(23, 59, 59))
        assert not dtb.contains_time(time(24, 0, 0))
        assert not dtb.contains_time(time(0, 0, 0))
    
    def test_invalid_ordering(self):
        """Test that start must be before end."""
        with pytest.raises(ValueError, match="must be before"):
            DailyTimeBracket(time(12, 0, 0), time(6, 0, 0))


# class TestTimeslice:
#     """Tests for Timeslice dataclass."""
    
#     def test_duration_hours(self):
#         """Test total duration calculation."""
#         for month in range(1, 13):
#             last_day = calendar.monthrange(2000, month)[1]
#             dt = DayType(month, 1, month, last_day)
#             dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
#             ts = Timeslice(year=2000, daytype=dt, dailytimebracket=dtb)
#             assert ts.duration_hours() == last_day * 24
    
#     def test_year_fraction(self):
#         """Test year fraction calculation."""
#         dt = DayType(1, 1, 12, 31)  # Full year
#         dtb = DailyTimeBracket(time(0, 0, 0), ENDOFDAY)  # Full day
#         ts = Timeslice(year=2000, daytype=dt, dailytimebracket=dtb)
        
#         assert abs(ts.year_fraction() - 1.0) < 0.001  # Should be ~100%
    
#     def test_contains_timestamp(self):
#         """Test timestamp containment."""
#         dt = DayType(6, 1, 6, 30)  # Month of June
#         dtb = DailyTimeBracket(time(8, 0, 0), time(18, 0, 0))  # 8AM to 6PM
#         ts = Timeslice(year=2000, daytype=dt, dailytimebracket=dtb)
        
#         # Should contain
#         assert ts.contains_timestamp(datetime(2000, 6, 15, 12, 0, 0))
        
#         # Wrong year
#         assert not ts.contains_timestamp(datetime(2001, 6, 15, 12, 0, 0))
        
#         # Wrong month
#         assert not ts.contains_timestamp(datetime(2000, 7, 15, 12, 0, 0))
        
#         # Wrong hour
#         assert not ts.contains_timestamp(datetime(2000, 6, 15, 20, 0, 0))


# class TestToTimeslices:
#     """Tests for to_timeslices function."""
    
#     def test_empty_snapshots(self):
#         """Test empty input raises error."""
#         with pytest.raises(ValueError, match="cannot be empty"):
#             to_timeslices(pd.DatetimeIndex([]))
    
#     def test_single_snapshot(self):
#         """Test single snapshot defaults to annual."""
#         snapshots = pd.DatetimeIndex(['2020-06-15'])
#         result = to_timeslices(snapshots)
        
#         assert len(result.years) == 1
#         assert len(result.daytypes) == 1
#         assert list(result.daytypes)[0].is_full_year()
#         assert len(result.dailytimebrackets) == 1
#         assert list(result.dailytimebrackets)[0].is_full_day()
    
#     def test_annual_resolution(self):
#         """Test annual resolution snapshots."""
#         snapshots = pd.DatetimeIndex(['2020-01-01', '2025-01-01', '2030-01-01'])
#         result = to_timeslices(snapshots)
        
#         assert result.years == [2020, 2025, 2030]
#         assert len(result.daytypes) == 1
#         assert len(result.dailytimebrackets) == 1
#         assert len(result.timeslices) == 3  # One per year
    
#     def test_irregular_annual_spacing(self):
#         """Test multi-year with irregular spacing."""
#         snapshots = pd.DatetimeIndex(['2020-01-01', '2030-01-01', '2050-01-01'])
#         result = to_timeslices(snapshots)
        
#         assert result.years == [2020, 2030, 2050]
#         # Each year should have one timeslice
#         year_counts = {}
#         for ts in result.timeslices:
#             year_counts[ts.year] = year_counts.get(ts.year, 0) + 1
#         assert year_counts == {2020: 1, 2030: 1, 2050: 1}
    
#     def test_monthly_resolution(self):
#         """Test monthly resolution snapshots."""
#         # First of each month in 2020
#         snapshots = pd.date_range('2020-01-01', periods=12, freq='MS')
#         result = to_timeslices(snapshots)
        
#         assert len(result.years) == 1
#         assert len(result.daytypes) == 12  # One per month
#         assert len(result.dailytimebrackets) == 1 # Full day
#         assert len(result.timeslices) == 12
#         assert result.validate_coverage(2020)  # Should cover full year
    
#     def test_daily_resolution(self):
#         """Test daily resolution for one week."""
#         snapshots = pd.date_range('2020-06-01', periods=7, freq='D')
#         result = to_timeslices(snapshots)
        
#         assert len(result.daytypes) == 7 # One per day
#         assert len(result.dailytimebrackets) == 1 # Full day
#         assert len(result.timeslices) == 7
#         # Verify coverage
#         assert result.validate_coverage(2020) == False  # Only covers 1 week!
    
#     def test_hourly_resolution_single_day(self):
#         """Test hourly resolution for a single day."""
#         snapshots = pd.date_range('2020-06-15', periods=24, freq='H')
#         result = to_timeslices(snapshots)
        
#         assert len(result.daytypes) == 1  # Just one day
#         assert len(result.dailytimebrackets) == 24  # 24 hours
#         assert len(result.timeslices) == 24
    
#     def test_hourly_resolution_full_year(self):
#         """Test hourly resolution for full year."""
#         snapshots = pd.date_range('2020-01-01', periods=8784, freq='H')  # Leap year
#         result = to_timeslices(snapshots, max_daytypes=366)
        
#         assert len(result.years) == 1
#         # Should aggregate to reasonable number
#         assert len(result.daytypes) <= 366
#         assert len(result.dailytimebrackets) == 24
#         assert len(result.timeslices) == len(result.daytypes) * 24
#         assert result.validate_coverage(2020)  # Full year coverage
    
#     def test_coverage_validation(self):
#         """Test that full year coverage validates correctly."""
#         # Create full year hourly snapshots
#         snapshots = pd.date_range('2020-01-01', periods=8784, freq='H')
#         result = to_timeslices(snapshots, max_daytypes=12)  # Monthly aggregation
        
#         # Should cover the full year
#         total_hours = sum(ts.duration_hours() for ts in result.timeslices)
#         assert abs(total_hours - 8784) < 1  # Leap year
    
#     def test_snapshot_mapping(self):
#         """Test that all snapshots map to timeslices."""
#         snapshots = pd.date_range('2020-06-01', periods=48, freq='H')
#         result = to_timeslices(snapshots)
        
#         # Every snapshot should map to exactly one timeslice
#         assert len(result.snapshot_to_timeslice) == len(snapshots)
#         for snapshot in snapshots:
#             assert snapshot in result.snapshot_to_timeslice
    
#     def test_multi_year_hourly(self):
#         """Test multi-year with hourly data."""
#         # 2 days from each of 3 years
#         snapshots = pd.concat([
#             pd.date_range('2020-06-15', periods=48, freq='H'),
#             pd.date_range('2025-06-15', periods=48, freq='H'),
#             pd.date_range('2030-06-15', periods=48, freq='H'),
#         ])
#         result = to_timeslices(snapshots)
        
#         assert result.years == [2020, 2025, 2030]
#         # All years should share the same daytype structure
#         year_2020_ts = [ts for ts in result.timeslices if ts.year == 2020]
#         year_2025_ts = [ts for ts in result.timeslices if ts.year == 2025]
#         assert len(year_2020_ts) == len(year_2025_ts)


# class TestOSeMOSYSOutput:
#     """Tests for OSeMOSYS-compatible output."""
    
#     def test_dataframe_generation(self):
#         """Test OSeMOSYS dataframe generation."""
#         snapshots = pd.date_range('2020-01-01', periods=24*7, freq='H')
#         result = to_timeslices(snapshots)
        
#         dfs = result.to_osemosys_dataframes()
        
#         assert 'YEAR' in dfs
#         assert 'TIMESLICE' in dfs
#         assert 'SEASON' in dfs
#         assert 'DAYTYPE' in dfs
#         assert 'DAILYTIMEBRACKET' in dfs
#         assert 'YearSplit' in dfs
        
#         # YearSplit values for a year should sum to fraction of year covered
#         year_split_sum = dfs['YearSplit'].groupby('YEAR')['VALUE'].sum()
#         # Since we only cover 1 week, sum should be ~7/365
#         assert year_split_sum[2020] < 0.03
    
#     def test_year_split_full_year(self):
#         """Test YearSplit sums to 1 for full year coverage."""
#         snapshots = pd.date_range('2020-01-01', periods=8784, freq='H')
#         result = to_timeslices(snapshots, max_daytypes=12)
        
#         dfs = result.to_osemosys_dataframes()
#         year_split_sum = dfs['YearSplit'].groupby('YEAR')['VALUE'].sum()
        
#         assert abs(year_split_sum[2020] - 1.0) < 0.01


# class TestAggregation:
#     """Tests for time series aggregation."""
    
#     def test_mean_aggregation(self):
#         """Test mean aggregation of time series."""
#         snapshots = pd.date_range('2020-06-15', periods=24, freq='H')
#         data = pd.Series(range(24), index=snapshots)
        
#         result = to_timeslices(snapshots)
#         agg = aggregate_timeseries(data, result, method='mean')
        
#         # Each hour is its own timeslice, so mean = value
#         assert len(agg) == 24
    
#     def test_sum_aggregation(self):
#         """Test sum aggregation of time series."""
#         snapshots = pd.date_range('2020-06-15', periods=24, freq='H')
#         data = pd.Series([1] * 24, index=snapshots)
        
#         result = to_timeslices(snapshots)
#         agg = aggregate_timeseries(data, result, method='sum')
        
#         total = agg['VALUE'].sum()
#         assert total == 24


# class TestEdgeCases:
#     """Tests for edge cases and corner cases."""
    
#     def test_dst_transition(self):
#         """Test handling of daylight saving time transitions."""
#         # Spring forward in 2020 US: March 8
#         snapshots = pd.date_range(
#             '2020-03-08', periods=24, freq='H', 
#             tz='America/New_York'
#         )
#         # Convert to UTC to avoid DST issues
#         snapshots_utc = snapshots.tz_convert('UTC').tz_localize(None)
        
#         result = to_timeslices(snapshots_utc)
#         assert len(result.snapshot_to_timeslice) == 24
    
#     def test_leap_second(self):
#         """Test that leap seconds don't cause issues."""
#         # Normal timestamp near potential leap second
#         snapshots = pd.DatetimeIndex([
#             '2020-06-30 23:59:59',
#             '2020-07-01 00:00:00',
#         ])
#         result = to_timeslices(snapshots)
#         assert len(result.timeslices) >= 1
    
#     def test_midnight_boundary(self):
#         """Test handling of midnight boundaries."""
#         snapshots = pd.DatetimeIndex([
#             '2020-06-15 00:00:00',
#             '2020-06-16 00:00:00',
#         ])
#         result = to_timeslices(snapshots)
        
#         # Both should map to different daytypes or same daytype
#         ts1 = result.snapshot_to_timeslice[snapshots[0]]
#         ts2 = result.snapshot_to_timeslice[snapshots[1]]
        
#         # June 15 and June 16 should be in different daytypes
#         assert ts1.daytype != ts2.daytype