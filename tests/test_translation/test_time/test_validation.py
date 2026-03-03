# tests/test_translation/test_time/test_validation.py

import pytest
import pandas as pd
from datetime import date

from pyoscomp.constants import ENDOFDAY, hours_in_year
from pyoscomp.translation.time.translate import to_timeslices
from pyoscomp.translation.time.mapping import create_map


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

    @staticmethod
    def _map(snapshots):
        """Helper: to_timeslices + create_map in one call."""
        result = to_timeslices(snapshots)
        return result, create_map(snapshots, result.timeslices)

    def test_mapping_consistency_single_snapshot(self):
        """Mapped duration matches period from snapshot to end-of-year."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        _, mapping = self._map(snapshots)

        start = pd.Timestamp('2020-06-15 12:00')
        end = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        expected = (end - start).total_seconds() / 3600

        mapped = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[0]])
        assert abs(mapped - expected) < 0.1

    def test_mapping_consistency_two_consecutive_snapshots(self):
        """First snapshot covers 24 h, second covers rest of year."""
        snapshots = pd.DatetimeIndex(['2020-06-15 00:00', '2020-06-16 00:00'])
        _, mapping = self._map(snapshots)

        dur1 = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[0]])
        assert abs(dur1 - 24.0) < 0.1

        end = pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
        expected2 = (end - snapshots[1]).total_seconds() / 3600
        dur2 = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[1]])
        assert abs(dur2 - expected2) < 0.1

    def test_mapping_consistency_hourly_snapshots(self):
        """Each non-final hourly snapshot covers exactly 1 hour."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        _, mapping = self._map(snapshots)

        for i in range(23):
            dur = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[i]])
            assert abs(dur - 1.0) < 0.1

    def test_mapping_consistency_daily_snapshots(self):
        """Each non-final daily snapshot covers exactly 24 hours."""
        snapshots = pd.date_range('2020-06-01', periods=7, freq='D')
        _, mapping = self._map(snapshots)

        for i in range(6):
            dur = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[i]])
            assert abs(dur - 24.0) < 0.1

    def test_mapping_consistency_mixed_times(self):
        """12-hour sub-daily snapshots produce 12-hour mapped durations."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00', '2020-06-15 12:00', '2020-06-16 00:00'
        ])
        _, mapping = self._map(snapshots)

        for i in range(2):
            dur = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[i]])
            assert abs(dur - 12.0) < 0.1

    def test_mapping_consistency_across_year_boundary(self):
        """Snapshot period crossing Dec 31 / Jan 1 maps to both years."""
        snapshots = pd.DatetimeIndex([
            '2020-12-31 12:00', '2021-01-01 12:00'
        ])
        _, mapping = self._map(snapshots)

        years_0 = set(y for y, _ in mapping[snapshots[0]])
        assert years_0 == {2020, 2021}

        dur0 = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[0]])
        assert abs(dur0 - 24.0) < 1 / 3600  # 1-second tolerance

        years_1 = set(y for y, _ in mapping[snapshots[1]])
        assert years_1 == {2021}

    def test_mapping_consistency_multi_year(self):
        """Multi-year snapshot period has correct total duration."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00', '2021-06-15 00:00', '2022-06-15 00:00'
        ])
        _, mapping = self._map(snapshots)

        expected = (snapshots[1] - snapshots[0]).total_seconds() / 3600
        dur0 = sum(ts.duration_hours(y) for y, ts in mapping[snapshots[0]])
        assert abs(dur0 - expected) < 0.1


class TestNoDuplicatesValidation:
    """Tests for no-duplicates invariant: each (year, timeslice) pair appears at most once per snapshot."""

    @staticmethod
    def _map(snapshots):
        result = to_timeslices(snapshots)
        return create_map(snapshots, result.timeslices)

    @staticmethod
    def _assert_no_duplicates(mapping, snapshots):
        for snap in snapshots:
            pairs = [(y, ts.name) for y, ts in mapping[snap]]
            assert len(pairs) == len(set(pairs)), (
                f"Duplicate (year, ts) for {snap}"
            )

    def test_no_duplicates_single_snapshot(self):
        """No duplicate timeslice pairs for single snapshot."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        self._assert_no_duplicates(self._map(snapshots), snapshots)

    def test_no_duplicates_multiple_snapshots(self):
        """No duplicate pairs across 10 hourly snapshots."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=10, freq='h')
        self._assert_no_duplicates(self._map(snapshots), snapshots)

    def test_no_duplicates_daily_snapshots(self):
        """No duplicate pairs for 30 daily snapshots."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        self._assert_no_duplicates(self._map(snapshots), snapshots)

    def test_no_duplicates_mixed_times(self):
        """No duplicate pairs for morning/evening snapshots."""
        morning = pd.date_range('2020-06-15 00:00', periods=5, freq='D')
        evening = pd.date_range('2020-06-15 18:00', periods=5, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(evening)))
        self._assert_no_duplicates(self._map(snapshots), snapshots)

    def test_no_duplicates_multi_year(self):
        """No duplicate pairs for multi-year snapshots."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00', '2021-06-15 00:00', '2022-06-15 00:00'
        ])
        self._assert_no_duplicates(self._map(snapshots), snapshots)

    def test_no_duplicates_gapped_snapshots(self):
        """No duplicate pairs for gapped dates within a year."""
        snapshots = pd.DatetimeIndex([
            '2020-03-01', '2020-03-05',
            '2020-06-01', '2020-06-10', '2020-09-01'
        ])
        self._assert_no_duplicates(self._map(snapshots), snapshots)


class TestCompletenessValidation:
    """Tests for completeness invariant: every snapshot has >= 1 mapped timeslice."""

    @staticmethod
    def _map(snapshots):
        result = to_timeslices(snapshots)
        return result, create_map(snapshots, result.timeslices)

    def test_completeness_single_snapshot(self):
        """Single snapshot has non-empty mapping."""
        snapshots = pd.DatetimeIndex(['2020-06-15 12:00'])
        _, mapping = self._map(snapshots)
        assert len(mapping[snapshots[0]]) > 0

    def test_completeness_hourly_snapshots(self):
        """All 24 hourly snapshots have non-empty mappings."""
        snapshots = pd.date_range('2020-06-15 00:00', periods=24, freq='h')
        result, mapping = self._map(snapshots)

        assert len(mapping) == len(snapshots)
        for snap in snapshots:
            assert len(mapping[snap]) > 0
            for y, ts in mapping[snap]:
                assert y in result.years
                assert ts in result.timeslices

    def test_completeness_daily_snapshots(self):
        """All 30 daily snapshots have non-empty mappings."""
        snapshots = pd.date_range('2020-06-01', periods=30, freq='D')
        _, mapping = self._map(snapshots)
        assert len(mapping) == 30
        for snap in snapshots:
            assert len(mapping[snap]) > 0

    def test_completeness_mixed_times(self):
        """Morning/evening snapshots all have non-empty mappings."""
        morning = pd.date_range('2020-06-15 00:00', periods=7, freq='D')
        evening = pd.date_range('2020-06-15 18:00', periods=7, freq='D')
        snapshots = pd.DatetimeIndex(sorted(list(morning) + list(evening)))
        _, mapping = self._map(snapshots)
        assert len(mapping) == len(snapshots)
        for snap in snapshots:
            assert len(mapping[snap]) > 0

    def test_completeness_multi_year(self):
        """Multi-year snapshots all have non-empty mappings."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00', '2021-06-15 00:00', '2022-06-15 00:00'
        ])
        result, mapping = self._map(snapshots)
        assert len(mapping) == 3
        for snap in snapshots:
            years = set(y for y, _ in mapping[snap])
            assert years.issubset(set(result.years))

    def test_completeness_gapped_snapshots(self):
        """Gapped snapshots all have non-empty mappings."""
        snapshots = pd.DatetimeIndex([
            '2020-01-15', '2020-06-15', '2020-11-15'
        ])
        _, mapping = self._map(snapshots)
        assert len(mapping) == 3
        for snap in snapshots:
            assert len(mapping[snap]) > 0

    def test_completeness_irregular_pattern(self):
        """Irregular date/time pattern: all snapshots mapped."""
        snapshots = pd.DatetimeIndex([
            '2020-03-01 00:00', '2020-03-05 06:00',
            '2020-06-01 12:00', '2020-06-10 18:00',
            '2020-09-01 23:00'
        ])
        _, mapping = self._map(snapshots)
        assert len(mapping) == 5
        for snap in snapshots:
            assert len(mapping[snap]) > 0


class TestCombinedValidationProperties:
    """Tests combining coverage, completeness, no-duplicates, and consistency."""

    @staticmethod
    def _validate_all(snapshots):
        """Run all four invariants on a snapshot set."""
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        # 1. Coverage
        assert result.validate_coverage()

        # 2. Completeness
        assert len(mapping) == len(snapshots)
        for snap in snapshots:
            assert len(mapping[snap]) > 0

        # 3. No duplicates
        for snap in snapshots:
            pairs = [(y, ts.name) for y, ts in mapping[snap]]
            assert len(pairs) == len(set(pairs))

        return result, mapping

    def test_all_invariants_hourly_week(self):
        """All invariants hold for 168 hourly snapshots (1 week)."""
        snapshots = pd.date_range(
            '2020-06-15 00:00', periods=168, freq='h'
        )
        _, mapping = self._validate_all(snapshots)

        # Consistency: each non-final snapshot covers 1 hour
        for i in range(167):
            dur = sum(
                ts.duration_hours(y) for y, ts in mapping[snapshots[i]]
            )
            assert abs(dur - 1.0) < 0.1

    def test_all_invariants_mixed_resolution(self):
        """All invariants hold for quarterly-subdaily snapshots."""
        dates = pd.date_range('2020-01-01', periods=4, freq='QS')
        times = ['00:00', '08:00', '16:00']
        snapshots = pd.DatetimeIndex([
            f"{d.date()} {t}" for d in dates for t in times
        ])
        self._validate_all(snapshots)

    def test_all_invariants_leap_year_boundary(self):
        """All invariants hold around Feb 28-29-Mar 1 in a leap year."""
        snapshots = pd.DatetimeIndex([
            '2020-02-28 00:00', '2020-02-29 00:00', '2020-03-01 00:00'
        ])
        result, mapping = self._validate_all(snapshots)

        # Leap year has 8784 hours
        total = sum(ts.duration_hours(2020) for ts in result.timeslices)
        assert abs(total - 8784) < 0.1

        # First two snapshots each cover 24 hours
        for i in range(2):
            dur = sum(
                ts.duration_hours(y)
                for y, ts in mapping[snapshots[i]]
            )
            assert abs(dur - 24.0) < 0.1
