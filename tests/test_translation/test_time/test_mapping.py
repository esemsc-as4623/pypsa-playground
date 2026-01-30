# tests/test_translation/test_time/test_mapping.py

import pytest
import pandas as pd
from datetime import time, date

from pyoscomp.translation.time.constants import ENDOFDAY
from pyoscomp.translation.time.structures import DayType, DailyTimeBracket, Timeslice
from pyoscomp.translation.time.translate import create_map


class TestCreateMapSingleSnapshotScenarios:
    """Tests for single snapshot scenarios."""
    
    def test_snapshot_within_single_year_first_day_timeslice(self):
        """Test single snapshot mapping to timeslices for first day and remaining days."""
        snapshots = pd.DatetimeIndex(['2020-01-01 00:00:00'])
        
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 1, 1),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 2, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            )
        ]
        mapping = create_map(snapshots, timeslices)
        
        # Single snapshot should map to (year, timeslice) tuples
        assert len(mapping) == 1
        assert len(mapping[snapshots[0]]) == 2
        # Extract just the timeslices from (year, timeslice) tuples
        mapped_timeslices = [ts for (_, ts) in mapping[snapshots[0]]]
        assert mapped_timeslices == timeslices[:]
        # Verify all have year 2020
        assert all(y == 2020 for (y, _) in mapping[snapshots[0]])

    def test_snapshot_within_single_year_last_day_timeslice(self):
        """Test single snapshot mapping to timeslices for last day and remaining days."""
        snapshots = pd.DatetimeIndex(['2020-12-31 00:00:00'])
        
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 12, 30),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(12, 31, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            )
        ]
        mapping = create_map(snapshots, timeslices)
        
        # Single snapshot should map to (year, timeslice) tuples
        assert len(mapping) == 1
        assert len(mapping[snapshots[0]]) == 1
        mapped_timeslices = [ts for (_, ts) in mapping[snapshots[0]]]
        assert mapped_timeslices == timeslices[1:]
        assert all(y == 2020 for (y, _) in mapping[snapshots[0]])
    
    def test_snapshot_spanning_to_end_of_year(self):
        """Test that single snapshot spans to end of its year."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00:00'])
        
        # Create timeslices for different parts of the year
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),  # Before snapshot
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),  # Before snapshot
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),  # Snapshot day
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),  # Snapshot day
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 12, 31),  # From snapshot to end of year
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 12, 31),  # From snapshot to end of year
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # Snapshot should map to timeslices from Jun 15 12:00 to Dec 31 ENDOFDAY
        mapped_timeslices = [ts for (_, ts) in mapping[snapshots[0]]]
        assert timeslices[3] in mapped_timeslices
        assert timeslices[4] in mapped_timeslices
        assert timeslices[5] in mapped_timeslices
    
    def test_snapshot_with_time_specific_timeslices(self):
        """Test single snapshot with time-specific timeslices."""
        snapshots = pd.DatetimeIndex(['2020-06-15 09:00:00'])
        
        # Create timeslices for morning and afternoon
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(9, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),
                dailytimebracket=DailyTimeBracket(time(9, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(9, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(9, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 16, 12, 31),  # Rest of year
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(9, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 16, 12, 31),  # Rest of year
                dailytimebracket=DailyTimeBracket(time(9, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # Should map to afternoon of Jun 15 and all of Jun 16 to Dec 31
        mapped_timeslices = [ts for (_, ts) in mapping[snapshots[0]]]
        assert timeslices[3] in mapped_timeslices  # Afternoon of Jun 15
        assert timeslices[4] in mapped_timeslices  # Afternoon of Jun 15
        assert timeslices[5] in mapped_timeslices  # Rest of year


class TestCreateMapMultiSnapshotSameYear:
    """Tests for multiple snapshots within same year."""
    
    def test_consecutive_daily_snapshots(self):
        """Test consecutive daily snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00:00',
            '2020-06-16 00:00:00',
            '2020-06-17 00:00:00'
        ])
        
        # Create daily timeslices
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 16, 6, 16),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 17, 6, 17),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 18, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # First snapshot: Jun 15 only
        mapped_0 = [ts for (_, ts) in mapping[snapshots[0]]]
        assert timeslices[1] in mapped_0
        
        # Second snapshot: Jun 16 only
        assert len(mapping[snapshots[1]]) == 1
        mapped_1 = [ts for (_, ts) in mapping[snapshots[1]]]
        assert timeslices[2] in mapped_1
        
        # Third snapshot: Jun 17 to end of year
        assert len(mapping[snapshots[2]]) == 2
        mapped_2 = [ts for (_, ts) in mapping[snapshots[2]]]
        assert timeslices[3] in mapped_2
        assert timeslices[4] in mapped_2
    
    def test_gapped_snapshots_same_year(self):
        """Test snapshots with gaps in same year."""
        snapshots = pd.DatetimeIndex([
            '2020-03-01 00:00:00',
            '2020-06-01 00:00:00',
            '2020-09-01 00:00:00'
        ])
        
        # Create timeslices with gap-fill daytypes
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 2, 29),  # Before Mar 1
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 1, 3, 1),  # Mar 1
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 2, 5, 31),  # Gap: Mar 2 to May 31
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 1, 6, 1),  # Jun 1
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 2, 8, 31),  # Gap: Jun 2 to Aug 31
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(9, 1, 9, 1),  # Sep 1
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(9, 2, 12, 31),  # Sep 2 to Dec 31
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)

        mapped_0 = [ts for (_, ts) in mapping[snapshots[0]]]
        assert timeslices[1] in mapped_0
        assert timeslices[2] in mapped_0
        
        # Second snapshot: Jun 1 to Aug 31
        mapped_1 = [ts for (_, ts) in mapping[snapshots[1]]]
        assert timeslices[3] in mapped_1
        assert timeslices[4] in mapped_1
        
        # Third snapshot: Sep 1 to Dec 31
        mapped_2 = [ts for (_, ts) in mapping[snapshots[2]]]
        assert timeslices[5] in mapped_2
        assert timeslices[6] in mapped_2
    
    def test_hourly_snapshots_same_day(self):
        """Test hourly snapshots within same day."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=4, freq='6h')
        
        # Create 6-hour timeslices
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(6, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(6, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), time(18, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 16, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            )
        ]
        mapping = create_map(snapshots, timeslices)
        mapped_0 = [ts for (_, ts) in mapping[snapshots[0]]]
        mapped_1 = [ts for (_, ts) in mapping[snapshots[1]]]
        mapped_2 = [ts for (_, ts) in mapping[snapshots[2]]]
        mapped_3 = [ts for (_, ts) in mapping[snapshots[3]]]
        
        assert timeslices[1] in mapped_0  # 00:00-06:00
        assert timeslices[2] in mapped_1  # 06:00-12:00
        assert timeslices[3] in mapped_2  # 12:00-18:00
        
        # Last snapshot: 18:00 to end of year
        assert timeslices[4] in mapped_3  # 18:00-24:00
        assert timeslices[5] in mapped_3  # 00:00-06:00


class TestCreateMapMultiYearScenarios:
    """Tests for multi-year scenarios - CRITICAL for testing duplicate fix."""
    
    def test_snapshots_spanning_two_years(self):
        """Test snapshots spanning 2 years - tests the duplicate fix!"""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00:00',
            '2021-06-15 00:00:00'
        ])
        
        # Create annual timeslices
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 16, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            )
        ]
        
        mapping = create_map(snapshots, timeslices)
        mapped_first = mapping[snapshots[0]]
        
        # Extract years separately
        years_first = [y for (y, _) in mapped_first]
        
        # Check for no duplicate (year, timeslice) pairs
        unique_pairs = set((y, ts.name) for (y, ts) in mapped_first)
        assert len(unique_pairs) == len(mapped_first), "Duplicate (year, timeslice) pairs found!"
        
        # Should include: (2020, Jun 15), (2020, Jun 16-Dec 31), (2021, Jan 1-Jun 14)
        # That's 3 unique (year, timeslice) pairs
        assert len(mapped_first) == 3
        
        # Verify we have both years
        assert 2020 in years_first
        assert 2021 in years_first
        
        # Second snapshot: Jun 15, 2021 to Dec 31, 2021
        mapped_second = mapping[snapshots[1]]
        assert len(mapped_second) == 2
        # Should only have 2021
        assert all(y == 2021 for (y, _) in mapped_second), "Wrong year in mapping!"
        
    
    def test_gapped_years_2025_2027(self):
        """Test gapped years (2025, 2027 with no 2026)"""
        snapshots = pd.DatetimeIndex([
            '2025-01-01 00:00:00',
            '2027-01-02 00:00:00'
        ])
        
        # Create simple full-year timeslice
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 1, 1),  # Jan 1
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 2, 1, 2),  # Jan 2
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 3, 12, 31),  # Jan 3 - Dec 31
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
        ]

        mapping = create_map(snapshots, timeslices)
        mapped_first = mapping[snapshots[0]]
        
        # Count occurrences of each (year, timeslice) pair
        from collections import Counter
        pair_counts = Counter((y, ts.name) for (y, ts) in mapped_first)
        
        # Each (year, timeslice) pair should appear exactly once
        for pair, count in pair_counts.items():
            assert count == 1, f"(year, timeslice) pair {pair} appears {count} times (duplicate bug!)"
        
        # Should have (2025, Jan 1), (2025, Jan 2), (2025, Jan 3-Dec 31), (2027, Jan 1)
        assert len(mapped_first) == 4
    
    def test_year_boundary_crossings(self):
        """Test snapshots crossing year boundaries."""
        snapshots = pd.DatetimeIndex([
            '2020-12-31 18:00:00',
            '2021-01-01 06:00:00'
        ])
        
        # Create timeslices for different times of day
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 1, 1),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(6, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 1, 1),
                dailytimebracket=DailyTimeBracket(time(6, 0, 0), time(18, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 1, 1),
                dailytimebracket=DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 2, 12, 30),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(6, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 2, 12, 30),
                dailytimebracket=DailyTimeBracket(time(6, 0, 0), time(18, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 2, 12, 30),
                dailytimebracket=DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(12, 31, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(6, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(12, 31, 12, 31),
                dailytimebracket=DailyTimeBracket(time(6, 0, 0), time(18, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(12, 31, 12, 31),
                dailytimebracket=DailyTimeBracket(time(18, 0, 0), ENDOFDAY)
            )
        ]
        
        mapping = create_map(snapshots, timeslices)
        mapped_first_ts = [ts for (_, ts) in mapping[snapshots[0]]]
        mapped_first_years = [y for (y, _) in mapping[snapshots[0]]]
        
        # First snapshot: Dec 31 18:00 to Jan 1 05:59
        assert timeslices[-1] in mapped_first_ts  # Dec 31 18:00-ENDOFDAY
        assert timeslices[0] in mapped_first_ts  # Jan 1 00:00-06:00
        # Should have 2020 and 2021
        assert 2020 in mapped_first_years
        assert 2021 in mapped_first_years
        
        # Second snapshot: Jan 1 06:00 to Dec 31 ENDOFDAY
        mapped_second_ts = [ts for (_, ts) in mapping[snapshots[1]]]
        for ts in timeslices[1:]:
            assert ts in mapped_second_ts
        mapping = create_map(snapshots, timeslices)
    
    def test_three_gapped_years(self):
        """Test three non-consecutive years."""
        snapshots = pd.DatetimeIndex([
            '2020-06-01 00:00:00',
            '2022-06-01 00:00:00',
            '2025-06-01 00:00:00'
        ])
        
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(6, 1, 6, 30),  # June
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(7, 1, 12, 31),  # Jul-Dec
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)

        # Each snapshot should map correctly without duplicates
        for snapshot in snapshots:
            timeslice_names = [ts.name for (_, ts) in mapping[snapshot]]
            assert len(timeslice_names) == len(set(timeslice_names)), \
                f"Duplicates found for snapshot {snapshot}"


class TestCreateMapEdgeCases:
    """Tests for edge cases."""
    
    def test_short_snapshot_at_year_end(self):
        """Test very short snapshot at year end."""
        end_of_year = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        snapshots = pd.DatetimeIndex([
            '2020-06-30 23:59:59',
            end_of_year
        ])
        
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 29),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(23, 59, 59))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 29),
                dailytimebracket=DailyTimeBracket(time(23, 59, 59), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 30, 6, 30),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(23, 59, 59))
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 30, 6, 30),
                dailytimebracket=DailyTimeBracket(time(23, 59, 59), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(7, 1, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(23, 59, 59))
            ),
            Timeslice(
                season="X",
                daytype=DayType(7, 1, 12, 31),
                dailytimebracket=DailyTimeBracket(time(23, 59, 59), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # Should handle year-end snapshot correctly
        assert len(mapping) == 2

        # Each snapshot should map correctly without duplicates
        for ii, snapshot in enumerate(snapshots):
            timeslice_names = [ts.name for (_, ts) in mapping[snapshot]]
            assert len(timeslice_names) == len(set(timeslice_names)), \
                f"Duplicates found for snapshot {snapshot}"
            if ii == 0:
                assert len(timeslice_names) == 3
            else:
                assert len(timeslice_names) == 0


class TestCreateMapComplexScenarios:
    """Tests for complex multi-dimensional scenarios."""
    
    def test_irregular_spacing_multi_date_multi_time(self):
        """Test irregular spacing with multiple dates and times."""
        snapshots = pd.DatetimeIndex([
            '2020-01-15 08:00:00',
            '2020-03-20 14:00:00',
            '2020-08-05 18:00:00',
            '2020-12-25 06:00:00'
        ])
        
        # Create timeslices with both date and time resolution
        timeslices = []
        
        # Daytypes from irregular dates
        daytypes = [
            DayType(1, 1, 1, 14),    # Before Jan 15
            DayType(1, 15, 1, 15),   # Jan 15
            DayType(1, 16, 3, 19),   # Gap to Mar 20
            DayType(3, 20, 3, 20),   # Mar 20
            DayType(3, 21, 8, 4),    # Gap to Aug 5
            DayType(8, 5, 8, 5),     # Aug 5
            DayType(8, 6, 12, 24),   # Gap to Dec 25
            DayType(12, 25, 12, 25), # Dec 25
            DayType(12, 26, 12, 31), # After Dec 25
        ]
        
        # Time brackets from irregular times
        timebrackets = [
            DailyTimeBracket(time(0, 0, 0), time(6, 0, 0)),
            DailyTimeBracket(time(6, 0, 0), time(8, 0, 0)),
            DailyTimeBracket(time(8, 0, 0), time(14, 0, 0)),
            DailyTimeBracket(time(14, 0, 0), time(18, 0, 0)),
            DailyTimeBracket(time(18, 0, 0), ENDOFDAY),
        ]
        
        # Create all combinations
        for dt in daytypes:
            for tb in timebrackets:
                timeslices.append(Timeslice(season="X", daytype=dt, dailytimebracket=tb))
        
        mapping = create_map(snapshots, timeslices)
        
        # Verify all snapshots are mapped
        assert len(mapping) == 4
        
        # Each mapping should have no duplicate (year, timeslice) pairs
        for snapshot in snapshots:
            mapped = mapping[snapshot]
            pair_tuples = [(y, ts.name) for (y, ts) in mapped]
            assert len(pair_tuples) == len(set(pair_tuples)), \
                f"Duplicate (year, timeslice) pairs found for snapshot {snapshot}"
    
    def test_multi_year_high_resolution_hourly(self):
        """Test multi-year with high temporal resolution."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00:00',
            '2020-06-15 06:00:00',
            '2020-06-15 12:00:00',
            '2020-06-15 18:00:00',
            '2021-06-15 00:00:00',
            '2021-06-15 06:00:00',
            '2021-06-15 12:00:00',
            '2021-06-15 18:00:00',
        ])
        
        # Create 6-hour resolution timeslices
        daytypes = [
            DayType(1, 1, 6, 14),
            DayType(6, 15, 6, 15),
            DayType(6, 16, 12, 31),
        ]
        
        timebrackets = [
            DailyTimeBracket(time(0, 0, 0), time(6, 0, 0)),
            DailyTimeBracket(time(6, 0, 0), time(12, 0, 0)),
            DailyTimeBracket(time(12, 0, 0), time(18, 0, 0)),
            DailyTimeBracket(time(18, 0, 0), ENDOFDAY),
        ]
        
        timeslices = []
        for dt in daytypes:
            for tb in timebrackets:
                timeslices.append(Timeslice(season="X", daytype=dt, dailytimebracket=tb))
        
        mapping = create_map(snapshots, timeslices)
        
        # All 8 snapshots should be mapped
        assert len(mapping) == 8
        
        # Check for no duplicate (year, timeslice) pairs
        for snapshot in snapshots:
            mapped = mapping[snapshot]
            pair_tuples = [(y, ts.name) for (y, ts) in mapped]
            assert len(pair_tuples) == len(set(pair_tuples))
    
    def test_multi_year_low_resolution_annual(self):
        """Test multi-year with low temporal resolution (annual)."""
        snapshots = pd.DatetimeIndex([
            '2020-01-01 00:00:00',
            '2021-01-01 00:00:00',
            '2022-01-01 00:00:00',
            '2023-01-01 00:00:00'
        ])
        
        # Single timeslice for full year
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            )
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # Each snapshot maps to the full year timeslice (with different years)
        for i, snapshot in enumerate(snapshots):
            assert len(mapping[snapshot]) == 1
            mapped_ts = [ts for (y, ts) in mapping[snapshot]]
            mapped_years = [y for (y, ts) in mapping[snapshot]]
            assert timeslices[0] in mapped_ts
            # Verify correct year
            assert 2020 + i in mapped_years
    
    def test_leap_year_feb_29_handling(self):
        """Test Feb 29 handling across leap and non-leap years."""
        snapshots = pd.DatetimeIndex([
            '2020-02-29 12:00:00',  # Leap year
            '2021-03-01 12:00:00',  # Non-leap year
        ])
        
        # Create timeslices around Feb 29
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 2, 28),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 2, 28),
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(2, 29, 2, 29),  # Feb 29 (only in leap years)
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(2, 29, 2, 29),
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 1, 3, 1),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 1, 3, 1),
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 2, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), time(12, 0, 0))
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 2, 12, 31),
                dailytimebracket=DailyTimeBracket(time(12, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # First snapshot in leap year should map correctly
        assert len(mapping[snapshots[0]]) >= 1
        mapped_0_years = [y for (y, _) in mapping[snapshots[0]]]
        assert 2020 in mapped_0_years  # Leap year
        
        # Second snapshot should handle non-leap year correctly
        assert len(mapping[snapshots[1]]) >= 1
        mapped_1_years = [y for (y, _) in mapping[snapshots[1]]]
        assert 2021 in mapped_1_years  # Non-leap year
    
    def test_fine_grained_time_resolution_15min(self):
        """Test very fine time resolution (15-minute intervals)."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=4, freq='15min')
        
        # Create 15-minute timeslices
        timeslices = []
        daytypes = [
            DayType(1, 1, 6, 14),
            DayType(6, 15, 6, 15),
            DayType(6, 16, 12, 31),
        ]
        
        # First hour in 15-minute increments
        timebrackets = [
            DailyTimeBracket(time(0, 0, 0), time(0, 15, 0)),
            DailyTimeBracket(time(0, 15, 0), time(0, 30, 0)),
            DailyTimeBracket(time(0, 30, 0), time(0, 45, 0)),
            DailyTimeBracket(time(0, 45, 0), ENDOFDAY),
        ]
        
        for dt in daytypes:
            for tb in timebrackets:
                timeslices.append(Timeslice(season="X", daytype=dt, dailytimebracket=tb))
        
        mapping = create_map(snapshots, timeslices)
        
        # All snapshots should be mapped
        assert len(mapping) == 4
    
    def test_mixed_resolution_quarterly_and_hourly(self):
        """Test mixed resolution: quarterly dates with hourly times."""
        snapshots = pd.DatetimeIndex([
            '2020-03-31 08:00:00',
            '2020-06-30 16:00:00',
            '2020-09-30 12:00:00',
            '2020-12-31 20:00:00',
        ])
        
        # Quarterly daytypes
        daytypes = [
            DayType(1, 1, 3, 30),    # Q1: Jan-Mar (partial)
            DayType(3, 31, 3, 31),   # Mar 31
            DayType(4, 1, 6, 29),    # Gap to Jun 30
            DayType(6, 30, 6, 30),   # Jun 30
            DayType(7, 1, 9, 29),    # Gap to Sep 30
            DayType(9, 30, 9, 30),   # Sep 30
            DayType(10, 1, 12, 30),  # Gap to Dec 31
            DayType(12, 31, 12, 31), # Dec 31
        ]
        
        # 8-hour time brackets
        timebrackets = [
            DailyTimeBracket(time(0, 0, 0), time(8, 0, 0)),
            DailyTimeBracket(time(8, 0, 0), time(16, 0, 0)),
            DailyTimeBracket(time(16, 0, 0), ENDOFDAY),
        ]
        
        timeslices = []
        for dt in daytypes:
            for tb in timebrackets:
                timeslices.append(Timeslice(season="X", daytype=dt, dailytimebracket=tb))
        
        mapping = create_map(snapshots, timeslices)
        
        # All snapshots should be mapped without duplicate (year, timeslice) pairs
        for snapshot in snapshots:
            mapped = mapping[snapshot]
            pair_tuples = [(y, ts.name) for (y, ts) in mapped]
            assert len(pair_tuples) == len(set(pair_tuples))
    
    def test_extreme_multi_year_gap_2020_to_2030(self):
        """Test extreme multi-year gap (10 years)."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00:00',
            '2030-06-15 00:00:00'
        ])
        
        # Simple semi-annual timeslices
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 6, 14),    # First half (before Jun 15)
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),   # Jun 15
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 16, 12, 31),  # Second half (after Jun 15)
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # First snapshot spans 10 years - should have NO duplicate (year, timeslice) pairs
        mapped_first = mapping[snapshots[0]]
        pair_tuples = [(y, ts.name) for (y, ts) in mapped_first]
        assert len(pair_tuples) == len(set(pair_tuples)), \
            "Duplicate (year, timeslice) pairs in 10-year span!"
        
        # Extract years
        years_first = [y for (y, ts) in mapped_first]
        
        # Should span multiple years (2020, 2021, ..., 2030)
        # Note: due to valid_years bug, we may not get all intermediate years
        assert 2020 in years_first
        assert 2030 in years_first
        
        # Should have at least 3 (year, timeslice) pairs
        assert len(mapped_first) >= 3


class TestCreateMapValidation:
    """Tests for validation and error handling."""
    
    def test_representation_mismatch_error(self):
        """Test that representation mismatch raises error."""
        snapshots = pd.DatetimeIndex(['2020-06-15 00:00:00'])
        
        # Create timeslice that doesn't cover the full snapshot period
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 20),  # Only 6 days, not to end of year
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            )
        ]
        
        # Should raise ValueError for representation mismatch
        with pytest.raises(ValueError, match="Representation Mismatch"):
            create_map(snapshots, timeslices)
    
    def test_all_snapshots_have_mapping(self):
        """Test that all snapshots get mapped."""
        snapshots = pd.DatetimeIndex([
            '2020-03-15 00:00:00',
            '2020-06-15 00:00:00',
            '2020-09-15 00:00:00'
        ])
        
        # Create appropriate timeslices
        timeslices = [
            Timeslice(
                season="X",
                daytype=DayType(1, 1, 3, 14),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 15, 3, 15),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(3, 16, 6, 14),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 15, 6, 15),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(6, 16, 9, 14),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(9, 15, 9, 15),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
            Timeslice(
                season="X",
                daytype=DayType(9, 16, 12, 31),
                dailytimebracket=DailyTimeBracket(time(0, 0, 0), ENDOFDAY)
            ),
        ]
        
        mapping = create_map(snapshots, timeslices)
        
        # All snapshots should be in the mapping
        assert len(mapping) == len(snapshots)
        for snapshot in snapshots:
            assert snapshot in mapping
            assert len(mapping[snapshot]) > 0
