# tests/test_translation/test_time/test_endpoints.py

import pytest
import pandas as pd
from datetime import date

from pyoscomp.translation.time.constants import ENDOFDAY
from pyoscomp.translation.time.translate import create_endpoints


class TestCreateEndpoints:
    """Tests for create_endpoints helper function."""
    
    # ========== Single Year Snapshots ==========
    
    def test_single_year_single_snapshot(self):
        """Test single snapshot in single year."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        # Should include: snapshot + start_of_year + end_of_year
        assert len(endpoints) == 3
        
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[1] == pd.Timestamp('2020-06-15 12:00:00')
        assert endpoints[2] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
    
    def test_single_year_multiple_snapshots(self):
        """Test multiple snapshots in single year."""
        snapshots = pd.DatetimeIndex([
            '2020-03-15 00:00:00',
            '2020-06-15 12:00:00',
            '2020-09-15 18:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should include: 3 snapshots + start_of_year + end_of_year = 5
        assert len(endpoints) == 5
        
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[1] == pd.Timestamp('2020-03-15 00:00:00')
        assert endpoints[2] == pd.Timestamp('2020-06-15 12:00:00')
        assert endpoints[3] == pd.Timestamp('2020-09-15 18:00:00')
        assert endpoints[4] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
    
    def test_single_year_hourly_snapshots(self):
        """Test hourly snapshots in single year."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        endpoints = create_endpoints(snapshots)
        
        # Should include: 24 snapshots + start_of_year + end_of_year = 26
        assert len(endpoints) == 26
        
        # Verify boundaries
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[-1] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
    
    def test_single_year_daily_snapshots(self):
        """Test daily snapshots across several months."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        endpoints = create_endpoints(snapshots)
        
        # Should include: 30 snapshots + start_of_year + end_of_year = 32
        assert len(endpoints) == 32
        
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[1] == pd.Timestamp('2020-06-01 00:00:00')
        assert endpoints[-1] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
    
    # ========== Multi-Year Snapshots ==========
    
    def test_multi_year_two_years_single_snapshot_each(self):
        """Test snapshots across two years with one snapshot per year."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 12:00:00',
            '2021-06-15 12:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should include: 2 snapshots + 2 * (start + end) = 2 + 4 = 6
        assert len(endpoints) == 6
        
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[1] == pd.Timestamp('2020-06-15 12:00:00')
        assert endpoints[2] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        assert endpoints[3] == pd.Timestamp('2021-01-01 00:00:00')
        assert endpoints[4] == pd.Timestamp('2021-06-15 12:00:00')
        assert endpoints[5] == pd.Timestamp.combine(date(2021, 12, 31), ENDOFDAY)
    
    def test_multi_year_two_years_multiple_snapshots(self):
        """Test multiple snapshots across two consecutive years."""
        snapshots = pd.DatetimeIndex([
            '2020-03-15 00:00:00',
            '2020-09-15 00:00:00',
            '2021-03-15 00:00:00',
            '2021-09-15 00:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should include: 4 snapshots + 2 * 2 year boundaries = 8
        assert len(endpoints) == 8
        
        # Verify sorting across years
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[2] == pd.Timestamp('2020-09-15 00:00:00')
        assert endpoints[3] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        assert endpoints[4] == pd.Timestamp('2021-01-01 00:00:00')
    
    def test_multi_year_gapped_years(self):
        """Test snapshots in non-consecutive years (2020, 2022, 2025)."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00:00',
            '2022-06-15 00:00:00',
            '2025-06-15 00:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should include: 3 snapshots + 3 * 2 year boundaries = 9
        assert len(endpoints) == 9
        
        # Verify all three years have boundaries
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[2] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        assert endpoints[3] == pd.Timestamp('2022-01-01 00:00:00')
        assert endpoints[5] == pd.Timestamp.combine(date(2022, 12, 31), ENDOFDAY)
        assert endpoints[6] == pd.Timestamp('2025-01-01 00:00:00')
        assert endpoints[8] == pd.Timestamp.combine(date(2025, 12, 31), ENDOFDAY)
    
    def test_multi_year_three_consecutive_years(self):
        """Test snapshots spanning three consecutive years."""
        snapshots = pd.DatetimeIndex([
            '2020-12-31 12:00:00',
            '2021-06-15 12:00:00',
            '2022-01-01 12:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should include: 3 snapshots + 3 * 2 boundaries = 9
        assert len(endpoints) == 9
        
        # Verify year boundaries for all three years
        assert pd.Timestamp('2020-01-01 00:00:00') in endpoints
        assert pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY) in endpoints
        assert pd.Timestamp('2021-01-01 00:00:00') in endpoints
        assert pd.Timestamp.combine(date(2021, 12, 31), ENDOFDAY) in endpoints
        assert pd.Timestamp('2022-01-01 00:00:00') in endpoints
        assert pd.Timestamp.combine(date(2022, 12, 31), ENDOFDAY) in endpoints
    
    def test_multi_year_many_years(self):
        """Test snapshots spanning many years."""
        snapshots = pd.DatetimeIndex([
            f'{year}-06-15 12:00:00' for year in range(2020, 2030)
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should include: 10 snapshots + 10 * 2 boundaries = 30
        assert len(endpoints) == 30
        
        # Verify first and last year boundaries
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[-1] == pd.Timestamp.combine(date(2029, 12, 31), ENDOFDAY)
    
    # ========== Year Boundary Inclusion ==========
    
    def test_year_boundary_jan_1_included(self):
        """Test that Jan 1 00:00:00 is always included."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        assert pd.Timestamp('2020-01-01 00:00:00') in endpoints
    
    def test_year_boundary_dec_31_endofday_included(self):
        """Test that Dec 31 ENDOFDAY is always included."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        expected_end = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        assert expected_end in endpoints
    
    def test_year_boundary_multiple_years_all_included(self):
        """Test that all year boundaries are included for multiple years."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 12:00:00',
            '2021-06-15 12:00:00',
            '2022-06-15 12:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Check all start boundaries
        for year in [2020, 2021, 2022]:
            assert pd.Timestamp(f'{year}-01-01 00:00:00') in endpoints
        
        # Check all end boundaries
        for year in [2020, 2021, 2022]:
            expected_end = pd.Timestamp.combine(date(year, 12, 31), ENDOFDAY)
            assert expected_end in endpoints
    
    def test_year_boundary_exact_time_components(self):
        """Test exact time components of year boundaries."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        # Start of year should be exactly midnight
        start = endpoints[0]
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
        assert start.microsecond == 0
        
        # End of year should be exactly ENDOFDAY
        end = endpoints[-1]
        assert end.hour == ENDOFDAY.hour
        assert end.minute == ENDOFDAY.minute
        assert end.second == ENDOFDAY.second
        assert end.microsecond == ENDOFDAY.microsecond
    
    def test_year_boundary_leap_year(self):
        """Test year boundaries work correctly for leap years."""
        snapshots = pd.DatetimeIndex(['2020-02-29 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        # Leap year boundaries should still be Jan 1 and Dec 31
        assert pd.Timestamp('2020-01-01 00:00:00') in endpoints
        assert pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY) in endpoints
        assert len(endpoints) == 3
    
    # ========== Deduplication and Sorting ==========
    
    def test_deduplication_duplicate_snapshots(self):
        """Test that duplicate snapshots are removed."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 12:00:00',
            '2020-06-15 12:00:00',
            '2020-06-15 12:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should have: 1 unique snapshot + 2 boundaries = 3
        assert len(endpoints) == 3
        
        # Count occurrences of the snapshot
        snapshot_count = sum(1 for ep in endpoints if ep == pd.Timestamp('2020-06-15 12:00:00'))
        assert snapshot_count == 1
    
    def test_deduplication_snapshot_at_year_start(self):
        """Test deduplication when snapshot is at Jan 1 00:00:00."""
        snapshots = pd.DatetimeIndex(['2020-01-01 00:00:00', '2020-06-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        # Snapshot at Jan 1 should merge with start_of_year boundary
        # Should have: 2 unique timestamps (Jan 1, Jun 15, Dec 31) = 3
        assert len(endpoints) == 3
        
        # Jan 1 should appear only once
        jan1_count = sum(1 for ep in endpoints if ep == pd.Timestamp('2020-01-01 00:00:00'))
        assert jan1_count == 1
    
    def test_deduplication_snapshot_at_year_end(self):
        """Test deduplication when snapshot is at Dec 31 ENDOFDAY."""
        end_of_year = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        snapshots = pd.DatetimeIndex([end_of_year, '2020-06-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        # Snapshot at Dec 31 ENDOFDAY should merge with end_of_year boundary
        # Should have: 3 unique (Jan 1, Jun 15, Dec 31 ENDOFDAY)
        assert len(endpoints) == 3
        
        # Dec 31 ENDOFDAY should appear only once
        dec31_count = sum(1 for ep in endpoints if ep == end_of_year)
        assert dec31_count == 1
    
    def test_deduplication_snapshot_at_both_boundaries(self):
        """Test deduplication when snapshots exist at both year boundaries."""
        end_of_year = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        snapshots = pd.DatetimeIndex([
            '2020-01-01 00:00:00',
            '2020-06-15 12:00:00',
            end_of_year
        ])
        endpoints = create_endpoints(snapshots)
        
        # All three should be unique: Jan 1, Jun 15, Dec 31
        assert len(endpoints) == 3
    
    def test_sorting_unsorted_snapshots(self):
        """Test that unsorted snapshots are sorted in output."""
        snapshots = pd.DatetimeIndex([
            '2020-09-15 00:00:00',
            '2020-03-15 00:00:00',
            '2020-06-15 00:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Verify sorted order
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[1] == pd.Timestamp('2020-03-15 00:00:00')
        assert endpoints[2] == pd.Timestamp('2020-06-15 00:00:00')
        assert endpoints[3] == pd.Timestamp('2020-09-15 00:00:00')
        assert endpoints[4] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
    
    def test_sorting_multi_year_unsorted(self):
        """Test sorting with unsorted multi-year snapshots."""
        snapshots = pd.DatetimeIndex([
            '2022-06-15 00:00:00',
            '2020-06-15 00:00:00',
            '2021-06-15 00:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Verify chronological order
        for i in range(len(endpoints) - 1):
            assert endpoints[i] <= endpoints[i + 1]
    
    def test_sorting_maintains_chronological_order(self):
        """Test that final list is in strict chronological order."""
        snapshots = pd.DatetimeIndex([
            '2020-12-31 23:00:00',
            '2020-01-01 01:00:00',
            '2020-06-15 12:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Check strict chronological order
        for i in range(len(endpoints) - 1):
            assert endpoints[i] <= endpoints[i + 1], \
                f"Not sorted: {endpoints[i]} > {endpoints[i + 1]}"
    
    # ========== Edge Cases ==========
    
    def test_single_snapshot_at_midnight(self):
        """Test single snapshot exactly at midnight."""
        snapshots = pd.DatetimeIndex(['2020-06-15 00:00:00'])
        endpoints = create_endpoints(snapshots)
        
        assert len(endpoints) == 3
        assert pd.Timestamp('2020-01-01 00:00:00') in endpoints
        assert pd.Timestamp('2020-06-15 00:00:00') in endpoints
        assert pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY) in endpoints
    
    def test_snapshot_with_microseconds(self):
        """Test snapshots with microsecond precision."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:30:45.123456'])
        endpoints = create_endpoints(snapshots)
        
        assert len(endpoints) == 3
        # Snapshot should be preserved with full precision
        assert pd.Timestamp('2020-06-15 12:30:45.123456') in endpoints
    
    def test_snapshots_across_year_boundary(self):
        """Test snapshots very close to year boundary."""
        end_of_year = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        snapshots = pd.DatetimeIndex([
            '2020-12-31 23:00:00',
            '2021-01-01 01:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Should include boundaries for both years
        assert pd.Timestamp('2020-01-01 00:00:00') in endpoints
        assert end_of_year in endpoints
        assert pd.Timestamp('2021-01-01 00:00:00') in endpoints
        assert pd.Timestamp.combine(date(2021, 12, 31), ENDOFDAY) in endpoints
    
    def test_empty_input_handling(self):
        """Test behavior with empty DatetimeIndex."""
        snapshots = pd.DatetimeIndex([])
        
        # Should handle gracefully - no years means no endpoints
        endpoints = create_endpoints(snapshots)
        assert len(endpoints) == 0
    
    def test_single_timestamp_full_year(self):
        """Test that single timestamp generates full year coverage."""
        snapshots = pd.DatetimeIndex(['2020-07-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        # Verify span covers full year
        assert endpoints[0] == pd.Timestamp('2020-01-01 00:00:00')
        assert endpoints[-1] == pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        
        # Time span should be ~365 days
        time_span = endpoints[-1] - endpoints[0]
        assert time_span.days == 365  # 2020 is leap year, so 366 days - 1
    
    def test_input_as_pd_index(self):
        """Test that pd.Index (not DatetimeIndex) is handled correctly."""
        snapshots = pd.Index(['2020-06-15 12:00:00', '2020-09-15 12:00:00'])
        endpoints = create_endpoints(snapshots)
        
        # Should convert to DatetimeIndex internally
        assert len(endpoints) == 4
        assert isinstance(endpoints[0], pd.Timestamp)
    
    def test_year_ordering_with_boundaries(self):
        """Test that year boundaries are properly interleaved with snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 12:00:00',
            '2021-06-15 12:00:00'
        ])
        endpoints = create_endpoints(snapshots)
        
        # Expected order: 2020-start, 2020-snapshot, 2020-end, 2021-start, 2021-snapshot, 2021-end
        expected_order = [
            pd.Timestamp('2020-01-01 00:00:00'),
            pd.Timestamp('2020-06-15 12:00:00'),
            pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY),
            pd.Timestamp('2021-01-01 00:00:00'),
            pd.Timestamp('2021-06-15 12:00:00'),
            pd.Timestamp.combine(date(2021, 12, 31), ENDOFDAY),
        ]
        
        assert endpoints == expected_order
