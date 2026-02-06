# tests/test_translation/test_time/test_validation.py

import pytest
import pandas as pd
from datetime import date

from pyoscomp.constants import ENDOFDAY, hours_in_year
from pyoscomp.translation.time.translate import to_timeslices


class TestCoverageValidation:
    """Tests for coverage invariant: sum of all timeslice hours equals hours in year."""
    
    def test_coverage_single_snapshot_single_year(self):
        """Test coverage for single snapshot in single year."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        result = to_timeslices(snapshots)
        
        # Verify validate_coverage() method returns True
        assert result.validate_coverage()
        
        # Manually verify: sum of all timeslice hours for 2020
        for year in result.years:
            total_hours = sum(
                ts.duration_hours(year) for ts in result.timeslices
            )
            expected_hours = hours_in_year(year)
            assert abs(total_hours - expected_hours) < 0.1  # Small tolerance for floating point
    
    def test_coverage_hourly_snapshots_single_day(self):
        """Test coverage for 24 hourly snapshots in single day."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        result = to_timeslices(snapshots)
        
        assert result.validate_coverage()
        
        # Verify manually
        for year in result.years:
            total_hours = sum(ts.duration_hours(year) for ts in result.timeslices)
            expected_hours = hours_in_year(year)
            assert abs(total_hours - expected_hours) < 0.1
    
    def test_coverage_daily_snapshots_full_month(self):
        """Test coverage for 30 daily snapshots (full month)."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        result = to_timeslices(snapshots)
        
        assert result.validate_coverage()
        
        for year in result.years:
            total_hours = sum(ts.duration_hours(year) for ts in result.timeslices)
            expected_hours = hours_in_year(year)
            assert abs(total_hours - expected_hours) < 0.1
    
    def test_coverage_multi_year_consecutive(self):
        """Test coverage for snapshots across multiple consecutive years."""
        snapshots = pd.DatetimeIndex(['2020-01-01', '2021-01-01', '2022-01-01'])
        result = to_timeslices(snapshots)
        
        assert result.validate_coverage()
        
        # Verify each year individually
        assert len(result.years) == 3
        for year in result.years:
            total_hours = sum(ts.duration_hours(year) for ts in result.timeslices)
            expected_hours = hours_in_year(year)
            assert abs(total_hours - expected_hours) < 0.1
    
    def test_coverage_leap_year(self):
        """Test coverage validation for leap year (2020)."""
        snapshots = pd.DatetimeIndex(['2020-02-29 00:00'])
        result = to_timeslices(snapshots)
        
        assert result.validate_coverage()
        assert result.years == [2020]
        
        # Leap year has 8784 hours (366 * 24)
        total_hours = sum(ts.duration_hours(2020) for ts in result.timeslices)
        assert abs(total_hours - 8784) < 0.1
    
    def test_coverage_non_leap_year(self):
        """Test coverage validation for non-leap year (2021)."""
        snapshots = pd.DatetimeIndex(['2021-06-15 00:00'])
        result = to_timeslices(snapshots)
        
        assert result.validate_coverage()
        assert result.years == [2021]
        
        # Non-leap year has 8760 hours (365 * 24)
        total_hours = sum(ts.duration_hours(2021) for ts in result.timeslices)
        assert abs(total_hours - 8760) < 0.1
    
    def test_coverage_mixed_times_multiple_days(self):
        """Test coverage for mixed times across multiple days."""
        morning = pd.date_range('2020-06-15 00:00', periods=7, freq='D')
        evening = pd.date_range('2020-06-15 18:00', periods=7, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(evening)))
        result = to_timeslices(snapshots)
        
        assert result.validate_coverage()
        
        for year in result.years:
            total_hours = sum(ts.duration_hours(year) for ts in result.timeslices)
            expected_hours = hours_in_year(year)
            assert abs(total_hours - expected_hours) < 0.1
    
    def test_coverage_gapped_snapshots(self):
        """Test coverage for snapshots with large gaps."""
        snapshots = pd.DatetimeIndex(['2020-01-15', '2020-06-15', '2020-11-15'])
        result = to_timeslices(snapshots)
        
        assert result.validate_coverage()
        
        for year in result.years:
            total_hours = sum(ts.duration_hours(year) for ts in result.timeslices)
            expected_hours = hours_in_year(year)
            assert abs(total_hours - expected_hours) < 0.1


class TestMappingConsistencyValidation:
    """Tests for mapping consistency: snapshot duration equals sum of mapped timeslice durations."""
    
    def test_mapping_consistency_single_snapshot(self):
        """Test mapping consistency for single snapshot."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        result = to_timeslices(snapshots)
        
        # Single snapshot maps to period from Jun 15 12:00 to Dec 31 ENDOFDAY
        snapshot = snapshots[0]
        mapped_timeslices = result.snapshot_to_timeslice[snapshot]
        
        # Calculate expected duration
        start = pd.Timestamp('2020-06-15 12:00')
        end = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        expected_duration = (end - start).total_seconds() / 3600  # Convert to hours
        
        # Calculate mapped duration
        mapped_duration = 0
        for year, ts in mapped_timeslices:
            mapped_duration += ts.duration_hours(year)
        
        # Should match within small tolerance
        assert abs(mapped_duration - expected_duration) < 0.1
    
    def test_mapping_consistency_two_consecutive_snapshots(self):
        """Test mapping consistency for two consecutive snapshots."""
        snapshots = pd.DatetimeIndex(['2020-06-15 00:00', '2020-06-16 00:00'])
        result = to_timeslices(snapshots)
        
        # First snapshot: Jun 15 00:00 to Jun 16 00:00 (24 hours)
        snapshot1 = snapshots[0]
        mapped_timeslices1 = result.snapshot_to_timeslice[snapshot1]
        mapped_duration1 = sum(ts.duration_hours(year) for year, ts in mapped_timeslices1)
        assert abs(mapped_duration1 - 24.0) < 0.1
        
        # Second snapshot: Jun 16 00:00 to Dec 31 ENDOFDAY
        snapshot2 = snapshots[1]
        mapped_timeslices2 = result.snapshot_to_timeslice[snapshot2]
        start = pd.Timestamp('2020-06-16 00:00')
        end = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        expected_duration2 = (end - start).total_seconds() / 3600
        mapped_duration2 = sum(ts.duration_hours(year) for year, ts in mapped_timeslices2)
        assert abs(mapped_duration2 - expected_duration2) < 0.1
    
    def test_mapping_consistency_hourly_snapshots(self):
        """Test mapping consistency for hourly snapshots."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        result = to_timeslices(snapshots)
        
        # Each snapshot (except last) should map to 1 hour
        for i in range(len(snapshots) - 1):
            snapshot = snapshots[i]
            mapped_timeslices = result.snapshot_to_timeslice[snapshot]
            mapped_duration = sum(ts.duration_hours(year) for year, ts in mapped_timeslices)
            assert abs(mapped_duration - 1.0) < 0.1
        
        # Last snapshot maps to rest of year
        last_snapshot = snapshots[-1]
        mapped_timeslices_last = result.snapshot_to_timeslice[last_snapshot]
        start = pd.Timestamp('2020-06-15 23:00')
        end = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        expected_duration = (end - start).total_seconds() / 3600
        mapped_duration_last = sum(ts.duration_hours(year) for year, ts in mapped_timeslices_last)
        assert abs(mapped_duration_last - expected_duration) < 0.1
    
    def test_mapping_consistency_daily_snapshots(self):
        """Test mapping consistency for daily snapshots."""
        snapshots = pd.date_range('2020-06-01', periods=7, freq='D')
        result = to_timeslices(snapshots)
        
        # Each snapshot (except last) should map to 24 hours
        for i in range(len(snapshots) - 1):
            snapshot = snapshots[i]
            mapped_timeslices = result.snapshot_to_timeslice[snapshot]
            mapped_duration = sum(ts.duration_hours(year) for year, ts in mapped_timeslices)
            assert abs(mapped_duration - 24.0) < 0.1
    
    def test_mapping_consistency_mixed_times(self):
        """Test mapping consistency for mixed time snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00',
            '2020-06-15 12:00',
            '2020-06-16 00:00'
        ])
        result = to_timeslices(snapshots)
        
        # First snapshot: 00:00 to 12:00 (12 hours)
        mapped_duration1 = sum(
            ts.duration_hours(year) 
            for year, ts in result.snapshot_to_timeslice[snapshots[0]]
        )
        assert abs(mapped_duration1 - 12.0) < 0.1
        
        # Second snapshot: 12:00 to next day 00:00 (12 hours)
        mapped_duration2 = sum(
            ts.duration_hours(year) 
            for year, ts in result.snapshot_to_timeslice[snapshots[1]]
        )
        assert abs(mapped_duration2 - 12.0) < 0.1
    
    def test_mapping_consistency_across_year_boundary(self):
        """Test mapping consistency for snapshots crossing year boundary."""
        snapshots = pd.DatetimeIndex(['2020-12-31 12:00', '2021-01-01 12:00'])
        result = to_timeslices(snapshots)
        
        # First snapshot: Dec 31 12:00 to Jan 1 12:00 (24 hours spanning two years)
        # Maps to: 2020-12-31 12:00 to ENDOFDAY (12h) + 2021-01-01 00:00 to 12:00 (12h)
        snapshot1 = snapshots[0]
        mapped_timeslices1 = result.snapshot_to_timeslice[snapshot1]
        
        # Should map to both 2020 and 2021 timeslices
        years_in_mapping1 = set(year for year, ts in mapped_timeslices1)
        assert years_in_mapping1 == {2020, 2021}
        
        # Duration should be 24 hours total (12 in 2020 + 12 in 2021)
        mapped_duration1 = sum(ts.duration_hours(year) for year, ts in mapped_timeslices1)
        assert abs(mapped_duration1 - 24.0) < 1/3600  # 1 second tolerance
        
        # Second snapshot: Jan 1 12:00 to end of 2021
        snapshot2 = snapshots[1]
        mapped_timeslices2 = result.snapshot_to_timeslice[snapshot2]
        
        # Should only map to 2021 timeslices
        years_in_mapping2 = set(year for year, ts in mapped_timeslices2)
        assert years_in_mapping2 == {2021}
    
    def test_mapping_consistency_multi_year(self):
        """Test mapping consistency for multi-year snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00',
            '2021-06-15 00:00',
            '2022-06-15 00:00'
        ])
        result = to_timeslices(snapshots)
        
        # First snapshot: Jun 15 2020 to Jun 15 2021 (365 days + 1 leap day = 366 days)
        snapshot1 = snapshots[0]
        start1 = pd.Timestamp('2020-06-15 00:00')
        end1 = pd.Timestamp('2021-06-15 00:00')
        expected_duration1 = (end1 - start1).total_seconds() / 3600
        mapped_duration1 = sum(
            ts.duration_hours(year) 
            for year, ts in result.snapshot_to_timeslice[snapshot1]
        )
        assert abs(mapped_duration1 - expected_duration1) < 0.1


class TestNoDuplicatesValidation:
    """Tests for no duplicates invariant: each timeslice index appears once per snapshot mapping."""
    
    def test_no_duplicates_single_snapshot(self):
        """Test no duplicate timeslice indices for single snapshot."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        result = to_timeslices(snapshots)
        
        snapshot = snapshots[0]
        mapped_items = result.snapshot_to_timeslice[snapshot]
        
        # Extract timeslice objects
        mapped_timeslices = [ts for year, ts in mapped_items]
        
        # Check no duplicates by converting to set
        assert len(mapped_timeslices) == len(set(mapped_timeslices))
        
        # Also check indices don't repeat
        timeslice_indices = [result.timeslices.index(ts) for ts in mapped_timeslices]
        assert len(timeslice_indices) == len(set(timeslice_indices))
    
    def test_no_duplicates_multiple_snapshots(self):
        """Test no duplicate timeslice indices across multiple snapshots."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=10, freq='h')
        result = to_timeslices(snapshots)
        
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            mapped_timeslices = [ts for year, ts in mapped_items]
            
            # No duplicates in this snapshot's mapping
            assert len(mapped_timeslices) == len(set(mapped_timeslices))
    
    def test_no_duplicates_daily_snapshots(self):
        """Test no duplicate timeslice indices for daily snapshots."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        result = to_timeslices(snapshots)
        
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            mapped_timeslices = [ts for year, ts in mapped_items]
            
            # No duplicates
            assert len(mapped_timeslices) == len(set(mapped_timeslices))
    
    def test_no_duplicates_mixed_times(self):
        """Test no duplicate timeslice indices for mixed time snapshots."""
        morning = pd.date_range('2020-06-15 00:00', periods=5, freq='D')
        evening = pd.date_range('2020-06-15 18:00', periods=5, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(evening)))
        result = to_timeslices(snapshots)
        
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            mapped_timeslices = [ts for year, ts in mapped_items]
            
            # No duplicates
            assert len(mapped_timeslices) == len(set(mapped_timeslices))
    
    def test_no_duplicates_multi_year(self):
        """Test no duplicate timeslice indices across multiple years."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00',
            '2021-06-15 00:00',
            '2022-06-15 00:00'
        ])
        result = to_timeslices(snapshots)
        
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            
            # Check (year, timeslice) tuples are unique
            assert len(mapped_items) == len(set(mapped_items))
            
            # Within each year, timeslice indices should not duplicate
            year_groups = {}
            for year, ts in mapped_items:
                if year not in year_groups:
                    year_groups[year] = []
                year_groups[year].append(ts)
            
            for year, timeslices in year_groups.items():
                assert len(timeslices) == len(set(timeslices))
    
    def test_no_duplicates_gapped_snapshots(self):
        """Test no duplicate timeslice indices for gapped snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-03-01', '2020-03-05',
            '2020-06-01', '2020-06-10',
            '2020-09-01'
        ])
        result = to_timeslices(snapshots)
        
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            mapped_timeslices = [ts for year, ts in mapped_items]
            
            # No duplicates
            assert len(mapped_timeslices) == len(set(mapped_timeslices))


class TestCompletenessValidation:
    """Tests for completeness invariant: every snapshot has at least one mapped timeslice."""
    
    def test_completeness_single_snapshot(self):
        """Test every snapshot has mapping - single snapshot case."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        result = to_timeslices(snapshots)
        
        # Every snapshot should be in the mapping
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0
    
    def test_completeness_hourly_snapshots(self):
        """Test every snapshot has mapping - hourly snapshots."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        result = to_timeslices(snapshots)
        
        # All snapshots should be in mapping
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            mapped_items = result.snapshot_to_timeslice[snapshot]
            assert len(mapped_items) > 0
            
            # Each mapping should have valid (year, timeslice) tuples
            for year, ts in mapped_items:
                assert year in result.years
                assert ts in result.timeslices
    
    def test_completeness_daily_snapshots(self):
        """Test every snapshot has mapping - daily snapshots."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        result = to_timeslices(snapshots)
        
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0
    
    def test_completeness_mixed_times(self):
        """Test every snapshot has mapping - mixed times."""
        morning = pd.date_range('2020-06-15 00:00', periods=7, freq='D')
        evening = pd.date_range('2020-06-15 18:00', periods=7, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(evening)))
        result = to_timeslices(snapshots)
        
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0
    
    def test_completeness_multi_year(self):
        """Test every snapshot has mapping - multi-year."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00',
            '2021-06-15 00:00',
            '2022-06-15 00:00'
        ])
        result = to_timeslices(snapshots)
        
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            mapped_items = result.snapshot_to_timeslice[snapshot]
            assert len(mapped_items) > 0
            
            # Verify years in mapping are valid
            mapped_years = set(year for year, ts in mapped_items)
            assert mapped_years.issubset(set(result.years))
    
    def test_completeness_gapped_snapshots(self):
        """Test every snapshot has mapping - gapped snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-01-15', '2020-06-15', '2020-11-15'
        ])
        result = to_timeslices(snapshots)
        
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0
    
    def test_completeness_irregular_pattern(self):
        """Test every snapshot has mapping - irregular pattern."""
        snapshots = pd.DatetimeIndex([
            '2020-03-01 00:00', '2020-03-05 06:00',
            '2020-06-01 12:00', '2020-06-10 18:00',
            '2020-09-01 23:00'
        ])
        result = to_timeslices(snapshots)
        
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0


class TestCombinedValidationProperties:
    """Tests combining multiple validation properties."""
    
    def test_all_invariants_hourly_week(self):
        """Test all invariants hold for hourly week snapshot."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=168, freq='h')  # 7 days
        result = to_timeslices(snapshots)
        
        # Coverage
        assert result.validate_coverage()
        
        # Completeness
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0
        
        # No duplicates
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            mapped_timeslices = [ts for year, ts in mapped_items]
            assert len(mapped_timeslices) == len(set(mapped_timeslices))
        
        # Mapping consistency - verify total coverage
        total_mapped_hours = 0
        for i, snapshot in enumerate(snapshots):
            if i < len(snapshots) - 1:
                # Each snapshot (except last) covers 1 hour
                mapped_duration = sum(
                    ts.duration_hours(year) 
                    for year, ts in result.snapshot_to_timeslice[snapshot]
                )
                assert abs(mapped_duration - 1.0) < 0.1
                total_mapped_hours += mapped_duration
    
    def test_all_invariants_mixed_resolution(self):
        """Test all invariants for mixed temporal resolution."""
        # Quarterly snapshots with multiple times per day
        dates = pd.date_range('2020-01-01', periods=4, freq='QS')
        times = ['00:00', '08:00', '16:00']
        snapshots = pd.DatetimeIndex([
            f"{d.date()} {t}" for d in dates for t in times
        ])
        result = to_timeslices(snapshots)
        
        # Coverage
        assert result.validate_coverage()
        
        # Completeness
        assert len(result.snapshot_to_timeslice) == len(snapshots)
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0
        
        # No duplicates
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            mapped_timeslices = [ts for year, ts in mapped_items]
            assert len(mapped_timeslices) == len(set(mapped_timeslices))
    
    def test_all_invariants_leap_year_boundary(self):
        """Test all invariants around leap year boundary."""
        snapshots = pd.DatetimeIndex([
            '2020-02-28 00:00',  # Before leap day
            '2020-02-29 00:00',  # Leap day
            '2020-03-01 00:00'   # After leap day
        ])
        result = to_timeslices(snapshots)
        
        # Coverage - should be valid for 2020 (leap year)
        assert result.validate_coverage()
        total_hours = sum(ts.duration_hours(2020) for ts in result.timeslices)
        assert abs(total_hours - 8784) < 0.1  # 366 * 24
        
        # Completeness
        assert len(result.snapshot_to_timeslice) == 3
        for snapshot in snapshots:
            assert snapshot in result.snapshot_to_timeslice
            assert len(result.snapshot_to_timeslice[snapshot]) > 0
        
        # No duplicates
        for snapshot in snapshots:
            mapped_items = result.snapshot_to_timeslice[snapshot]
            mapped_timeslices = [ts for year, ts in mapped_items]
            assert len(mapped_timeslices) == len(set(mapped_timeslices))
        
        # Mapping consistency
        # First snapshot: Feb 28 to Feb 29 (24 hours)
        duration1 = sum(
            ts.duration_hours(year) 
            for year, ts in result.snapshot_to_timeslice[snapshots[0]]
        )
        assert abs(duration1 - 24.0) < 0.1
        
        # Second snapshot: Feb 29 to Mar 1 (24 hours)
        duration2 = sum(
            ts.duration_hours(year) 
            for year, ts in result.snapshot_to_timeslice[snapshots[1]]
        )
        assert abs(duration2 - 24.0) < 0.1
